// @vitest-environment node
// Frontend-to-backend integration test. Runs only when a backend is available:
//   VITE_API_BASE_URL=http://127.0.0.1:8000 API_TEST_PDFS=/path/a.pdf,/path/b.pdf pnpm test
import { readFileSync } from 'node:fs';
import { basename } from 'node:path';
import { describe, expect, it } from 'vitest';
import { askPapers, comparePapers, getHealth, getInsights, listPapers, summarizePaper, uploadPapers, waitForJob } from './paper-api';

const pdfs = (process.env.API_TEST_PDFS ?? '').split(',').filter(Boolean);
const enabled = Boolean(process.env.VITE_API_BASE_URL) && pdfs.length >= 2;

describe.skipIf(!enabled)('frontend client against a live backend', () => {
  it('uploads, ingests, searches, summarises, compares', async () => {
    const files = pdfs.map(p => new File([readFileSync(p)], basename(p), { type: 'application/pdf' }));
    const { jobs, rejected } = await uploadPapers(files);
    expect(rejected).toEqual([]);
    const finished = await Promise.all(jobs.map(j => waitForJob(j, () => {}, 200, 120_000)));
    expect(finished.map(j => j.status)).toEqual(['completed', 'completed']);

    const papers = await listPapers();
    expect(papers.length).toBeGreaterThanOrEqual(2);
    expect(papers[0].indexing?.indexed).toBe(true);
    expect((await getHealth()).components.papers).toBeGreaterThanOrEqual(2);

    const qa = await askPapers('Which dataset was used for training?', papers.map(p => p.paper_id));
    expect(['evidence_only', 'answered']).toContain(qa.status);
    expect(qa.evidence[0]).toMatchObject({ paper_id: expect.any(String), section_name: expect.any(String), page_start: expect.any(Number) });

    const none = await askPapers('quantum chromodynamics lattice gauge', []);
    expect(none.status).toBe('insufficient_evidence');

    const summary = await summarizePaper(papers[0].paper_id);
    expect(summary.summary.length).toBeGreaterThan(10);
    const cmp = await comparePapers([papers[0].paper_id, papers[1].paper_id]);
    expect(cmp.table).toHaveLength(10);
    const ins = await getInsights(papers.map(p => p.paper_id));
    expect(ins.paper_count).toBe(papers.length);
    await expect(comparePapers([papers[0].paper_id, papers[0].paper_id])).rejects.toThrow(/two different papers/);
  }, 120_000);
});
