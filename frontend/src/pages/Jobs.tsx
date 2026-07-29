import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Page from '../components/animations/Page';
import { Card } from '../components/ui/Card';
import { EmptyState } from '../components/ui/EmptyState';
import { Pagination, usePagination } from '../components/ui/Pagination';
import { createJob, jobs } from '../api/client';
import { useToast } from '../components/ui/Toast';
import { useState } from 'react';

export default function Jobs() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [page, setPage] = useState(1);
  const { data = [] } = useQuery({ queryKey: ['jobs'], queryFn: jobs, refetchInterval: 2000 });
  const paginated = usePagination(data, page, 6);
  const run = useMutation({ mutationFn: (t: string) => createJob(t, {}), onSuccess: () => { qc.invalidateQueries({ queryKey: ['jobs'] }); toast('Job iniciado em background.', 'success'); }, onError: () => toast('Não foi possível iniciar o job.', 'error') });
  return <Page>
    <div className="flex flex-wrap justify-between items-center gap-3 mb-4"><div><h2 className="text-3xl font-black">Jobs / Automação</h2><p className="text-slate-400">Execução assíncrona com polling, progresso e logs.</p></div><div className="flex gap-2 flex-wrap">{['scraping', 'pricing', 'publish', 'ml-train'].map(t => <button key={t} disabled={run.isPending} onClick={() => run.mutate(t)} className="btn btn-ghost">{run.isPending ? 'Iniciando...' : t}</button>)}</div></div>
    <div className="space-y-3">{data.length ? paginated.items.map((j: any) => <Card key={j.id}><div className="flex justify-between mb-2"><b>{j.job_type}</b><span className="status-badge">{j.status}</span></div><div className="h-3 bg-white/10 rounded-full overflow-hidden"><div className="h-full bg-gradient-to-r from-sky-300 to-violet-400 transition-all" style={{ width: `${Math.min(100, Number(j.progress_current || 0))}%` }} /></div><p className="text-slate-400 mt-2">{j.progress_label} · {j.duration_seconds || 0}s</p><pre className="text-xs mt-3 whitespace-pre-wrap text-slate-400 max-h-32 overflow-auto">{j.stdout_tail}</pre>{j.error_message && <p className="text-red-300 mt-2">{j.error_message}</p>}</Card>) : <Card><EmptyState title="Nenhum job executado" description="Inicie scraping, pricing, publish ou ML para validar o executor em background." /></Card>}</div>
    <Pagination page={paginated.page} totalPages={paginated.totalPages} onPage={setPage}/>
  </Page>;
}
