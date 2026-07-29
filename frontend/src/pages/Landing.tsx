import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { AlertTriangle, BarChart3, Brain, CheckCircle2, ClipboardCheck, PackageCheck, Rocket, ShieldCheck, Sparkles, Workflow } from 'lucide-react';

const pain = ['Preço errado drenando margem', 'Análise manual de concorrência', 'Retrabalho na publicação', 'Falta de visibilidade executiva'];
const features = [
  ['Produtos', PackageCheck], ['Concorrência', BarChart3], ['Pricing', Sparkles], ['Publicação', Rocket],
  ['Jobs', Workflow], ['ML MVP', Brain], ['Dashboard', ClipboardCheck], ['Logs', ShieldCheck],
] as const;
const steps = ['Cadastrar produto', 'Analisar concorrência', 'Calcular preço', 'Publicar dry-run', 'Monitorar resultado'];

export default function Landing() {
  return <div className="min-h-screen grid-bg aurora overflow-hidden">
    <section className="max-w-7xl mx-auto px-6 py-8 relative">
      <nav className="flex justify-between items-center glass premium-border rounded-3xl px-5 py-4">
        <b className="text-2xl tracking-tight">MarketPlace Seller Platform</b>
        <div className="hidden md:flex gap-6 text-sm text-slate-300"><a href="#solucao">Solução</a><a href="#features">Funcionalidades</a><a href="#fluxo">Como funciona</a></div>
        <Link to="/login" className="btn btn-primary">Entrar no ambiente demo</Link>
      </nav>
      <div className="grid lg:grid-cols-2 gap-12 items-center py-24">
        <motion.div initial={{ opacity: 0, y: 32 }} animate={{ opacity: 1, y: 0 }}>
          <div className="flex flex-wrap gap-2 mb-6">{['AI-ready', 'Pricing engine', 'Dry-run seguro', 'Multi-tenant demo'].map(x => <span className="glass rounded-full px-4 py-2 text-sm" key={x}>{x}</span>)}</div>
          <h1 className="text-5xl md:text-7xl font-black leading-tight">Automação premium para sellers venderem com margem, dados e velocidade.</h1>
          <p className="text-xl text-slate-300 mt-6">Uma plataforma SaaS demonstrável para centralizar produtos, coletar concorrência, calcular preço sugerido, simular publicação e acompanhar jobs operacionais em tempo real.</p>
          <div className="flex flex-wrap gap-4 mt-8"><Link className="btn btn-primary" to="/login">Ver painel executivo</Link><a className="btn btn-ghost" href="#features">Simular precificação</a></div>
        </motion.div>
        <motion.div animate={{ y: [0, -14, 0] }} transition={{ repeat: Infinity, duration: 7 }} className="glass premium-border glow rounded-[2.4rem] p-6 relative overflow-hidden">
          <div className="absolute bg-orb bg-sky-400/40 w-44 h-44 right-4 top-6" />
          <div className="mini-grid rounded-[2rem] p-5 relative">
            <div className="grid grid-cols-2 gap-4">
              {['Margem média 27%', 'Jobs 12', 'Ofertas 148', 'Dry-run OK'].map((x, i) => <motion.div key={x} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: .15 * i }} className="glass rounded-3xl p-5"><p className="text-sm text-slate-300">{x.split(' ')[0]}</p><b className="text-3xl">{x.split(' ').slice(1).join(' ')}</b></motion.div>)}
            </div>
            <div className="glass rounded-3xl mt-4 p-5"><div className="h-3 skeleton rounded-full mb-3"/><div className="h-3 skeleton rounded-full w-2/3 mb-3"/><div className="h-24 rounded-2xl bg-gradient-to-br from-sky-400/20 to-violet-500/20 border border-white/10"/></div>
          </div>
        </motion.div>
      </div>
      <section className="grid md:grid-cols-4 gap-4" id="dores">{pain.map((x, i) => <motion.div key={x} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * .08 }} className="glass premium-border rounded-3xl p-5"><AlertTriangle className="text-amber-300"/><b className="block mt-4">{x}</b></motion.div>)}</section>
      <section id="solucao" className="py-20"><div className="glass premium-border rounded-[2.4rem] p-8 grid lg:grid-cols-2 gap-8"><div><p className="text-sky-300 font-bold">Solução</p><h2 className="text-4xl font-black mt-2">Operação comercial com pricing, concorrência e publicação em um único fluxo.</h2></div><div className="grid gap-3">{['Precificação inteligente com fallback seguro', 'Coleta de concorrência com histórico', 'Publicação segura em modo dry-run', 'Dashboard executivo com dados reais'].map(x => <div className="flex gap-3 items-center" key={x}><CheckCircle2 className="text-emerald-300"/><span>{x}</span></div>)}</div></div></section>

      <section className="py-16" id="para-quem"><h2 className="text-4xl font-black mb-8">Pronto para sellers, agências e operações de marketplace</h2><div className="grid md:grid-cols-3 gap-4">{['Sellers que precisam proteger margem', 'Agências que operam múltiplas contas', 'Times comerciais que querem decisão baseada em dados'].map(x => <div key={x} className="glass premium-border rounded-3xl p-6"><b className="text-xl">{x}</b><p className="text-slate-400 mt-3">Centralize produtos, preços, concorrência, simulações e alertas em um painel executivo.</p></div>)}</div></section>
      <section className="py-16"><div className="grid lg:grid-cols-2 gap-4"><div className="glass premium-border rounded-[2rem] p-8"><p className="text-red-200 font-bold">Antes</p><h3 className="text-3xl font-black mt-2">Competição no escuro</h3><p className="text-slate-300 mt-3">Planilhas soltas, preço manual, margem invisível, publicação com risco e pouca priorização.</p></div><div className="glass premium-border rounded-[2rem] p-8"><p className="text-emerald-200 font-bold">Depois</p><h3 className="text-3xl font-black mt-2">Operação com inteligência comercial</h3><p className="text-slate-300 mt-3">Preço por cenário, concorrência monitorada, dry-run validado, insights por impacto e dashboard executivo.</p></div></div></section>
      <section className="py-16"><h2 className="text-4xl font-black mb-8">Resultados esperados</h2><div className="grid md:grid-cols-4 gap-4">{['Menos erro manual', 'Mais proteção de margem', 'Mais velocidade operacional', 'Decisão com dados'].map(x => <div key={x} className="glass premium-border rounded-3xl p-6"><b>{x}</b><p className="text-slate-400 mt-2">Indicadores e ações claras para melhorar a rotina comercial.</p></div>)}</div></section>
      <section id="features" className="grid md:grid-cols-4 gap-4">{features.map(([label, Icon], i) => <motion.div key={label} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * .05 }} whileHover={{ y: -8, rotateX: 2 }} className="glass premium-border rounded-3xl p-6"><Icon className="text-sky-300"/><b className="block text-xl mt-5">{label}</b><p className="text-slate-400 mt-2">Fluxo real conectado ao backend, com estados de loading, erro e histórico.</p></motion.div>)}</section>
      <section id="fluxo" className="py-20"><h2 className="text-4xl font-black mb-8">Como funciona</h2><div className="grid md:grid-cols-5 gap-4">{steps.map((x, i) => <div key={x} className="glass premium-border rounded-3xl p-5"><span className="status-badge">0{i + 1}</span><b className="block mt-5">{x}</b></div>)}</div></section>
      <section className="pb-20"><div className="glass premium-border glow rounded-[2.4rem] p-10 text-center"><h2 className="text-4xl font-black">Veja a demo funcionando agora.</h2><p className="text-slate-300 mt-3">Login demo, produtos reais em banco, pricing, jobs, ML MVP e dry-run de publicação.</p><Link className="btn btn-primary inline-block mt-6" to="/login">Entrar no demo</Link></div></section>
    </section>
  </div>;
}
