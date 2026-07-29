import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Page from '../components/animations/Page';
import { Card, Skeleton } from '../components/ui/Card';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { EmptyState } from '../components/ui/EmptyState';
import { Pagination, usePagination } from '../components/ui/Pagination';
import { createProduct, deleteProduct, money, products, updateProduct } from '../api/client';
import { useToast } from '../components/ui/Toast';

const emptyForm = { sku: '', title: '', description: '', category: '', brand: '', cost_price: 0, base_price: 0, min_margin: 0.18, stock_quantity: 0, gtin: '', ncm: '' };

export default function Products() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [query, setQuery] = useState('');
  const [form, setForm] = useState<any | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<any | null>(null);
  const [page, setPage] = useState(1);
  const { data = [], isLoading, isError } = useQuery({ queryKey: ['products'], queryFn: products });
  const filtered = useMemo(() => data.filter((p: any) => `${p.sku} ${p.titulo} ${p.marca} ${p.categoria_nome}`.toLowerCase().includes(query.toLowerCase())), [data, query]);
  const paginated = usePagination(filtered, page, 8);
  const save = useMutation({ mutationFn: (payload: any) => payload.id ? updateProduct(payload.id, payload) : createProduct(payload), onSuccess: () => { qc.invalidateQueries({ queryKey: ['products'] }); setForm(null); toast('Produto salvo com sucesso.', 'success'); }, onError: () => toast('Não foi possível salvar o produto.', 'error') });
  const remove = useMutation({ mutationFn: deleteProduct, onSuccess: () => { qc.invalidateQueries({ queryKey: ['products'] }); setDeleteTarget(null); toast('Produto excluído com segurança.', 'success'); }, onError: () => toast('Não foi possível excluir o produto.', 'error') });
  return <Page>
    <div className="flex flex-wrap justify-between items-center gap-3 mb-4"><div><h2 className="text-3xl font-black">Produtos</h2><p className="text-slate-400">CRUD real persistido no banco, isolado por tenant.</p></div><button onClick={() => setForm(emptyForm)} className="btn btn-primary">Criar produto</button></div>
    <input className="input mb-4" value={query} onChange={e => { setQuery(e.target.value); setPage(1); }} placeholder="Buscar por SKU, título, marca ou categoria..." />
    {isLoading ? <Skeleton className="h-96" /> : isError ? <Card><b>Erro ao carregar produtos</b><p className="text-slate-400 mt-2">Verifique se o backend está online e tente novamente.</p></Card> : <div className="overflow-hidden rounded-[2rem] glass premium-border">
      {filtered.length ? <><table className="table-premium text-sm"><thead><tr><th>Produto</th><th>Categoria</th><th>Estoque</th><th>Preço</th><th>Ações</th></tr></thead><tbody>{paginated.items.map((p: any) => <tr key={p.id} className="border-t border-white/10"><td><b>{p.titulo}</b><p className="text-slate-400">{p.sku} · {p.marca || 'Sem marca'}</p></td><td>{p.categoria_nome || '-'}</td><td><span className="status-badge">{p.estoque}</span></td><td>{money(p.preco_base)}</td><td><div className="flex gap-2 justify-end"><Link className="btn btn-ghost" to={`/app/produtos/${p.id}`}>Abrir</Link><button className="btn btn-ghost" onClick={() => setForm({ id: p.id, sku: p.sku, title: p.titulo, description: p.descricao, category: p.categoria_nome, brand: p.marca, cost_price: p.custo, base_price: p.preco_base, min_margin: p.margem_minima, stock_quantity: p.estoque, gtin: p.gtin, ncm: p.ncm })}>Editar</button><button className="btn btn-danger" onClick={() => setDeleteTarget(p)}>Excluir</button></div></td></tr>)}</tbody></table><Pagination page={paginated.page} totalPages={paginated.totalPages} onPage={setPage}/></> : <EmptyState title="Nenhum produto encontrado" description="Crie seu primeiro produto para liberar pricing, concorrência, dry-run e jobs." action={<button className="btn btn-primary" onClick={() => setForm(emptyForm)}>Criar produto</button>} />}
    </div>}
    {form && <div className="fixed inset-0 bg-black/70 z-50 grid place-items-center p-4"><Card className="max-w-3xl w-full"><h3 className="text-2xl font-black mb-4">{form.id ? 'Editar produto' : 'Novo produto'}</h3><div className="grid md:grid-cols-2 gap-3">{['sku','title','category','brand','gtin','ncm'].map(k => <input key={k} className="input" placeholder={k} value={form[k] || ''} onChange={e => setForm({ ...form, [k]: e.target.value })} />)}{['cost_price','base_price','min_margin','stock_quantity'].map(k => <input key={k} className="input" type="number" step="0.01" placeholder={k} value={form[k] ?? ''} onChange={e => setForm({ ...form, [k]: Number(e.target.value) })} />)}<textarea className="input md:col-span-2" placeholder="description" value={form.description || ''} onChange={e => setForm({ ...form, description: e.target.value })} /></div><div className="flex justify-end gap-2 mt-4"><button className="btn btn-ghost" disabled={save.isPending} onClick={() => setForm(null)}>Cancelar</button><button className="btn btn-primary" disabled={save.isPending || !form.sku || !form.title} onClick={() => save.mutate(form)}>{save.isPending ? 'Salvando...' : 'Salvar'}</button></div></Card></div>}
    <ConfirmDialog open={!!deleteTarget} title="Excluir produto?" description={`Essa ação remove ${deleteTarget?.titulo || 'o produto'} do fluxo ativo da demo.`} loading={remove.isPending} confirmText="Excluir produto" onCancel={() => setDeleteTarget(null)} onConfirm={() => remove.mutate(deleteTarget.id)} />
  </Page>;
}
