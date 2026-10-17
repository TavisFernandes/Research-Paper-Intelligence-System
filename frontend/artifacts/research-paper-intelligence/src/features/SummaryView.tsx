import { useEffect, useState } from 'react';
import { summarizePaper, type PaperRow, type SummaryResponse } from '@/lib/paper-api';
import { Eyebrow, ErrorNote, Loading, Tag, card, pages, sectionLabel } from './ui';

export function SummaryView({ paper }: { paper: PaperRow }) {
  const [data, setData] = useState<SummaryResponse>();
  const [error, setError] = useState('');
  useEffect(() => {
    let cancelled = false;
    setData(undefined); setError('');
    summarizePaper(paper.paper_id).then(r => { if (!cancelled) setData(r); }).catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : 'Summary failed.'); });
    return () => { cancelled = true; };
  }, [paper.paper_id]);

  return (
    <div className="space-y-5">
      <section className={card}>
        <div className="flex flex-wrap items-center justify-between gap-2"><Eyebrow>Paper summary</Eyebrow>{data?.backend && <span className="mono text-[9px] uppercase text-[#7b8881]">method: {data.backend}</span>}</div>
        <h2 className="serif mt-2 break-words text-[28px] leading-tight tracking-[-.03em] text-[#29475a]">{paper.title || paper.filename}</h2>
        {!data && !error && <Loading label="Summarising…" />}
        {error && <ErrorNote message={error} />}
        {data && <p className="mt-4 text-[13px] leading-6 text-[#3c5662]">{data.summary || 'No summary could be generated for this paper.'}</p>}
        {data?.backend === 'extractive' && <p className="mt-3 text-[11px] text-[#8a6425]">Extractive summary (sentences selected from the paper). Enable LED on the backend (ENABLE_LED=true) for abstractive summaries.</p>}
      </section>
      {data?.highlights && (
        <section className={card}>
          <div className="flex items-center gap-2"><Eyebrow>Detected entities</Eyebrow><Tag kind="reported">from text</Tag></div>
          <dl className="mt-4 grid gap-4 sm:grid-cols-2">
            {Object.entries(data.highlights).map(([key, values]) => (
              <div key={key}><dt className="mono text-[9px] uppercase tracking-[.14em] text-[#7b8881]">{key}</dt>
                <dd className="mt-1.5 flex flex-wrap gap-1.5">{values.length ? values.map(v => <span key={v} className="rounded-full bg-[#efe5d4] px-2.5 py-1 text-[11px] text-[#4d5f5a]">{v}</span>) : <span className="text-[11px] text-[#9aa49d]">none detected</span>}</dd></div>
            ))}
          </dl>
        </section>
      )}
      {data?.sections && data.sections.length > 0 && (
        <section className={card}>
          <Eyebrow>Section summaries</Eyebrow>
          <div className="mt-4 divide-y divide-[#e6dccd]">
            {data.sections.map(s => (
              <article key={s.section_name} className="py-4 first:pt-0 last:pb-0">
                <h3 className="text-[13px] font-semibold text-[#29475a]">{sectionLabel(s.section_name)} <span className="mono ml-2 text-[9px] font-normal text-[#7b8881]">{pages(s.pages[0], s.pages[1])}</span></h3>
                <p className="mt-1.5 text-[12px] leading-5 text-[#4d6068]">{s.summary || '—'}</p>
              </article>
            ))}
          </div>
        </section>
      )}
      {data && !data.sections?.length && <p className="text-[11px] text-[#8a6425]">No standard sections were identified in this paper, so only an overall summary is available.</p>}
    </div>
  );
}

export function OverviewView({ paper }: { paper: PaperRow }) {
  const entities = paper.analysis?.entities ?? [];
  const groups = ['DATASET', 'MODEL', 'ALGORITHM', 'METRIC', 'ORGANIZATION', 'SCIENTIFIC_ENTITY'];
  return (
    <div className="space-y-5">
      <section className={card}>
        <Eyebrow>Processing result</Eyebrow>
        <h2 className="serif mt-2 break-words text-[28px] tracking-[-.03em] text-[#29475a]">{paper.title || paper.filename}</h2>
        <dl className="mt-5 grid grid-cols-2 gap-4 text-[12px] sm:grid-cols-4">
          {[['Pages', paper.total_pages], ['Chunks', paper.chunk_count], ['Sections', paper.sections.length], ['Indexed', paper.indexing?.indexed ? `yes (${paper.indexing.vector_store})` : 'no']].map(([k, v]) => (
            <div key={String(k)}><dt className="mono text-[9px] uppercase tracking-[.14em] text-[#7b8881]">{k}</dt><dd className="mt-1 text-[16px] font-semibold text-[#29475a]">{v}</dd></div>
          ))}
        </dl>
        {paper.indexing && paper.indexing.semantic === false && <p className="mt-4 text-[11px] text-[#8a6425]">Embeddings use a non-semantic fallback; install BGE-M3 on the backend for semantic retrieval.</p>}
        {paper.indexing?.vector_store === 'memory' && <p className="mt-2 text-[11px] text-[#8a6425]">Vectors are in the in-memory store (not persisted). Start Redis Stack for persistent storage.</p>}
        {paper.analysis?.warnings.map(w => <p key={w} className="mt-2 text-[11px] text-[#a55743]">⚠ {w}</p>)}
      </section>
      <section className={card}>
        <Eyebrow>Sections found</Eyebrow>
        <div className="mt-3 flex flex-wrap gap-2">{paper.sections.map(s => <span key={s} className="rounded-full border border-[#d9cdbd] px-3 py-1 text-[11px] text-[#4d5f5a]">{sectionLabel(s)}</span>)}</div>
        {paper.sections.length === 0 || (paper.sections.length === 1 && paper.sections[0] === 'UNKNOWN') ? <p className="mt-3 text-[11px] text-[#8a6425]">No standard section headings were recognised, so no section boundaries were created.</p> : null}
      </section>
      <section className={card}>
        <Eyebrow>Entities</Eyebrow>
        <div className="mt-4 space-y-4">
          {groups.map(label => { const items = entities.filter(e => e.label === label).slice(0, 12); return items.length ? (
            <div key={label}><p className="mono text-[9px] uppercase tracking-[.14em] text-[#7b8881]">{label.replace('_', ' ')}</p><div className="mt-1.5 flex flex-wrap gap-1.5">{items.map(e => <span key={e.text} title={`source: ${e.source}`} className="rounded-full bg-[#efe5d4] px-2.5 py-1 text-[11px] text-[#4d5f5a]">{e.text}{e.count > 1 ? ` ×${e.count}` : ''}</span>)}</div></div>) : null; })}
          {entities.length === 0 && <p className="text-[12px] text-[#7b8881]">No entities detected.</p>}
        </div>
        <p className="mt-4 text-[10px] text-[#9aa49d]">NER: {Object.entries(paper.analysis?.backends ?? {}).map(([k, v]) => `${k}=${v.split(':')[0].split(' ')[0]}`).join(' · ')}</p>
        {paper.analysis?.keywords?.length ? <><div className="mt-5"><Eyebrow>Keywords (TF-IDF)</Eyebrow></div><div className="mt-2 flex flex-wrap gap-1.5">{paper.analysis.keywords.slice(0, 15).map(k => <span key={k.keyword} className="rounded-full border border-[#e1d6c5] px-2.5 py-1 text-[11px] text-[#5f7a74]">{k.keyword}</span>)}</div></> : null}
      </section>
    </div>
  );
}
