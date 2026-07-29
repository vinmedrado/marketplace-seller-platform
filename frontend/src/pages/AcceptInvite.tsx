import { FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { acceptInvite, inviteDetails } from '../api/client';

type Details = { email: string; role: string; organization: string; expires_at?: string };

export default function AcceptInvite() {
  const { token = '' } = useParams();
  const navigate = useNavigate();
  const [details, setDetails] = useState<Details | null>(null);
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('Carregando convite...');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    inviteDetails(token)
      .then((response) => { setDetails(response); setMessage(''); })
      .catch((error) => setMessage(error?.response?.data?.detail?.message || 'Convite inválido ou expirado.'));
  }, [token]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setMessage('');
    try {
      await acceptInvite(token, { name, password });
      setMessage('Convite aceito. Redirecionando para o login...');
      setTimeout(() => navigate('/login'), 900);
    } catch (error: any) {
      setMessage(error?.response?.data?.detail?.message || 'Não foi possível aceitar o convite.');
    } finally {
      setLoading(false);
    }
  }

  return <div className="min-h-screen grid-bg aurora grid place-items-center p-6">
    <Link to="/login" className="fixed left-6 top-6 btn btn-ghost">← Login</Link>
    <form onSubmit={submit} className="glass premium-border rounded-[2rem] w-full max-w-md p-7">
      <span className="badge">CONVITE SELLEROS</span>
      <h1 className="text-3xl font-black mt-5">Entrar na organização</h1>
      {details && <>
        <p className="text-slate-300 mt-2">{details.organization} convidou <strong>{details.email}</strong> como {details.role}.</p>
        <label className="block mt-6"><span className="text-sm text-slate-400">Nome</span><input className="input mt-1" value={name} onChange={(event) => setName(event.target.value)} required minLength={2} /></label>
        <label className="block mt-3"><span className="text-sm text-slate-400">Senha</span><input className="input mt-1" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={10} /></label>
        <button className="btn btn-primary w-full mt-6" disabled={loading}>{loading ? 'Aceitando...' : 'Aceitar convite'}</button>
      </>}
      {message && <p className="text-sm text-slate-300 mt-4" role="status">{message}</p>}
    </form>
  </div>;
}
