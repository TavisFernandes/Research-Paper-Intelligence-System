import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as api from '@/lib/paper-api';
import { ChatPanel } from './ChatPanel';
import { CompareView } from './CompareView';
import { UploadPanel } from './UploadPanel';

vi.mock('@/lib/paper-api', async () => ({ ...(await vi.importActual<typeof import('@/lib/paper-api')>('@/lib/paper-api')), askPapers: vi.fn(), uploadPapers: vi.fn(), waitForJob: vi.fn() }));

const evidence = { ref: 1, paper_id: 'P001', title: 'Paper One', filename: 'a.pdf', chunk_id: 'P001_RESULTS_001', section_name: 'RESULTS', page_start: 3, page_end: 3, text: 'Recall@10 was 0.91.', score: 0.03, dense_score: 0.71, lexical_coverage: 0.8 };
const base = { evidence: [evidence], grounded: true, citations_used: [1], retrieval: { mode: 'hybrid', embedding_backend: 'bge-m3', vector_store: 'redis', warnings: [] }, generation: { backend: 'openai-compatible', model: 'm' } };

beforeEach(() => vi.clearAllMocks());

describe('ChatPanel', () => {
  it('shows the answer with source metadata for each evidence passage', async () => {
    vi.mocked(api.askPapers).mockResolvedValue({ ...base, status: 'answered', answer: 'It was 0.91 [1].' });
    render(<ChatPanel paperIds={['P001']} scopeLabel="Paper One" />);
    await userEvent.type(screen.getByLabelText('Research question'), 'What recall?');
    await userEvent.click(screen.getByLabelText('Send question'));
    expect(await screen.findByText('It was 0.91 [1].')).toBeInTheDocument();
    const item = screen.getByTestId('evidence-1');
    expect(item).toHaveTextContent('Paper One');
    expect(item).toHaveTextContent('Results');
    expect(item).toHaveTextContent('p. 3');
    expect(item).toHaveTextContent('Recall@10 was 0.91.');
  });

  it('states clearly when evidence is insufficient or no LLM is configured', async () => {
    vi.mocked(api.askPapers).mockResolvedValue({ ...base, status: 'evidence_only', answer: null, grounded: false, citations_used: [], message: 'No language model is configured.' });
    render(<ChatPanel paperIds={['P001']} scopeLabel="x" />);
    await userEvent.type(screen.getByLabelText('Research question'), 'q');
    await userEvent.click(screen.getByLabelText('Send question'));
    expect(await screen.findByText(/No language model is configured/)).toBeInTheDocument();
  });

  it('shows an error state when the request fails', async () => {
    vi.mocked(api.askPapers).mockRejectedValue(new Error('The vector store is unavailable.'));
    render(<ChatPanel paperIds={[]} scopeLabel="x" />);
    await userEvent.type(screen.getByLabelText('Research question'), 'q');
    await userEvent.click(screen.getByLabelText('Send question'));
    expect(await screen.findByRole('alert')).toHaveTextContent('vector store is unavailable');
  });
});

describe('UploadPanel', () => {
  it('rejects non-PDF files without calling the API', async () => {
    render(<UploadPanel open onClose={() => {}} onDone={() => {}} />);
    const input = screen.getByTestId('input-paper-file') as HTMLInputElement;
    await userEvent.upload(input, new File(['x'], 'notes.txt', { type: 'text/plain' }), { applyAccept: false });
    expect(await screen.findByRole('alert')).toHaveTextContent('only PDF files are supported');
    expect(api.uploadPapers).not.toHaveBeenCalled();
  });

  it('uploads PDFs, shows progress and reports finished paper ids', async () => {
    const job = { job_id: 'j1', paper_id: 'P001', filename: 'a.pdf', status: 'queued', stage: 'queued', progress: 0, error: null, duplicate_of: null } as const;
    vi.mocked(api.uploadPapers).mockResolvedValue({ jobs: [job], rejected: [] });
    vi.mocked(api.waitForJob).mockImplementation(async (j, onUpdate) => { onUpdate({ ...j, status: 'processing', stage: 'embedding_and_indexing', progress: 80 }); const done = { ...j, status: 'completed' as const, progress: 100, stage: 'done' }; onUpdate(done); return done; });
    const onDone = vi.fn();
    render(<UploadPanel open onClose={() => {}} onDone={onDone} />);
    await userEvent.upload(screen.getByTestId('input-paper-file'), new File(['%PDF-1.4'], 'a.pdf', { type: 'application/pdf' }));
    await waitFor(() => expect(onDone).toHaveBeenCalledWith(['P001']));
    expect(screen.getByText('a.pdf')).toBeInTheDocument();
  });

  it('shows the failure reason for a job that failed', async () => {
    const job = { job_id: 'j2', paper_id: 'P002', filename: 'bad.pdf', status: 'queued', stage: 'queued', progress: 0, error: null, duplicate_of: null } as const;
    vi.mocked(api.uploadPapers).mockResolvedValue({ jobs: [job], rejected: [] });
    vi.mocked(api.waitForJob).mockImplementation(async (j, onUpdate) => { const failed = { ...j, status: 'failed' as const, stage: 'failed', error: 'The PDF is password-protected and cannot be read.' }; onUpdate(failed); return failed; });
    render(<UploadPanel open onClose={() => {}} onDone={() => {}} />);
    await userEvent.upload(screen.getByTestId('input-paper-file'), new File(['%PDF-1.4'], 'bad.pdf', { type: 'application/pdf' }));
    expect(await screen.findByText(/password-protected/)).toBeInTheDocument();
  });
});

describe('CompareView', () => {
  it('asks for a second paper when fewer than two exist', () => {
    render(<CompareView papers={[{ paper_id: 'P001', filename: 'a.pdf', title: 'A', total_pages: 1, status: 'indexed', chunk_count: 1, sections: [], keywords: [] }]} />);
    expect(screen.getByText('Comparison needs two papers.')).toBeInTheDocument();
  });
});
