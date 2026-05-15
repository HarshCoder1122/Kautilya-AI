/**
 * Kautilya AI — Production frontend server
 * Serves the React SPA and proxies /api/* to the Flask backend.
 * Set BACKEND_URL env var to the Flask backend base URL (no trailing slash).
 */

const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 8000;
const BACKEND_URL = process.env.BACKEND_URL || 'https://harshsharma1212-kautilyabackend.hf.space';
const HF_TOKEN = process.env.HF_TOKEN || '';

// Proxy /api/*, /embed/* → Flask backend (full path preserved, streaming-safe)
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
      console.log(`[Proxy] ${req.method} ${req.url} → ${BACKEND_URL}${req.url}`);
    },
  },
}));

// Serve React static build
const BUILD = path.join(__dirname, 'build');
app.use(express.static(BUILD));

// SPA fallback
app.get('*', (req, res) => {
  res.sendFile(path.join(BUILD, 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`[Kautilya] Frontend proxy server on port ${PORT}`);
  console.log(`[Kautilya] API proxied to ${BACKEND_URL}`);
});
