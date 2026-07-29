import { AnimatePresence, motion } from 'framer-motion';

export function ConfirmDialog({
  open,
  title,
  description,
  confirmText = 'Confirmar',
  cancelText = 'Cancelar',
  loading = false,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmText?: string;
  cancelText?: string;
  loading?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return <AnimatePresence>
    {open && <motion.div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <motion.div initial={{ opacity: 0, y: 24, scale: .96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 18, scale: .96 }} className="glass premium-border rounded-[2rem] max-w-lg w-full p-6 glow-soft">
        <div className="h-12 w-12 rounded-2xl bg-rose-400/15 border border-rose-300/20 grid place-items-center mb-4">!</div>
        <h3 className="text-2xl font-black">{title}</h3>
        <p className="text-slate-300 mt-2">{description}</p>
        <div className="flex justify-end gap-3 mt-6">
          <button className="btn btn-ghost" disabled={loading} onClick={onCancel}>{cancelText}</button>
          <button className="btn btn-danger" disabled={loading} onClick={onConfirm}>{loading ? 'Excluindo...' : confirmText}</button>
        </div>
      </motion.div>
    </motion.div>}
  </AnimatePresence>;
}
