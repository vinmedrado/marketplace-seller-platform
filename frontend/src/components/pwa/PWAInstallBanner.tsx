import { Download, Smartphone, X } from 'lucide-react';
import { usePWAStatus } from '../../hooks/usePWAStatus';
import { useToast } from '../ui/Toast';

export default function PWAInstallBanner() {
  const { canInstall, install, dismissInstall, platform } = usePWAStatus();
  const { toast } = useToast();
  if (!canInstall) return null;
  async function onInstall() {
    const ok = await install();
    toast(ok ? 'MarketPlace Seller Platform instalado como app.' : 'Instalação cancelada. Você pode instalar depois.', ok ? 'success' : 'info');
  }
  return <div className="install-hint glass premium-border rounded-3xl p-4 flex flex-col sm:flex-row sm:items-center gap-3 glow-soft safe-bottom">
    <div className="h-11 w-11 rounded-2xl bg-sky-400/15 border border-sky-300/20 grid place-items-center shrink-0"><Smartphone className="text-sky-200" /></div>
    <div className="flex-1 min-w-0"><b>Instalar MarketPlace Seller Platform</b><p className="text-sm text-slate-300">Abra como app no {platform === 'android' ? 'Android' : platform === 'ios' ? 'iPhone/iPad' : 'desktop'} com carregamento mais rápido e shell offline seguro.</p></div>
    <div className="flex gap-2"><button className="btn btn-primary" onClick={onInstall}><Download size={17}/> Instalar</button><button className="btn btn-ghost" onClick={dismissInstall} aria-label="Dispensar instalação"><X size={17}/></button></div>
  </div>;
}
