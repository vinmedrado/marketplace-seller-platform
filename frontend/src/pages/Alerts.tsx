import { useEffect, useMemo, useState } from 'react';
import { BellRing, CheckCircle2, MessageCircle, Send, ShieldAlert, Smartphone, WifiOff } from 'lucide-react';
import { alertsHistory, alertsSettings, alertsTest, saveAlertsSettings } from '../api/client';

const ALERT_TYPES = [
  ['LOW_STOCK', 'Estoque baixo'],
  ['OUT_OF_STOCK', 'Sem estoque'],
  ['ACCOUNT_HEALTH_RISK', 'Conta em risco'],
  ['BUYBOX_RISK', 'Risco Buy Box'],
  ['BUYBOX_OPPORTUNITY', 'Oportunidade Buy Box'],
  ['QUESTION_PENDING_TOO_LONG', 'Pergunta > 2h'],
  ['PRICE_RISK', 'Risco de preço'],
  ['SYNC_ERROR', 'Erro de sync'],
] as const;

const severities = ['info', 'warning', 'critical'] as const;

function Badge({ children, tone = 'slate' }: { children: any; tone?: 'green'|'red'|'yellow'|'slate'|'blue' }) {
  const cls = tone === 'green' ? 'text-emerald-200 bg-emerald-400/10 border-emerald-300/20' : tone === 'red' ? 'text-rose-200 bg-rose-400/10 border-rose-300/20' : tone === 'yellow' ? 'text-amber-200 bg-amber-400/10 border-amber-300/20' : tone === 'blue' ? 'text-sky-200 bg-sky-400/10 border-sky-300/20' : 'text-slate-200 bg-white/10 border-white/10';
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-bold ${cls}`}>{children}</span>;
}

export default function Alerts() {
  const [settings, setSettings] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<string>('');
  const provider = useMemo(() => settings?.providers || {}, [settings]);

  async function load() {
    setLoading(true);
    try {
      const [s, h] = await Promise.all([alertsSettings(), alertsHistory()]);
      setSettings(s);
      setHistory(h.items || []);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function patch(next: any) { setSettings((prev: any) => ({ ...(prev || {}), ...next })); }

  async function save() {
    setSaving(true);
    try {
      const updated = await saveAlertsSettings(settings);
      setSettings(updated);
      await load();
    } finally { setSaving(false); }
  }

  async function test() {
    setSaving(true);
    setTestResult('');
    try {
      const result = await alertsTest();
      setTestResult(result.sent ? 'Alerta teste enviado para pelo menos um canal.' : (result.reason || 'Nenhum canal enviou o alerta.'));
      await load();
    } finally { setSaving(false); }
  }

  const enabledTypes = settings?.enabled_alert_types || [];
  const toggleType = (type: string) => {
    const set = new Set(enabledTypes);
    if (set.has(type)) set.delete(type);
    else set.add(type);
    patch({ enabled_alert_types: Array.from(set) });
  };

  if (loading) return <div className="glass premium-border rounded-[2rem] p-8 text-slate-300">Carregando configurações de alertas...</div>;

  return <div className="space-y-6">
    <section className="glass premium-border rounded-[2rem] p-6">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <p className="text-sm text-sky-200 font-bold flex items-center gap-2"><BellRing size={18}/> Alertas operacionais</p>
          <h2 className="text-3xl font-black mt-1">Telegram/WhatsApp para eventos críticos</h2>
          <p className="text-slate-300 mt-2 max-w-3xl">Telegram é gratuito e recomendado. WhatsApp depende da Evolution API configurada no backend. Alertas são deduplicados para evitar spam.</p>
        </div>
        <button onClick={test} disabled={saving} className="btn btn-primary flex items-center gap-2"><Send size={18}/> Enviar alerta teste</button>
      </div>
      {testResult && <div className="mt-4 rounded-2xl bg-white/10 border border-white/10 p-4 text-sm text-slate-200">{testResult}</div>}
    </section>

    <section className="grid lg:grid-cols-2 gap-5">
      <div className="glass premium-border rounded-[2rem] p-6 space-y-4">
        <div className="flex items-center justify-between"><h3 className="text-xl font-black flex items-center gap-2"><MessageCircle/> Telegram</h3>{provider.telegram?.configured ? <Badge tone="green">Provider configurado</Badge> : <Badge tone="yellow">Token pendente</Badge>}</div>
        <label className="flex items-center gap-3 text-sm"><input type="checkbox" checked={!!settings?.telegram_enabled} onChange={e=>patch({telegram_enabled:e.target.checked})}/> Ativar Telegram</label>
        <input className="input w-full" placeholder="Telegram chat ID" value={settings?.telegram_chat_id || ''} onChange={e=>patch({telegram_chat_id:e.target.value})}/>
        <p className="text-xs text-slate-400">O token do bot fica apenas no backend via TELEGRAM_BOT_TOKEN. O chat ID é salvo por tenant.</p>
      </div>
      <div className="glass premium-border rounded-[2rem] p-6 space-y-4">
        <div className="flex items-center justify-between"><h3 className="text-xl font-black flex items-center gap-2"><Smartphone/> WhatsApp</h3>{provider.whatsapp?.configured ? <Badge tone="green">Evolution configurada</Badge> : <Badge tone="yellow">Indisponível</Badge>}</div>
        <label className="flex items-center gap-3 text-sm"><input type="checkbox" checked={!!settings?.whatsapp_enabled} onChange={e=>patch({whatsapp_enabled:e.target.checked})}/> Ativar WhatsApp</label>
        <input className="input w-full" placeholder="Telefone com DDI/DDD" value={settings?.whatsapp_phone || ''} onChange={e=>patch({whatsapp_phone:e.target.value})}/>
        <p className="text-xs text-slate-400">Depende de EVOLUTION_API_URL, EVOLUTION_API_KEY e EVOLUTION_INSTANCE no ambiente.</p>
      </div>
    </section>

    <section className="glass premium-border rounded-[2rem] p-6 space-y-5">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div><h3 className="text-xl font-black">Preferências</h3><p className="text-slate-400 text-sm">Defina severidade mínima, tipos de alerta e janela silenciosa.</p></div>
        <button onClick={save} disabled={saving} className="btn btn-primary"><CheckCircle2 size={18}/> Salvar configurações</button>
      </div>
      <div className="grid md:grid-cols-3 gap-4">
        <label className="space-y-2 text-sm"><span className="text-slate-300">Severidade mínima</span><select className="input w-full" value={settings?.min_severity || 'warning'} onChange={e=>patch({min_severity:e.target.value})}>{severities.map(s=><option key={s} value={s}>{s}</option>)}</select></label>
        <label className="space-y-2 text-sm"><span className="text-slate-300">Quiet hours início</span><input className="input w-full" placeholder="22:00" value={settings?.quiet_hours_start || ''} onChange={e=>patch({quiet_hours_start:e.target.value})}/></label>
        <label className="space-y-2 text-sm"><span className="text-slate-300">Quiet hours fim</span><input className="input w-full" placeholder="07:00" value={settings?.quiet_hours_end || ''} onChange={e=>patch({quiet_hours_end:e.target.value})}/></label>
      </div>
      <div className="flex flex-wrap gap-2">{ALERT_TYPES.map(([type,label])=><button key={type} onClick={()=>toggleType(type)} className={`rounded-full border px-3 py-2 text-xs font-bold ${enabledTypes.includes(type) ? 'bg-sky-400/15 border-sky-300/30 text-sky-100' : 'bg-white/5 border-white/10 text-slate-400'}`}>{label}</button>)}</div>
    </section>

    <section className="glass premium-border rounded-[2rem] p-6">
      <div className="flex items-center justify-between mb-4"><h3 className="text-xl font-black">Histórico de alertas</h3><Badge tone="blue">{history.length} recentes</Badge></div>
      {!history.length ? <div className="rounded-3xl border border-dashed border-white/15 p-8 text-center text-slate-400"><WifiOff className="mx-auto mb-3"/> Nenhum alerta enviado ainda.</div> : <div className="overflow-x-auto"><table className="w-full text-sm"><thead className="text-slate-400"><tr><th className="text-left p-3">Data</th><th className="text-left p-3">Tipo</th><th className="text-left p-3">Severidade</th><th className="text-left p-3">Canal</th><th className="text-left p-3">Status</th><th className="text-left p-3">Mensagem</th></tr></thead><tbody>{history.map((h:any)=><tr key={h.id} className="border-t border-white/10"><td className="p-3 text-slate-300">{h.created_at?.slice(0,16).replace('T',' ')}</td><td className="p-3 font-bold">{h.alert_type}</td><td className="p-3"><Badge tone={h.severity==='critical'?'red':h.severity==='warning'?'yellow':'blue'}>{h.severity}</Badge></td><td className="p-3">{h.provider}</td><td className="p-3"><Badge tone={h.status==='sent'?'green':h.status==='failed'?'red':'slate'}>{h.status}</Badge></td><td className="p-3 text-slate-400 max-w-lg truncate">{h.title || h.message}</td></tr>)}</tbody></table></div>}
      <p className="text-xs text-slate-500 mt-4 flex items-center gap-2"><ShieldAlert size={14}/> Tokens e chaves de providers nunca são expostos nesta tela.</p>
    </section>
  </div>;
}
