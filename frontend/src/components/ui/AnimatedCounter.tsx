import { motion, useMotionValue, useTransform, animate } from 'framer-motion';
import { useEffect } from 'react';

export function AnimatedCounter({ value, suffix = '' }: { value: number; suffix?: string }) {
  const count = useMotionValue(0);
  const rounded = useTransform(count, latest => `${Math.round(latest).toLocaleString('pt-BR')}${suffix}`);
  useEffect(() => {
    const controls = animate(count, Number(value || 0), { duration: .8, ease: 'easeOut' });
    return controls.stop;
  }, [count, value]);
  return <motion.span>{rounded}</motion.span>;
}
