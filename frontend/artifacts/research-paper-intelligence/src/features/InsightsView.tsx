import { useEffect, useState, type ReactNode } from 'react';
import { getInsights, type InsightsResponse, type PaperRow } from '@/lib/paper-api';
import { Eyebrow, Empty, ErrorNote, Loading, Tag, card, pages, sectionLabel } from './ui';

const chip = (text: string, key: string, note?: string) => <span key={key} title={note} className="rounded-full bg-[#efe5d4] px-2.5 py-1 text-[11px] text-[#4d5f5a]">{text}</span>;

export function InsightsView({ papers }: { papers: PaperRow[] }) {
  const ids = papers.map(p => p.paper_id);
  const key = ids.join('|');
  const [data, setData] = useState<InsightsResponse>();
  const [error, setError] = useState('');
  useEffect(() => {
    if (ids.length < 2) { setData(undefined); return; }
    let cancelled = false;
    setData(undefined); setError('');
    getInsights(ids).then(r => { if (!cancelled) setData(r); }).catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : 'Insights failed.'); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (papers.length < 2) return <Empty title="Insights need at least two papers.">Select two or more papers in the strip above.</Empty>;
  if (error) return <ErrorNote message={error} />;
  if (!data) return <Loading label="Analysing papers…" />;
  const name = (id: string) => data.papers.find(p => p.paper_id === id)?.title || data.papers.find(p => p.paper_id === id)?.filename || id;
  const group = (title: string, items: InsightsResponse['common_datasets']) => (
    <div><h3 className="mono text-[9px] uppercase tracking-[.14em] text-[#7b8881]">{title}</h3>
      <div className="mt-1.5 flex flex-wrap gap-1.5">{items.length ? items.slice(0, 14).map(i => chip(`${i.name}${i.common ? ` · ${i.count} papers` : ''}`, i.name, i.papers.map(name).join(', '))) : <span className="text-[11px] text-[#9aa49d]">none detected</span>}</div></div>
  );
  const reported = (items: { paper_id: string; evidence: { text: string; section_name: string; page_start: number }[] }[]): ReactNode =>
    items.length ? <ul className="mt-2 space-y-2">{items.map(r => <li key={r.paper_id} className="text-[12px] leading-5 text-[#4d6068]"><strong className="text-[#29475a]">{name(r.paper_id)}:</strong> {r.evidence.slice(0, 2).map(e => `${e.text} (${sectionLabel(e.section_name)}, ${pages(e.page_start, e.page_start)})`).join(' ')}</li>)}</ul>
      : <p className="mt-2 text-[12px] text-[#9aa49d]">Nothing identified in the selected papers.</p>;
  const terms = (items: { term: string; papers: string[] }[]) => items.length ? <div className="mt-2 flex flex-wrap gap-1.5">{items.map(t => chip(t.term, t.term, t.papers.map(name).join(', ')))}</div> : <p className="mt-2 text-[12px] text-[#9aa49d]">No terms shared by two or more papers.</p>;

  return (
    <div className="space-y-5">
      <section className={card}>
        <div className="flex items-center gap-2"><Eyebrow>Similarity matrix</Eyebrow><Tag kind="inferred" /></div>
        <div className="mt-4 overflow-x-auto"><table className="text-[12px]" data-testid="similarity-matrix"><thead><tr><th />{data.similarity_matrix.paper_ids.map(id => <th key={id} className="px-3 py-1 text-[10px] font-medium text-[#7b8881]">{id}</th>)}</tr></thead>
          <tbody>{data.similarity_matrix.values.map((row, i) => <tr key={i}><th className="pr-3 text-left text-[10px] font-medium text-[#7b8881]">{data.similarity_matrix.paper_ids[i]}</th>{row.map((v, j) => <td key={j} className="px-3 py-1 text-center" style={{ background: `rgba(197,121,80,${Math.max(0, v) * 0.5})` }}>{v.toFixed(2)}</td>)}</tr>)}</tbody></table></div>
        <p className="mt-3 text-[10px] text-[#9aa49d]">{data.similarity_matrix.basis}</p>
      </section>
      <section className={`${card} space-y-4`}>
        <div className="flex items-center gap-2"><Eyebrow>Datasets, models, algorithms, metrics</Eyebrow><Tag kind="reported">detected in text</Tag></div>
        {group('Datasets', data.common_datasets)}{group('Models', data.common_models)}{group('Algorithms', data.common_algorithms)}{group('Metrics', data.common_metrics)}
      </section>
      <section className={card}>
        <div className="flex items-center gap-2"><Eyebrow>Reported results by metric</Eyebrow><Tag kind="reported" /></div>
        {data.performance_patterns.metrics.length === 0 && <p className="mt-2 text-[12px] text-[#9aa49d]">No metric values were identified in results-like sections.</p>}
        {data.performance_patterns.metrics.map(m => <div key={m.metric} className="mt-4"><h3 className="text-[12px] font-semibold text-[#29475a]">{m.metric}</h3>
          <ul className="mt-1 space-y-1 text-[12px] text-[#4d6068]">{m.reports.slice(0, 4).map((r, i) => <li key={i}><strong>{name(r.paper_id)}</strong>: {r.value} — “{r.sentence}” <span className="text-[#a66547]">({sectionLabel(r.section_name)}, p. {r.page})</span></li>)}</ul></div>)}
        <p className="mt-4 text-[10px] text-[#8a6425]">Values are copied from each paper; they are comparable only when datasets and protocols match.</p>
      </section>
      <section className={card}>
        <div className="flex items-center gap-2"><Eyebrow>Methodologies & themes</Eyebrow><Tag kind="inferred" /></div>
        <h3 className="mt-3 text-[12px] font-semibold text-[#29475a]">Shared methodology terms</h3>{terms(data.common_methodologies.terms)}
        <h3 className="mt-4 text-[12px] font-semibold text-[#29475a]">Recurring themes</h3>{terms(data.recurring_themes.terms)}
        <p className="mt-2 text-[10px] text-[#9aa49d]">{data.recurring_themes.note}</p>
      </section>
      <section className={card}>
        <div className="flex items-center gap-2"><Eyebrow>Problems & limitations</Eyebrow><Tag kind="reported" /></div>
        <h3 className="mt-3 text-[12px] font-semibold text-[#29475a]">Research problems stated</h3>{reported(data.recurring_problems.reported)}
        <h3 className="mt-4 text-[12px] font-semibold text-[#29475a]">Limitations stated</h3>{reported(data.common_limitations.reported)}
      </section>
      <section className={card}>
        <div className="flex items-center gap-2"><Eyebrow>Future work & gaps</Eyebrow></div>
        <div className="mt-3 flex items-center gap-2"><h3 className="text-[12px] font-semibold text-[#29475a]">Stated by the authors</h3><Tag kind="reported" /></div>{reported(data.research_gaps.reported_future_work)}
        <div className="mt-5 flex items-center gap-2"><h3 className="text-[12px] font-semibold text-[#29475a]">Differences across these papers</h3><Tag kind="inferred" /></div>
        {data.research_gaps.inferred.length ? <ul className="mt-2 list-disc space-y-1 pl-5 text-[12px] text-[#4d6068]">{data.research_gaps.inferred.map(g => <li key={g.text}>{g.text}</li>)}</ul> : <p className="mt-2 text-[12px] text-[#9aa49d]">None.</p>}
        <p className="mt-3 text-[10px] text-[#8a6425]">{data.research_gaps.note}</p>
      </section>
      <ul className="list-disc space-y-1 pl-5 text-[10px] text-[#9aa49d]">{data.caveats.map(c => <li key={c}>{c}</li>)}</ul>
    </div>
  );
}
