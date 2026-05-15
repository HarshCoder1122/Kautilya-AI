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

// Proxy /api/* and /v1/* → Flask backend (streaming-safe)
const proxyOpts = {
  target: BACKEND_URL,
  changeOrigin: true,
  on: {
    error: (err, req, res) => {
      console.error('[Proxy] Error:', err.message);
      if (!res.headersSent) res.status(502).json({ error: 'Backend unavailable' });
    },
  },
  // Required for SSE streaming (don't buffer)
  selfHandleResponse: false,
};

app.use('/api', createProxyMiddleware(proxyOpts));
app.use('/v1', createProxyMiddleware(proxyOpts));
app.use('/embed', createProxyMiddleware(proxyOpts));

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
