export function usePagination<T>(items: T[], page: number, pageSize = 8) {
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  const safePage = Math.min(Math.max(page, 1), totalPages);
  const start = (safePage - 1) * pageSize;
  return { page: safePage, totalPages, items: items.slice(start, start + pageSize), start, total: items.length };
}

export function Pagination({ page, totalPages, onPage }: { page: number; totalPages: number; onPage: (page: number) => void }) {
  if (totalPages <= 1) return null;
  return <div className="flex items-center justify-end gap-2 p-4 text-sm">
    <button className="btn btn-ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>Anterior</button>
    <span className="text-slate-300 px-3">Página {page} de {totalPages}</span>
    <button className="btn btn-ghost" disabled={page >= totalPages} onClick={() => onPage(page + 1)}>Próxima</button>
  </div>;
}
