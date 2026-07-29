import { useEffect, useMemo, useState } from 'react';

declare global {
  interface WindowEventMap { beforeinstallprompt: BeforeInstallPromptEvent; }
  interface BeforeInstallPromptEvent extends Event { prompt: () => Promise<void>; userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>; }
}

function isStandalone() {
  return window.matchMedia('(display-mode: standalone)').matches || (window.navigator as any).standalone === true;
}
function detectPlatform() {
  const ua = navigator.userAgent.toLowerCase();
  if (/iphone|ipad|ipod/.test(ua)) return 'ios';
  if (/android/.test(ua)) return 'android';
  if (/chrome|edge|edg/.test(ua)) return 'desktop-chromium';
  return 'desktop';
}
export function usePWAStatus() {
  const [online, setOnline] = useState(navigator.onLine);
  const [installed, setInstalled] = useState(isStandalone());
  const [promptEvent, setPromptEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [dismissed, setDismissed] = useState(localStorage.getItem('marketplace-seller-platform_pwa_install_dismissed') === '1');
  const [lastSync, setLastSync] = useState(localStorage.getItem('marketplace-seller-platform_last_online_at') || '');
  const platform = useMemo(() => detectPlatform(), []);
  useEffect(() => {
    const onOnline = () => { const now = new Date().toISOString(); localStorage.setItem('marketplace-seller-platform_last_online_at', now); setLastSync(now); setOnline(true); };
    const onOffline = () => setOnline(false);
    const onBeforeInstall = (event: BeforeInstallPromptEvent) => { event.preventDefault(); setPromptEvent(event); };
    const onInstalled = () => { setInstalled(true); setPromptEvent(null); localStorage.setItem('marketplace-seller-platform_pwa_installed', '1'); };
    window.addEventListener('online', onOnline); window.addEventListener('offline', onOffline); window.addEventListener('beforeinstallprompt', onBeforeInstall); window.addEventListener('appinstalled', onInstalled);
    return () => { window.removeEventListener('online', onOnline); window.removeEventListener('offline', onOffline); window.removeEventListener('beforeinstallprompt', onBeforeInstall); window.removeEventListener('appinstalled', onInstalled); };
  }, []);
  async function install() {
    if (!promptEvent) return false;
    await promptEvent.prompt();
    const choice = await promptEvent.userChoice;
    setPromptEvent(null);
    if (choice.outcome === 'accepted') { setInstalled(true); return true; }
    return false;
  }
  function dismissInstall() { localStorage.setItem('marketplace-seller-platform_pwa_install_dismissed','1'); setDismissed(true); }
  const canInstall = !!promptEvent && !installed && !dismissed;
  return { online, installed, canInstall, install, dismissInstall, platform, lastSync };
}
