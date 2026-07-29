import { useQuery } from '@tanstack/react-query';
import { Activity, AlertTriangle, CheckCircle2, PackageX, PauseCircle, ShieldAlert, ShieldCheck, TrendingDown, TrendingUp } from 'lucide-react';
import Page from '../components/animations/Page';
import { Card, Skeleton } from '../components/ui/Card';
import { accountHealth } from '../api/client';

function pct(v?: number | null) {
  if (v === null || v === undefined) return 'Não disponível';
  const n = Number(v);
  const normalized = n > 1 ? n / 100 : n;
  return `${(normalized * 100).toLocaleString('pt-BR', { maximumFractionDigits: 2 })}%`;
}

function dateFmt(v?: string | null) {
  return v ? new Date(v).toLocaleString('pt-BR') : '—';
}

function statusClasses(status?: string) {
  const s = (status || '').toUpperCase();
  if (s === 'EXCELENTE') return 'border-emerald-300/30 bg-emerald-400/10 text-emerald-100';
  if (s === 'BOA') return 'border-sky-300/30 bg-sky-400/10 text-sky-100';
  if (s === 'ATENÇÃO') return 'border-amber-300/30 bg-amber-400/10 text-amber-100';
  if (s === 'RISCO') return 'border-orange-300/30 bg-orange-400/10 text-orange-100';
  return 'border-red-300/30 bg-red-400/10 text-red-100';
}

function severityClasses(severity?: string) {
  if (severity === 'critical') return 'border-red-300/30 bg-red-400/10 text-red-100';
  if (severity === 'warning') return 'border-amber-300/30 bg-amber-400/10 text-amber-100';
  return 'border-sky-300/30 bg-sky-400/10 text-sky-100';
}

function MetricCard({ label, value, hint, icon: Icon }: { label: string; value: any; hint?: string; icon: any }) {
  return <Card>
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="text-slate-400 text-sm">{label}</p>
        <b className="text-2xl block mt-2">{value}</b>
        {hint && <p className="text-xs text-slate-500 mt-2">{hint}</p>}
      </div>
      <div className="h-11 w-11 rounded-2xl bg-white/10 border border-white/10 flex items-center justify-center"><Icon size={20}/></div>
    </div>
  </Card>;
}

export default function AccountHealth() {
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['account-health'],
    queryFn: accountHealth,
    retry: 1,
    refetchInterval: 120000,
  });

  const alerts = data?.alerts || [];
  const metrics = data?.metrics || {};
  const trend = data?.trends || {};

  return <Page>
    <div className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-white/[0.06] p-8 mb-5 glow-soft">
      <div className="absolute -right-20 -top-20 h-72 w-72 rounded-full bg-emerald-400/20 blur-3xl" />
      <div className="relative z-10 flex flex-col xl:flex-row xl:items-end xl:justify-between gap-5">
        <div>
          <span className="status-badge text-emerald-200">Mercado Livre · monitoramento operacional</span>
          <h2 className="text-4xl font-black mt-4">Saúde da Conta</h2>
          <p className="text-slate-300 mt-3 text-lg max-w-4xl">Score interno SellerOS com reputação disponível pela API, catálogo sincronizado, riscos de estoque, anúncios pausados e alertas preventivos.</p>
          <p className="text-xs text-slate-500 mt-2">Não é score oficial Mercado Livre. Métricas indisponíveis aparecem como “não disponível”.</p>
        </div>
        <button className="btn btn-primary" disabled={isFetching} onClick={() => refetch()}>{isFetching ? 'Atualizando...' : 'Atualizar saúde'}</button>
      </div>
    </div>

    {isLoading && <Skeleton className="h-96" />}

    {error && <Card>
      <div className="flex items-start gap-3">
        <ShieldAlert className="text-amber-200" />
        <div>
          <h3 className="font-black text-lg">Não foi possível carregar saúde da conta</h3>
          <p className="text-slate-400 mt-1">Verifique se o seller Mercado Livre está conectado, se o token está válido e se o catálogo já foi sincronizado.</p>
        </div>
      </div>
    </Card>}

    {!isLoading && !error && data && <>
      <div className="grid xl:grid-cols-[1.2fr_2fr] gap-4 mb-5">
        <Card className={`${statusClasses(data.status)} border`}>
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm opacity-80">Score interno SellerOS</p>
              <div className="flex items-end gap-3 mt-4"><b className="text-7xl leading-none">{data.score}</b><span className="text-xl mb-2">/100</span></div>
              <span className="inline-flex mt-5 rounded-full px-4 py-2 text-sm font-bold bg-black/20 border border-white/10">{data.status}</span>
            </div>
            <ShieldCheck size={72} className="opacity-80" />
          </div>
          <div className="mt-6 grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-2xl bg-black/15 p-3 border border-white/10"><p className="opacity-70">Reputação ML</p><b>{data.reputation_level || 'Não disponível'}</b></div>
            <div className="rounded-2xl bg-black/15 p-3 border border-white/10"><p className="opacity-70">Última leitura</p><b>{dateFmt(data.generated_at)}</b></div>
          </div>
        </Card>

        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
          <MetricCard icon={AlertTriangle} label="Cancelamentos" value={pct(metrics.cancellations_rate)} hint={data.data_availability?.cancellations_rate ? 'Métrica retornada pela API ML' : 'Métrica não disponível na API'} />
          <MetricCard icon={ShieldAlert} label="Reclamações" value={pct(metrics.claims_rate)} hint={data.data_availability?.claims_rate ? 'Métrica retornada pela API ML' : 'Métrica não disponível na API'} />
          <MetricCard icon={Activity} label="Atraso envio" value={pct(metrics.delayed_rate)} hint={data.data_availability?.delayed_rate ? 'Métrica retornada pela API ML' : 'Métrica não disponível na API'} />
          <MetricCard icon={CheckCircle2} label="Produtos ativos" value={metrics.active_products ?? 0} />
          <MetricCard icon={PauseCircle} label="Produtos pausados" value={metrics.paused_products ?? 0} />
          <MetricCard icon={PackageX} label="Health ruim" value={metrics.poor_health_products ?? 0} />
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mb-5">
        <Card className="lg:col-span-1">
          <div className="flex items-center gap-3">
            {trend.worsening ? <TrendingDown className="text-red-200"/> : trend.improving ? <TrendingUp className="text-emerald-200"/> : <Activity className="text-sky-200"/>}
            <div>
              <p className="text-slate-400">Tendência</p>
              <h3 className="text-xl font-black">{trend.worsening ? 'Piorando' : trend.improving ? 'Melhorando' : 'Estável'}</h3>
            </div>
          </div>
          <p className="text-slate-400 mt-4 text-sm">Delta vs. snapshot anterior: <b className="text-white">{trend.delta ?? 0}</b> ponto(s). Snapshot anterior: <b className="text-white">{trend.previous_score ?? '—'}</b>.</p>
        </Card>
        <Card className="lg:col-span-2">
          <p className="text-slate-400">Seller conectado</p>
          <div className="grid md:grid-cols-3 gap-3 mt-3">
            <div className="rounded-2xl bg-white/[0.06] p-4 border border-white/10"><p className="text-xs text-slate-500">Nickname</p><b>{data.seller?.nickname || '—'}</b></div>
            <div className="rounded-2xl bg-white/[0.06] p-4 border border-white/10"><p className="text-xs text-slate-500">Seller ID</p><b>{data.seller?.seller_id || '—'}</b></div>
            <div className="rounded-2xl bg-white/[0.06] p-4 border border-white/10"><p className="text-xs text-slate-500">País</p><b>{data.seller?.country_id || '—'}</b></div>
          </div>
        </Card>
      </div>

      <Card>
        <div className="flex items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="text-xl font-black">Alertas e recomendações</h3>
            <p className="text-slate-400 text-sm">Gerados a partir de métricas reais disponíveis e catálogo sincronizado.</p>
          </div>
          <span className="status-badge">{alerts.length} alerta(s)</span>
        </div>
        {alerts.length === 0 && <div className="rounded-3xl bg-white/[0.04] border border-white/10 p-8 text-center">
          <h4 className="font-black text-lg">Nenhum alerta relevante agora.</h4>
          <p className="text-slate-400 mt-2">Continue monitorando reputação, estoque e anúncios pausados após novas sincronizações.</p>
        </div>}
        <div className="grid lg:grid-cols-2 gap-4">
          {alerts.map((a:any, idx:number) => <div key={`${a.type}-${idx}`} className={`rounded-3xl border p-5 ${severityClasses(a.severity)}`}>
            <div className="flex items-center justify-between gap-3">
              <b>{a.title}</b>
              <span className="text-xs uppercase font-black">{a.severity}</span>
            </div>
            <p className="text-sm mt-3 opacity-90">{a.description}</p>
            <p className="text-sm mt-3"><b>Ação recomendada:</b> {a.recommendation}</p>
            <div className="flex gap-2 mt-4 text-xs opacity-80"><span>Valor: {String(a.metric_value ?? '—')}</span><span>Limite: {String(a.threshold ?? '—')}</span></div>
          </div>)}
        </div>
      </Card>
    </>}
  </Page>;
}
