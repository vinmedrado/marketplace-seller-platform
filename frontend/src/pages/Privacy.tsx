import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Page from '../components/animations/Page';
import { Card } from '../components/ui/Card';
import { createPrivacyRequest, privacyExport, privacyNotice, privacyRequests } from '../api/client';
import { useToast } from '../components/ui/Toast';
import { useState } from 'react';

const requestTypes = [
  ['access', 'Confirmação e acesso'],
  ['correction', 'Correção'],
  ['deletion', 'Eliminação'],
  ['anonymization', 'Anonimização ou bloqueio'],
  ['portability', 'Portabilidade'],
  ['revocation', 'Revogação de consentimento'],
  ['review', 'Revisão de decisão automatizada'],
] as const;

export default function Privacy() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [requestType, setRequestType] = useState('access');
  const [description, setDescription] = useState('');
  const { data: notice } = useQuery({ queryKey: ['privacy-notice'], queryFn: privacyNotice });
  const { data: requests } = useQuery({ queryKey: ['privacy-requests'], queryFn: privacyRequests });
  const create = useMutation({
    mutationFn: createPrivacyRequest,
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ['privacy-requests'] });
      setDescription('');
      toast(`Solicitação registrada: ${result.protocol}`, 'success');
    },
    onError: () => toast('Não foi possível registrar a solicitação.', 'error'),
  });

  const downloadExport = async () => {
    try {
      const payload = await privacyExport();
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'marketplace-seller-platform-meus-dados.json';
      anchor.click();
      URL.revokeObjectURL(url);
      toast('Exportação gerada no seu dispositivo.', 'success');
    } catch {
      toast('Não foi possível gerar a exportação.', 'error');
    }
  };

  return <Page>
    <div className="flex flex-wrap justify-between gap-3 mb-4">
      <div><h2 className="text-3xl font-black">Privacidade e LGPD</h2><p className="text-slate-400">Transparência, controle e protocolos para exercício dos direitos do titular.</p></div>
      <button className="btn btn-primary" onClick={downloadExport}>Exportar meus dados</button>
    </div>
    <div className="grid xl:grid-cols-2 gap-4">
      <Card>
        <p className="text-xs uppercase tracking-widest text-sky-300 font-bold">Aviso de privacidade</p>
        <h3 className="text-xl font-black mt-2">O que é tratado</h3>
        <ul className="mt-3 grid gap-2 text-slate-300 list-disc pl-5">
          {notice?.data_categories?.map((item: string) => <li key={item}>{item}</li>)}
        </ul>
        <p className="text-sm text-slate-400 mt-4">Contato: {notice?.contact || 'não configurado'}</p>
        <p className="text-sm text-slate-400 mt-2">{notice?.automated_decisions}</p>
      </Card>
      <Card>
        <p className="text-xs uppercase tracking-widest text-violet-300 font-bold">Exercer um direito</p>
        <div className="grid gap-3 mt-3">
          <select className="input" value={requestType} onChange={(event) => setRequestType(event.target.value)}>
            {requestTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <textarea className="input min-h-28" maxLength={1000} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Contexto opcional da solicitação" />
          <button className="btn btn-primary" disabled={create.isPending} onClick={() => create.mutate({ request_type: requestType, description })}>{create.isPending ? 'Registrando...' : 'Gerar protocolo'}</button>
        </div>
      </Card>
    </div>
    <Card className="mt-4">
      <h3 className="text-xl font-black">Meus protocolos</h3>
      <div className="overflow-x-auto mt-3"><table className="w-full text-left">
        <thead><tr className="text-slate-400"><th className="p-3">Protocolo</th><th className="p-3">Direito</th><th className="p-3">Status</th><th className="p-3">Prazo informado</th></tr></thead>
        <tbody>{requests?.items?.map((item: any) => <tr key={item.protocol} className="border-t border-white/10"><td className="p-3 break-all">{item.protocol}</td><td className="p-3">{item.type_label}</td><td className="p-3">{item.status}</td><td className="p-3">{new Date(item.deadline_at).toLocaleDateString('pt-BR')}</td></tr>)}</tbody>
      </table></div>
      {!requests?.items?.length && <p className="text-slate-400 mt-3">Nenhuma solicitação registrada.</p>}
    </Card>
  </Page>;
}
