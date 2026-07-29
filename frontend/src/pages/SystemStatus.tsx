import { useQuery } from '@tanstack/react-query';
import { Activity, BellRing, CheckCircle2, Database, DownloadCloud, PlugZap, Server, Wifi, WifiOff } from 'lucide-react';
import Page from '../components/animations/Page';
import { Card, Skeleton } from '../components/ui/Card';
import { systemStatus } from '../api/client';
import { usePWAStatus } from '../hooks/usePWAStatus';

export default function SystemStatus() {
  const pwa = usePWAStatus();
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['system-status'], queryFn: systemStatus });
  if (isLoading) return <Page><Skeleton className="h-96" /></Page>;
  if (isError) return <Page><Card><b>Status indisponível</b><p className="text-slate-400 mt-2">Não foi possível consultar a API agora.</p></Card></Page>;
  const modules = Object.entries(data?.modules || {});
  return <Page>
    <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-4"><div><span className="status-badge text-sky-200">PWA + Produto final</span><h2 className="text-3xl font-black mt-3">Status do Sistema</h2><p className="text-slate-400">Visão operacional para API, banco, sync, alertas e módulos ativos.</p></div><button className="btn btn-primary" onClick={() => refetch()}>Atualizar</button></div>
    <div className="grid md:grid-cols-4 gap-4"><Card><Server className="text-sky-300" /><p className="text-slate-400 mt-3">API</p><b className="text-2xl">{data?.api}</b></Card><Card><Database className="text-emerald-300" /><p className="text-slate-400 mt-3">Banco</p><b className="text-2xl">{data?.database}</b></Card><Card><BellRing className="text-amber-300" /><p className="text-slate-400 mt-3">Alertas ativos</p><b className="text-2xl">{data?.active_alerts || 0}</b></Card><Card><Activity className="text-violet-300" /><p className="text-slate-400 mt-3">Ambiente</p><b className="text-2xl">{data?.environment}</b></Card></div>

    <div className="grid md:grid-cols-3 gap-4 mt-4"><Card><Wifi className={pwa.online ? 'text-emerald-300' : 'text-amber-300'} /><p className="text-slate-400 mt-3">Conexão</p><b className="text-2xl">{pwa.online ? 'Online' : 'Offline'}</b><p className="text-xs text-slate-500 mt-2">Última conexão registrada: {pwa.lastSync ? new Date(pwa.lastSync).toLocaleString('pt-BR') : '—'}</p></Card><Card>{pwa.online ? <Wifi className="text-emerald-300" /> : <WifiOff className="text-amber-300" />}<p className="text-slate-400 mt-3">Offline shell</p><b className="text-2xl">Ativo</b><p className="text-xs text-slate-500 mt-2">Shell e assets estáticos com cache. Dados sensíveis são Network Only.</p></Card><Card><DownloadCloud className={pwa.installed ? 'text-sky-300' : 'text-slate-400'} /><p className="text-slate-400 mt-3">Instalação PWA</p><b className="text-2xl">{pwa.installed ? 'Instalada' : pwa.canInstall ? 'Disponível' : 'Aguardando navegador'}</b><p className="text-xs text-slate-500 mt-2">Android/Desktop usam prompt. iOS instala via Compartilhar &gt; Adicionar à Tela de Início.</p></Card></div>
    <div className="grid lg:grid-cols-[1fr_360px] gap-4 mt-4"><Card><h3 className="text-2xl font-black mb-4">Módulos ativos</h3><div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">{modules.map(([name, ok]) => <div key={name} className="rounded-2xl bg-white/10 border border-white/10 p-4 flex items-center gap-3"><CheckCircle2 className={ok ? 'text-emerald-300' : 'text-slate-500'} /><div><b>{name}</b><p className="text-sm text-slate-400">{ok ? 'Ativo' : 'Pendente'}</p></div></div>)}</div></Card><Card><PlugZap className="text-sky-300" /><h3 className="text-xl font-black mt-3">Última sync</h3>{data?.last_sync ? <div className="mt-3 text-sm text-slate-300"><p>Tipo: {data.last_sync.type || '—'}</p><p>Status: {data.last_sync.status || '—'}</p><p>Criado em: {String(data.last_sync.created_at || '—')}</p></div> : <p className="text-slate-400 mt-3">Nenhum job de sync encontrado ainda.</p>}<p className="text-xs text-slate-500 mt-5">Service worker 15.1 usa Cache First para assets, Network First apenas para APIs públicas seguras e Network Only para OAuth, tokens, billing, webhooks e dados sensíveis.</p></Card></div>
  </Page>;
}
