/**
 * Copies maplibre-gl's pre-built CSP worker from node_modules into public/
 * so it is served from OUR origin. Two constraints force this:
 *   1. Browsers refuse `new Worker(<cross-origin URL>)` outright
 *      (SecurityError) — so a CDN worker URL can never work.
 *   2. Our CSP script-src has no `blob:`, so maplibre's default inline
 *      blob worker is blocked in production.
 * Running this on every dev/build keeps the worker byte-identical to the
 * installed maplibre-gl version (a mismatch breaks the worker protocol).
 */
const fs = require('fs');
const path = require('path');

const src = path.join(__dirname, '..', 'node_modules', 'maplibre-gl', 'dist', 'maplibre-gl-csp-worker.js');
const dest = path.join(__dirname, '..', 'public', 'maplibre-gl-csp-worker.js');

if (!fs.existsSync(src)) {
  console.error('[sync-maplibre-worker] maplibre-gl not installed — run npm install first');
  process.exit(1);
}

fs.copyFileSync(src, dest);
const ver = require(path.join(__dirname, '..', 'node_modules', 'maplibre-gl', 'package.json')).version;
console.log(`[sync-maplibre-worker] public/maplibre-gl-csp-worker.js synced (maplibre-gl@${ver})`);
