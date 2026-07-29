import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import Page from '../components/animations/Page';
import { Card } from '../components/ui/Card';
import { products, titleOptimizerAnalyze, titleOptimizerProduct, money } from '../api/client';

function scoreClass(score:number){return score>=85?'text-emerald-200':score>=70?'text-sky-200':score>=50?'text-amber-200':'text-red-200'}
function asList(v:any){return Array.isArray(v)?v:[]}

export default function TitleOptimizer(){
  const [mode,setMode]=useState<'product'|'manual'>('product');
  const [productId,setProductId]=useState('');
  const [query,setQuery]=useState('');
  const catalog=useQuery({queryKey:['title-products'],queryFn:products});
  const items=useMemo(()=>Array.isArray(catalog.data)?catalog.data:[],[catalog.data]);
  const analyzeProduct=useMutation({mutationFn:()=>titleOptimizerProduct(productId)});
  const analyzeManual=useMutation({mutationFn:()=>titleOptimizerAnalyze(query)});
  const data=analyzeProduct.data||analyzeManual.data;
  const score=data?.score||{};
  const canRun=mode==='product'?Boolean(productId)&&!analyzeProduct.isPending:query.trim().length>=3&&!analyzeManual.isPending;
  function run(){
    if(mode==='product') analyzeProduct.mutate();
    else analyzeManual.mutate();
  }

  return <Page>
    <div className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-white/[0.06] p-8 mb-5 glow-soft">
      <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-violet-400/20 blur-3xl" />
      <div className="relative z-10 max-w-4xl">
        <span className="status-badge text-violet-200">PATCH 13/15 FINAL · IA segura · Mercado Livre público</span>
        <h2 className="text-4xl font-black mt-4">Otimização de Título com IA</h2>
        <p className="text-slate-300 mt-3 text-lg">Analise o título atual, compare termos recorrentes dos concorrentes e gere sugestões seguras sem alterar anúncios automaticamente.</p>
        <p className="text-amber-200 mt-3 text-sm">As sugestões não garantem posição no Mercado Livre. Revise antes de aplicar.</p>
      </div>
    </div>

    <Card className="mb-5">
      <div className="flex flex-wrap gap-3 mb-5">
        <button className={`btn ${mode==='product'?'btn-primary':'btn-ghost'}`} onClick={()=>setMode('product')}>Selecionar produto do catálogo</button>
        <button className={`btn ${mode==='manual'?'btn-primary':'btn-ghost'}`} onClick={()=>setMode('manual')}>Análise manual por busca</button>
      </div>
      {mode==='product'?<div className="grid lg:grid-cols-[1fr_auto] gap-3 items-end">
        <label><span className="text-sm text-slate-400">Produto interno</span><select className="input mt-2" value={productId} onChange={e=>setProductId(e.target.value)}>
          <option value="">Selecione um produto sincronizado</option>{items.map((p:any)=><option key={p.id} value={p.id}>{p.titulo||p.title||p.sku}</option>)}
        </select></label>
        <button className="btn btn-primary" disabled={!canRun} onClick={run}>{analyzeProduct.isPending?'Analisando...':'Otimizar título'}</button>
      </div>:<div className="grid lg:grid-cols-[1fr_auto] gap-3 items-end">
        <label><span className="text-sm text-slate-400">Busca ou título atual</span><input className="input mt-2" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Ex.: camiseta oversized preta masculina" /></label>
        <button className="btn btn-primary" disabled={!canRun} onClick={run}>{analyzeManual.isPending?'Analisando...':'Analisar busca'}</button>
      </div>}
      {(analyzeProduct.error||analyzeManual.error)&&<p className="text-red-200 mt-3">Não foi possível executar a análise. Verifique o produto/busca e tente novamente.</p>}
    </Card>

    {!data&&<div className="rounded-3xl border border-white/10 bg-white/[0.04] p-8 text-center"><h3 className="text-xl font-black">Escolha um modo para começar</h3><p className="text-slate-400 mt-2">O resultado exibirá score, termos de concorrentes, top anúncios públicos, sugestões e alertas de compliance.</p></div>}

    {data&&<>
      <div className="grid md:grid-cols-4 gap-4 mb-5">
        <Card><p className="text-slate-400">Score interno</p><b className={`text-4xl ${scoreClass(Number(score.score||0))}`}>{score.score||0}</b><p className="text-sm mt-1">{score.status||'—'}</p></Card>
        <Card><p className="text-slate-400">IA utilizada</p><b className="text-2xl">{data.ai_provider}</b><p className="text-xs text-slate-400 mt-1">{data.ai_available?'Groq configurado':'Fallback seguro'}</p></Card>
        <Card><p className="text-slate-400">Concorrentes</p><b className="text-3xl">{asList(data.top_competitors).length}</b><p className="text-xs text-slate-400 mt-1">Dados públicos ML</p></Card>
        <Card><p className="text-slate-400">Sugestões</p><b className="text-3xl">{asList(data.optimized_titles).length}</b><p className="text-xs text-slate-400 mt-1">Nada aplicado automaticamente</p></Card>
      </div>

      <div className="grid xl:grid-cols-3 gap-4 mb-5">
        <Card className="xl:col-span-2"><h3 className="text-xl font-black">Título atual</h3><p className="text-2xl font-black mt-3">{data.current_title}</p><div className="grid md:grid-cols-2 gap-4 mt-5">
          <div><h4 className="font-black text-emerald-200 mb-2">Pontos fortes</h4>{asList(score.strengths).map((s:string)=><p key={s} className="text-sm text-slate-300">✓ {s}</p>)}{!asList(score.strengths).length&&<p className="text-sm text-slate-400">Sem força destacada.</p>}</div>
          <div><h4 className="font-black text-amber-200 mb-2">Pontos fracos</h4>{asList(score.weaknesses).map((s:string)=><p key={s} className="text-sm text-slate-300">• {s}</p>)}{!asList(score.weaknesses).length&&<p className="text-sm text-slate-400">Sem fraqueza relevante.</p>}</div>
        </div></Card>
        <Card><h3 className="text-xl font-black">Termos recorrentes</h3><div className="flex flex-wrap gap-2 mt-4">{asList(data.competitor_terms).map((t:string)=><span key={t} className="status-badge">{t}</span>)}</div>{!asList(data.competitor_terms).length&&<p className="text-slate-400 mt-2">Sem termos suficientes.</p>}</Card>
      </div>

      <Card className="mb-5"><div className="flex justify-between gap-3 mb-4"><div><h3 className="text-xl font-black">Títulos sugeridos</h3><p className="text-slate-400">Copie somente após revisar atributos reais do produto.</p></div><span className="status-badge">Gerado: {new Date(data.generated_at).toLocaleString('pt-BR')}</span></div><div className="grid lg:grid-cols-3 gap-4">
        {asList(data.optimized_titles).map((s:any,idx:number)=><div key={`${s.title}-${idx}`} className="rounded-3xl bg-white/[0.06] border border-white/10 p-5 flex flex-col gap-3"><span className="status-badge w-fit">Sugestão {idx+1}</span><h4 className="font-black text-lg">{s.title}</h4><p className="text-sm text-slate-300"><b>Motivo:</b> {s.reasoning}</p><p className="text-sm text-slate-300"><b>Impacto esperado:</b> {s.expected_impact}</p><p className="text-xs text-amber-200">{s.risk_notes}</p><button className="btn btn-primary mt-auto" onClick={()=>navigator.clipboard?.writeText(s.title)}>Copiar sugestão</button></div>)}
      </div></Card>

      <div className="grid xl:grid-cols-3 gap-4">
        <Card className="xl:col-span-2"><h3 className="text-xl font-black mb-4">Top concorrentes públicos</h3><div className="space-y-3">{asList(data.top_competitors).map((c:any,idx:number)=><div key={`${c.permalink}-${idx}`} className="rounded-3xl bg-white/[0.06] border border-white/10 p-4 grid md:grid-cols-[64px_1fr_auto] gap-4"><img src={c.thumbnail||'https://placehold.co/64x64'} className="w-16 h-16 rounded-2xl object-cover bg-white/10"/><div><a className="font-black hover:underline" href={c.permalink} target="_blank" rel="noreferrer">{c.title}</a><div className="flex flex-wrap gap-2 mt-2 text-xs"><span className="status-badge">{money(c.price)}</span><span className="status-badge">{c.sold_quantity||0} vendidos</span><span className="status-badge">{c.category_id||'categoria n/d'}</span>{c.free_shipping&&<span className="status-badge">Frete grátis</span>}</div></div><b className="text-2xl">#{idx+1}</b></div>)}</div></Card>
        <Card><h3 className="text-xl font-black">Avisos e compliance</h3><div className="space-y-3 mt-4">{asList(data.warnings).map((w:string)=><p key={w} className="rounded-2xl bg-amber-400/10 border border-amber-300/20 p-3 text-sm text-amber-100">{w}</p>)}</div></Card>
      </div>
    </>}
  </Page>
}
