import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { CheckCircle2, EyeOff, Gauge, PlayCircle, ShieldAlert, Sparkles } from 'lucide-react';
import { actionCenter, applyAction, ignoreAction, resolveAction, money } from '../api/client';
import { Card, Skeleton } from '../components/ui/Card';
import { useToast } from '../components/ui/Toast';

const priorityClass:any={HIGH:'text-rose-200 bg-rose-500/15 border-rose-300/20',MEDIUM:'text-amber-200 bg-amber-500/15 border-amber-300/20',LOW:'text-sky-200 bg-sky-500/15 border-sky-300/20'};
export default function ActionCenter(){
  const qc=useQueryClient(); const {toast}=useToast();
  const {data,isLoading}=useQuery({queryKey:['action-center'],queryFn:actionCenter});
  const refresh=()=>{qc.invalidateQueries({queryKey:['action-center']});qc.invalidateQueries({queryKey:['ai-copilot-context']});};
  const apply=useMutation({mutationFn:applyAction,onSuccess:()=>{toast('Ação marcada como aplicada.','success');refresh();}});
  const ignore=useMutation({mutationFn:ignoreAction,onSuccess:()=>{toast('Ação ignorada com histórico salvo.','success');refresh();}});
  const resolve=useMutation({mutationFn:resolveAction,onSuccess:()=>{toast('Ação resolvida.','success');refresh();}});
  if(isLoading)return <Skeleton className="h-[520px]"/>;
  const summary=data?.summary||{}; const items=data?.items||[];
  return <motion.div initial={{opacity:0,y:18}} animate={{opacity:1,y:0}} className="space-y-6">
    <div className="glass premium-border rounded-[2rem] p-8 overflow-hidden relative">
      <div className="bg-orb w-80 h-80 bg-sky-500/30 -right-20 -top-20"/><p className="text-sky-200 font-bold flex gap-2"><Sparkles/>Action Intelligence Cockpit</p>
      <h2 className="text-4xl font-black mt-2">Action Center</h2><p className="text-slate-300 mt-2 max-w-3xl">Tudo que exige decisão: recomendações do Copilot, alertas críticos, produtos em risco, jobs com falha e oportunidades de pricing.</p>
      <div className="grid md:grid-cols-5 gap-3 mt-6">{[['Pendentes',summary.pending],['Críticas',summary.critical],['Aplicadas',summary.applied],['Resolvidas',summary.resolved],['Impacto aberto',money(summary.estimated_pending_impact)]].map(([l,v])=><div className="rounded-3xl bg-white/10 p-4 border border-white/10"><p className="text-xs text-slate-400">{l}</p><b className="text-2xl">{v as any}</b></div>)}</div>
    </div>
    <div className="grid xl:grid-cols-3 gap-4">{items.map((a:any,i:number)=><Card key={a.id} className="relative overflow-hidden">
      <motion.div initial={{opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{delay:i*.035}}>
        <div className="flex items-center justify-between gap-3"><span className={`status-badge border ${priorityClass[a.priority]||priorityClass.MEDIUM}`}>{a.priority}</span><span className="status-badge">{a.status}</span></div>
        <h3 className="text-xl font-black mt-4">{a.title}</h3><p className="text-sm text-slate-400 mt-1">{a.origin} · {a.category}</p>
        <p className="text-slate-300 mt-4 min-h-16">{a.explanation}</p>
        <div className="mt-4 rounded-2xl bg-white/10 p-4 border border-white/10"><p className="text-xs text-slate-400">Ação recomendada</p><b>{a.recommended_action}</b><p className="text-xs text-sky-200 mt-2">Próxima melhor ação: {a.next_best_action}</p></div>
        <div className="grid grid-cols-2 gap-3 mt-4"><div className="rounded-2xl bg-emerald-400/10 p-3"><p className="text-xs text-slate-400">Impacto</p><b>{a.impact_label}</b></div><div className="rounded-2xl bg-violet-400/10 p-3"><p className="text-xs text-slate-400">Confiança</p><b>{Math.round((a.confidence||0)*100)}%</b></div></div>
        <div className="flex flex-wrap gap-2 mt-5"><button onClick={()=>apply.mutate(a.id)} className="btn btn-primary text-sm"><CheckCircle2 size={16}/> Aplicar</button><button onClick={()=>resolve.mutate(a.id)} className="btn btn-ghost text-sm"><ShieldAlert size={16}/> Resolver</button><button onClick={()=>ignore.mutate(a.id)} className="btn btn-ghost text-sm"><EyeOff size={16}/> Ignorar</button><button className="btn btn-ghost text-sm"><PlayCircle size={16}/> Simular</button></div>
      </motion.div>
    </Card>)}</div>
    <Card><h3 className="text-xl font-black flex gap-2"><Gauge/> Histórico de decisão</h3><div className="mt-4 space-y-3">{(data?.decision_history||[]).map((d:any)=><div className="flex justify-between rounded-2xl bg-white/5 p-3 border border-white/10"><span>{d.title}</span><b>{d.status}</b></div>)}</div></Card>
  </motion.div>
}
