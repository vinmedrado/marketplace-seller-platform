import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Lock, Mail, Sparkles } from 'lucide-react';
import { login } from '../api/client';
import { useToast } from '../components/ui/Toast';

export default function Login() {
  const demoEnabled = import.meta.env.DEV || import.meta.env.VITE_ENABLE_DEMO_LOGIN === 'true';
  const nav = useNavigate();
  const { toast } = useToast();
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [loading, setLoading] = useState(false);
  async function submit(useDemo = false) {
    setLoading(true);
    toast('Validando credenciais...', 'loading');
    try {
      await login(useDemo ? 'demo@marketplace.local' : email, useDemo ? 'demo123456' : senha);
      toast('Login realizado. Abrindo dashboard.', 'success');
      setTimeout(() => nav('/app/dashboard'), 280);
    } catch (e: any) {
      toast(e?.response?.data?.detail?.message || 'Não foi possível entrar. Verifique API e credenciais.', 'error');
    } finally { setLoading(false); }
  }
  return <div className="min-h-screen grid-bg aurora grid place-items-center p-6 overflow-hidden">
    <Link to="/" className="fixed left-6 top-6 btn btn-ghost">← Landing</Link>
    <motion.div initial={{ opacity: 0, y: 28, scale: .96 }} animate={{ opacity: 1, y: 0, scale: 1 }} className="glass premium-border glow rounded-[2.4rem] w-full max-w-md p-7 relative overflow-hidden">
      <div className="absolute bg-orb bg-sky-400/30 w-40 h-40 -right-10 -top-10" />
      <div className="relative">
        <div className="h-14 w-14 rounded-2xl bg-gradient-to-tr from-sky-400 to-violet-500 grid place-items-center shadow-[0_0_38px_rgba(99,102,241,.4)]"><Sparkles/></div>
        <h1 className="text-4xl font-black mt-6">Entrar no SellerOS</h1>
        <p className="text-slate-300 mt-2">Acesse sua operação SellerOS com inteligência operacional, integrações e visão executiva em tempo real.</p>
        <div className="space-y-3 mt-6">
          <label className="block"><span className="text-sm text-slate-400">E-mail</span><div className="relative mt-1"><Mail className="absolute left-4 top-3.5 text-slate-400" size={18}/><input className="input pl-12" value={email} onChange={e => setEmail(e.target.value)} /></div></label>
          <label className="block"><span className="text-sm text-slate-400">Senha</span><div className="relative mt-1"><Lock className="absolute left-4 top-3.5 text-slate-400" size={18}/><input className="input pl-12" type="password" value={senha} onChange={e => setSenha(e.target.value)} /></div></label>
        </div>
        <button disabled={loading || !email || !senha} onClick={() => submit()} className="btn btn-primary w-full mt-6">{loading ? 'Entrando...' : 'Entrar'}</button>
        {demoEnabled && <>
          <button disabled={loading} onClick={() => submit(true)} className="btn btn-ghost w-full mt-3">Entrar na demonstração local</button>
          <p className="text-xs text-slate-400 mt-5">Disponível apenas no ambiente local de desenvolvimento.</p>
        </>}
      </div>
    </motion.div>
  </div>;
}
