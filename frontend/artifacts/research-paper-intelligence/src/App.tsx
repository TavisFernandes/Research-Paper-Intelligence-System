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
import { deletePaper, getHealth, listPapers, type Health, type PaperRow } from '@/lib/paper-api';
import { ChatPanel } from '@/features/ChatPanel';
import { CompareView } from '@/features/CompareView';
import { InsightsView } from '@/features/InsightsView';
import { OverviewView, SummaryView } from '@/features/SummaryView';
import { UploadPanel } from '@/features/UploadPanel';
import { Empty, ErrorNote, Loading, paperLabel } from '@/features/ui';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import NotFound from '@/pages/not-found';

const MODES = [
  { id: 'overview', label: 'Overview', icon: BookOpen },
  { id: 'summary', label: 'Summary', icon: FlaskConical },
  { id: 'compare', label: 'Compare', icon: GitCompare },
  { id: 'insights', label: 'Insights', icon: BarChart3 },
] as const;
type Mode = (typeof MODES)[number]['id'];

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

function Sidebar({ papers, activeId, onSelect, onUpload, onDelete }: { papers: PaperRow[]; activeId?: string; onSelect: (id: string) => void; onUpload: () => void; onDelete: (id: string) => void }) {
  return (
    <aside className="hidden w-[245px] shrink-0 flex-col bg-[#29475a] text-[#f4eee4] lg:flex">
      <div className="px-6 pb-8 pt-7"><Link href="/" className="focus-ring inline-flex rounded-lg" data-testid="link-console-logo"><Logo inverse /></Link></div>
      <div className="px-3">
        <div className="mono mb-2 px-3 text-[9px] uppercase tracking-[.18em] text-[#91aaa9]">Workspace</div>
        <Link href="/console" className="focus-ring mb-1 flex items-center gap-3 rounded-[4px] bg-[#38596a] px-3 py-2.5 text-[12px] text-[#fffaf2]"><BrainCircuit size={15} /> Reading desk</Link>
        <button onClick={onUpload} className="focus-ring flex w-full items-center gap-3 rounded-[4px] px-3 py-2.5 text-left text-[12px] text-[#bfcbc7] hover:bg-[#345366]" data-testid="button-sidebar-upload"><Plus size={15} /> Add papers</button>
      </div>
      <div className="scrollbar-thin mt-8 flex-1 overflow-auto px-3">
        <div className="mono mb-2 px-3 text-[9px] uppercase tracking-[.18em] text-[#91aaa9]">Library ({papers.length})</div>
        {papers.length === 0 ? <div className="mx-3 rounded border border-dashed border-[#6c8490] p-4 text-[11px] leading-5 text-[#aebfbb]">No papers yet.<br />Add a PDF to begin.</div> : papers.map(p => (
          <div key={p.paper_id} className={`group flex items-start gap-2 rounded-[4px] px-3 py-2.5 ${activeId === p.paper_id ? 'bg-[#38596a]' : 'hover:bg-[#345366]'}`}>
            <button onClick={() => onSelect(p.paper_id)} className="focus-ring min-w-0 flex-1 text-left"><span className="mono block text-[9px] text-[#91aaa9]">{p.paper_id}</span><span className="block truncate text-[11px] text-[#e8e1d3]">{paperLabel(p)}</span></button>
            <button onClick={() => onDelete(p.paper_id)} className="focus-ring rounded p-1 text-[#91aaa9] opacity-0 hover:text-[#e8bb84] focus:opacity-100 group-hover:opacity-100" aria-label={`Delete ${paperLabel(p)}`}><X size={12} /></button>
          </div>
        ))}
      </div>
    </aside>
  );
}

function HealthBadge() {
  const [health, setHealth] = useState<Health>();
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => { getHealth().then(setHealth).catch(() => setFailed(true)); }, []);
  const label = failed ? 'Backend offline' : !health ? 'Checking…' : health.status === 'ok' ? 'All systems ready' : 'Degraded';
  const tone = failed ? 'bg-[#f3d9d0] text-[#a55743]' : health?.status === 'ok' ? 'bg-[#dfece3] text-[#3f6b4d]' : 'bg-[#f3e6cf] text-[#8a6425]';
  return (
    <div className="relative">
      <button onClick={() => setOpen(o => !o)} className={`focus-ring rounded-full px-3 py-1.5 text-[10px] font-semibold ${tone}`} aria-expanded={open} data-testid="health-badge">{label}</button>
      {open && <div className="absolute right-0 top-9 z-40 w-[320px] rounded border border-[#d9cdbd] bg-[#fffaf2] p-4 text-[11px] leading-4 text-[#4d6068] shadow-lg" role="dialog">
        {failed && <p>The frontend cannot reach the API. Start the backend and check VITE_API_BASE_URL.</p>}
        {health && <><p className="mb-2 font-semibold text-[#29475a]">Vector store: {health.components.vector_store?.backend}{health.components.vector_store?.persistent ? ' (persistent)' : ' (not persistent)'} · Embeddings: {health.components.embeddings?.backend}</p>
          {health.warnings.length ? <ul className="list-disc space-y-1 pl-4">{health.warnings.map(w => <li key={w}>{w}</li>)}</ul> : <p>No warnings.</p>}</>}
      </div>}
    </div>
  );
}

function Console() {
  const [papers, setPapers] = useState<PaperRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [activeId, setActiveId] = useState<string>();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [mode, setMode] = useState<Mode>('overview');
  const [scopeAll, setScopeAll] = useState(true);

  async function refresh(select?: string) {
    try {
      const rows = await listPapers();
      setPapers(rows); setLoadError('');
      setActiveId(prev => select ?? (prev && rows.some(r => r.paper_id === prev) ? prev : rows[0]?.paper_id));
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'Unable to load papers.');
    } finally { setLoading(false); }
  }
  useEffect(() => { void refresh(); }, []);

  async function remove(id: string) {
    if (!window.confirm('Delete this paper and its indexed chunks?')) return;
    try { await deletePaper(id); await refresh(); } catch (error) { setLoadError(error instanceof Error ? error.message : 'Delete failed.'); }
  }

  const active = papers.find(p => p.paper_id === activeId);
  const scopeIds = scopeAll || !active ? papers.map(p => p.paper_id) : [active.paper_id];
  const scopeLabel = scopeAll || !active ? `all ${papers.length} paper${papers.length === 1 ? '' : 's'}` : paperLabel(active);
  let content;
  if (loading) content = <Loading label="Loading your library…" />;
  else if (papers.length === 0) content = <Empty title="A clear desk is a good start.">Upload one or more research PDFs. They are parsed, split into sections, embedded and indexed for question answering, summaries and comparison.</Empty>;
  else if (mode === 'compare') content = <CompareView papers={papers} />;
  else if (mode === 'insights') content = <InsightsView papers={papers} />;
  else if (!active) content = <Empty title="Select a paper." />;
  else content = mode === 'summary' ? <SummaryView paper={active} /> : <OverviewView paper={active} />;

  return (
    <div className="paper-noise flex min-h-[100dvh] bg-[#f6f1e8] text-[#29475a]">
      <Sidebar papers={papers} activeId={activeId} onSelect={id => { setActiveId(id); if (mode === 'compare' || mode === 'insights') setMode('overview'); }} onUpload={() => setUploadOpen(true)} onDelete={remove} />
      <div className="min-w-0 flex-1">
        <header className="relative z-20 flex h-[72px] items-center justify-between border-b border-[#ddd1c1] bg-[#f8f2e9]/95 px-4 backdrop-blur sm:px-7">
          <div><span className="mono text-[9px] uppercase tracking-[.18em] text-[#a66547]">Research Paper Intelligence</span><h1 className="serif text-[22px] leading-none tracking-[-.03em]">Reading desk</h1></div>
          <div className="flex items-center gap-2"><HealthBadge /><button onClick={() => setUploadOpen(true)} className="focus-ring flex items-center gap-1.5 rounded-full bg-[#c57950] px-4 py-2 text-[11px] font-semibold text-white" data-testid="button-upload"><Upload size={13} /> Add papers</button></div>
        </header>
        <UploadPanel open={uploadOpen} onClose={() => setUploadOpen(false)} onDone={ids => { void refresh(ids[ids.length - 1]); setUploadOpen(false); }} />
        <main className="mx-auto max-w-[1100px] px-4 py-5 sm:px-7 sm:py-7">
          {loadError && <div className="mb-4"><ErrorNote message={loadError} /></div>}
          {papers.length > 0 && <div className="scrollbar-thin mb-5 flex gap-1 overflow-x-auto border-b border-[#ddd1c1]" role="tablist">{MODES.map(({ id, label, icon: Icon }) => (
            <button key={id} role="tab" aria-selected={mode === id} onClick={() => setMode(id)} className={`focus-ring flex shrink-0 items-center gap-2 border-b-2 px-3 py-3 text-[11px] font-semibold ${mode === id ? 'border-[#c57950] text-[#29475a]' : 'border-transparent text-[#7b8881] hover:text-[#29475a]'}`}><Icon size={14} /> {label}</button>))}</div>}
          {papers.length > 0 && <div className="mb-4 flex flex-wrap gap-2 md:hidden">{papers.map(p => <button key={p.paper_id} onClick={() => setActiveId(p.paper_id)} className={`rounded-full border px-3 py-1 text-[11px] ${p.paper_id === activeId ? 'border-[#c57950] bg-[#fffaf2]' : 'border-[#d9cdbd]'}`}>{p.paper_id}</button>)}</div>}
          {content}
          {papers.length > 0 && <div className="mt-6">
            <label className="mb-2 flex items-center gap-2 text-[11px] text-[#7b8881]"><input type="checkbox" checked={scopeAll} onChange={e => setScopeAll(e.target.checked)} /> Ask across all papers (uncheck to ask only the selected paper)</label>
            <ChatPanel key={scopeIds.join('|')} paperIds={scopeIds} scopeLabel={scopeLabel} />
          </div>}
        </main>
      </div>
    </div>
  );
}

function Router() {
  return <ErrorBoundary><Switch><Route path="/" component={Landing} /><Route path="/console" component={Console} /><Route component={NotFound} /></Switch></ErrorBoundary>;
}

const queryClient = new QueryClient();

function App() {
  return <QueryClientProvider client={queryClient}><TooltipProvider><WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}><Router /></WouterRouter><Toaster /></TooltipProvider></QueryClientProvider>;
}

export default App;
