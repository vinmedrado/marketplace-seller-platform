import { CheckCircle2, DownloadCloud, Wifi, WifiOff } from 'lucide-react';
import { usePWAStatus } from '../../hooks/usePWAStatus';

export default function PWAStatusBadge() {
  const { online, installed } = usePWAStatus();
  return <div className="hidden sm:flex items-center gap-2">
    <span className={`status-badge ${online ? 'text-emerald-200' : 'text-amber-200'}`}>{online ? <Wifi size={14}/> : <WifiOff size={14}/>} {online ? 'Online' : 'Offline'}</span>
    <span className={`status-badge ${installed ? 'text-sky-200' : 'text-slate-300'}`}>{installed ? <CheckCircle2 size={14}/> : <DownloadCloud size={14}/>} {installed ? 'PWA instalada' : 'PWA disponível'}</span>
  </div>;
}
