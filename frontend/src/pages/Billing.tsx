import { useEffect, useMemo, useState } from 'react';
import { BadgeCheck, CreditCard, Crown, RefreshCw, ShieldCheck, Sparkles, TriangleAlert, XCircle } from 'lucide-react';
import { billingCancel, billingPlans, billingStatus, billingSubscribe, money } from '../api/client';

function Badge({ children, tone='slate' }: { children:any; tone?: 'green'|'yellow'|'red'|'blue'|'slate' }) {
  const cls = tone==='green'?'bg-emerald-400/10 text-emerald-200 border-emerald-300/20':tone==='yellow'?'bg-amber-400/10 text-amber-200 border-amber-300/20':tone==='red'?'bg-rose-400/10 text-rose-200 border-rose-300/20':tone==='blue'?'bg-sky-400/10 text-sky-200 border-sky-300/20':'bg-white/10 text-slate-200 border-white/10';
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-bold ${cls}`}>{children}</span>;
}

const defaultCustomer = { name: '', email: '', document: '', phone: '' };

export default function Billing() {
  const [plans, setPlans] = useState<any[]>([]);
  const [status, setStatus] = useState<any>(null);
  const [selectedPlan, setSelectedPlan] = useState('GROWTH');
  const [customer, setCustomer] = useState<any>(defaultCustomer);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function load() {
    setLoading(true);
    try {
      const [p, s] = await Promise.all([billingPlans(), billingStatus()]);
      setPlans(p.plans || []);
      setStatus(s);
      setSelectedPlan(s?.plan?.code || 'GROWTH');
    } finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);
  const providerConfigured = !!status?.provider?.configured;
  const currentPlan = status?.plan;
  const subscription = status?.subscription || {};
  const usage = status?.usage || {};
  const limits = status?.limits || {};
  const selected = useMemo(() => plans.find((p:any)=>p.code===selectedPlan), [plans, selectedPlan]);

  async function subscribe() {
    setBusy(true); setMessage('');
    try {
      const result = await billingSubscribe(selectedPlan, customer);
      setMessage(result?.message || (result?.ok ? 'Assinatura criada/atualizada.' : 'Não foi possível criar assinatura.'));
      await load();
    } catch (err:any) { setMessage(err?.response?.data?.detail?.message || err.message || 'Erro ao criar assinatura.'); }
    finally { setBusy(false); }
  }

  async function cancel() {
    if (!window.confirm('Cancelar renovação da assinatura?')) return;
    setBusy(true); setMessage('');
    try { await billingCancel(); setMessage('Cancelamento solicitado.'); await load(); }
    catch (err:any) { setMessage(err?.response?.data?.detail?.message || err.message || 'Erro ao cancelar.'); }
    finally { setBusy(false); }
  }

  if (loading) return <div className="glass premium-border rounded-[2rem] p-8 text-slate-300">Carregando billing...</div>;

  return <div className="space-y-6">
    <section className="glass premium-border rounded-[2rem] p-6">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
        <div>
          <p className="text-sm text-sky-200 font-bold flex items-center gap-2"><CreditCard size={18}/> Billing Pagar.me</p>
          <h2 className="text-3xl font-black mt-1">Assinatura e monetização SaaS</h2>
          <p className="text-slate-300 mt-2 max-w-3xl">Controle de plano, limites e status de cobrança. O SellerOS não salva dados de cartão; pagamentos devem usar token/card_id/checkout seguro do provider.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={providerConfigured?'green':'yellow'}>{providerConfigured ? 'Pagar.me configurado' : 'Pagar.me indisponível'}</Badge>
          <Badge tone="blue">Plano atual: {currentPlan?.name || 'Starter'}</Badge>
          <Badge tone={['active','paid','trial','trialing','pending'].includes(String(subscription.status).toLowerCase())?'green':'red'}>{subscription.status || 'trial'}</Badge>
        </div>
      </div>
      {message && <div className="mt-4 rounded-2xl border border-white/10 bg-white/10 p-4 text-sm text-slate-200">{message}</div>}
    </section>

    <section className="grid lg:grid-cols-3 gap-5">
      <div className="glass premium-border rounded-[2rem] p-6 lg:col-span-1">
        <h3 className="text-xl font-black flex items-center gap-2"><ShieldCheck/> Status atual</h3>
        <div className="mt-5 space-y-3 text-sm text-slate-300">
          <p>Plano: <b className="text-white">{currentPlan?.name}</b></p>
          <p>Status: <b className="text-white">{subscription.status || 'trial'}</b></p>
          <p>Período: <b className="text-white">{subscription.current_period_start?.slice(0,10) || '—'} até {subscription.current_period_end?.slice(0,10) || '—'}</b></p>
          <p>Trial até: <b className="text-white">{subscription.trial_ends_at?.slice(0,10) || '—'}</b></p>
          <p>Último pagamento: <b className="text-white">{subscription.last_payment_status || '—'}</b></p>
        </div>
        {subscription.cancel_at_period_end && <div className="mt-4 rounded-2xl bg-amber-400/10 border border-amber-300/20 p-3 text-amber-100 text-sm">Renovação marcada para cancelamento.</div>}
        <button onClick={cancel} disabled={busy || !subscription.pagarme_subscription_id} className="btn btn-ghost w-full mt-5"><XCircle size={17}/> Cancelar renovação</button>
      </div>

      <div className="glass premium-border rounded-[2rem] p-6 lg:col-span-2">
        <div className="flex items-center justify-between gap-3"><h3 className="text-xl font-black flex items-center gap-2"><RefreshCw/> Uso e limites</h3>{status?.limit_warning && <Badge tone="yellow">Atenção ao limite</Badge>}</div>
        <div className="grid md:grid-cols-2 gap-4 mt-5">
          <div className="rounded-3xl bg-white/[0.06] border border-white/10 p-5">
            <p className="text-slate-400 text-sm">Produtos</p><p className="text-3xl font-black mt-1">{usage.products || 0}<span className="text-base text-slate-400"> / {limits.products ?? 'ilimitado'}</span></p>
          </div>
          <div className="rounded-3xl bg-white/[0.06] border border-white/10 p-5">
            <p className="text-slate-400 text-sm">Usuários</p><p className="text-3xl font-black mt-1">{usage.users || 0}<span className="text-base text-slate-400"> / {limits.users ?? 'ilimitado'}</span></p>
          </div>
        </div>
        {status?.limit_reason && <div className="mt-4 rounded-2xl bg-amber-400/10 border border-amber-300/20 p-4 text-sm text-amber-100 flex gap-2"><TriangleAlert size={18}/>{status.limit_reason}</div>}
      </div>
    </section>

    <section className="grid xl:grid-cols-3 gap-5">
      {plans.map((p:any)=><div key={p.code} className={`glass premium-border rounded-[2rem] p-6 ${currentPlan?.code===p.code?'shadow-[0_0_36px_rgba(56,189,248,.18)]':''}`}>
        <div className="flex items-center justify-between"><h3 className="text-2xl font-black">{p.name}</h3>{currentPlan?.code===p.code ? <Badge tone="green">Atual</Badge> : <Crown className="text-sky-200"/>}</div>
        <p className="text-3xl font-black mt-4">{money(p.monthly_price)}<span className="text-sm text-slate-400">/mês</span></p>
        <div className="mt-4 text-sm text-slate-300 space-y-1"><p>Produtos: <b>{p.limits.products ?? 'Ilimitado'}</b></p><p>Usuários: <b>{p.limits.users ?? 'Ilimitado'}</b></p></div>
        <ul className="mt-4 space-y-2 text-sm text-slate-300">{(p.features||[]).map((f:string)=><li key={f} className="flex gap-2"><BadgeCheck size={16} className="text-emerald-300 shrink-0"/> {f}</li>)}</ul>
        <button onClick={()=>setSelectedPlan(p.code)} className={`btn w-full mt-5 ${selectedPlan===p.code?'btn-primary':'btn-ghost'}`}>{selectedPlan===p.code?'Selecionado':'Selecionar'}</button>
      </div>)}
    </section>

    <section className="glass premium-border rounded-[2rem] p-6">
      <div className="flex items-center gap-2 mb-4"><Sparkles/><h3 className="text-xl font-black">Assinar plano selecionado {selected?.name ? `— ${selected.name}` : ''}</h3></div>
      {!providerConfigured && <div className="mb-4 rounded-2xl bg-amber-400/10 border border-amber-300/20 p-4 text-sm text-amber-100">Pagar.me não está configurado neste ambiente. A tela continua funcional, mas a criação real de assinatura exige PAGARME_API_KEY.</div>}
      <div className="grid md:grid-cols-4 gap-3">
        <input className="input" placeholder="Nome" value={customer.name} onChange={e=>setCustomer({...customer,name:e.target.value})}/>
        <input className="input" placeholder="E-mail" value={customer.email} onChange={e=>setCustomer({...customer,email:e.target.value})}/>
        <input className="input" placeholder="CPF/CNPJ" value={customer.document} onChange={e=>setCustomer({...customer,document:e.target.value})}/>
        <input className="input" placeholder="Telefone" value={customer.phone} onChange={e=>setCustomer({...customer,phone:e.target.value})}/>
      </div>
      <button onClick={subscribe} disabled={busy} className="btn btn-primary mt-5"><CreditCard size={18}/> Criar assinatura</button>
      <p className="text-xs text-slate-500 mt-3">Não insira dados de cartão nesta tela. Use checkout/tokenização segura do Pagar.me para cobrança real.</p>
    </section>
  </div>;
}
