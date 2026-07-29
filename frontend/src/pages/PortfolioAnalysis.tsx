import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Page from '../components/animations/Page';
import { Card } from '../components/ui/Card';
import { portfolioAnalysis, money } from '../api/client';

const classLabel:any={STAR:'Estrela',CASH_COW:'Vaca leiteira',PROBLEM:'Problema',DOG:'Abacaxi'};
const classTone:any={STAR:'text-emerald-200',CASH_COW:'text-sky-200',PROBLEM:'text-amber-200',DOG:'text-red-200'};
function pct(v:any){return v===null||v===undefined?'—':`${(Number(v)*100).toFixed(1)}%`}
function num(v:any){return v===null||v===undefined?'—':Number(v).toFixed(2)}
function score(v:any){return v===null||v===undefined?'—':Number(v).toFixed(0)}

export default function PortfolioAnalysis(){
  const [cls,setCls]=useState('ALL');
  const [risk,setRisk]=useState('ALL');
  const [opp,setOpp]=useState('ALL');
  const q=useQuery({queryKey:['portfolio-analysis'],queryFn:portfolioAnalysis});
  const data=q.data;
  const products=useMemo(()=>{
    const rows=Array.isArray(data?.products)?data.products:[];
    return rows.filter((p:any)=>{
      if(cls!=='ALL'&&p.portfolio_class!==cls)return false;
      if(risk==='HIGH'&&Number(p.risk_score||0)<70)return false;
      if(risk==='LOW'&&Number(p.risk_score||0)>=70)return false;
      if(opp==='HIGH'&&Number(p.opportunity_score||0)<70)return false;
      if(opp==='LOW'&&Number(p.opportunity_score||0)>=70)return false;
      return true;
    })
  },[data,cls,risk,opp]);
  const summary=data?.summary||{};

  return <Page>
    <div className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-white/[0.06] p-8 mb-5 glow-soft">
      <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-emerald-400/20 blur-3xl" />
      <div className="relative z-10 max-w-5xl">
        <span className="status-badge text-emerald-200">PATCH 14/15 FINAL · Portfólio estratégico · Dados reais disponíveis</span>
        <h2 className="text-4xl font-black mt-4">Análise de Portfólio</h2>
        <p className="text-slate-300 mt-3 text-lg">Classifique produtos por giro, margem, risco e oportunidade para decidir onde priorizar, melhorar, ajustar preço, repor estoque ou descontinuar.</p>
        <p className="text-slate-400 mt-3 text-sm">Classificação interna SellerOS baseada nos dados disponíveis. Quanto mais dados financeiros e históricos, maior a precisão.</p>
      </div>
    </div>

    {q.isLoading&&<Card><p>Gerando análise estratégica do portfólio...</p></Card>}
    {q.error&&<Card><p className="text-red-200">Não foi possível carregar a análise de portfólio.</p></Card>}

    {data&&<>
      <div className="grid md:grid-cols-5 gap-4 mb-5">
        <Card><p className="text-slate-400">Estrelas</p><b className="text-4xl text-emerald-200">{summary.stars||0}</b><p className="text-xs text-slate-400 mt-1">Alto giro + boa margem</p></Card>
        <Card><p className="text-slate-400">Vacas</p><b className="text-4xl text-sky-200">{summary.cows||0}</b><p className="text-xs text-slate-400 mt-1">Alto giro + margem baixa</p></Card>
        <Card><p className="text-slate-400">Problemas</p><b className="text-4xl text-amber-200">{summary.problems||0}</b><p className="text-xs text-slate-400 mt-1">Baixo giro + boa margem</p></Card>
        <Card><p className="text-slate-400">Abacaxis</p><b className="text-4xl text-red-200">{summary.dogs||0}</b><p className="text-xs text-slate-400 mt-1">Baixo giro + margem baixa</p></Card>
        <Card><p className="text-slate-400">Saúde</p><b className="text-4xl">{summary.portfolio_health_score||0}</b><p className="text-xs text-slate-400 mt-1">Score interno 0–100</p></Card>
      </div>

      <div className="grid xl:grid-cols-[1fr_1.35fr] gap-5 mb-5">
        <Card>
          <h3 className="text-xl font-black mb-4">Matriz 2x2</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-3xl border border-emerald-300/20 bg-emerald-400/10 p-5"><b className="text-emerald-200">Estrela</b><p className="text-sm text-slate-300 mt-2">Alto giro / boa margem</p><p className="text-3xl font-black mt-4">{summary.stars||0}</p></div>
            <div className="rounded-3xl border border-sky-300/20 bg-sky-400/10 p-5"><b className="text-sky-200">Vaca leiteira</b><p className="text-sm text-slate-300 mt-2">Alto giro / margem baixa</p><p className="text-3xl font-black mt-4">{summary.cows||0}</p></div>
            <div className="rounded-3xl border border-amber-300/20 bg-amber-400/10 p-5"><b className="text-amber-200">Problema</b><p className="text-sm text-slate-300 mt-2">Baixo giro / boa margem</p><p className="text-3xl font-black mt-4">{summary.problems||0}</p></div>
            <div className="rounded-3xl border border-red-300/20 bg-red-400/10 p-5"><b className="text-red-200">Abacaxi</b><p className="text-sm text-slate-300 mt-2">Baixo giro / margem baixa</p><p className="text-3xl font-black mt-4">{summary.dogs||0}</p></div>
          </div>
        </Card>
        <Card>
          <div className="flex flex-wrap justify-between gap-3 mb-5"><div><h3 className="text-xl font-black">Filtros</h3><p className="text-slate-400">Foque por classe, risco e oportunidade.</p></div><span className="status-badge">{products.length} produtos</span></div>
          <div className="grid md:grid-cols-3 gap-3">
            <label><span className="text-sm text-slate-400">Classe</span><select className="input mt-2" value={cls} onChange={e=>setCls(e.target.value)}><option value="ALL">Todas</option><option value="STAR">Estrela</option><option value="CASH_COW">Vaca leiteira</option><option value="PROBLEM">Problema</option><option value="DOG">Abacaxi</option></select></label>
            <label><span className="text-sm text-slate-400">Risco</span><select className="input mt-2" value={risk} onChange={e=>setRisk(e.target.value)}><option value="ALL">Todos</option><option value="HIGH">Alto</option><option value="LOW">Baixo/médio</option></select></label>
            <label><span className="text-sm text-slate-400">Oportunidade</span><select className="input mt-2" value={opp} onChange={e=>setOpp(e.target.value)}><option value="ALL">Todas</option><option value="HIGH">Alta</option><option value="LOW">Baixa/média</option></select></label>
          </div>
          <div className="grid md:grid-cols-3 gap-3 mt-5 text-sm text-slate-300">
            <div className="rounded-2xl bg-white/[0.05] p-4"><b>Giro médio</b><p>{num(summary.avg_sales_velocity)} vendas/dia</p></div>
            <div className="rounded-2xl bg-white/[0.05] p-4"><b>Margem média</b><p>{pct(summary.avg_margin)}</p></div>
            <div className="rounded-2xl bg-white/[0.05] p-4"><b>Gerado em</b><p>{new Date(data.generated_at).toLocaleString('pt-BR')}</p></div>
          </div>
        </Card>
      </div>

      <Card>
        <div className="flex flex-wrap justify-between gap-3 mb-4"><div><h3 className="text-xl font-black">Produtos classificados</h3><p className="text-slate-400">Nenhuma alteração é aplicada automaticamente.</p></div><button className="btn btn-ghost" onClick={()=>q.refetch()}>Atualizar análise</button></div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[1100px]">
            <thead><tr className="text-left text-slate-400 border-b border-white/10"><th className="py-3">Produto</th><th>Classe</th><th>Giro</th><th>Margem</th><th>Buy Box</th><th>Título</th><th>Risco</th><th>Oportunidade</th><th>Recomendação</th></tr></thead>
            <tbody>{products.map((p:any)=><tr key={p.product_id} className="border-b border-white/5 align-top"><td className="py-4"><div className="flex gap-3"><img src={p.thumbnail||'https://placehold.co/56x56'} className="w-14 h-14 rounded-2xl object-cover bg-white/10"/><div><b>{p.title}</b><p className="text-xs text-slate-400">{p.external_product_id||'Produto interno'} · {money(p.price)}</p>{(p.warnings||[]).slice(0,2).map((w:string)=><p key={w} className="text-xs text-amber-200 mt-1">• {w}</p>)}</div></div></td><td><span className={`font-black ${classTone[p.portfolio_class]}`}>{classLabel[p.portfolio_class]}</span><p className="text-xs text-slate-400">conf. {pct(p.confidence)}</p></td><td>{num(p.sales_velocity)}</td><td>{pct(p.estimated_margin)}</td><td>{score(p.buybox_probability)}</td><td>{score(p.title_score)}</td><td>{score(p.risk_score)}</td><td>{score(p.opportunity_score)}</td><td>{(p.recommendations||[]).slice(0,3).map((r:string)=><p key={r} className="text-slate-300">• {r}</p>)}</td></tr>)}</tbody>
          </table>
        </div>
      </Card>
    </>}
  </Page>
}
