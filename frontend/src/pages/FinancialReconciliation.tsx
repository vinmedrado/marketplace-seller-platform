import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Banknote, Calendar, CheckCircle2, FileText, RefreshCw, Save, ShieldAlert } from 'lucide-react';
import { financialReconciliation, saveManualBankReceived, money } from '../api/client';

function Badge({ children, tone='slate' }: { children:any; tone?: 'green'|'yellow'|'red'|'blue'|'slate' }) {
  const cls = tone==='green'?'bg-emerald-400/10 text-emerald-200 border-emerald-300/20':tone==='yellow'?'bg-amber-400/10 text-amber-200 border-amber-300/20':tone==='red'?'bg-rose-400/10 text-rose-200 border-rose-300/20':tone==='blue'?'bg-sky-400/10 text-sky-200 border-sky-300/20':'bg-white/10 text-slate-200 border-white/10';
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-bold ${cls}`}>{children}</span>;
}
function Card({ label, value, hint, tone='slate' }: { label:string; value:any; hint?:string; tone?:'green'|'yellow'|'red'|'blue'|'slate' }) {
  return <div className="rounded-3xl bg-white/[0.06] border border-white/10 p-5"><p className="text-sm text-slate-400">{label}</p><p className={`text-2xl font-black mt-1 ${tone==='red'?'text-rose-200':tone==='green'?'text-emerald-200':tone==='yellow'?'text-amber-200':'text-white'}`}>{value}</p>{hint&&<p className="text-xs text-slate-400 mt-2">{hint}</p>}</div>;
}
function todayOffset(days:number){ const d=new Date(); d.setDate(d.getDate()+days); return d.toISOString().slice(0,10); }

export default function FinancialReconciliation(){
  const [startDate,setStartDate]=useState(todayOffset(-30));
  const [endDate,setEndDate]=useState(todayOffset(0));
  const [data,setData]=useState<any>(null);
  const [bank,setBank]=useState('');
  const [loading,setLoading]=useState(false);
  const [message,setMessage]=useState('');

  const load=useCallback(async()=>{ setLoading(true); setMessage(''); try{ const r=await financialReconciliation(startDate,endDate); setData(r); if(r?.summary?.bank_received_amount!=null) setBank(String(r.summary.bank_received_amount)); } catch(err:any){ setMessage(err?.response?.data?.detail?.message||err.message||'Erro ao gerar reconciliação.'); } finally{ setLoading(false); } },[startDate,endDate]);
  async function saveBank(){ setLoading(true); setMessage(''); try{ const r=await saveManualBankReceived({start_date:startDate,end_date:endDate,bank_received_amount:Number(bank)}); setMessage(r?.message||'Valor salvo.'); await load(); } catch(err:any){ setMessage(err?.response?.data?.detail?.message||err.message||'Erro ao salvar valor recebido.'); } finally{ setLoading(false); } }
  useEffect(()=>{ void load(); },[load]);

  const s=data?.summary||{}; const dq=useMemo(()=>data?.data_quality||{},[data?.data_quality]); const alerts=data?.alerts||[]; const dre=data?.dre||[];
  const qualityTone = dq.status==='complete'?'green':dq.status==='partial'?'yellow':'red';
  const diffTone = s.reconciliation_difference==null?'slate':Math.abs(Number(s.reconciliation_difference))<10?'green':Math.abs(Number(s.reconciliation_difference))<100?'yellow':'red';
  const notes = useMemo(()=>[...(dq.notes||[]), ...(dq.missing_fields?.length?[`Campos ausentes: ${dq.missing_fields.join(', ')}`]:[])], [dq]);

  return <div className="space-y-6">
    <section className="glass premium-border rounded-[2rem] p-6">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
        <div><p className="text-sm text-sky-200 font-bold flex items-center gap-2"><Banknote size={18}/> Reconciliação Financeira Mercado Livre</p><h2 className="text-3xl font-black mt-1">DRE operacional e conferência de repasses</h2><p className="text-slate-300 mt-2 max-w-3xl">Cruza pedidos, pagamentos, taxas, devoluções e valor recebido informado manualmente. Não há integração bancária automática neste MVP.</p></div>
        <div className="flex flex-wrap gap-2"><Badge tone={qualityTone as any}>Qualidade: {dq.status||'—'}</Badge><Badge tone="blue">Período {data?.period?.start_date||startDate} → {data?.period?.end_date||endDate}</Badge></div>
      </div>
      <div className="grid md:grid-cols-5 gap-3 mt-5">
        <label className="text-sm text-slate-300"><span className="flex gap-2 items-center mb-1"><Calendar size={15}/> Data inicial</span><input className="input" type="date" value={startDate} onChange={e=>setStartDate(e.target.value)}/></label>
        <label className="text-sm text-slate-300"><span className="flex gap-2 items-center mb-1"><Calendar size={15}/> Data final</span><input className="input" type="date" value={endDate} onChange={e=>setEndDate(e.target.value)}/></label>
        <button onClick={load} disabled={loading} className="btn btn-primary mt-6"><RefreshCw size={17}/> Gerar reconciliação</button>
      </div>
      {message && <div className="mt-4 rounded-2xl bg-white/10 border border-white/10 p-4 text-sm text-slate-200">{message}</div>}
    </section>

    <section className="grid md:grid-cols-5 gap-4">
      <Card label="Receita bruta" value={s.gross_revenue==null?'—':money(s.gross_revenue)} tone="green" hint={`${s.orders_count||0} pedidos`} />
      <Card label="Taxas ML" value={s.ml_fees==null?'—':money(s.ml_fees)} tone="yellow" />
      <Card label="Devoluções/estornos" value={money((Number(s.refunds_amount||0)+Number(s.chargebacks_amount||0)))} tone="red" />
      <Card label="Receita líquida" value={s.net_revenue==null?'—':money(s.net_revenue)} tone="blue" />
      <Card label="Diferença" value={s.reconciliation_difference==null?'—':money(s.reconciliation_difference)} tone={diffTone as any} hint="Banco informado - líquido ML" />
    </section>

    <section className="grid xl:grid-cols-2 gap-5">
      <div className="glass premium-border rounded-[2rem] p-6">
        <h3 className="text-xl font-black flex items-center gap-2"><FileText/> DRE simplificado</h3>
        <div className="mt-5 space-y-3">
          {dre.map((r:any)=><div key={r.label} className="flex items-center justify-between rounded-2xl bg-white/[0.05] border border-white/10 p-4"><span className="text-slate-300">{r.label}</span><b className={r.type==='negative'?'text-rose-200':r.type==='positive'?'text-emerald-200':'text-sky-200'}>{r.amount==null?'—':money(r.amount)}</b></div>)}
        </div>
      </div>
      <div className="glass premium-border rounded-[2rem] p-6">
        <h3 className="text-xl font-black flex items-center gap-2"><Save/> Valor recebido no banco</h3>
        <p className="text-sm text-slate-400 mt-2">Campo manual para comparar o que o Mercado Livre indica como líquido com o que você recebeu. Não salva dado bancário sensível.</p>
        <div className="flex flex-col md:flex-row gap-3 mt-5"><input className="input" type="number" min="0" step="0.01" placeholder="Ex.: 1250.50" value={bank} onChange={e=>setBank(e.target.value)}/><button onClick={saveBank} disabled={loading || !bank} className="btn btn-primary"><Save size={17}/> Salvar/comparar</button></div>
        <div className="mt-5 grid md:grid-cols-2 gap-3"><Card label="Recebido informado" value={s.bank_received_amount==null?'—':money(s.bank_received_amount)} /><Card label="Diferença calculada" value={s.reconciliation_difference==null?'—':money(s.reconciliation_difference)} tone={diffTone as any}/></div>
      </div>
    </section>

    <section className="grid xl:grid-cols-2 gap-5">
      <div className="glass premium-border rounded-[2rem] p-6">
        <h3 className="text-xl font-black flex items-center gap-2"><ShieldAlert/> Alertas financeiros</h3>
        <div className="mt-5 space-y-3">{alerts.length===0?<div className="rounded-2xl bg-white/[0.05] border border-white/10 p-5 text-slate-300">Nenhum alerta financeiro relevante para o período.</div>:alerts.map((a:any)=><div key={a.type} className="rounded-2xl bg-white/[0.05] border border-white/10 p-4"><div className="flex items-center justify-between gap-3"><b className="text-white">{a.title}</b><Badge tone={a.severity==='critical'?'red':a.severity==='warning'?'yellow':'blue'}>{a.severity}</Badge></div><p className="text-sm text-slate-300 mt-2">{a.description}</p><p className="text-xs text-slate-400 mt-2">Ação: {a.recommended_action}</p></div>)}</div>
      </div>
      <div className="glass premium-border rounded-[2rem] p-6">
        <h3 className="text-xl font-black flex items-center gap-2"><CheckCircle2/> Qualidade dos dados</h3>
        <div className="mt-5 rounded-2xl bg-white/[0.05] border border-white/10 p-5"><Badge tone={qualityTone as any}>{dq.status||'—'}</Badge><p className="text-sm text-slate-300 mt-3">A reconciliação usa somente campos retornados pela API do Mercado Livre. Campos ausentes ficam nulos para não criar números falsos.</p>{notes.length>0&&<ul className="mt-4 space-y-2 text-sm text-slate-400">{notes.map((n:string,i:number)=><li key={i} className="flex gap-2"><AlertTriangle size={15} className="text-amber-300 shrink-0"/> {n}</li>)}</ul>}</div>
      </div>
    </section>
  </div>;
}
