import { afterEach, describe, expect, it, vi } from 'vitest';
import { askPapers, listPapers, waitForJob, type Job } from './paper-api';

const job = (over: Partial<Job>): Job => ({ job_id: 'j1', paper_id: 'P001', filename: 'a.pdf', status: 'queued', stage: 'queued', progress: 0, error: null, duplicate_of: null, ...over });
const reply = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));

afterEach(() => vi.restoreAllMocks());

describe('paper-api', () => {
  it('reports an unreachable backend with a helpful message', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('network'));
    await expect(listPapers()).rejects.toThrow(/Unable to reach the backend/);
  });

  it('surfaces the backend detail message for errors', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => reply({ detail: 'The vector store is unavailable.' }, 503));
    await expect(askPapers('q', ['P001'])).rejects.toThrow('The vector store is unavailable.');
  });

  it('sends the question and omits paper_ids when none are selected', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockImplementation(() => reply({ status: 'evidence_only', evidence: [] }));
    await askPapers('What dataset?', []);
    const body = JSON.parse((spy.mock.calls[0][1] as RequestInit).body as string);
    expect(body).toEqual({ query: 'What dataset?' });
  });

  it('polls a job until it reaches a terminal state', async () => {
    const states = [job({ status: 'processing', progress: 40 }), job({ status: 'completed', progress: 100 })];
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => reply(states.shift()));
    const seen: string[] = [];
    const done = await waitForJob(job({}), j => seen.push(j.status), 1);
    expect(done.status).toBe('completed');
    expect(seen).toEqual(['queued', 'processing', 'completed']);
  });
});
