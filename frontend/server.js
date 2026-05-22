/**
 * Kautilya AI — Production frontend server
 * Serves the React SPA, proxies /api/* to the Flask backend, and keeps the
 * HF Space warm so requests don't hit a 30s cold-start.
 * Env:
 *   BACKEND_URL — Flask backend base URL (no trailing slash)
 *   HF_TOKEN    — required if backend Space is private
 *   PORT        — listen port (Koyeb sets this automatically)
 */

const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const path = require('path');
const https = require('https');
const http = require('http');

const app = express();
const PORT = process.env.PORT || 8000;
const BACKEND_URL = process.env.BACKEND_URL || 'https://harshsharma1212-kautilyabackend.hf.space';
const HF_TOKEN = process.env.HF_TOKEN || '';

// ── Gzip/brotli compression on everything ─────────────────────────────
try {
  const compression = require('compression');
  app.use(compression());
} catch (e) {
  console.warn('[Kautilya] compression module not installed — skipping');
}

// ── Razorpay webhook async forwarder ──────────────────────────────────
// Razorpay times out the webhook after ~5s. If HF Space is sleeping a cold
// start can take 30-60s, so we accept the webhook here, ACK 200 immediately,
// and forward to HF in the background with retries. Raw bytes are preserved
// so the signature verifies on the Flask side. This runs BEFORE the proxy.
app.post('/api/billing/razorpay-webhook',
  express.raw({ type: '*/*', limit: '2mb' }),
  (req, res) => {
    // ACK Razorpay immediately so they don't retry/timeout
    res.status(200).send('OK');

    const body = req.body;
    const signature = req.headers['x-razorpay-signature'];
    const eventName = (() => {
      try { return JSON.parse(body.toString('utf8')).event; } catch { return 'unknown'; }
    })();
    console.log(`[Webhook] Forwarding event=${eventName} bytes=${body.length}`);

    const target = new URL(BACKEND_URL + '/api/billing/razorpay-webhook');
    const lib = target.protocol === 'https:' ? https : http;

    const forward = (attempt = 1) => {
      const req2 = lib.request({
        method: 'POST',
        hostname: target.hostname,
        port: target.port || (target.protocol === 'https:' ? 443 : 80),
        path: target.pathname,
        headers: {
          'Content-Type': req.headers['content-type'] || 'application/json',
          'Content-Length': body.length,
          'X-Razorpay-Signature': signature || '',
          ...(HF_TOKEN ? { 'Authorization': `Bearer ${HF_TOKEN}` } : {}),
        },
        timeout: 60000,
      }, (r) => {
        let chunks = '';
        r.on('data', (c) => { chunks += c; });
        r.on('end', () => {
          console.log(`[Webhook] HF returned ${r.statusCode} (attempt ${attempt}) body=${chunks.slice(0, 200)}`);
          if (r.statusCode >= 500 && attempt < 4) {
            setTimeout(() => forward(attempt + 1), attempt * 5000);
          }
        });
      });
      req2.on('error', (err) => {
        console.warn(`[Webhook] forward error attempt ${attempt}: ${err.message}`);
        if (attempt < 4) setTimeout(() => forward(attempt + 1), attempt * 5000);
      });
      req2.on('timeout', () => { req2.destroy(); });
      req2.write(body);
      req2.end();
    };
    forward();
  }
);

// ── Proxy /api/*, /embed/* → Flask backend (streaming-safe) ───────────
// HF Space is private → inject HF_TOKEN as Authorization for the gateway,
// move user's original Authorization to X-Kautilya-Auth so Flask still sees it.
app.use(createProxyMiddleware({
  target: BACKEND_URL,
  changeOrigin: true,
  pathFilter: ['/api/**', '/embed/**'],
  on: {
    error: (err, req, res) => {
      console.error('[Proxy] Error:', err.message);
      if (!res.headersSent) res.status(502).json({ error: 'Backend unavailable' });
    },
    proxyReq: (proxyReq, req) => {
      if (HF_TOKEN) {
        const userAuth = req.headers['authorization'];
        if (userAuth) proxyReq.setHeader('X-Kautilya-Auth', userAuth);
        proxyReq.setHeader('Authorization', `Bearer ${HF_TOKEN}`);
      }
    },
  },
}));

// ── Proxy /__/* → Firebase Auth handler (so custom authDomain works) ──
const FIREBASE_PROJECT_ID = process.env.REACT_APP_FIREBASE_PROJECT_ID || 'jarvis-a6e18';
const FIREBASE_TARGET = `https://${FIREBASE_PROJECT_ID}.firebaseapp.com`;

app.use(createProxyMiddleware({
  target: FIREBASE_TARGET,
  changeOrigin: true,
  pathFilter: ['/__/**'],
  on: {
    error: (err, req, res) => {
      console.error('[Firebase Proxy] Error:', err.message);
      if (!res.headersSent) res.status(502).json({ error: 'Firebase Auth proxy failed' });
    },
  },
}));

// ── Static React build with proper cache headers ──────────────────────
// - index.html + sw.js: NEVER cache (so kill-switch + new builds propagate)
// - hashed assets under /static/: cache forever (filenames change on rebuild)
const BUILD = path.join(__dirname, 'build');
app.use(express.static(BUILD, {
  etag: true,
  lastModified: true,
  setHeaders: (res, filePath) => {
    const lower = filePath.toLowerCase();
    if (lower.endsWith('index.html') || lower.endsWith('/sw.js') || lower.endsWith('\\sw.js')) {
      res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
      res.setHeader('Pragma', 'no-cache');
      res.setHeader('Expires', '0');
    } else if (lower.includes('/static/') || lower.includes('\\static\\')) {
      res.setHeader('Cache-Control', 'public, max-age=31536000, immutable');
    }
  },
}));

// SPA fallback: index.html must not be cached so users always get the
// latest asset hashes when a new build is deployed.
app.get('*', (req, res) => {
  res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
  res.setHeader('Pragma', 'no-cache');
  res.setHeader('Expires', '0');
  res.sendFile(path.join(BUILD, 'index.html'));
});

// ── Backend warmup ────────────────────────────────────────────────────
// HF Spaces sleeps after inactivity; ping /api/config/firebase every 4 min
// so the first user request doesn't hit a 30s cold start.
function warmupBackend() {
  try {
    const url = new URL(BACKEND_URL + '/api/config/firebase');
    const lib = url.protocol === 'https:' ? https : http;
    const opts = {
      method: 'GET',
      hostname: url.hostname,
      path: url.pathname,
      headers: HF_TOKEN ? { 'Authorization': `Bearer ${HF_TOKEN}` } : {},
      timeout: 15000,
    };
    const req = lib.request(opts, (res) => {
      res.on('data', () => {});
      res.on('end', () => {});
    });
    req.on('error', () => {});
    req.on('timeout', () => { req.destroy(); });
    req.end();
  } catch (e) { /* ignore */ }
}
setInterval(warmupBackend, 4 * 60 * 1000);
setTimeout(warmupBackend, 5000);  // kick once at startup

app.listen(PORT, '0.0.0.0', () => {
  console.log(`[Kautilya] Frontend server on port ${PORT}`);
  console.log(`[Kautilya] API proxied to ${BACKEND_URL}`);
  console.log(`[Kautilya] Cache: index.html=no-cache, /static/*=immutable, warmup every 4m`);
});
