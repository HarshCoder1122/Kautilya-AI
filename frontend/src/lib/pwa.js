// PWA registration + install prompt plumbing.
// Captures the beforeinstallprompt event so the React UI can trigger
// the native install dialog at the right moment.

let _deferredPrompt = null;
const _listeners = new Set();

function _emit() {
  _listeners.forEach((cb) => {
    try { cb(_deferredPrompt); } catch (e) { /* noop */ }
  });
}

export function onInstallPromptChange(cb) {
  _listeners.add(cb);
  cb(_deferredPrompt);
  return () => _listeners.delete(cb);
}

export async function triggerInstallPrompt() {
  if (!_deferredPrompt) return { outcome: 'unavailable' };
  const promptEvt = _deferredPrompt;
  _deferredPrompt = null;
  _emit();
  try {
    await promptEvt.prompt();
    const choice = await promptEvt.userChoice;
    return choice;
  } catch (e) {
    return { outcome: 'error', error: String(e) };
  }
}

export function isStandalone() {
  if (typeof window === 'undefined') return false;
  return (
    window.matchMedia?.('(display-mode: standalone)').matches ||
    window.navigator.standalone === true
  );
}

export function registerPWA() {
  if (typeof window === 'undefined') return;

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    _deferredPrompt = e;
    _emit();
  });

  window.addEventListener('appinstalled', () => {
    _deferredPrompt = null;
    _emit();
  });

  if ('serviceWorker' in navigator && window.location.protocol === 'https:') {
    window.addEventListener('load', () => {
      navigator.serviceWorker
        .register('/sw.js')
        .then((reg) => {
          // Pick up SW updates without forcing a hard reload.
          if (reg.waiting) reg.waiting.postMessage('SKIP_WAITING');
          reg.addEventListener('updatefound', () => {
            const sw = reg.installing;
            if (!sw) return;
            sw.addEventListener('statechange', () => {
              if (sw.state === 'installed' && navigator.serviceWorker.controller) {
                sw.postMessage('SKIP_WAITING');
              }
            });
          });
        })
        .catch((err) => console.warn('[PWA] SW register failed:', err));
    });
  }
}
