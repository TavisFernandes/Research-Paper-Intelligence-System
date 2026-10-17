import { useEffect, useState } from 'react';
import { comparePapers, type Cell, type CompareResponse, type PaperRow } from '@/lib/paper-api';
import { Eyebrow, Empty, ErrorNote, Loading, Tag, card, pages, paperLabel, sectionLabel } from './ui';

export function CompareView({ papers }: { papers: PaperRow[] }) {
  const [leftId, setLeftId] = useState(papers[0]?.paper_id ?? '');
  const [rightId, setRightId] = useState(papers[1]?.paper_id ?? '');
  const [data, setData] = useState<CompareResponse>();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!papers.find(p => p.paper_id === leftId)) setLeftId(papers[0]?.paper_id ?? '');
    if (!papers.find(p => p.paper_id === rightId) || rightId === leftId) setRightId(papers.find(p => p.paper_id !== leftId)?.paper_id ?? '');
  }, [papers, leftId, rightId]);

  useEffect(() => {
    if (!leftId || !rightId || leftId === rightId) { setData(undefined); return; }
    let cancelled = false;
    setLoading(true); setError(''); setData(undefined);
    comparePapers([leftId, rightId]).then(r => { if (!cancelled) setData(r); })
      .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : 'Comparison failed.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [leftId, rightId]);

  if (papers.length < 2) return <Empty title="Comparison needs two papers.">Upload at least two papers, then pick any pair to compare.</Empty>;
  const select = (value: string, set: (v: string) => void, label: string, exclude: string) => (
    <label className="flex-1 text-[11px] text-[#7b8881]">{label}
      <select value={value} onChange={e => set(e.target.value)} className="focus-ring mt-1 block w-full rounded border border-[#d9cdbd] bg-[#fbf6ee] px-3 py-2 text-[12px] text-[#29475a]">
        {papers.filter(p => p.paper_id !== exclude).map(p => <option key={p.paper_id} value={p.paper_id}>{paperLabel(p)}</option>)}
      </select></label>
  );
  return (
    <div className="space-y-5">
      <section className={card}>
        <Eyebrow>Pairwise comparison</Eyebrow>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row">{select(leftId, setLeftId, 'Paper A', rightId)}{select(rightId, setRightId, 'Paper B', leftId)}</div>
        {loading && <Loading label="Comparing…" />}
        {error && <div className="mt-4"><ErrorNote message={error} /></div>}
        {data && <p className="mt-4 text-[12px] text-[#4d6068]">Overall similarity of abstract/introduction/conclusion: <strong>{data.overall_similarity.toFixed(2)}</strong> <Tag kind="inferred" /> <span className="text-[10px] text-[#9aa49d]">({data.similarity_basis})</span></p>}
      </section>
      {data && (
        <>
          <section className={`${card} overflow-x-auto !p-0`}>
            <table className="w-full min-w-[640px] border-collapse text-left text-[12px]" data-testid="comparison-table">
              <thead><tr className="border-b border-[#e6dccd] text-[10px] uppercase tracking-[.1em] text-[#7b8881]"><th className="w-[140px] p-4">Dimension</th><th className="p-4">{paperLabel(data.left)}</th><th className="p-4">{paperLabel(data.right)}</th></tr></thead>
              <tbody>
                {data.table.map(row => (
                  <tr key={row.dimension} className="border-b border-[#efe6d8] align-top">
                    <th className="p-4 text-[12px] font-semibold text-[#29475a]">{row.dimension}</th>
                    <td className="p-4"><CellView cell={row.left} /></td><td className="p-4"><CellView cell={row.right} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="border-t border-[#e6dccd] px-4 py-3 text-[10px] text-[#9aa49d]">Cells are sentences copied from the papers with section and page. “Not reported” means no matching text was identified, not that the paper lacks it.</p>
          </section>
          <section className={card}>
            <div className="flex items-center gap-2"><Eyebrow>Cross-paper observations</Eyebrow><Tag kind="inferred" /></div>
            <p className="mt-2 text-[11px] text-[#8a6425]">{data.inferred.note}</p>
            <h3 className="mt-4 text-[12px] font-semibold text-[#29475a]">Shared</h3>
            <List items={data.inferred.similarities} empty="No shared datasets, models or metrics were detected." />
            <h3 className="mt-4 text-[12px] font-semibold text-[#29475a]">Differences</h3>
            <List items={data.inferred.differences} empty="No differences detected." />
          </section>
          {data.narrative?.status === 'ok' && <section className={card}><div className="flex items-center gap-2"><Eyebrow>Narrative</Eyebrow><Tag kind="generated" /></div><p className="mt-3 whitespace-pre-wrap text-[12px] leading-5">{data.narrative.text}</p></section>}
        </>
      )}
    </div>
  );
}

function List({ items, empty }: { items: string[]; empty: string }) {
  return items.length ? <ul className="mt-2 list-disc space-y-1.5 pl-5 text-[12px] leading-5 text-[#4d6068]">{items.map(i => <li key={i}>{i}</li>)}</ul> : <p className="mt-2 text-[12px] text-[#9aa49d]">{empty}</p>;
}

function CellView({ cell }: { cell: Cell }) {
  if (!cell.sources.length && !cell.entities.length) return <span className="text-[#9aa49d]">{cell.text}</span>;
  return (
    <div className="space-y-2">
      {cell.entities.length > 0 && <div className="flex flex-wrap gap-1">{cell.entities.slice(0, 8).map(e => <span key={e} className="rounded-full bg-[#efe5d4] px-2 py-0.5 text-[10px] text-[#4d5f5a]">{e}</span>)}</div>}
      {cell.text && <p className="leading-5 text-[#4d6068]">{cell.text}</p>}
      {cell.sources.length > 0 && <p className="mono text-[9px] uppercase tracking-[.08em] text-[#a66547]">{cell.sources.map(s => `${sectionLabel(s.section_name)} ${pages(s.page_start, s.page_end)}`).filter((v, i, a) => a.indexOf(v) === i).join(' · ')}</p>}
    </div>
  );
}
