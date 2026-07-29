import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Page from '../components/animations/Page';
import { Card } from '../components/ui/Card';
import { getSettings, me, saveSettings } from '../api/client';
import { useToast } from '../components/ui/Toast';
import { useEffect, useState } from 'react';

export default function Settings() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const { data: user } = useQuery({ queryKey: ['me'], queryFn: me });
  const { data } = useQuery({ queryKey: ['settings'], queryFn: getSettings });
  const [form, setForm] = useState<any>({});
  useEffect(() => { if (data) setForm(data); }, [data]);
  const save = useMutation({ mutationFn: saveSettings, onSuccess: () => { qc.invalidateQueries({ queryKey: ['settings'] }); toast('Configurações salvas com sucesso.', 'success'); }, onError: () => toast('Não foi possível salvar as configurações.', 'error') });
  const update = (path:string, value:any) => {
    const [a,b] = path.split('.');
    setForm((f:any)=> b ? ({...f, [a]: {...(f[a]||{}), [b]: value}}) : ({...f, [a]: value}));
  };
  return <Page>
    <div className="flex flex-wrap justify-between gap-3 mb-4"><div><h2 className="text-3xl font-black">Configurações SaaS</h2><p className="text-slate-400">Perfil da empresa, margem, comissão, impostos, alertas, modo operacional e credenciais.</p></div><button className="btn btn-primary" disabled={save.isPending} onClick={()=>save.mutate(form)}>{save.isPending?'Salvando...':'Salvar configurações'}</button></div>
    <div className="grid lg:grid-cols-3 gap-4">
      <Card><p className="text-slate-400">Usuário</p><b className="text-xl">{user?.nome || 'Carregando...'}</b><p className="text-slate-400">{user?.email}</p></Card>
      <Card><p className="text-slate-400">Tenant</p><b className="text-xl break-all">{user?.tenant_id}</b></Card>
      <Card><p className="text-slate-400">Modo</p><b className="text-xl">{form?.mode || 'demo'}</b><p className="text-slate-400">Verificação de e-mail desabilitada</p></Card>
    </div>
    <div className="grid lg:grid-cols-2 gap-4 mt-4">
      <Card><b>Perfil da empresa</b><div className="grid gap-3 mt-3"><input className="input" placeholder="Nome da empresa" value={form.company_profile?.name || ''} onChange={e=>update('company_profile.name', e.target.value)} /><input className="input" placeholder="Segmento" value={form.company_profile?.segment || ''} onChange={e=>update('company_profile.segment', e.target.value)} /></div></Card>
      <Card><b>Regras de margem</b><div className="grid md:grid-cols-2 gap-3 mt-3"><input className="input" type="number" placeholder="Margem mínima %" value={form.margin_rules?.minimum_margin_pct || 0} onChange={e=>update('margin_rules.minimum_margin_pct', Number(e.target.value))} /><input className="input" type="number" placeholder="Margem alvo %" value={form.margin_rules?.target_margin_pct || 0} onChange={e=>update('margin_rules.target_margin_pct', Number(e.target.value))} /></div></Card>
      <Card><b>Comissão e impostos</b><div className="grid md:grid-cols-2 gap-3 mt-3"><input className="input" type="number" value={form.default_commission_pct || 0} onChange={e=>update('default_commission_pct', Number(e.target.value))} /><input className="input" type="number" value={form.default_tax_pct || 0} onChange={e=>update('default_tax_pct', Number(e.target.value))} /></div></Card>
      <Card><b>Marketplace e alertas</b><p className="text-slate-400 mt-2">Mercado Livre: {form.marketplace_credentials?.mercadolivre || 'not_configured'}</p><p className="text-slate-400">Alertas: margem, falha de job e concorrente agressivo ativos na demo.</p></Card>
    </div>
    <Card className="mt-4"><b>Política de preço</b><textarea className="input mt-3" value={form.pricing_policy || ''} onChange={e=>update('pricing_policy', e.target.value)} /><p className="text-slate-400 mt-2">Nenhuma credencial real deve ser versionada. Use .env para produção.</p></Card>
  </Page>;
}
