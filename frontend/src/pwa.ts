export function registerSellerOSPWA() {
  if (!('serviceWorker' in navigator) || !import.meta.env.PROD) return;
  window.addEventListener('load', async () => {
    try {
      const registration = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
      registration.addEventListener('updatefound', () => {
        const worker = registration.installing;
        if (!worker) return;
        worker.addEventListener('statechange', () => {
          if (worker.state === 'installed' && navigator.serviceWorker.controller) {
            window.dispatchEvent(new CustomEvent('selleros-pwa-update-ready'));
          }
        });
      });
    } catch (err) {
      console.warn('[SellerOS PWA] Service worker não registrado', err);
    }
  });
}
