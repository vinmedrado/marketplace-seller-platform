import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Page from '../components/animations/Page';
import { Card, Skeleton } from '../components/ui/Card';
import { answerQuestion, pendingQuestions, suggestQuestionAnswer } from '../api/client';

function fmtDate(v?: string | null) {
  return v ? new Date(v).toLocaleString('pt-BR') : '—';
}

function providerLabel(q: any) {
  if (q?.ai_available) return 'IA real';
  return 'Fallback seguro';
}

function confidenceLabel(v?: number) {
  if (v === undefined || v === null) return '—';
  return `${Math.round(Number(v) * 100)}% confiança`;
}

export default function Questions() {
  const qc = useQueryClient();
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [customContext, setCustomContext] = useState<Record<string, string>>({});
  const { data, isLoading, error } = useQuery({ queryKey: ['questions-pending'], queryFn: () => pendingQuestions(), refetchInterval: 45000, retry: 1 });

  const suggest = useMutation({
    mutationFn: ({ id, context }: { id: string; context?: string }) => suggestQuestionAnswer(id, context),
    onSuccess: (res: any) => {
      setEdits(prev => ({ ...prev, [res.id]: res.suggested_answer || '' }));
      qc.invalidateQueries({ queryKey: ['questions-pending'] });
    },
  });

  const send = useMutation({
    mutationFn: ({ id, text }: { id: string; text: string }) => answerQuestion(id, text),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['questions-pending'] }),
  });

  const questions = data?.questions || [];

  return <Page>
    <div className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-white/[0.06] p-8 mb-5 glow-soft">
      <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-violet-400/20 blur-3xl" />
      <div className="relative z-10 max-w-4xl">
        <span className="status-badge text-violet-200">Mercado Livre · atendimento assistido</span>
        <h2 className="text-4xl font-black mt-4">Perguntas ML com IA</h2>
        <p className="text-slate-300 mt-3 text-lg">Liste perguntas abertas reais, gere sugestões seguras e envie somente após revisar e aprovar.</p>
        <p className="text-amber-200 mt-2 text-sm">As respostas são sugestões. Revise antes de enviar ao cliente.</p>
      </div>
    </div>

    <div className="grid lg:grid-cols-4 gap-4 mb-5">
      <Card><p className="text-slate-400">Perguntas abertas</p><b className="text-3xl">{data?.total ?? 0}</b></Card>
      <Card><p className="text-slate-400">IA real</p><b className="text-3xl">{questions.filter((q:any)=>q.ai_available).length}</b></Card>
      <Card><p className="text-slate-400">Fallback seguro</p><b className="text-3xl">{questions.filter((q:any)=>!q.ai_available).length}</b></Card>
      <Card><p className="text-slate-400">Atualizado em</p><b>{fmtDate(data?.generated_at)}</b></Card>
    </div>

    {isLoading && <Skeleton className="h-96" />}
    {error && <Card><p className="text-red-200">Não foi possível buscar perguntas. Verifique se o seller Mercado Livre está conectado e se o token está válido.</p></Card>}

    {!isLoading && !error && questions.length === 0 && <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-8 text-center">
      <h3 className="text-xl font-black">Nenhuma pergunta aberta no momento.</h3>
      <p className="text-slate-400 mt-2">Quando compradores enviarem perguntas em anúncios conectados, elas aparecerão aqui para revisão e resposta assistida.</p>
    </div>}

    <div className="space-y-4">
      {questions.map((q:any) => {
        const text = edits[q.id] ?? q.suggested_answer ?? '';
        const isSending = send.isPending;
        return <Card key={q.id} className="overflow-hidden">
          <div className="grid xl:grid-cols-[96px_1fr_420px] gap-4">
            <div>{q.item_thumbnail ? <img src={q.item_thumbnail} className="w-24 h-24 rounded-3xl object-cover bg-white/10"/> : <div className="w-24 h-24 rounded-3xl bg-white/10"/>}</div>
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className="status-badge">{providerLabel(q)}</span>
                <span className="status-badge">{confidenceLabel(q.confidence)}</span>
                <span className="status-badge">{q.status || 'UNANSWERED'}</span>
              </div>
              <a className="text-lg font-black hover:underline" href={q.item_permalink || '#'} target="_blank" rel="noreferrer">{q.item_title || q.item_id || 'Produto Mercado Livre'}</a>
              <p className="text-xs text-slate-500 mt-1">Pergunta {q.id} · criada em {fmtDate(q.created_at)}</p>
              <div className="rounded-2xl bg-white/[0.06] border border-white/10 p-4 mt-4">
                <p className="text-xs text-slate-400 font-bold mb-1">Pergunta do comprador</p>
                <p className="text-slate-100">{q.question_text}</p>
              </div>
              <label className="block mt-4">
                <span className="text-xs text-slate-400">Contexto opcional para regenerar sugestão</span>
                <input className="input mt-2" value={customContext[q.id] || ''} onChange={e=>setCustomContext(prev=>({...prev,[q.id]:e.target.value}))} placeholder="Ex.: confirmar compatibilidade apenas com modelo X" />
              </label>
            </div>
            <div>
              <div className="flex items-center justify-between gap-2 mb-2">
                <b>Resposta sugerida/editável</b>
                <span className="text-xs text-amber-200">Revise antes de enviar</span>
              </div>
              <textarea className="input min-h-44" value={text} onChange={e=>setEdits(prev=>({...prev,[q.id]:e.target.value}))} />
              <div className="flex flex-wrap gap-2 mt-3">
                <button className="btn" disabled={suggest.isPending} onClick={()=>suggest.mutate({id:q.id, context:customContext[q.id]})}>{suggest.isPending?'Gerando...':'Gerar sugestão'}</button>
                <button className="btn" disabled={!text} onClick={()=>navigator.clipboard?.writeText(text)}>Copiar resposta</button>
                <button className="btn btn-primary" disabled={isSending || text.trim().length < 2} onClick={()=>{ if(window.confirm('Enviar esta resposta ao comprador no Mercado Livre?')) send.mutate({id:q.id, text}); }}>{isSending?'Enviando...':'Enviar resposta'}</button>
              </div>
              {send.error && <p className="text-red-200 mt-3 text-sm">Falha ao enviar. Revise a pergunta, conexão ML e tente novamente.</p>}
              {suggest.error && <p className="text-red-200 mt-3 text-sm">Não foi possível gerar sugestão agora.</p>}
            </div>
          </div>
        </Card>;
      })}
    </div>
  </Page>;
}
