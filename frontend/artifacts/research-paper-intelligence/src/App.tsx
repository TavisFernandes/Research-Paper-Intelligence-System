import { useEffect, useRef, useState, type DragEvent, type ReactNode } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ArrowDownRight,
  ArrowRight,
  BarChart3,
  BookOpen,
  BrainCircuit,
  Check,
  ChevronRight,
  Clipboard,
  CloudUpload,
  FileText,
  FlaskConical,
  FolderOpen,
  GitCompare,
  Highlighter,
  Layers3,
  Menu,
  MessageCircle,
  MoreHorizontal,
  Network,
  Plus,
  Quote,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Tag,
  Upload,
  X,
} from 'lucide-react';
import { Link, Route, Switch, Router as WouterRouter, useLocation } from 'wouter';
import { ErrorBoundary } from '@/components/error-boundary';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import { uploadAndProcessPaper, type ProcessedPaper } from '@/lib/paper-api';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import NotFound from '@/pages/not-found';

type Paper = {
  id: string;
  shortTitle: string;
  title: string;
  authors: string;
  year: string;
  pages: string;
  accent: string;
  initials: string;
  journal: string;
  data: ProcessedPaper;
};

type ChatMessage = { id: number; role: 'user' | 'assistant'; text: string; cite?: string };

const SUGGESTIONS = [
  'What is the central contribution?',
  'Explain the method in plain language',
  'What are the main limitations?',
  'How do these studies differ?',
];

const MODES = [
  { id: 'overview', label: 'Overview', icon: BookOpen },
  { id: 'methods', label: 'Methods', icon: FlaskConical },
  { id: 'findings', label: 'Findings', icon: BarChart3 },
  { id: 'compare', label: 'Compare', icon: GitCompare },
] as const;

const PAPER_ACCENTS = ['#c57950', '#6f8793', '#b59a62', '#78917f'];

function toPaper(data: ProcessedPaper, index: number): Paper {
  const filename = data.filename || 'Untitled PDF';
  const initials = filename.replace(/\.pdf$/i, '').split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0]).join('').toUpperCase() || 'PDF';
  return {
    id: data.paper_id,
    shortTitle: filename.length > 34 ? `${filename.slice(0, 34)}…` : filename,
    title: filename,
    authors: 'Authors unavailable',
    year: 'Year unavailable',
    pages: `${data.total_pages} ${data.total_pages === 1 ? 'page' : 'pages'}`,
    accent: PAPER_ACCENTS[index % PAPER_ACCENTS.length],
    initials,
    journal: 'Source metadata unavailable',
    data,
  };
}

function Logo({ inverse = false }: { inverse?: boolean }) {
  return (
    <div className="flex items-center gap-2.5" data-testid="brand-logo">
      <div className={`relative flex h-9 w-9 items-center justify-center rounded-[11px] ${inverse ? 'bg-[#d6ad72]' : 'bg-[#29475a]'}`}>
        <div className={`absolute h-5 w-3.5 -rotate-12 rounded-[2px] border ${inverse ? 'border-[#29475a]' : 'border-[#f7f1e7]'}`} />
        <div className={`absolute ml-1 mt-1 h-5 w-3.5 rotate-12 rounded-[2px] border ${inverse ? 'border-[#29475a]' : 'border-[#f7f1e7]'}`} />
        <span className={`relative text-[11px] font-bold ${inverse ? 'text-[#29475a]' : 'text-[#f7f1e7]'}`}>R</span>
      </div>
      <span className={`text-[15px] font-semibold tracking-[-.02em] ${inverse ? 'text-[#f7f1e7]' : 'text-[#29475a]'}`}>
        paper<span className={inverse ? 'text-[#d6ad72]' : 'text-[#c57950]'}>intel</span>
      </span>
    </div>
  );
}

function Landing() {
  const [, setLocation] = useLocation();
  return (
    <div className="paper-noise min-h-[100dvh] overflow-hidden bg-[#f6f1e8] text-[#21394b]">
      <header className="relative z-10 mx-auto flex max-w-[1240px] items-center justify-between px-5 py-5 sm:px-8 lg:px-12">
        <Link href="/" className="focus-ring rounded-lg" data-testid="link-home-logo"><Logo /></Link>
        <nav className="hidden items-center gap-8 text-[12px] font-medium text-[#526574] md:flex" aria-label="Primary navigation">
          <a href="#how-it-works" className="focus-ring rounded-md transition-colors hover:text-[#21394b]" data-testid="link-how-it-works">How it works</a>
          <a href="#workspace" className="focus-ring rounded-md transition-colors hover:text-[#21394b]" data-testid="link-workspace">The workspace</a>
          <a href="#principles" className="focus-ring rounded-md transition-colors hover:text-[#21394b]" data-testid="link-principles">Our approach</a>
        </nav>
        <button onClick={() => setLocation('/console')} className="focus-ring group flex items-center gap-2 rounded-full border border-[#29475a]/15 bg-[#fffaf2] px-4 py-2 text-[12px] font-semibold text-[#29475a] shadow-[0_3px_12px_rgba(36,54,63,.05)] transition hover:-translate-y-0.5 hover:border-[#c57950]/40 hover:text-[#b2643e]" data-testid="button-open-workspace">
          Open workspace <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" />
        </button>
      </header>

      <main>
        <section className="relative mx-auto grid max-w-[1240px] items-center gap-14 px-5 pb-24 pt-16 sm:px-8 sm:pt-24 lg:grid-cols-[.94fr_1.06fr] lg:px-12 lg:pb-32 lg:pt-28">
          <div className="pointer-events-none absolute -left-40 top-20 h-[480px] w-[480px] rounded-full bg-[#d6ad72]/15 blur-3xl" />
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .7 }} className="relative z-10">
            <div className="mb-6 flex items-center gap-3 text-[10px] font-semibold uppercase tracking-[.19em] text-[#a66547]">
              <span className="h-px w-7 bg-[#c57950]" /> A better way into the literature
            </div>
            <h1 className="serif max-w-[590px] text-[clamp(3.7rem,7.2vw,6.7rem)] leading-[.91] tracking-[-.055em] text-[#21394b]">
              Read the<br /><em className="font-normal text-[#bd744f]">thinking</em>,<br />not every page.
            </h1>
            <p className="mt-8 max-w-[470px] text-[16px] leading-7 text-[#5c6e78]">
              Paperintel turns dense research into a conversation you can trust. Ask better questions, see the method, and find the thread between studies.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <button onClick={() => setLocation('/console')} className="focus-ring group flex items-center gap-3 rounded-full bg-[#29475a] px-5 py-3 text-[13px] font-semibold text-[#f8f2e7] shadow-[0_8px_22px_rgba(41,71,90,.2)] transition hover:-translate-y-0.5 hover:bg-[#1e394a]" data-testid="button-start-reading">
                Start reading <ArrowDownRight size={16} className="transition-transform group-hover:translate-x-0.5 group-hover:translate-y-0.5" />
              </button>
              <span className="mono pl-1 text-[10px] text-[#8a918c]">No account needed · mock workspace</span>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, scale: .96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: .85, delay: .12 }} className="relative min-h-[460px] lg:min-h-[540px]">
            <div className="paper-grid absolute right-0 top-3 h-[390px] w-[92%] rounded-[2px] border border-[#29475a]/10 opacity-60 lg:h-[480px]" />
            <div className="absolute -right-4 top-10 h-[380px] w-[86%] rotate-[5deg] rounded-[4px] border border-[#d8c9b4] bg-[#e7ddcc] shadow-[0_16px_36px_rgba(66,66,54,.12)] lg:h-[470px]" />
            <div className="absolute right-4 top-4 h-[380px] w-[86%] -rotate-[2deg] rounded-[4px] border border-[#d8c9b4] bg-[#fffaf2] p-7 shadow-[0_16px_36px_rgba(66,66,54,.14)] lg:h-[470px] lg:p-10">
              <div className="flex items-start justify-between">
                <div className="h-7 w-7 rounded-[4px] bg-[#29475a] text-center text-[12px] font-bold leading-7 text-[#f8f2e7]">R</div>
                <span className="mono text-[9px] uppercase tracking-[.16em] text-[#a7a094]">paper / 01</span>
              </div>
              <div className="mt-14 border-t border-[#29475a]/20 pt-4">
                <p className="serif text-[clamp(1.7rem,3.4vw,2.7rem)] leading-[.98] tracking-[-.04em] text-[#29475a]">Your research<br />paper</p>
                <p className="mt-4 text-[10px] text-[#7c8684]">Upload a PDF to begin</p>
              </div>
              <div className="mt-14 space-y-2 opacity-60">
                {[72, 94, 86, 65, 90, 76, 51].map((width, index) => <div key={index} className="h-[3px] rounded-full bg-[#9eaaab]" style={{ width: `${width}%` }} />)}
              </div>
              <div className="absolute bottom-8 left-7 right-7 flex items-end justify-between lg:bottom-10 lg:left-10 lg:right-10">
                <span className="mono text-[9px] text-[#a7a094]">SOURCE PDF</span>
                <div className="h-11 w-11 rounded-full border border-[#c57950]/40 p-1.5"><div className="h-full w-full rounded-full border border-dashed border-[#c57950] opacity-70" /></div>
              </div>
            </div>
            <motion.div animate={{ y: [0, -7, 0] }} transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }} className="absolute -bottom-3 left-0 w-[215px] rounded-[4px] border border-[#29475a]/15 bg-[#29475a] p-5 text-[#f8f2e7] shadow-[0_18px_35px_rgba(41,71,90,.2)] sm:left-4">
              <div className="mb-4 flex items-center gap-2 text-[#d6ad72]"><Sparkles size={14} /><span className="mono text-[9px] uppercase tracking-[.15em]">plain-language note</span></div>
              <p className="serif text-[20px] leading-[1.05]">“Keep the source<br />in view.”</p>
              <div className="mt-4 flex items-center gap-2 text-[10px] text-[#b8c1be]"><span className="h-1.5 w-1.5 rounded-full bg-[#d6ad72]" /> structure preserved</div>
            </motion.div>
            <div className="absolute right-0 top-[52%] hidden w-[155px] translate-x-4 rounded-[3px] border border-[#d7c6ae] bg-[#f1e5d2] p-4 shadow-[0_12px_26px_rgba(70,57,43,.12)] sm:block">
              <div className="mono text-[9px] uppercase tracking-[.13em] text-[#a66547]">structure / 03</div>
              <div className="mt-3 flex items-end gap-1.5">{[25, 43, 34, 66, 52, 79, 68].map((height, i) => <span key={i} className="w-2 rounded-t-sm bg-[#c57950]" style={{ height }} />)}</div>
              <p className="mt-3 text-[10px] leading-4 text-[#68746f]">Pages, sections, and chunks.</p>
            </div>
          </motion.div>
        </section>

        <section id="how-it-works" className="border-y border-[#29475a]/10 bg-[#e9dfcf]/55">
          <div className="mx-auto max-w-[1240px] px-5 py-20 sm:px-8 lg:px-12 lg:py-24">
            <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
              <div><span className="mono text-[10px] uppercase tracking-[.2em] text-[#a66547]">A calm research loop</span><h2 className="serif mt-3 text-4xl tracking-[-.04em] text-[#29475a] sm:text-5xl">From paper pile to<br /><em className="font-normal text-[#b56f4b]">point of view.</em></h2></div>
              <p className="max-w-[285px] text-[13px] leading-6 text-[#66756f]">Less tab-switching. More useful questions. A desk that remembers what matters.</p>
            </div>
            <div className="mt-16 grid gap-0 border-t border-[#29475a]/15 md:grid-cols-3">
              {[
                ['01', 'Bring your sources', 'Drop in one study or a whole reading list. Keep the context together.', Upload],
                ['02', 'Ask like a human', 'No query language. Ask what you actually want to understand, in your own words.', MessageCircle],
                ['03', 'Follow the evidence', 'Every answer stays close to the page, with methods, caveats, and citations in view.', Network],
              ].map(([number, title, copy, Icon]) => (
                <div key={number as string} className="group border-b border-[#29475a]/15 py-8 md:border-b-0 md:border-r md:px-8 md:first:pl-0 md:last:border-r-0">
                  <div className="flex items-center justify-between"><span className="mono text-[10px] text-[#a66547]">{number as string}</span><Icon size={18} strokeWidth={1.4} className="text-[#74867e] transition-colors group-hover:text-[#c57950]" /></div>
                  <h3 className="mt-10 text-[17px] font-semibold text-[#29475a]">{title as string}</h3><p className="mt-3 max-w-[245px] text-[13px] leading-6 text-[#6d7b76]">{copy as string}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="workspace" className="mx-auto grid max-w-[1240px] items-center gap-16 px-5 py-24 sm:px-8 lg:grid-cols-[.8fr_1.2fr] lg:px-12 lg:py-32">
          <div>
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.2em] text-[#a66547]"><Layers3 size={14} /> The workspace</div>
            <h2 className="serif mt-5 text-5xl leading-[.95] tracking-[-.045em] text-[#29475a]">A research desk,<br /><span className="text-[#bd744f]">not a dashboard.</span></h2>
            <p className="mt-6 max-w-[405px] text-[14px] leading-7 text-[#687871]">Built for the middle of the work: when you have three PDFs open, a half-formed question, and a deadline that is suddenly much closer than expected.</p>
            <button onClick={() => setLocation('/console')} className="focus-ring mt-8 flex items-center gap-2 text-[13px] font-semibold text-[#29475a] transition hover:text-[#b56f4b]" data-testid="button-see-workspace">See the workspace <ChevronRight size={15} /></button>
          </div>
          <div className="relative rounded-[5px] border border-[#29475a]/12 bg-[#fffaf2] p-3 shadow-[0_20px_50px_rgba(46,62,66,.09)] sm:p-5">
            <div className="flex items-center justify-between border-b border-[#29475a]/10 pb-4"><div className="flex items-center gap-2"><div className="h-2 w-2 rounded-full bg-[#c57950]" /><span className="mono text-[9px] uppercase tracking-[.15em] text-[#80908a]">workspace / synthesis</span></div><MoreHorizontal size={17} className="text-[#91a099]" /></div>
            <div className="grid gap-5 py-5 sm:grid-cols-[1fr_1.15fr]">
              <div className="rounded-[3px] border border-[#d9cbb9] bg-[#f4ecdf] p-4"><div className="mono text-[9px] text-[#b56f4b]">YOUR SOURCES</div><div className="mt-4 space-y-2"><div className="flex items-center gap-2 rounded-[3px] bg-[#fffaf2]/75 p-2"><span className="flex h-6 w-6 items-center justify-center rounded-[2px] bg-[#c57950] text-[8px] font-bold text-[#fffaf2]">PDF</span><span className="truncate text-[10px] font-medium text-[#53646a]">Your uploaded paper</span></div></div><div className="mt-6 border-t border-[#d2c2ad] pt-3 text-[10px] text-[#7c8880]">Upload to start</div></div>
              <div className="rounded-[3px] border border-[#d6d9d1] bg-[#f9f8f3] p-4"><div className="flex items-center justify-between"><span className="mono text-[9px] text-[#b56f4b]">STRUCTURED PAPER</span><Quote size={15} className="text-[#c57950]" /></div><p className="serif mt-5 text-[23px] leading-[1.05] text-[#29475a]">Pages become sections and chunks.</p><div className="mt-7 h-2 w-full rounded-full bg-[#e3e2da]"><div className="h-full w-[72%] rounded-full bg-[#6f8793]" /></div><div className="mt-2 flex justify-between text-[9px] text-[#84908a]"><span>processing stages</span><span>PDF → chunks</span></div><div className="mt-6 flex gap-2"><span className="rounded-full bg-[#e8d7c0] px-2 py-1 text-[9px] text-[#8e5b40]">sections</span><span className="rounded-full bg-[#dbe5e3] px-2 py-1 text-[9px] text-[#5d7473]">chunks</span></div></div>
            </div>
          </div>
        </section>

        <section id="principles" className="bg-[#29475a] text-[#f7f1e7]">
          <div className="mx-auto grid max-w-[1240px] gap-12 px-5 py-20 sm:px-8 lg:grid-cols-[.8fr_1.2fr] lg:px-12 lg:py-24">
            <div><span className="mono text-[10px] uppercase tracking-[.2em] text-[#d6ad72]">Our north star</span><h2 className="serif mt-4 text-5xl leading-[.95] tracking-[-.04em]">Clarity is<br />a form of care.</h2></div>
            <div className="grid gap-8 sm:grid-cols-2">{[['Stay close to the source', 'We make it easy to see where an idea came from, and where it stops.'], ['Make complexity legible', 'Good explanations do not flatten nuance. They give it a shape you can hold.'], ['Leave room for thinking', 'The interface should recede so your questions can come forward.'], ['Work in public, privately', 'A quiet place to form a point of view before you share it.']].map(([title, copy], i) => <div key={title} className="border-t border-[#f7f1e7]/20 pt-4"><span className="mono text-[10px] text-[#d6ad72]">0{i + 1}</span><h3 className="mt-5 text-[15px] font-semibold">{title}</h3><p className="mt-2 text-[13px] leading-6 text-[#bdc8c4]">{copy}</p></div>)}</div>
          </div>
        </section>
      </main>
      <footer className="mx-auto flex max-w-[1240px] flex-col gap-4 px-5 py-8 text-[11px] text-[#7a8880] sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-12"><Logo /><span>For the curious, the careful, and the almost-done.</span><span className="mono text-[10px]">© 2025 paperintel</span></footer>
    </div>
  );
}

function Sidebar({ papers, onUpload, onClear }: { papers: Paper[]; onUpload: () => void; onClear: () => void }) {
  const [location] = useLocation();
  return (
    <aside className="hidden w-[245px] shrink-0 flex-col bg-[#29475a] text-[#f4eee4] lg:flex">
      <div className="px-6 pb-8 pt-7"><Link href="/" className="focus-ring inline-flex rounded-lg" data-testid="link-console-logo"><Logo inverse /></Link></div>
      <div className="px-3">
        <div className="mono mb-2 px-3 text-[9px] uppercase tracking-[.18em] text-[#91aaa9]">Workspace</div>
        <Link href="/console" className={`focus-ring mb-1 flex items-center gap-3 rounded-[4px] px-3 py-2.5 text-[12px] ${location === '/console' ? 'bg-[#38596a] text-[#fffaf2]' : 'text-[#bfcbc7] hover:bg-[#345366]'}`} data-testid="link-workspace-nav"><BrainCircuit size={15} /> Reading desk</Link>
        <button onClick={onUpload} className="focus-ring flex w-full items-center gap-3 rounded-[4px] px-3 py-2.5 text-left text-[12px] text-[#bfcbc7] hover:bg-[#345366]" data-testid="button-sidebar-upload"><Plus size={15} /> Add papers</button>
      </div>
      <div className="mt-8 flex-1 overflow-auto px-3 scrollbar-thin">
        <div className="mb-2 flex items-center justify-between px-3"><span className="mono text-[9px] uppercase tracking-[.18em] text-[#91aaa9]">In this session</span>{papers.length > 0 && <button onClick={onClear} className="focus-ring text-[10px] text-[#91aaa9] hover:text-[#e8bb84]" data-testid="button-clear-papers">Clear</button>}</div>
        {papers.length === 0 ? <div className="mx-3 rounded border border-dashed border-[#6c8490] p-4 text-[11px] leading-5 text-[#aebfbb]">Your reading list is empty.<br />Add a paper to begin.</div> : papers.map(p => <div key={p.id} className="group flex items-start gap-2.5 rounded-[4px] px-3 py-3 hover:bg-[#345366]"><span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-[2px] text-[8px] font-bold text-[#29475a]" style={{ background: p.accent }}>{p.initials}</span><div className="min-w-0"><p className="truncate text-[11px] text-[#e8ece5]">{p.shortTitle}</p><p className="mt-1 text-[9px] text-[#9cb0ae]">{p.year} · {p.pages}</p></div></div>)}
      </div>
      <div className="border-t border-[#547080] px-6 py-5"><button onClick={() => window.alert('Settings are available in the full product.')} className="focus-ring flex items-center gap-3 text-[11px] text-[#bac9c4] hover:text-[#fffaf2]" data-testid="button-settings"><Settings2 size={15} /> Preferences</button><div className="mt-5 flex items-center gap-2"><div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#d6ad72] text-[10px] font-bold text-[#29475a]">AM</div><div><p className="text-[10px] text-[#e7ece5]">Alex Morgan</p><p className="text-[9px] text-[#91aaa9]">Research session</p></div></div></div>
    </aside>
  );
}

function UploadTray({ open, onClose, onAdd, status, error }: { open: boolean; onClose: () => void; onAdd: (file: File) => void; status: string; error: string }) {
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault(); setDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) onAdd(file);
  }
  return <AnimatePresence>{open && <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }} className="absolute right-3 top-16 z-30 w-[min(380px,calc(100vw-24px))] rounded-[7px] border border-[#d5c9b8] bg-[#fffaf2] p-5 shadow-[0_18px_45px_rgba(44,58,62,.18)]" data-testid="panel-upload">
    <div className="flex items-start justify-between"><div><p className="serif text-[25px] tracking-[-.03em] text-[#29475a]">Add to your desk</p><p className="mt-1 text-[11px] text-[#7b8881]">PDFs work best · up to 20MB each</p></div><button onClick={onClose} className="focus-ring rounded p-1 text-[#81908b] hover:bg-[#eee4d6]" aria-label="Close upload panel" data-testid="button-close-upload"><X size={16} /></button></div>
    <div onDragOver={event => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={handleDrop} className={`mt-5 rounded-[5px] border border-dashed p-7 text-center transition-colors ${dragging ? 'border-[#c57950] bg-[#f6e9d8]' : 'border-[#cfc2b0] bg-[#f7f1e8]'}`} data-testid="dropzone-papers">
      <CloudUpload size={26} className="mx-auto text-[#b76e4a]" strokeWidth={1.5} /><p className="mt-3 text-[12px] font-semibold text-[#425c68]">{dragging ? 'Release to add' : 'Drop papers here'}</p><p className="mt-1 text-[10px] text-[#8a948c]">or choose files from your computer</p>
      <input ref={fileRef} type="file" accept=".pdf,application/pdf" className="sr-only" onChange={event => { if (event.target.files?.[0]) onAdd(event.target.files[0]); event.target.value = ''; }} data-testid="input-paper-file" />
      <button onClick={() => fileRef.current?.click()} className="focus-ring mt-4 rounded-full border border-[#29475a]/20 bg-[#fffaf2] px-4 py-2 text-[11px] font-semibold text-[#29475a] hover:border-[#c57950]" data-testid="button-choose-file"><FolderOpen size={13} className="mr-1.5 inline" /> Choose PDF</button>
    </div>
    {status && <p className="mt-4 text-[10px] text-[#6e8a7f]" role="status">{status}</p>}
    {error && <p className="mt-4 text-[10px] leading-4 text-[#a55743]" role="alert">{error}</p>}
    <p className="mt-4 flex items-center gap-1.5 text-[10px] text-[#8b948e]"><ShieldCheck size={12} className="text-[#6e8a7f]" /> Files stay in this local session.</p>
  </motion.div>}</AnimatePresence>;
}

function PaperStrip({ papers, activeId, onSelect, onRemove, onUpload }: { papers: Paper[]; activeId?: string; onSelect: (id: string) => void; onRemove: (id: string) => void; onUpload: () => void }) {
  return <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
    {papers.map(p => <motion.div layout key={p.id} onClick={() => onSelect(p.id)} className={`flex min-w-[190px] cursor-pointer items-center gap-2 rounded-[4px] border px-2.5 py-2 shadow-[0_2px_8px_rgba(45,59,62,.04)] ${activeId === p.id ? 'border-[#c57950] bg-[#fffaf2]' : 'border-[#d9cdbd] bg-[#f8f1e7]'}`} data-testid={`card-selected-paper-${p.id}`}><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[2px] text-[8px] font-bold text-[#fffaf2]" style={{ background: p.accent }}>{p.initials}</span><div className="min-w-0 flex-1"><p className="truncate text-[10px] font-semibold text-[#425762]">{p.shortTitle}</p><p className="mt-0.5 text-[9px] text-[#84908b]">{p.pages} · {p.data.sections.length} sections</p></div><button onClick={event => { event.stopPropagation(); onRemove(p.id); }} className="focus-ring rounded p-1 text-[#9da49d] hover:bg-[#f0e4d6] hover:text-[#b56f4b]" aria-label={`Remove ${p.shortTitle}`} data-testid={`button-remove-paper-${p.id}`}><X size={13} /></button></motion.div>)}
    <button onClick={onUpload} className="focus-ring flex h-[47px] min-w-[104px] items-center justify-center gap-1.5 rounded-[4px] border border-dashed border-[#c9bcaa] text-[10px] font-semibold text-[#77847e] hover:border-[#c57950] hover:text-[#b56f4b]" data-testid="button-add-more-papers"><Plus size={13} /> Add paper</button>
  </div>;
}

function InsightRail({ papers }: { papers: Paper[] }) {
  return <aside className="hidden w-[268px] shrink-0 border-l border-[#ddd1c1] bg-[#f7f1e8] xl:block">
    <div className="px-5 py-6"><div className="flex items-center justify-between"><span className="mono text-[9px] uppercase tracking-[.18em] text-[#a66547]">Paper map</span><Network size={15} className="text-[#84958c]" /></div><div className="mt-6 rounded-[4px] border border-dashed border-[#d8c9b4] bg-[#f1e8da] p-5 text-[11px] leading-5 text-[#7d897f]">Relationships and comparison will appear after the analysis modules are connected.</div></div>
    <div className="border-t border-[#ddd1c1] px-5 py-6"><div className="flex items-center justify-between"><span className="mono text-[9px] uppercase tracking-[.18em] text-[#a66547]">Processed structure</span><Tag size={14} className="text-[#84958c]" /></div><div className="mt-4 space-y-3">{papers.map(paper => <div key={paper.id} className="text-[10px] text-[#65756f]"><div className="flex justify-between gap-2"><span className="truncate">{paper.shortTitle}</span><span>{paper.data.sections.length} sections</span></div><p className="mt-1 text-[9px] text-[#89938d]">{paper.data.chunks.length} chunks · {paper.data.total_pages} pages</p></div>)}</div></div>
    <div className="border-t border-[#ddd1c1] px-5 py-6"><div className="flex items-center justify-between"><span className="mono text-[9px] uppercase tracking-[.18em] text-[#a66547]">Source coverage</span><Highlighter size={14} className="text-[#84958c]" /></div><p className="mt-4 text-[11px] leading-5 text-[#7d897f]">Coverage scores are not available until the retrieval module is implemented.</p></div>
  </aside>;
}

function Overview({ papers }: { papers: Paper[] }) {
  const paper = papers[0];
  const data = paper?.data;
  const stages = [
    ['PDF uploaded', true], ['Text extraction / OCR', Boolean(data?.pages.length)], ['Text cleaning', Boolean(data?.pages.some(page => page.cleaned_text))],
    ['Sentence segmentation', Boolean(data?.pages.length)], ['Tokenization', Boolean(data?.pages.length)], ['Lemmatization', Boolean(data?.pages.length)],
    ['Section identification', Boolean(data?.sections.length)], ['Chunking', Boolean(data?.chunks.length)],
  ];
   return <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
    <div className="grid gap-5 xl:grid-cols-[1.35fr_.65fr]">
      <section className="rounded-[5px] border border-[#d9cdbd] bg-[#fffaf2] p-5 shadow-[0_3px_12px_rgba(45,59,62,.035)] sm:p-7"><div className="flex items-center justify-between"><div><span className="mono text-[9px] uppercase tracking-[.18em] text-[#b56f4b]">Paper overview</span><h2 className="serif mt-2 break-words text-[31px] leading-none tracking-[-.04em] text-[#29475a]">{paper?.title ?? 'No paper selected'}</h2></div><span className="rounded-full bg-[#e4eee9] px-2.5 py-1 text-[9px] font-semibold text-[#56736e]">processed document</span></div><p className="mt-6 max-w-[670px] text-[14px] leading-7 text-[#54666c]">{paper ? 'The backend has preserved this document as pages, sections, and chunks. Analysis and question answering will be added in later modules.' : 'Upload a research paper to begin analysis.'}</p><div className="mt-7 grid gap-3 border-t border-[#e6dccd] pt-5 sm:grid-cols-3">{[[String(data?.total_pages ?? 0), 'pages indexed'], [String(data?.sections.length ?? 0), 'sections'], [String(data?.chunks.length ?? 0), 'chunks']].map(([value, label]) => <div key={label}><p className="serif text-3xl text-[#29475a]">{value}</p><p className="mt-1 text-[10px] text-[#89938d]">{label}</p></div>)}</div></section>
      <section className="rounded-[5px] bg-[#29475a] p-5 text-[#f8f2e7] shadow-[0_8px_22px_rgba(41,71,90,.12)] sm:p-7"><div className="flex items-center gap-2 text-[#d6ad72]"><Quote size={16} /><span className="mono text-[9px] uppercase tracking-[.17em]">Analysis status</span></div><p className="serif mt-10 text-[28px] leading-[1.04] tracking-[-.03em]">{paper ? 'Document structure is ready.' : 'Upload a paper to begin.'}</p><div className="mt-10 flex items-center gap-2 text-[10px] text-[#b9c7c2]"><span className="h-1.5 w-1.5 rounded-full bg-[#d6ad72]" /> {paper ? 'PDF processing complete' : 'No sources selected'}</div></section>
    </div>
    <section className="rounded-[5px] border border-[#d9cdbd] bg-[#fffaf2] p-5 sm:p-7"><div className="flex items-center justify-between"><div><span className="mono text-[9px] uppercase tracking-[.18em] text-[#b56f4b]">NLP pipeline</span><h2 className="serif mt-2 text-[28px] tracking-[-.04em] text-[#29475a]">From PDF to structured paper</h2></div><span className="text-[10px] text-[#89938d]">Module 1</span></div><div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{stages.map(([label, complete], index) => <div key={label as string} className="flex items-center gap-2 rounded-[4px] border border-[#e6dccd] bg-[#faf4eb] px-3 py-3 text-[11px] text-[#53666c]"><span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] ${complete ? 'bg-[#dbe8df] text-[#55766c]' : 'bg-[#eee5d8] text-[#9b9388]'}`}>{complete ? '✓' : index + 1}</span>{label as string}</div>)}</div><p className="mt-5 text-[10px] leading-5 text-[#89938d]">Implemented: extraction, cleaning, segmentation, tokenization, lemmatization, section detection, and chunking. Embeddings, retrieval, summarization, Q&amp;A, and comparison are planned for later modules.</p></section>
    <section className="rounded-[5px] border border-[#d9cdbd] bg-[#fffaf2] p-5 sm:p-7"><div className="flex items-center justify-between"><div><span className="mono text-[9px] uppercase tracking-[.18em] text-[#b56f4b]">Sections</span><h2 className="serif mt-2 text-[28px] tracking-[-.04em] text-[#29475a]">What the processor found</h2></div><span className="text-[10px] text-[#89938d]">{data?.sections.length ?? 0} detected</span></div>{data?.sections.length ? <div className="mt-6 divide-y divide-[#e6dccd]">{data.sections.slice(0, 8).map(section => <div key={`${section.section_name}-${section.page_start}`} className="grid gap-2 py-4 sm:grid-cols-[190px_1fr]"><h3 className="text-[13px] font-semibold text-[#405967]">{section.section_name}</h3><p className="text-[12px] leading-5 text-[#74817c]">Pages {section.page_start}–{section.page_end} · {section.text.slice(0, 220)}{section.text.length > 220 ? '…' : ''}</p></div>)}</div> : <p className="mt-5 text-[12px] text-[#7f8b84]">No sections detected in this document.</p>}</section>
  </motion.div>;
}

function Methods() {
  return <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="grid gap-5 lg:grid-cols-[1.2fr_.8fr]"><section className="rounded-[5px] border border-[#d9cdbd] bg-[#fffaf2] p-5 sm:p-7"><span className="mono text-[9px] uppercase tracking-[.18em] text-[#b56f4b]">Method anatomy</span><h2 className="serif mt-2 text-3xl tracking-[-.04em] text-[#29475a]">Analysis not available yet</h2><p className="mt-6 text-[12px] leading-6 text-[#74817c]">Methodology extraction belongs to the next NLP analysis module. The current backend has preserved the document structure for that work.</p></section><div className="space-y-5"><section className="rounded-[5px] border border-[#d9cdbd] bg-[#f0e5d4] p-5 sm:p-7"><div className="flex items-center gap-2"><FlaskConical size={16} className="text-[#b56f4b]" /><span className="mono text-[9px] uppercase tracking-[.18em] text-[#a66547]">Current output</span></div><p className="mt-6 text-[12px] leading-6 text-[#718079]">Pages, cleaned text, sections, and chunks are available in the Overview tab.</p></section><section className="rounded-[5px] border border-[#d9cdbd] bg-[#fffaf2] p-5 sm:p-7"><span className="mono text-[9px] uppercase tracking-[.18em] text-[#b56f4b]">Next module</span><p className="mt-4 text-[12px] leading-6 text-[#718079]">TF-IDF, named entities, keywords, and research information extraction.</p></section></div></motion.div>;
  return <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="grid gap-5 lg:grid-cols-[1.2fr_.8fr]">
    <section className="rounded-[5px] border border-[#d9cdbd] bg-[#fffaf2] p-5 sm:p-7"><span className="mono text-[9px] uppercase tracking-[.18em] text-[#b56f4b]">Method anatomy</span><h2 className="serif mt-2 text-3xl tracking-[-.04em] text-[#29475a]">How the studies make their case</h2><div className="mt-8 space-y-0">{[['01', 'Problem framing', 'The authors identify sequence modeling as a bottleneck: recurrence makes long-range relationships expensive to learn.', 'premise'], ['02', 'Intervention', 'A self-attention mechanism gives each token a weighted view of every other token in the same sequence.', 'mechanism'], ['03', 'Evaluation', 'Translation, parsing, and language modeling benchmarks test whether the approach generalizes beyond one task.', 'evidence']].map(([number, title, copy, label]) => <div key={number} className="relative flex gap-4 pb-8 last:pb-0"><div className="relative flex w-7 shrink-0 justify-center"><span className="z-10 flex h-7 w-7 items-center justify-center rounded-full bg-[#e8d7c0] mono text-[10px] text-[#8d5e43]">{number}</span><span className="absolute top-7 h-full w-px bg-[#ddcfbd] last:hidden" /></div><div><span className="rounded-full bg-[#e3ece8] px-2 py-1 text-[9px] text-[#5f7772]">{label}</span><h3 className="mt-3 text-[14px] font-semibold text-[#425b66]">{title}</h3><p className="mt-2 max-w-[590px] text-[12px] leading-6 text-[#74817c]">{copy}</p></div></div>)}</div></section>
    <div className="space-y-5"><section className="rounded-[5px] border border-[#d9cdbd] bg-[#f0e5d4] p-5 sm:p-7"><div className="flex items-center gap-2"><FlaskConical size={16} className="text-[#b56f4b]" /><span className="mono text-[9px] uppercase tracking-[.18em] text-[#a66547]">Design notes</span></div><div className="mt-6 space-y-4">{[['Dataset', 'WMT 2014 translation benchmarks'], ['Baseline', 'Strong recurrent and convolutional models'], ['Primary metric', 'BLEU score + training time']].map(([a,b]) => <div key={a} className="flex justify-between gap-4 border-b border-[#d7c5ad] pb-3 text-[11px]"><span className="text-[#8a938b]">{a}</span><span className="text-right font-medium text-[#53656a]">{b}</span></div>)}</div></section><section className="rounded-[5px] border border-[#d9cdbd] bg-[#fffaf2] p-5 sm:p-7"><span className="mono text-[9px] uppercase tracking-[.18em] text-[#b56f4b]">Read with care</span><p className="mt-4 text-[12px] leading-6 text-[#718079]">Benchmark performance is not the same as understanding. The papers establish a strong engineering result; they do not settle how representations encode meaning.</p></section></div>
  </motion.div>;
}

function Findings() {
  return <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5"><section className="rounded-[5px] border border-[#d9cdbd] bg-[#fffaf2] p-5 sm:p-7"><span className="mono text-[9px] uppercase tracking-[.18em] text-[#b56f4b]">Findings at a glance</span><h2 className="serif mt-2 text-3xl tracking-[-.04em] text-[#29475a]">Analysis not available yet</h2><p className="mt-6 text-[12px] leading-6 text-[#74817c]">The current backend module processes and structures PDF content. It does not extract findings, metrics, or claims yet.</p></section><section className="rounded-[5px] bg-[#29475a] p-6 text-[#f7f1e7]"><span className="mono text-[9px] uppercase tracking-[.18em] text-[#d6ad72]">Next NLP / AI stages</span><p className="mt-5 text-[12px] leading-6 text-[#bdc8c4]">TF-IDF + NER, embeddings, vector retrieval, summarization, Q&amp;A, and paper comparison.</p></section></motion.div>;
  const bars = [42, 58, 54, 74, 66, 87, 78];
  return <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5"><section className="rounded-[5px] border border-[#d9cdbd] bg-[#fffaf2] p-5 sm:p-7"><div className="flex flex-wrap items-end justify-between gap-4"><div><span className="mono text-[9px] uppercase tracking-[.18em] text-[#b56f4b]">Findings at a glance</span><h2 className="serif mt-2 text-3xl tracking-[-.04em] text-[#29475a]">The evidence leans one way</h2></div><div className="text-right"><p className="serif text-3xl text-[#29475a]">+1.8</p><p className="text-[10px] text-[#89938d]">BLEU over prior best</p></div></div><div className="mt-9 flex h-[175px] items-end gap-2 border-b border-[#cfc5b6] px-2 sm:gap-4">{bars.map((height, i) => <div key={i} className="group flex flex-1 flex-col items-center gap-2"><div className="relative w-full max-w-[42px] rounded-t-[3px] bg-[#6f8793] transition-all group-hover:bg-[#c57950]" style={{ height: `${height}%` }}><span className="absolute -top-5 left-1/2 -translate-x-1/2 text-[9px] text-[#73827d] opacity-0 transition-opacity group-hover:opacity-100">{(22 + i * 1.8).toFixed(1)}</span></div><span className="mono text-[8px] text-[#a0a59e]">{['RNN', 'CNN', 'LSTM', 'T-1', 'T-2', 'T-3', 'Ours'][i]}</span></div>)}</div><div className="mt-5 flex flex-wrap items-center gap-5 text-[10px] text-[#7b8780]"><span className="flex items-center gap-2"><span className="h-2 w-2 rounded-sm bg-[#6f8793]" /> benchmark score</span><span className="flex items-center gap-2"><span className="h-2 w-2 rounded-sm bg-[#c57950]" /> hover to inspect</span></div></section><div className="grid gap-5 md:grid-cols-2"><section className="rounded-[5px] bg-[#29475a] p-6 text-[#f7f1e7]"><span className="mono text-[9px] uppercase tracking-[.18em] text-[#d6ad72]">Most surprising</span><p className="serif mt-5 text-2xl leading-[1.08]">Quality improves without reading left to right.</p><p className="mt-5 text-[12px] leading-5 text-[#bdc8c4]">The model attends to the whole sequence in parallel, which is the conceptual break these results make visible.</p></section><section className="rounded-[5px] border border-[#d9cdbd] bg-[#fffaf2] p-6"><span className="mono text-[9px] uppercase tracking-[.18em] text-[#b56f4b]">Open question</span><p className="serif mt-5 text-2xl leading-[1.08] text-[#29475a]">What gets lost at longer context?</p><p className="mt-5 text-[12px] leading-5 text-[#74817c]">The next generation of work asks whether the same mechanism stays reliable as sequences and datasets grow.</p></section></div></motion.div>;
}

function CompareView({ papers }: { papers: Paper[] }) {
  const left = papers[0];
  const right = papers[1];
  if (!left || !right) return <div className="rounded-[5px] border border-dashed border-[#cfc2b0] bg-[#faf4eb] px-6 py-16 text-center"><GitCompare size={28} className="mx-auto text-[#bf9d7d]" /><h3 className="serif mt-4 text-2xl text-[#29475a]">Comparison needs two papers.</h3><p className="mx-auto mt-2 max-w-[320px] text-[12px] leading-5 text-[#7f8b84]">Upload and select a second paper to compare source structure. Semantic comparison is not available yet.</p></div>;
  return <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5"><section className="rounded-[5px] border border-[#d9cdbd] bg-[#fffaf2] p-5 sm:p-7"><div className="flex flex-wrap items-end justify-between gap-4"><div><span className="mono text-[9px] uppercase tracking-[.18em] text-[#b56f4b]">Side by side</span><h2 className="serif mt-2 text-3xl tracking-[-.04em] text-[#29475a]">Where the studies meet</h2></div><span className="rounded-full bg-[#e4eee9] px-2.5 py-1 text-[9px] font-semibold text-[#56736e]">{papers.length} sources selected</span></div><div className="mt-8 overflow-x-auto"><div className="min-w-[580px]"><div className="grid grid-cols-[.7fr_1fr_1fr] border-b border-[#d8cdbd] pb-3"><span className="mono text-[9px] uppercase tracking-[.15em] text-[#9b9d93]">Dimension</span><span className="text-[12px] font-semibold text-[#c57950]">{left.shortTitle}</span><span className="text-[12px] font-semibold text-[#6f8793]">{right.shortTitle}</span></div>{[['Core idea', 'Learn relationships with attention', 'Pre-train both sides of context'], ['Training signal', 'Sequence-to-sequence translation', 'Masked language modeling'], ['Best at', 'Long-range dependencies', 'Rich word representations'], ['Trade-off', 'More compute per layer', 'Fine-tuning task dependence']].map(([dim, l, r]) => <div key={dim} className="grid grid-cols-[.7fr_1fr_1fr] border-b border-[#e6dccd] py-4"><span className="text-[11px] font-semibold text-[#77847e]">{dim}</span><span className="pr-5 text-[11px] leading-5 text-[#5d7077]">{l}</span><span className="pr-5 text-[11px] leading-5 text-[#5d7077]">{r}</span></div>)}</div></div></section><section className="rounded-[5px] bg-[#f0e5d4] p-5 sm:p-7"><div className="flex items-center gap-2"><GitCompare size={16} className="text-[#b56f4b]" /><span className="mono text-[9px] uppercase tracking-[.18em] text-[#a66547]">Synthesis</span></div><p className="serif mt-5 max-w-[780px] text-[26px] leading-[1.08] tracking-[-.03em] text-[#29475a]">“{left.shortTitle}” changes the <em className="font-normal text-[#b56f4b]">shape</em> of the problem; “{right.shortTitle}” changes the information available to solve it.</p></section></motion.div>;
}

function ChatPanel({ papers }: { papers: Paper[] }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [value, setValue] = useState('');
  const [thinking, setThinking] = useState(false);
  useEffect(() => { setMessages([]); setValue(''); setThinking(false); }, [papers[0]?.id]);
  function sendMessage(text = value) {
    const clean = text.trim(); if (!clean || thinking || !papers.length) return;
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', text: clean }]); setValue(''); setThinking(true);
    window.setTimeout(() => { setMessages(prev => [...prev, { id: Date.now() + 1, role: 'assistant', text: 'Analysis not available yet — this question-answering module will be added in the next backend phase.' }]); setThinking(false); }, 350);
  }
  return <section className="flex min-h-[355px] flex-col rounded-[5px] border border-[#d9cdbd] bg-[#fffaf2] shadow-[0_3px_12px_rgba(45,59,62,.035)]"><div className="flex items-center justify-between border-b border-[#e6dccd] px-5 py-4"><div className="flex items-center gap-2.5"><div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#e8d7c0] text-[#a66547]"><MessageCircle size={14} /></div><div><h2 className="text-[12px] font-semibold text-[#405966]">Ask your papers</h2><p className="text-[9px] text-[#89938d]">Answers stay close to the source</p></div></div><span className="flex items-center gap-1.5 text-[9px] text-[#799087]"><span className="h-1.5 w-1.5 rounded-full bg-[#7da18d]" /> ready</span></div><div className="scrollbar-thin flex-1 space-y-4 overflow-y-auto px-5 py-5">{messages.map(message => <div key={message.id} className={`flex gap-2.5 ${message.role === 'user' ? 'justify-end' : ''}`} data-testid={`message-${message.role}-${message.id}`}><div className={`max-w-[88%] rounded-[5px] px-3.5 py-3 ${message.role === 'user' ? 'bg-[#29475a] text-[#f7f1e7]' : 'bg-[#f1e8da] text-[#53666c]'}`}><p className="text-[11px] leading-5">{message.text}</p>{message.cite && <p className={`mt-2 border-t pt-2 text-[9px] ${message.role === 'user' ? 'border-[#577080] text-[#b8c7c2]' : 'border-[#ddd0bd] text-[#9a745c]'}`}>{message.cite}</p>}</div></div>)}{thinking && <div className="flex items-center gap-2 text-[10px] text-[#8a958e]" data-testid="status-chat-thinking"><span className="flex gap-1"><i className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#c57950]" /><i className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#c57950] [animation-delay:150ms]" /><i className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#c57950] [animation-delay:300ms]" /></span> Reading across sources…</div>}</div><div className="border-t border-[#e6dccd] p-3"><div className="flex gap-2 overflow-x-auto pb-2 scrollbar-thin">{SUGGESTIONS.map(suggestion => <button key={suggestion} onClick={() => sendMessage(suggestion)} className="focus-ring shrink-0 rounded-full border border-[#ded2c3] px-2.5 py-1.5 text-[9px] text-[#71817c] hover:border-[#c57950] hover:text-[#a66547]" data-testid={`button-suggestion-${suggestion.slice(0, 8).replace(/\s/g, '-')}`}>{suggestion}</button>)}</div><form onSubmit={event => { event.preventDefault(); sendMessage(); }} className="flex items-center gap-2 rounded-[4px] border border-[#d6c9b8] bg-[#f9f4eb] px-3 py-1.5"><input value={value} onChange={event => setValue(event.target.value)} placeholder="Ask a question about your sources…" className="focus-ring min-w-0 flex-1 bg-transparent py-1.5 text-[11px] text-[#405966] outline-none placeholder:text-[#9aa099]" aria-label="Ask a question about your sources" data-testid="input-chat-question" /><button type="submit" disabled={!value.trim() || thinking} className="focus-ring flex h-7 w-7 shrink-0 items-center justify-center rounded-[3px] bg-[#29475a] text-[#f7f1e7] transition hover:bg-[#c57950] disabled:cursor-not-allowed disabled:opacity-35" aria-label="Send question" data-testid="button-send-question"><Send size={13} /></button></form></div></section>;
}

function Console() {
  const [selected, setSelected] = useState<Paper[]>([]);
  const [activeId, setActiveId] = useState<string>();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [mode, setMode] = useState<(typeof MODES)[number]['id']>('overview');
  const [toast, setToast] = useState('');
  const [uploadStatus, setUploadStatus] = useState('');
  const [uploadError, setUploadError] = useState('');
  const activePaper = selected.find(paper => paper.id === activeId);
  async function addPaper(file: File) {
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      setUploadError('Only PDF files are supported.');
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setUploadError('This file is larger than the 20MB limit.');
      return;
    }
    setUploadError('');
    setUploadStatus('Uploading paper...');
    try {
      setUploadStatus('Processing paper...');
      const processed = await uploadAndProcessPaper(file);
      const nextPaper = toPaper(processed, selected.length);
      setSelected(previous => [...previous.filter(paper => paper.id !== nextPaper.id), nextPaper]);
      setActiveId(nextPaper.id);
      setUploadStatus('Paper processed successfully.');
      setUploadOpen(false);
    } catch (error) {
      setUploadStatus('');
      setUploadError(error instanceof Error ? error.message : 'Unable to process this paper. Please try again.');
    }
  }
  function removePaper(id: string) { setSelected(previous => previous.filter(paper => paper.id !== id)); if (activeId === id) setActiveId(selected.find(paper => paper.id !== id)?.id); if (mode === 'compare' && selected.length <= 2) setMode('overview'); }
  function clearPapers() { setSelected([]); setActiveId(undefined); setMode('overview'); }
  function notify(message: string) { setToast(message); window.setTimeout(() => setToast(''), 2200); }
  const currentContent = mode === 'methods' ? <Methods /> : mode === 'findings' ? <Findings /> : mode === 'compare' ? <CompareView papers={selected} /> : <Overview papers={activePaper ? [activePaper] : []} />;
  return <div className="paper-noise flex min-h-[100dvh] bg-[#f6f1e8] text-[#29475a]">
    <Sidebar papers={selected} onUpload={() => setUploadOpen(true)} onClear={clearPapers} />
    <div className="min-w-0 flex-1">
      <header className="relative z-20 flex h-[72px] items-center justify-between border-b border-[#ddd1c1] bg-[#f8f2e9]/95 px-4 backdrop-blur sm:px-7">
        <div className="flex items-center gap-3"><button onClick={() => setMobileMenu(true)} className="focus-ring rounded p-1 text-[#60736f] lg:hidden" aria-label="Open navigation" data-testid="button-open-mobile-menu"><Menu size={20} /></button><div><div className="flex items-center gap-2"><span className="mono text-[9px] uppercase tracking-[.16em] text-[#a66547]">Reading desk</span><span className="rounded-full bg-[#e4eee9] px-2 py-0.5 text-[8px] font-semibold text-[#638078]">LOCAL DEMO</span></div><h1 className="mt-1 text-[15px] font-semibold tracking-[-.02em] text-[#405b67]">Synthesis session</h1></div></div>
        <div className="flex items-center gap-2"><button onClick={() => notify('Search is scoped to your selected papers.')} className="focus-ring hidden items-center gap-2 rounded-full border border-[#d9cdbd] px-3 py-2 text-[10px] text-[#81908a] sm:flex" data-testid="button-search"><Search size={13} /> Search desk</button><button onClick={() => setUploadOpen(!uploadOpen)} className="focus-ring flex items-center gap-2 rounded-full bg-[#29475a] px-3.5 py-2 text-[10px] font-semibold text-[#f7f1e7] transition hover:bg-[#c57950]" data-testid="button-header-upload"><Plus size={14} /> <span className="hidden sm:inline">Add paper</span></button></div>
      </header>
      <UploadTray open={uploadOpen} onClose={() => { setUploadOpen(false); setUploadError(''); }} onAdd={addPaper} status={uploadStatus} error={uploadError} />
      <main className="mx-auto max-w-[1380px] px-4 py-5 sm:px-7 sm:py-7">
        <PaperStrip papers={selected} activeId={activeId} onSelect={setActiveId} onRemove={removePaper} onUpload={() => setUploadOpen(true)} />
        <div className="mt-7 flex flex-col gap-7 xl:flex-row">
          <div className="min-w-0 flex-1">
            <div className="mb-5 flex items-end justify-between gap-4"><div><span className="mono text-[9px] uppercase tracking-[-.18em] text-[#a66547]">Synthesis / {selected.length} {selected.length === 1 ? 'source' : 'sources'}</span><h2 className="serif mt-2 text-[35px] leading-none tracking-[-.045em] text-[#29475a] sm:text-[43px]">Make sense of it.</h2></div><button onClick={() => notify('Saved to your local reading notes.')} className="focus-ring hidden items-center gap-1.5 rounded-full border border-[#d7cabb] px-3 py-2 text-[10px] font-semibold text-[#71817c] hover:border-[#c57950] hover:text-[#b56f4b] sm:flex" data-testid="button-save-session"><Check size={13} /> Save session</button></div>
            <div className="scrollbar-thin mb-5 flex gap-1 overflow-x-auto border-b border-[#ddd1c1]">{MODES.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => setMode(id)} className={`focus-ring flex shrink-0 items-center gap-2 border-b-2 px-3 py-3 text-[11px] font-semibold transition ${mode === id ? 'border-[#c57950] text-[#b56f4b]' : 'border-transparent text-[#81908a] hover:text-[#536b73]'}`} data-testid={`button-mode-${id}`}><Icon size={14} /> {label}{id === 'compare' && selected.length < 2 && <span className="mono text-[8px] opacity-60">2+</span>}</button>)}</div>
            {selected.length === 0 ? <div className="rounded-[5px] border border-dashed border-[#cfc2b0] bg-[#faf4eb] px-6 py-16 text-center"><FileText size={28} className="mx-auto text-[#bf9d7d]" /><h3 className="serif mt-4 text-2xl text-[#29475a]">A clear desk is a good start.</h3><p className="mx-auto mt-2 max-w-[300px] text-[12px] leading-5 text-[#7f8b84]">Add a PDF or choose a sample paper to begin asking questions.</p><button onClick={() => setUploadOpen(true)} className="focus-ring mt-6 rounded-full bg-[#29475a] px-4 py-2.5 text-[11px] font-semibold text-[#f7f1e7] hover:bg-[#c57950]" data-testid="button-empty-add-paper"><Upload size={13} className="mr-1.5 inline" /> Add a paper</button></div> : currentContent}
            <div className="mt-6"><ChatPanel papers={activePaper ? [activePaper] : []} /></div>
          </div>
          <InsightRail papers={selected} />
        </div>
      </main>
    </div>
    <AnimatePresence>{mobileMenu && <><motion.button initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setMobileMenu(false)} className="fixed inset-0 z-40 bg-[#182d3b]/35 lg:hidden" aria-label="Close navigation overlay" data-testid="button-close-mobile-overlay" /><motion.aside initial={{ x: -280 }} animate={{ x: 0 }} exit={{ x: -280 }} className="fixed inset-y-0 left-0 z-50 flex w-[270px] flex-col bg-[#29475a] text-[#f4eee4] lg:hidden"><div className="flex items-center justify-between px-6 pb-8 pt-7"><Link href="/" className="focus-ring rounded-lg" data-testid="link-mobile-logo"><Logo inverse /></Link><button onClick={() => setMobileMenu(false)} className="focus-ring rounded p-1 text-[#b8c7c2]" aria-label="Close navigation" data-testid="button-close-mobile-menu"><X size={18} /></button></div><div className="px-3"><span className="mono px-3 text-[9px] uppercase tracking-[.18em] text-[#91aaa9]">Workspace</span><button onClick={() => { setMobileMenu(false); setUploadOpen(true); }} className="focus-ring mt-3 flex w-full items-center gap-3 rounded-[4px] px-3 py-2.5 text-left text-[12px] font-medium text-[#bfcbc7] hover:bg-[#345366]" data-testid="button-mobile-upload"><Plus size={15} /> Add papers</button></div><div className="mt-7 flex-1 px-6 text-[11px] leading-6 text-[#aebfbb]">A focused desk for the papers you are trying to understand.</div></motion.aside></>}</AnimatePresence>
    <AnimatePresence>{toast && <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }} className="fixed bottom-5 left-1/2 z-50 -translate-x-1/2 rounded-full bg-[#29475a] px-4 py-2.5 text-[11px] font-medium text-[#f7f1e7] shadow-lg" role="status" data-testid="status-toast">{toast}</motion.div>}</AnimatePresence>
  </div>;
}

function Router() {
  return <ErrorBoundary><Switch><Route path="/" component={Landing} /><Route path="/console" component={Console} /><Route component={NotFound} /></Switch></ErrorBoundary>;
}

const queryClient = new QueryClient();

function App() {
  return <QueryClientProvider client={queryClient}><TooltipProvider><WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}><Router /></WouterRouter><Toaster /></TooltipProvider></QueryClientProvider>;
}

export default App;