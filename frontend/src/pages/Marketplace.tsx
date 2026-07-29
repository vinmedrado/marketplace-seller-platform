import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Page from '../components/animations/Page';
import { Card, Skeleton } from '../components/ui/Card';
import { buyboxOverview, getMarketplaceConnectUrl, healthcheck, marketplaceIntelligence, marketplaceProducts, marketplaceSummary, money, syncMarketplaceCatalog } from '../api/client';

function flagLabel(flag: string) {
  const labels: Record<string, string> = {
    LOW_STOCK: 'Estoque baixo',
    OUT_OF_STOCK: 'Sem estoque',
    PAUSED: 'Pausado',
    POOR_HEALTH: 'Saúde baixa',
    PRICE_RISK: 'Risco de preço',
  };
  return labels[flag] || flag;
}

function severityLabel(severity: string) {
  const labels: Record<string, string> = { critical: 'Crítico', warning: 'Alerta', opportunity: 'Oportunidade', info: 'Info' };
  return labels[severity] || severity;
}

function fmtDate(v?: string | null) {
  return v ? new Date(v).toLocaleString('pt-BR') : '—';
}

function ProductEmptyState({ connected }: { connected: boolean }) {
  return <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-8 text-center">
    <h3 className="text-xl font-black">{connected ? 'Conta conectada. Catálogo ainda não sincronizado.' : 'Conecte seu seller Mercado Livre'}</h3>
    <p className="text-slate-400 mt-2 max-w-2xl mx-auto">
      {connected
        ? 'Sincronize seu catálogo para gerar resumo operacional, flags de saúde, riscos e recomendações reais.'
        : 'A conexão OAuth real libera leitura de catálogo, status de anúncios, estoque e inteligência operacional por produto.'}
    </p>
  </div>;
}

export default function Marketplace(){
  const qc = useQueryClient();
  const {data:health}=useQuery({queryKey:['api-health'],queryFn:healthcheck,refetchInterval:60000,retry:1});
  const {data:summary,isLoading:loadingSummary}=useQuery({queryKey:['marketplace-summary'],queryFn:marketplaceSummary,refetchInterval:30000});
  const {data:catalog,isLoading:loadingProducts}=useQuery({queryKey:['marketplace-products'],queryFn:()=>marketplaceProducts({page_size:50}),refetchInterval:45000});
  const {data:intelligence,isLoading:loadingIntelligence}=useQuery({queryKey:['marketplace-intelligence'],queryFn:()=>marketplaceIntelligence(),refetchInterval:45000});
  const {data:buybox}=useQuery({queryKey:['buybox-overview-mini'],queryFn:()=>buyboxOverview(30),refetchInterval:90000});

  const connect=useMutation({
    mutationFn:getMarketplaceConnectUrl,
    onSuccess:(res:any)=>{ if(res?.link) window.location.href=res.link; }
  });
  const sync=useMutation({
    mutationFn:()=>syncMarketplaceCatalog({limit:50}),
    onSuccess:()=>{
      qc.invalidateQueries({queryKey:['marketplace-products']});
      qc.invalidateQueries({queryKey:['marketplace-summary']});
      qc.invalidateQueries({queryKey:['marketplace-intelligence']});
    }
  });

  if(loadingSummary)return <Page><Skeleton className="h-96"/></Page>;

  const seller = summary?.seller || {};
  const catalogSummary = summary?.catalog || {};
  const syncSummary = summary?.sync || {};
  const intelSummary = summary?.intelligence || {};
  const items = catalog?.items || [];
  const buyboxByProduct = new Map((buybox?.items || []).map((b:any)=>[String(b.product_id), b]));
  const connected = Boolean(seller.connected);
  const hasProducts = Number(catalogSummary.total_products || 0) > 0;
  const topInsights = [...(intelligence?.critical || []), ...(intelligence?.warnings || []), ...(intelligence?.opportunities || [])].slice(0, 8);

  return <Page>
    <div className="flex flex-col gap-2 mb-5">
      <h2 className="text-3xl font-black">Cockpit Mercado Livre</h2>
      <p className="text-slate-400">Dashboard operacional real: seller conectado, catálogo sincronizado, saúde de anúncios e Action Intelligence baseada em dados reais.</p>
      <div className="flex flex-wrap gap-2 text-xs">
        <span className="status-badge">API: {health?.api || 'verificando'}</span>
        <span className="status-badge">Banco: {health?.database || 'verificando'}</span>
        <span className="status-badge">Ambiente: {health?.environment || '—'}</span>
        <span className="status-badge">Marketplace API: {health?.marketplace_api || '—'}</span>
      </div>
    </div>

    <div className="grid lg:grid-cols-3 gap-4 mb-5">
      <Card>
        <div className="flex justify-between gap-3 items-start">
          <div>
            <h3 className="text-2xl font-black">Seller Status</h3>
            <p className="text-slate-400 mt-1">Mercado Livre OAuth real</p>
          </div>
          <span className={`status-badge ${connected?'text-emerald-200':'text-amber-200'}`}>{connected?'Conectado':'Não conectado'}</span>
        </div>
        <div className="grid grid-cols-2 gap-3 mt-5">
          <div className="rounded-2xl bg-white/10 p-4"><p className="text-slate-400">Nickname</p><b>{seller.nickname || '—'}</b></div>
          <div className="rounded-2xl bg-white/10 p-4"><p className="text-slate-400">País</p><b>{seller.country_id || '—'}</b></div>
          <div className="rounded-2xl bg-white/10 p-4"><p className="text-slate-400">Seller ID</p><b>{seller.seller_id || '—'}</b></div>
          <div className="rounded-2xl bg-white/10 p-4"><p className="text-slate-400">Token expira</p><b>{fmtDate(seller.token_expires_at)}</b></div>
        </div>
        <div className="flex flex-wrap gap-3 mt-5">
          <button className="btn btn-primary" disabled={connect.isPending} onClick={()=>connect.mutate()}>{connect.isPending?'Abrindo OAuth...':'Conectar Mercado Livre'}</button>
          <button className="btn" disabled={!connected || sync.isPending} onClick={()=>sync.mutate()}>{sync.isPending?'Sincronizando...':'Sincronizar Catálogo'}</button>
        </div>
        {connect.error&&<p className="text-red-200 mt-3">Não foi possível iniciar OAuth. Valide variáveis ML e FERNET_KEY.</p>}
        {sync.error&&<p className="text-red-200 mt-3">Falha na sincronização. Verifique seller conectado, refresh token e /health.</p>}
        {sync.data&&<p className="text-emerald-200 mt-3">Sync concluído: {sync.data.total_synced} produtos, {sync.data.new_products} novos, {sync.data.updated_products} atualizados.</p>}
      </Card>

      <Card className="lg:col-span-2">
        <div className="flex justify-between gap-3 items-start mb-4">
          <div><h3 className="text-xl font-black">Resumo operacional</h3><p className="text-slate-400">Indicadores calculados sobre produtos reais do tenant autenticado.</p></div>
          <span className="status-badge">Último sync: {fmtDate(syncSummary.last_synced_at)}</span>
        </div>
        <div className="grid md:grid-cols-4 gap-3">
          <div className="rounded-2xl bg-white/10 p-4"><p className="text-slate-400">Total produtos</p><b className="text-2xl">{catalogSummary.total_products || 0}</b></div>
          <div className="rounded-2xl bg-white/10 p-4"><p className="text-slate-400">Ativos</p><b className="text-2xl">{catalogSummary.active_products || 0}</b></div>
          <div className="rounded-2xl bg-white/10 p-4"><p className="text-slate-400">Pausados</p><b className="text-2xl">{catalogSummary.paused_products || 0}</b></div>
          <div className="rounded-2xl bg-white/10 p-4"><p className="text-slate-400">Sem estoque</p><b className="text-2xl">{catalogSummary.out_of_stock_products || 0}</b></div>
          <div className="rounded-2xl bg-white/10 p-4"><p className="text-slate-400">Estoque baixo</p><b className="text-2xl">{catalogSummary.low_stock_products || 0}</b></div>
          <div className="rounded-2xl bg-white/10 p-4"><p className="text-slate-400">Health ruim</p><b className="text-2xl">{catalogSummary.poor_health_products || 0}</b></div>
          <div className="rounded-2xl bg-white/10 p-4"><p className="text-slate-400">Preço médio</p><b>{money(catalogSummary.avg_price || 0)}</b></div>
          <div className="rounded-2xl bg-white/10 p-4"><p className="text-slate-400">Unidades totais</p><b>{catalogSummary.total_inventory_units || 0}</b></div>
        </div>
      </Card>
    </div>

    {!connected && <ProductEmptyState connected={false}/>}
    {connected && !hasProducts && <ProductEmptyState connected={true}/>}

    {connected && hasProducts && <div className="grid xl:grid-cols-3 gap-4">
      <Card className="xl:col-span-2">
        <div className="flex justify-between items-center mb-4 gap-3">
          <div>
            <h3 className="text-xl font-black">Produtos sincronizados</h3>
            <p className="text-slate-400">Preço, estoque, status, vendas e health flags vindos da API Mercado Livre.</p>
          </div>
          <span className="status-badge">Status sync: {syncSummary.last_sync_status || '—'}</span>
        </div>
        {loadingProducts ? <Skeleton className="h-64"/> : <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-slate-400 border-b border-white/10">
              <tr><th className="py-3">Produto</th><th>Preço</th><th>Estoque</th><th>Status</th><th>Vendidos</th><th>Health</th><th>Ação sugerida</th></tr>
            </thead>
            <tbody>
              {items.map((p:any)=>{
                const insight = topInsights.find((i:any)=>i.product_id === String(p.id));
                const bx = buyboxByProduct.get(String(p.id)) as any;
                const bxProb = Number(bx?.current_probability || 0);
                const bxLabel = !bx ? null : bxProb < 45 ? 'Buy Box baixo' : bxProb < 65 ? 'Buy Box médio' : 'Buy Box forte';
                return <tr key={p.id} className="border-b border-white/5 align-top">
                  <td className="py-3 min-w-[340px]"><div className="flex items-center gap-3"><img src={p.thumbnail || 'https://placehold.co/64x64'} className="w-12 h-12 rounded-xl object-cover bg-white/10"/><div><a className="font-bold hover:underline" href={p.permalink} target="_blank" rel="noreferrer">{p.title}</a><p className="text-xs text-slate-500">{p.external_product_id} · {p.category_id || 'sem categoria'}</p><div className="flex flex-wrap gap-1 mt-2">{(p.health_flags||[]).length ? p.health_flags.map((f:string)=><span key={f} className="text-xs rounded-full bg-white/10 px-2 py-1">{flagLabel(f)}</span>) : <span className="text-xs text-emerald-200">Sem flags críticas</span>} {bxLabel&&<span className="text-xs rounded-full bg-sky-400/10 text-sky-200 px-2 py-1">{bxLabel}</span>}</div></div></div></td>
                  <td className="font-bold">{money(p.price)}</td>
                  <td>{p.available_quantity}</td>
                  <td><span className="status-badge">{p.status || '—'}</span></td>
                  <td>{p.sold_quantity || 0}</td>
                  <td>{p.health === null || p.health === undefined ? '—' : `${Math.round(Number(p.health)*100)}%`}</td>
                  <td className="min-w-[240px]"><p className="text-slate-300">{insight?.recommended_action || 'Monitorar anúncio e manter dados atualizados.'}</p></td>
                </tr>;
              })}
            </tbody>
          </table>
        </div>}
      </Card>

      <Card>
        <h3 className="text-xl font-black">Action Intelligence</h3>
        <p className="text-slate-400 mt-1">Riscos e oportunidades gerados somente a partir dos produtos reais sincronizados.</p>
        <div className="grid grid-cols-3 gap-2 mt-4 text-center">
          <div className="rounded-2xl bg-white/10 p-3"><p className="text-slate-400 text-xs">Críticos</p><b>{intelSummary.critical_alerts_count || intelligence?.summary?.critical || 0}</b></div>
          <div className="rounded-2xl bg-white/10 p-3"><p className="text-slate-400 text-xs">Alertas</p><b>{intelSummary.warnings_count || intelligence?.summary?.warnings || 0}</b></div>
          <div className="rounded-2xl bg-white/10 p-3"><p className="text-slate-400 text-xs">Oportun.</p><b>{intelSummary.opportunities_count || intelligence?.summary?.opportunities || 0}</b></div>
        </div>
        {loadingIntelligence ? <Skeleton className="h-40 mt-4"/> : <div className="flex flex-col gap-3 mt-4">
          {topInsights.map((i:any,idx:number)=><div key={`${i.type}-${i.product_id}-${idx}`} className="rounded-2xl bg-white/[0.06] border border-white/10 p-4">
            <div className="flex justify-between gap-2"><b>{i.title}</b><span className="status-badge">{severityLabel(i.severity)}</span></div>
            <p className="text-slate-400 text-sm mt-2">{i.description}</p>
            <p className="text-slate-200 text-sm mt-2"><b>Ação:</b> {i.recommended_action}</p>
          </div>)}
          {!topInsights.length&&<p className="text-slate-400 mt-4">{intelligence?.message || 'Nenhum alerta operacional relevante encontrado.'}</p>}
        </div>}
      </Card>
    </div>}
  </Page>;
}
