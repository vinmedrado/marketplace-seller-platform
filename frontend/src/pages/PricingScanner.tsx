import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import Page from '../components/animations/Page';
import { Card } from '../components/ui/Card';
import { marketPriceScan, money } from '../api/client';

function pct(v?: number | null) { return v === null || v === undefined ? '—' : `${Number(v).toFixed(2)}%`; }
function metric(v?: number | null) { return v === null || v === undefined ? '—' : money(v); }

function MiniDistribution({ data }: { data: any }) {
  const dist = data?.price_distribution || {};
  const bars = [
    ['Mínimo', dist.min],
    ['P25', dist.p25],
    ['Mediana', dist.median],
    ['P75', dist.p75],
    ['Máximo', dist.max],
  ];
  const max = Number(dist.max || 0) || 1;
  return <div className="grid md:grid-cols-5 gap-3 mt-4">
    {bars.map(([label, value]: any) => <div key={label} className="rounded-2xl bg-white/10 p-4 border border-white/10">
      <p className="text-xs text-slate-400">{label}</p>
      <b className="text-lg">{metric(value)}</b>
      <div className="h-2 rounded-full bg-white/10 mt-3 overflow-hidden">
        <div className="h-full rounded-full bg-sky-300/70" style={{ width: `${Math.max(8, Math.min(100, (Number(value || 0) / max) * 100))}%` }} />
      </div>
    </div>)}
  </div>;
}

export default function PricingScanner() {
  const [query, setQuery] = useState('');
  const [cost, setCost] = useState('');
  const scan = useMutation({
    mutationFn: () => marketPriceScan(query, cost ? Number(cost.replace(',', '.')) : undefined),
  });
  const data = scan.data;
  const suggested = data?.suggested_price || {};
  const canScan = query.trim().length >= 3 && !scan.isPending;

  return <Page>
    <div className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-white/[0.06] p-8 mb-5 glow-soft">
      <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-sky-400/20 blur-3xl" />
      <div className="relative z-10 max-w-4xl">
        <span className="status-badge text-sky-200">Ferramenta freemium · Mercado Livre público</span>
        <h2 className="text-4xl font-black mt-4">Scanner de Precificação Mercado Livre</h2>
        <p className="text-slate-300 mt-3 text-lg">Use este scanner gratuito para entender seu mercado antes de precificar seu anúncio. A análise consulta anúncios públicos reais e não exige login.</p>
        <p className="text-slate-400 mt-2">Conecte sua conta Mercado Livre para monitorar seus próprios produtos, estoque e alertas automaticamente.</p>
      </div>
    </div>

    <Card className="mb-5">
      <div className="grid lg:grid-cols-[1fr_220px_auto] gap-3 items-end">
        <label>
          <span className="text-sm text-slate-400">Nome do produto</span>
          <input className="input mt-2" value={query} onChange={e => setQuery(e.target.value)} placeholder="Ex.: camiseta oversized preta" />
        </label>
        <label>
          <span className="text-sm text-slate-400">Custo de aquisição opcional</span>
          <input className="input mt-2" value={cost} onChange={e => setCost(e.target.value)} placeholder="Ex.: 42,90" inputMode="decimal" />
        </label>
        <button className="btn btn-primary" disabled={!canScan} onClick={() => scan.mutate()}>{scan.isPending ? 'Analisando...' : 'Analisar Mercado'}</button>
      </div>
      {query.trim().length > 0 && query.trim().length < 3 && <p className="text-amber-200 mt-3">Digite pelo menos 3 caracteres para pesquisar.</p>}
      {scan.error && <p className="text-red-200 mt-3">Não foi possível executar o scanner agora. Verifique a busca ou tente novamente em alguns minutos.</p>}
    </Card>

    {!data && <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-8 text-center">
      <h3 className="text-xl font-black">Comece pesquisando um produto real</h3>
      <p className="text-slate-400 mt-2">O resultado vai mostrar distribuição de preços, top concorrentes, pontos fortes/fracos e preço sugerido com margem estimada quando você informar custo.</p>
    </div>}

    {data && <>
      <div className="grid md:grid-cols-5 gap-4 mb-5">
        <Card><p className="text-slate-400">Preço mínimo</p><b className="text-2xl">{metric(data.price_distribution?.min)}</b></Card>
        <Card><p className="text-slate-400">Mediana</p><b className="text-2xl">{metric(data.price_distribution?.median)}</b></Card>
        <Card><p className="text-slate-400">Preço médio</p><b className="text-2xl">{metric(data.price_distribution?.avg)}</b></Card>
        <Card><p className="text-slate-400">Preço sugerido</p><b className="text-2xl text-sky-200">{metric(suggested.price)}</b></Card>
        <Card><p className="text-slate-400">Margem estimada</p><b className="text-2xl">{suggested.estimated_margin == null ? '—' : money(suggested.estimated_margin)}</b><p className="text-xs text-slate-400 mt-1">{pct(suggested.margin_percent)}</p></Card>
      </div>

      <Card className="mb-5">
        <div className="flex flex-wrap justify-between gap-3">
          <div>
            <h3 className="text-xl font-black">Distribuição de preços</h3>
            <p className="text-slate-400">{data.analyzed_count} anúncios válidos analisados de {data.total_found} resultados públicos encontrados.</p>
          </div>
          <span className="status-badge">{suggested.competitiveness_position || '—'}</span>
        </div>
        <MiniDistribution data={data}/>
        <div className="rounded-2xl bg-white/10 border border-white/10 p-4 mt-4">
          <b>Raciocínio do preço sugerido</b>
          <p className="text-slate-300 mt-2">{suggested.reasoning}</p>
        </div>
      </Card>

      <div className="grid xl:grid-cols-3 gap-4">
        <Card className="xl:col-span-2">
          <div className="flex justify-between gap-3 mb-4">
            <div><h3 className="text-xl font-black">Top concorrentes</h3><p className="text-slate-400">Priorizados por vendas, frete grátis, preço competitivo e reputação disponível.</p></div>
            <span className="status-badge">Gerado: {new Date(data.generated_at).toLocaleString('pt-BR')}</span>
          </div>
          <div className="space-y-3">
            {(data.top_competitors || []).map((c:any, idx:number) => <div key={`${c.permalink}-${idx}`} className="rounded-3xl bg-white/[0.06] border border-white/10 p-4 grid md:grid-cols-[72px_1fr_auto] gap-4">
              {c.thumbnail ? <img src={c.thumbnail} className="w-16 h-16 rounded-2xl object-cover bg-white/10"/> : <div className="w-16 h-16 rounded-2xl bg-white/10"/>}
              <div>
                <a className="font-black hover:underline" href={c.permalink} target="_blank" rel="noreferrer">{c.title}</a>
                <div className="flex flex-wrap gap-2 mt-2 text-xs">
                  <span className="status-badge">{money(c.price)}</span>
                  <span className="status-badge">{c.sold_quantity || 0} vendidos</span>
                  <span className="status-badge">{c.free_shipping ? 'Frete grátis' : 'Sem frete grátis'}</span>
                  <span className="status-badge">{c.condition || 'condição n/d'}</span>
                </div>
                <div className="grid md:grid-cols-2 gap-3 mt-3">
                  <div><p className="text-xs text-emerald-200 font-bold">Forças</p><p className="text-sm text-slate-300">{(c.strengths || []).join(' · ') || 'Sem força destacada'}</p></div>
                  <div><p className="text-xs text-amber-200 font-bold">Fraquezas</p><p className="text-sm text-slate-300">{(c.weaknesses || []).join(' · ') || 'Sem fraqueza destacada'}</p></div>
                </div>
              </div>
              <div className="text-right"><b className="text-2xl">#{idx+1}</b><p className="text-xs text-slate-400 mt-1">{c.seller_reputation || 'reputação não disponível'}</p></div>
            </div>)}
          </div>
        </Card>

        <Card>
          <h3 className="text-xl font-black">Insights de mercado</h3>
          <p className="text-slate-400 mt-1">Leitura objetiva da amostra pública.</p>
          <div className="space-y-3 mt-4">
            {(data.insights || []).map((i:string, idx:number) => <div key={idx} className="rounded-2xl bg-white/10 border border-white/10 p-4 text-slate-200">{i}</div>)}
          </div>
          <div className="rounded-2xl bg-sky-400/10 border border-sky-300/20 p-4 mt-5">
            <b>Próximo passo</b>
            <p className="text-sm text-slate-300 mt-2">Conecte o seller para transformar essa análise em monitoramento contínuo dos seus anúncios reais.</p>
            <a className="btn btn-primary inline-block mt-4" href="/app/marketplace">Conectar Mercado Livre</a>
          </div>
        </Card>
      </div>
    </>}
  </Page>;
}
