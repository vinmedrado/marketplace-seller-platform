import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { Brain, Sparkles, ArrowRight, AlertTriangle } from 'lucide-react';
import Page from '../components/animations/Page';
import { Card, Skeleton } from '../components/ui/Card';
import { aiCopilotContext, applyAction, ignoreAction, money } from '../api/client';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useToast } from '../components/ui/Toast';

function Priority({ value }: { value: string }) { return <span className={`status-badge ${value==='HIGH'?'text-rose-200':value==='MEDIUM'?'text-amber-200':'text-sky-200'}`}>{value}</span>; }

export default function AICopilot(){
  const qc=useQueryClient(); const {toast}=useToast(); const apply=useMutation({mutationFn:applyAction,onSuccess:()=>{toast('Recomendação aplicada.','success');qc.invalidateQueries({queryKey:['ai-copilot-context']});}}); const ignore=useMutation({mutationFn:ignoreAction,onSuccess:()=>{toast('Recomendação ignorada.','success');qc.invalidateQueries({queryKey:['ai-copilot-context']});}}); const {data,isLoading}=useQuery({queryKey:['ai-copilot-context'],queryFn:aiCopilotContext,refetchInterval:60000});
  if(isLoading) return <Page><Skeleton className="h-[560px]"/></Page>;
  const score=data?.score||{};
  return <Page>
    <div className="relative overflow-hidden rounded-[2rem] glass premium-border p-8 glow mb-5">
      <div className="bg-orb w-72 h-72 bg-sky-400/30 -right-12 -top-16"/><div className="bg-orb w-64 h-64 bg-fuchsia-400/20 left-1/3 bottom-0"/>
      <p className="text-sky-200 font-black flex gap-2 items-center"><Brain/> AI Operations Copilot</p>
      <h1 className="text-5xl font-black max-w-4xl mt-3">Copiloto operacional para decisões de margem, pricing, concorrência e jobs.</h1>
      <p className="text-slate-300 max-w-4xl mt-4 text-lg">{data?.summary}</p>
      <div className="grid md:grid-cols-4 gap-3 mt-7">
        <div className="rounded-3xl bg-white/10 p-4 border border-white/10"><p className="text-slate-400">Maturity Score</p><b className="text-4xl">{score.score}<span className="text-xl text-slate-400">/100</span></b><p className="text-sky-200">{score.category}</p></div>
        <div className="rounded-3xl bg-white/10 p-4 border border-white/10"><p className="text-slate-400">Impacto priorizado</p><b className="text-3xl">{money(data?.recommendations?.reduce((a:number,b:any)=>a+Number(b.impact_estimated||0),0))}</b><p className="text-slate-400">estimado/mês</p></div>
        <div className="rounded-3xl bg-white/10 p-4 border border-white/10"><p className="text-slate-400">Alertas críticos</p><b className="text-4xl">{data?.smart_alerts?.critical||0}</b><p className="text-rose-200">exigem decisão</p></div>
        <div className="rounded-3xl bg-white/10 p-4 border border-white/10"><p className="text-slate-400">Modo</p><b className="text-xl">Action AI</b><p className="text-emerald-200">memória curta + status</p></div>
      </div>
      {data?.executive_context&&<div className="mt-4 rounded-3xl bg-white/10 border border-white/10 p-4"><b>Contexto executivo:</b> {data.executive_context.pending_actions} ações pendentes · {money(data.executive_context.estimated_open_impact)} em impacto aberto · janela {data.executive_context.memory_window}</div>}
    </div>
    <div className="grid xl:grid-cols-[1.45fr_.85fr] gap-4">
      <Card><div className="flex justify-between mb-4"><div><h2 className="text-2xl font-black">Recomendações autônomas</h2><p className="text-slate-400">Ações priorizadas com justificativa executiva.</p></div><Sparkles className="text-sky-200"/></div><div className="space-y-3">{(data?.recommendations||[]).map((r:any,i:number)=><motion.div initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} transition={{delay:i*.04}} key={r.id} className="rounded-3xl bg-white/[.07] border border-white/10 p-4 hover:bg-white/[.10] transition"><div className="flex justify-between gap-4"><div><Priority value={r.priority}/><b className="block mt-3 text-lg">{r.title}</b><p className="text-slate-300 mt-2">{(r.recommended_action||r.suggested_action)}</p><p className="text-slate-400 text-sm mt-2">{(r.ai_reasoning||r.explanation)}</p></div><div className="text-right min-w-32"><p className="text-slate-400">Impacto</p><b className="text-sky-200">{money(r.impact_estimated)}</b><p className="text-xs text-slate-500 mt-2">confiança {Math.round(Number(r.confidence||0)*100)}%</p></div></div><div className="flex gap-2 mt-4"><button onClick={()=>apply.mutate(r.id)} className="btn btn-primary text-sm">Aplicar</button><button onClick={()=>ignore.mutate(r.id)} className="btn btn-ghost text-sm">Ignorar</button><button className="btn btn-ghost text-sm">{r.next_best_action||r.cta} <ArrowRight size={16} className="inline"/></button></div></motion.div>)}</div></Card>
      <div className="space-y-4"><Card><h2 className="font-black text-xl">Smart Alerts</h2><div className="mt-3 space-y-3">{(data?.smart_alerts?.items||[]).slice(0,5).map((a:any)=><div key={a.category} className="rounded-2xl bg-white/[.06] p-3 border border-white/10"><div className="flex justify-between"><b>{a.title}</b><AlertTriangle size={18} className="text-amber-200"/></div><p className="text-sm text-slate-400 mt-1">{a.summary}</p><p className="text-sky-200 text-sm mt-1">{a.recommended_action}</p></div>)}</div></Card><Card><h2 className="font-black text-xl">Timeline viva</h2><div className="mt-4 space-y-3">{(data?.timeline?.items||[]).slice(0,6).map((t:any)=><div key={t.time+t.title} className="flex gap-3"><span className="text-sky-200 font-black w-14">{t.time}</span><div className="flex-1 border-l border-white/15 pl-3 pb-3"><b>{t.title}</b><p className="text-sm text-slate-400">{t.description}</p></div></div>)}</div></Card></div>
    </div>
  </Page>
}
