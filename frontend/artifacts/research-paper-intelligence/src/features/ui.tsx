import type { ReactNode } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';

export const card = 'rounded-[5px] border border-[#d9cdbd] bg-[#fffaf2] p-5 shadow-[0_3px_12px_rgba(45,59,62,.035)] sm:p-7';

export function Eyebrow({ children }: { children: ReactNode }) {
  return <span className="mono text-[9px] uppercase tracking-[.18em] text-[#b56f4b]">{children}</span>;
}

export function Loading({ label }: { label: string }) {
  return <div className="flex items-center gap-2 py-6 text-[12px] text-[#6e8a7f]" role="status"><Loader2 size={15} className="animate-spin" /> {label}</div>;
}

export function ErrorNote({ message }: { message: string }) {
  return <div className="flex items-start gap-2 rounded border border-[#e2b9a8] bg-[#fbeee7] p-3 text-[12px] text-[#a55743]" role="alert"><AlertTriangle size={15} className="mt-0.5 shrink-0" /> <span>{message}</span></div>;
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="rounded-[5px] border border-dashed border-[#cfc2b0] bg-[#faf4eb] px-6 py-14 text-center"><h3 className="serif text-2xl text-[#29475a]">{title}</h3>{children && <p className="mx-auto mt-2 max-w-[360px] text-[12px] leading-5 text-[#7d897f]">{children}</p>}</div>;
}

export function Tag({ kind, children }: { kind: 'reported' | 'inferred' | 'generated'; children?: ReactNode }) {
  const style = { reported: 'bg-[#e4efe6] text-[#3f6b4d]', inferred: 'bg-[#f3e6cf] text-[#8a6425]', generated: 'bg-[#e6e3f1] text-[#5a4f8a]' }[kind];
  return <span className={`mono rounded-full px-2 py-0.5 text-[9px] uppercase tracking-[.1em] ${style}`}>{children ?? kind}</span>;
}

export const pages = (a: number, b: number) => (a === b ? `p. ${a}` : `pp. ${a}–${b}`);
export const sectionLabel = (name: string) => name.replace(/_/g, ' ').toLowerCase().replace(/^\w/, c => c.toUpperCase());
export const paperLabel = (p: { title: string | null; filename: string | null; paper_id: string }) => p.title || p.filename || p.paper_id;
