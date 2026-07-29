import type { ReactNode } from 'react';
import { createContext, useContext, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, CheckCircle2, Info, Loader2 } from 'lucide-react';

type Toast = { id: number; type: 'success' | 'error' | 'loading' | 'info'; message: string };
const C = createContext<{ toast: (message: string, type?: Toast['type']) => void }>({ toast: () => {} });

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  function toast(message: string, type: Toast['type'] = 'info') {
    const id = Date.now() + Math.random();
    setItems(v => [...v, { id, type, message }]);
    setTimeout(() => setItems(v => v.filter(x => x.id !== id)), type === 'loading' ? 2200 : 3600);
  }
  useEffect(() => {
    const h = (e: any) => toast(e.detail || 'Erro de API', 'error');
    window.addEventListener('api-error', h);
    return () => window.removeEventListener('api-error', h);
  }, []);
  const icon = (t: Toast['type']) => t === 'success' ? <CheckCircle2 className="text-emerald-300"/> : t === 'error' ? <AlertTriangle className="text-rose-300"/> : t === 'loading' ? <Loader2 className="animate-spin text-sky-300"/> : <Info className="text-sky-300"/>;
  return <C.Provider value={{ toast }}>{children}<div className="fixed right-5 top-5 z-[80] space-y-2"><AnimatePresence>{items.map(t => <motion.div key={t.id} initial={{ opacity: 0, x: 36, scale: .94 }} animate={{ opacity: 1, x: 0, scale: 1 }} exit={{ opacity: 0, x: 36, scale: .94 }} className="glass premium-border rounded-2xl px-4 py-3 min-w-80 flex gap-3 items-start glow-soft">
    <div className="mt-1">{icon(t.type)}</div><div><b>{t.type === 'success' ? 'Ação concluída' : t.type === 'error' ? 'Algo deu errado' : t.type === 'loading' ? 'Processando' : 'Informação'}</b><p className="text-sm text-slate-300">{t.message}</p></div>
  </motion.div>)}</AnimatePresence></div></C.Provider>;
}
export const useToast = () => useContext(C);
