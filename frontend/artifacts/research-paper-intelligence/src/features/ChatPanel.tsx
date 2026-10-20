import { useEffect, useRef, useState } from 'react';
import { MessageCircle, Quote, Send } from 'lucide-react';
import { askPapers, searchPapers, type QAResponse } from '@/lib/paper-api';
import { Eyebrow, ErrorNote, Loading, card, pages, paperLabel, sectionLabel } from './ui';

type Turn = { id: number; question: string; response?: QAResponse; generatingAnswer?: boolean; error?: string };
const SUGGESTIONS = ['Which dataset was used?', 'What methodology do the authors use?', 'What are the main results?', 'What limitations are reported?'];

const STATUS_NOTE: Record<QAResponse['status'], string> = {
  answered: '', insufficient_evidence: 'The retrieved evidence was not sufficient to answer.',
  llm_unavailable: 'The language model is unavailable, so only retrieved evidence is shown.',
  evidence_only: 'No language model is configured, so only retrieved evidence is shown (no generated answer).',
  generating: '',
};

export function ChatPanel({ paperIds, scopeLabel }: { paperIds: string[]; scopeLabel: string }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' }); }, [turns, busy]);

  async function send(text = value) {
    const question = text.trim();
    if (!question || busy) return;
    const id = Date.now();
    setTurns(prev => [...prev, { id, question }]);
    setValue('');
    setBusy(true);
    let evidenceResponse: QAResponse | undefined;
    try {
      const search = await searchPapers(question, paperIds);
      evidenceResponse = {
        status: search.results.length ? 'generating' : 'insufficient_evidence',
        answer: null,
        message: search.results.length ? 'Relevant passages are ready. A cited answer is still being generated.' : undefined,
        evidence: search.results.map((item, index) => ({ ref: index + 1, ...item })),
        grounded: false,
        citations_used: [],
        retrieval: {
          mode: search.mode,
          embedding_backend: search.embedding_backend,
          vector_store: search.vector_store,
          warnings: search.warnings,
        },
        generation: { backend: 'pending', model: null },
      };
      setTurns(prev => prev.map(t => (t.id === id ? { ...t, response: evidenceResponse, generatingAnswer: search.results.length > 0 } : t)));
      const response = await askPapers(question, paperIds, undefined, search.retrieval_id);
      setTurns(prev => prev.map(t => (t.id === id ? { ...t, response, generatingAnswer: false } : t)));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'The question could not be answered.';
      setTurns(prev => prev.map(t => {
        if (t.id !== id) return t;
        if (evidenceResponse) {
          return { ...t, response: { ...evidenceResponse, status: 'llm_unavailable', message }, generatingAnswer: false };
        }
        return { ...t, error: message };
      }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={`${card} flex min-h-[360px] flex-col !p-0`} aria-label="Ask the papers">
      <div className="flex items-center justify-between border-b border-[#e6dccd] px-5 py-4">
        <div className="flex items-center gap-2.5"><MessageCircle size={16} className="text-[#b56f4b]" /><div><Eyebrow>Ask with citations</Eyebrow><p className="text-[11px] text-[#7b8881]">Searching: {scopeLabel}</p></div></div>
      </div>
      <div className="flex-1 space-y-5 overflow-auto px-5 py-4">
        {turns.length === 0 && (
          <div className="flex flex-wrap gap-2">{SUGGESTIONS.map(s => <button key={s} onClick={() => void send(s)} disabled={!paperIds.length && false} className="focus-ring rounded-full border border-[#d9cdbd] px-3 py-1.5 text-[11px] text-[#5f7a74] hover:border-[#c57950]">{s}</button>)}</div>
        )}
        {turns.map(turn => (
          <div key={turn.id} className="space-y-3">
            <p className="ml-auto max-w-[85%] rounded-[8px] bg-[#29475a] px-3.5 py-2.5 text-[12px] text-[#f7f1e7]">{turn.question}</p>
            {turn.error && <ErrorNote message={turn.error} />}
            {!turn.error && !turn.response && <Loading label="Finding relevant passages…" />}
            {turn.response && <Answer response={turn.response} />}
            {!turn.error && turn.generatingAnswer && <Loading label="Writing a cited answer…" />}
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <form className="flex gap-2 border-t border-[#e6dccd] p-3" onSubmit={e => { e.preventDefault(); void send(); }}>
        <input value={value} onChange={e => setValue(e.target.value)} placeholder="Ask a research question…" aria-label="Research question" maxLength={2000}
          className="focus-ring min-w-0 flex-1 rounded-full border border-[#d9cdbd] bg-[#fbf6ee] px-4 py-2.5 text-[12px] outline-none placeholder:text-[#9aa49d]" />
        <button type="submit" disabled={busy || !value.trim()} className="focus-ring flex h-10 w-10 items-center justify-center rounded-full bg-[#c57950] text-white disabled:opacity-40" aria-label="Send question"><Send size={15} /></button>
      </form>
    </section>
  );
}

function Answer({ response }: { response: QAResponse }) {
  const note = STATUS_NOTE[response.status];
  return (
    <div className="space-y-3">
      {response.answer && <p className="whitespace-pre-wrap rounded-[8px] border border-[#e1d6c5] bg-[#f8f1e6] px-3.5 py-3 text-[12px] leading-5 text-[#3c5662]">{response.answer}</p>}
      {(note || response.message) && <p className="text-[11px] leading-4 text-[#8a6425]">{response.message || note}</p>}
      {response.warnings?.map(w => <p key={w} className="text-[11px] text-[#8a6425]">⚠ {w}</p>)}
      {response.retrieval.warnings.map(w => <p key={w} className="text-[10px] text-[#9a8f78]">{w}</p>)}
      {response.evidence.length > 0 && (
        <details open={response.status !== 'answered'} className="rounded border border-[#e1d6c5]">
          <summary className="cursor-pointer px-3 py-2 text-[11px] font-semibold text-[#425c68]"><Quote size={12} className="mr-1.5 inline" />Evidence ({response.evidence.length}){response.grounded ? ' · answer cites ' + response.citations_used.map(n => `[${n}]`).join('') : ''}</summary>
          <ol className="space-y-2 px-3 pb-3">
            {response.evidence.map(ev => (
              <li key={ev.chunk_id} className="rounded bg-[#fffaf2] p-2.5 text-[11px] leading-4 text-[#5b6f69]" data-testid={`evidence-${ev.ref}`}>
                <p className="mono mb-1 text-[9px] uppercase tracking-[.1em] text-[#a66547]">[{ev.ref}] {paperLabel(ev)} · {sectionLabel(ev.section_name)} · {pages(ev.page_start, ev.page_end)}{ev.dense_score != null ? ` · sim ${ev.dense_score.toFixed(2)}` : ''}</p>
                <p>{ev.text}</p>
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}
