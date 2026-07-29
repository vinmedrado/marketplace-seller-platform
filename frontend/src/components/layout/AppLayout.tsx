import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { BarChart3, Box, Brain, ChevronLeft, CloudCog, Command, Menu, PackageSearch, Rocket, Search, Settings, Tags, Users, CreditCard, PlugZap, Sparkles, Activity, Calculator, Clock, Crown, Radar, Crosshair, Flame, FileText, ScanLine, MessageCircleQuestion, HeartPulse, Trophy, BellRing, ReceiptText, TrendingUp, Landmark, Smartphone, XCircle, ShieldCheck } from 'lucide-react';
import { useState } from 'react';
import AlertBell from '../ui/AlertBell';
import CommandPalette from '../ui/CommandPalette';
import PWAInstallBanner from '../pwa/PWAInstallBanner';
import NetworkStatusToast from '../pwa/NetworkStatusToast';
import PWAStatusBadge from '../pwa/PWAStatusBadge';

const items = [
  ['/app/dashboard', 'Dashboard', BarChart3], ['/app/onboarding', 'Onboarding', Sparkles], ['/app/marketplace', 'Marketplace', PlugZap], ['/app/produtos', 'Produtos', Box], ['/app/pricing-scanner', 'Scanner de Preços', ScanLine], ['/app/questions', 'Perguntas ML', MessageCircleQuestion], ['/app/account-health', 'Saúde da Conta', HeartPulse], ['/app/buybox', 'Buy Box Score', Trophy], ['/app/alerts', 'Alertas', BellRing], ['/app/forecast', 'Previsão de Demanda', TrendingUp], ['/app/billing', 'Assinatura', ReceiptText], ['/app/portfolio', 'Análise de Portfólio', BarChart3], ['/app/title-optimizer', 'Otimização de Título', Sparkles], ['/app/system-status', 'Status do Sistema', Smartphone], ['/app/finance-reconciliation', 'Reconciliação Financeira', Landmark], ['/app/concorrencia', 'Concorrência', PackageSearch], ['/app/precificacao', 'Precificação', Tags], ['/app/publicacao', 'Publicação', Rocket], ['/app/inteligencia', 'ML / Inteligência', Brain], ['/app/ai-copilot', 'AI Copilot', Brain], ['/app/action-center', 'Action Center', Crosshair], ['/app/market-war-room', 'Market War Room', Flame], ['/app/intelligence-center', 'Intelligence Center', Sparkles], ['/app/executive', 'Executive Mode', Crown], ['/app/executive-summary', 'Executive Summary', FileText], ['/app/timeline', 'Operational Timeline', Clock], ['/app/market-radar', 'Market Radar', Radar], ['/app/health', 'Health Monitoring', Activity], ['/app/simulador', 'Simulador Executivo', Calculator], ['/app/profit-simulator', 'Profit Simulator Pro', Calculator], ['/app/jobs', 'Jobs', CloudCog], ['/app/plano', 'Plano', CreditCard], ['/app/usuarios', 'Usuários', Users], ['/app/privacidade', 'Privacidade e LGPD', ShieldCheck], ['/app/configuracoes', 'Configurações', Settings],
] as const;

export default function AppLayout() {
  const [open, setOpen] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const current = items.find(([to]) => location.pathname.startsWith(to));
  const Nav = ({ compact = false }: { compact?: boolean }) => <>
    <button onClick={() => compact ? setMobileOpen(false) : setOpen(!open)} className="btn btn-ghost flex items-center justify-center gap-3 min-h-12">
      {compact ? <XCircle /> : open ? <ChevronLeft /> : <Menu />}{(!compact && open) || compact ? <span className="text-lg">MarketPlace Seller Platform</span> : null}
    </button>
    <div className="rounded-2xl bg-emerald-400/10 text-emerald-200 border border-emerald-300/20 px-3 py-3 text-xs font-bold flex items-center gap-2">
      <span className="h-2 w-2 rounded-full bg-emerald-300 animate-pulse" />{(open || compact) && 'Console pessoal operacional'}
    </div>
    <nav className="flex flex-col gap-2 overflow-y-auto no-scrollbar pr-1 pb-4">
      {items.map(([to, label, Icon]) => <NavLink key={to} to={to} onClick={() => setMobileOpen(false)} className={({ isActive }) => `relative rounded-2xl px-4 py-3 min-h-12 flex items-center gap-3 transition group ${isActive ? 'bg-white/15 text-white shadow-[0_0_28px_rgba(125,211,252,.12)]' : 'text-slate-300 hover:bg-white/10'}`}>
        {({ isActive }) => <>{isActive && <motion.span layoutId={compact ? 'activeMobileNav' : 'activeNav'} className="absolute left-0 top-2 bottom-2 w-1 rounded-full bg-sky-300" />}<Icon size={20} className="group-hover:scale-110 transition shrink-0" />{(open || compact) && <span>{label}</span>}</>}
      </NavLink>)}
    </nav>
  </>;
  return <div className="min-h-screen grid-bg aurora lg:flex">
    <button onClick={() => setMobileOpen(true)} className="lg:hidden fixed left-4 bottom-4 z-40 btn btn-primary rounded-full shadow-2xl" aria-label="Abrir menu"><Menu /></button>
    {mobileOpen && <div className="lg:hidden fixed inset-0 z-50 bg-black/70 backdrop-blur-sm p-3" onClick={() => setMobileOpen(false)}><aside onClick={e => e.stopPropagation()} className="glass premium-border rounded-[1.5rem] p-4 flex flex-col gap-4 h-[calc(100vh-1.5rem)] w-full max-w-sm"><Nav compact /></aside></div>}
    <motion.aside animate={{ width: open ? 286 : 94 }} className="hidden lg:flex glass premium-border m-4 rounded-[2rem] p-4 flex-col gap-4 sticky top-4 h-[calc(100vh-2rem)]"><Nav /></motion.aside>
    <main className="flex-1 p-3 sm:p-4 min-w-0 pb-20 lg:pb-4">
      <div className="glass premium-border rounded-[1.5rem] lg:rounded-[2rem] p-4 mb-4 flex items-center justify-between gap-4">
        <div className="min-w-0"><p className="text-xs sm:text-sm text-slate-400 truncate">MarketPlace Seller Platform / {current?.[1] || 'App'}</p><h1 className="text-lg sm:text-xl font-black truncate">Cockpit operacional MarketPlace Seller Platform</h1></div>
        <div className="hidden xl:flex items-center gap-2 bg-white/10 rounded-2xl px-4 py-3 text-slate-300 border border-white/10 min-w-80"><Search size={18}/><span className="flex-1">Buscar produtos, jobs e oportunidades</span><span className="text-xs text-slate-400">Ctrl K</span><Command size={16}/></div>
        <div className="flex items-center gap-2 sm:gap-3"><PWAStatusBadge/><AlertBell/><span className="hidden md:inline-flex status-badge text-sky-200">API conectada</span><div className="h-10 w-10 sm:h-11 sm:w-11 rounded-2xl bg-gradient-to-tr from-sky-400 via-violet-500 to-fuchsia-500 shadow-[0_0_35px_rgba(139,92,246,.32)]" /></div>
      </div>
      <Outlet />
      <CommandPalette />
      <NetworkStatusToast />
      <PWAInstallBanner />
    </main>
  </div>;
}
