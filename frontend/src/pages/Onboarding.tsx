import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { BellRing, CheckCircle2, PackageSearch, PlugZap, Rocket, Sparkles, Trophy } from 'lucide-react';
import Page from '../components/animations/Page';
import { Card, Skeleton } from '../components/ui/Card';
import { getOnboarding, onboardingInsights, saveOnboarding, syncMarketplaceCatalog } from '../api/client';

const stepIcons = [PlugZap, PackageSearch, Sparkles, BellRing, Rocket];
const money = (v?: number | null) => v == null ? '—' : new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(v));
const pct = (v?: number | null) => v == null ? '—' : `${Math.round(Number(v) * 100)}%`;

function InsightCard({ title, item, fallback }: { title: string; item: any; fallback: string }) {
  return <div className="rounded-3xl bg-white/10 border border-white/10 p-4 min-h-36">
    <p className="text-xs text-slate-400 font-bold uppercase tracking-wide">{title}</p>
    {item ? <><b className="block mt-2 line-clamp-2">{item.title}</b><p className="text-sm text-slate-400 mt-2">{item.reason}</p><div className="flex flex-wrap gap-2 mt-3"><span className="status-badge">Preço {money(item.price)}</span>{item.buybox_probability != null && <span className="status-badge">Buy Box {Math.round(item.buybox_probability)}%</span>}{item.estimated_margin != null && <span className="status-badge">Margem {pct(item.estimated_margin)}</span>}{item.title_score != null && <span className="status-badge">Título {item.title_score}</span>}</div></> : <p className="text-slate-400 mt-3 text-sm">{fallback}</p>}
  </div>;
}

export default function Onboarding() {
  const { data, isLoading, refetch } = useQuery({ queryKey: ['onboarding'], queryFn: getOnboarding });
  const { data: insights, isLoading: loadingInsights, refetch: refetchInsights } = useQuery({ queryKey: ['onboarding-insights'], queryFn: onboardingInsights });
  const [form, setForm] = useState<any>({});
  const saveMut = useMutation({ mutationFn: saveOnboarding, onSuccess: () => refetch() });
  const syncMut = useMutation({ mutationFn: () => syncMarketplaceCatalog({ mode: 'incremental' }), onSuccess: () => refetchInsights() });
  if (isLoading || loadingInsights) return <Page><Skeleton className="h-96" /></Page>;
  const steps = insights?.steps || [];
  const completed = steps.filter((s: any) => s.done).length;
  const progress = steps.length ? Math.round((completed / steps.length) * 100) : 0;
  const save = (step: number, done = false) => saveMut.mutate({ current_step: step, completed: done, data: { ...data?.data, ...form, final_onboarding: true } });
  const h = insights?.highlights || {};

  return <Page>
    <div className="grid xl:grid-cols-[1fr_360px] gap-4">
      <div className="space-y-4">
        <Card className="overflow-hidden relative"><div className="absolute right-0 top-0 h-48 w-48 bg-sky-400/20 blur-3xl rounded-full" /><div className="relative flex flex-col md:flex-row md:items-end md:justify-between gap-4"><div><span className="status-badge text-sky-200">PATCH 15/15 FINAL</span><h2 className="text-3xl md:text-4xl font-black mt-3">Primeira experiência SellerOS</h2><p className="text-slate-400 mt-2 max-w-2xl">Conecte, sincronize e veja os primeiros riscos e oportunidades em poucos minutos. Nenhuma alteração é enviada automaticamente ao Mercado Livre.</p></div><div className="text-right"><b className="text-4xl">{progress}%</b><p className="text-slate-400">pronto</p></div></div><div className="h-3 rounded-full bg-white/10 mt-5 overflow-hidden"><div className="h-full bg-gradient-to-r from-sky-400 to-violet-500" style={{ width: `${progress}%` }} /></div></Card>
        <div className="grid md:grid-cols-5 gap-3">{steps.map((s: any, i: number) => { const Icon = stepIcons[i] || CheckCircle2; return <Card key={s.key} className="p-4"><Icon className={s.done ? 'text-emerald-300' : 'text-slate-400'} /><b className="block mt-3 text-sm">{s.title}</b><span className="status-badge mt-3 inline-flex">{s.done ? 'Concluído' : 'Pendente'}</span></Card>; })}</div>
        <Card><div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4"><div><h3 className="text-2xl font-black">Insights iniciais</h3><p className="text-slate-400">Resumo criado com Buy Box, Forecast, Portfólio, Título e Account Health quando disponíveis.</p></div><button className="btn btn-primary" disabled={syncMut.isPending} onClick={() => syncMut.mutate()}>{syncMut.isPending ? 'Sincronizando...' : 'Sincronizar catálogo'}</button></div><div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3"><InsightCard title="Maior risco Buy Box" item={h.highest_buybox_risk} fallback="Rode Buy Box Score para identificar risco competitivo." /><InsightCard title="Melhor margem" item={h.best_margin} fallback="Informe custos ou rode reconciliação para estimar margem." /><InsightCard title="Estoque crítico" item={h.critical_stock} fallback="Rode Forecast para estimar dias de estoque." /><InsightCard title="Título fraco" item={h.weak_title} fallback="Rode Otimização de Título para gerar score." /><InsightCard title="Oportunidade principal" item={h.main_opportunity} fallback="Rode Análise de Portfólio para priorizar produtos." /></div></Card>
        <Card><h3 className="text-2xl font-black mb-2">Configuração rápida</h3><p className="text-slate-400 mb-5">Preferências continuam salvas no backend existente de onboarding.</p><div className="grid md:grid-cols-3 gap-3"><input className="input" placeholder="Nome da empresa" defaultValue={data?.data?.company_name || ''} onChange={e => setForm((v: any) => ({ ...v, company_name: e.target.value }))} /><select className="input" defaultValue={data?.data?.operation_type || 'revenda'} onChange={e => setForm((v: any) => ({ ...v, operation_type: e.target.value }))}><option value="revenda">Revenda</option><option value="marca_propria">Marca própria</option><option value="distribuidor">Distribuidor</option></select><input className="input" type="number" placeholder="Margem mínima %" defaultValue={data?.data?.min_margin_pct || 18} onChange={e => setForm((v: any) => ({ ...v, min_margin_pct: Number(e.target.value) }))} /></div><div className="flex flex-wrap gap-3 mt-6"><button className="btn btn-ghost" onClick={() => save(Math.max(1, Number(insights?.next_step || 1) - 1))}>Salvar progresso</button><button className="btn btn-primary" onClick={() => save(5, true)}>Seu SellerOS está pronto</button><Link className="btn btn-ghost" to="/app/alerts">Configurar alertas</Link><Link className="btn btn-ghost" to="/app/dashboard">Ir para cockpit</Link></div></Card>
      </div>
      <aside className="space-y-4"><Card><Trophy className="text-sky-300" /><h3 className="font-black text-xl mt-3">Valor imediato</h3><p className="text-slate-400 mt-2">O onboarding prioriza ações que ajudam o seller a ver risco, estoque, título e oportunidade sem precisar navegar por todos os módulos.</p></Card><Card><h3 className="font-black mb-3">Avisos</h3>{(insights?.warnings || []).length ? insights.warnings.map((w: string) => <p key={w} className="text-sm text-amber-100 bg-amber-400/10 border border-amber-300/20 rounded-2xl p-3 mb-2">{w}</p>) : <p className="text-emerald-200">Base inicial pronta para operação.</p>}<p className="text-xs text-slate-500 mt-4">{insights?.disclaimer}</p></Card></aside>
    </div>
  </Page>;
}
