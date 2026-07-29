import { useEffect, useRef } from 'react';
import { WifiOff } from 'lucide-react';
import { usePWAStatus } from '../../hooks/usePWAStatus';
import { useToast } from '../ui/Toast';

export default function NetworkStatusToast() {
  const { online } = usePWAStatus();
  const { toast } = useToast();
  const mounted = useRef(false);
  useEffect(() => {
    if (!mounted.current) { mounted.current = true; return; }
    toast(online ? 'Conexão restaurada. Atualize os dados para ver informações recentes.' : 'Você está offline. Alguns dados podem não estar atualizados.', online ? 'success' : 'info');
  }, [online, toast]);
  if (online) return null;
  return <div className="fixed left-3 right-3 top-3 z-[70] lg:left-auto lg:right-5 lg:w-[420px] glass premium-border rounded-2xl px-4 py-3 flex items-start gap-3">
    <WifiOff className="text-amber-200 mt-1" /><div><b>Modo offline</b><p className="text-sm text-slate-300">Você está offline. Alguns dados podem não estar atualizados.</p></div>
  </div>;
}
