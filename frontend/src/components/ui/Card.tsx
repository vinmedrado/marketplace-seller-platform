import type { Key, ReactNode } from 'react';
import { motion } from 'framer-motion';

type CardProps = { children: ReactNode; className?: string; key?: Key };
type SkeletonProps = { className?: string; key?: Key };

export function Card({ children, className = '' }: CardProps) {
  return <motion.div whileHover={{ y: -4, scale: 1.008 }} transition={{ duration: .2 }} className={`glass premium-border card ${className}`}>{children}</motion.div>;
}

export function Skeleton({ className = 'h-32' }: SkeletonProps) {
  return <div className={`glass rounded-3xl skeleton ${className}`} />;
}
