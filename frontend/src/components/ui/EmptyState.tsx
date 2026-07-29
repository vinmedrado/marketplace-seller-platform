import type { ReactNode } from 'react';
import { Sparkles } from 'lucide-react';

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="rounded-[2rem] border border-dashed border-white/15 bg-white/[0.04] p-8 text-center">
    <div className="mx-auto h-12 w-12 rounded-2xl bg-sky-400/15 border border-sky-300/20 grid place-items-center mb-4"><Sparkles size={20}/></div>
    <b className="text-xl">{title}</b>
    <p className="text-slate-400 max-w-xl mx-auto mt-2">{description}</p>
    {action && <div className="mt-5">{action}</div>}
  </div>;
}
