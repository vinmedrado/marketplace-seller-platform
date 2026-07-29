import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import Page from '../components/animations/Page';
import { Card } from '../components/ui/Card';
import { EmptyState } from '../components/ui/EmptyState';
import { Pagination, usePagination } from '../components/ui/Pagination';
import { money, products, publishDryRun, publishHistory, publishPreview } from '../api/client';
import { useToast } from '../components/ui/Toast';

export default function Publish() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [pid, setPid] = useState('');
  const [showPayload, setShowPayload] = useState(false);
  const [page, setPage] = useState(1);
  const { data: ps = [] } = useQuery({ queryKey: ['products'], queryFn: products });
  const selected = pid || ps[0]?.id;
  const { data: preview } = useQuery({ queryKey: ['publish-preview', selected], queryFn: () => publishPreview(selected), enabled: !!selected });
  const { data: hist = [] } = useQuery({ queryKey: ['publish-history'], queryFn: publishHistory });
  const pub = useMutation({ mutationFn: () => publishDryRun(selected), onSuccess: () => { qc.invalidateQueries({ queryKey: ['publish-history'] }); toast('Dry-run de publicação gerado com sucesso.', 'success'); }, onError: () => toast('Falha ao gerar publicação dry-run.', 'error') });
  const last = pub.data;
  const paginated = usePagination(hist, page, 6);
  return <Page>
    <div className="flex flex-wrap justify-between items-center gap-3 mb-4"><div><h2 className="text-3xl font-black">Publicação Dry-run</h2><p className="text-slate-400">Checklist, preview do anúncio, riscos, payload técnico e simulação segura.</p></div><button className="btn btn-primary" disabled={!selected || pub.isPending} onClick={() => pub.mutate()}>{pub.isPending ? 'Enviando...' : 'Simular publicação'}</button></div>
    <select className="input mb-4" value={pid} onChange={e => setPid(e.target.value)}><option value="">Selecione ou use primeiro produto</option>{ps.map((p: any) => <option key={p.id} value={p.id}>{p.sku} · {p.titulo}</option>)}</select>
    <div className="grid lg:grid-cols-3 gap-4 mb-4"><Card><b>Checklist antes de publicar</b><div className="mt-3 space-y-2">{preview?.checklist?.map((c:any)=><div key={c.label} className="flex justify-between gap-2 rounded-2xl bg-white/10 p-3"><span>{c.label}</span><span className="status-badge">{c.ok?'OK':'Risco'}</span></div>)}</div></Card><Card><b>Preview do anúncio</b><p className="text-2xl font-black mt-3">{preview?.preview?.title || 'Selecione um produto'}</p><p className="text-sky-200 mt-2">{money(preview?.preview?.price)} · estoque {preview?.preview?.stock || 0}</p><p className="text-slate-400">Categoria: {preview?.preview?.category || '-'}</p></Card><Card><b>Riscos e recomendações</b><p className="text-slate-300 mt-3">{preview?.risks?.length ? preview.risks.join(', ') : 'Sem riscos críticos.'}</p><p className="text-sky-200 mt-3">{preview?.recommendations?.[0]}</p><button className="btn btn-ghost mt-4" onClick={()=>setShowPayload(!showPayload)}>{showPayload?'Ocultar payload':'Ver payload técnico'}</button></Card></div>
    {showPayload && <Card className="mb-4"><b>Payload técnico opcional</b><pre className="mt-3 text-xs overflow-auto text-slate-300">{JSON.stringify(preview?.technical_payload, null, 2)}</pre></Card>}
    {last && <div className="grid md:grid-cols-3 gap-4 mb-4"><Card><p className="text-slate-400">Status</p><b className="text-2xl">{last.status}</b></Card><Card><p className="text-slate-400">Preço</p><b className="text-2xl">{money(last.preco)}</b></Card><Card><p className="text-slate-400">Dry-run</p><b className="text-2xl">{String(last.dry_run)}</b></Card></div>}
    <Card><b>Histórico de publicação</b>{hist.length ? <><div className="mt-4 space-y-3">{paginated.items.map((h: any) => <details key={h.id} className="rounded-2xl bg-white/10 p-3 border border-white/10"><summary className="cursor-pointer flex justify-between gap-3"><span>{h.status} · {new Date(h.criado_em).toLocaleString('pt-BR')}</span><span>{h.duracao_ms || 0}ms</span></summary><pre className="mt-3 text-xs overflow-auto text-slate-300">{JSON.stringify(h.payload || h.resposta || h.erro, null, 2)}</pre></details>)}</div><Pagination page={paginated.page} totalPages={paginated.totalPages} onPage={setPage}/></> : <div className="mt-4"><EmptyState title="Sem publicações dry-run" description="Simule uma publicação para criar histórico, payload e logs amigáveis." /></div>}</Card>
  </Page>;
}
