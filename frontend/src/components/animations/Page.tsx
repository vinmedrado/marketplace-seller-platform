import type { ReactNode } from 'react';
import { motion } from 'framer-motion';

export default function Page({ children }: { children: ReactNode }) {
  return <motion.div initial={{ opacity: 0, y: 18, filter: 'blur(8px)' }} animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }} exit={{ opacity: 0, y: -12 }} transition={{ duration: .36, ease: 'easeOut' }}>
    {children}
  </motion.div>;
}
