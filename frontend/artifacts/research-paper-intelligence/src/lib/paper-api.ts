/** Typed client for the FastAPI backend. Base URL comes from VITE_API_BASE_URL (empty = same origin / dev proxy). */

export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed' | 'duplicate';
export type Job = { job_id: string; paper_id: string | null; filename: string; status: JobStatus; stage: string; progress: number; error: string | null; duplicate_of: string | null };

export type Entity = { label: string; text: string; source: string; count: number };
export type PaperRow = {
  paper_id: string; filename: string | null; title: string | null; total_pages: number; status: string; chunk_count: number;
  sections: string[]; keywords: string[];
  analysis?: { keywords: { keyword: string; score: number; count: number }[]; entities: Entity[]; warnings: string[]; backends: Record<string, string> };
  indexing?: { indexed: boolean; embedding_backend: string | null; vector_store: string | null; semantic?: boolean; persistent?: boolean };
};

export type Evidence = {
  ref: number; paper_id: string; title: string | null; filename: string | null; chunk_id: string; section_name: string;
  page_start: number; page_end: number; text: string; score: number | null; dense_score: number | null; lexical_coverage: number | null;
};
export type QAStatus = 'answered' | 'insufficient_evidence' | 'llm_unavailable' | 'evidence_only' | 'generating';
export type QAResponse = {
  status: QAStatus; answer: string | null; message?: string; evidence: Evidence[]; grounded: boolean; citations_used: number[]; warnings?: string[];
  retrieval: { mode: string; embedding_backend: string; vector_store: string; warnings: string[] }; generation: { backend: string; model: string | null };
};
export type SearchResponse = {
  retrieval_id: string;
  mode: string; embedding_backend: string; vector_store: string; warnings: string[];
  results: Omit<Evidence, 'ref'>[]; returned: number;
};

export type SectionSummary = { section_name: string; pages: [number, number]; summary: string; backend: string };
export type SummaryResponse = {
  paper_id: string; title?: string | null; found: boolean; summary: string; backend?: string; note?: string; pages?: [number, number];
  sections?: SectionSummary[]; highlights?: Record<string, string[]>;
};

export type Source = { section_name: string; page_start: number; page_end: number; chunk_id: string | null };
export type Cell = { text: string; sources: Source[]; entities: string[] };
export type CompareResponse = {
  left: { paper_id: string; title: string | null; filename: string | null }; right: { paper_id: string; title: string | null; filename: string | null };
  overall_similarity: number; similarity_basis: string;
  table: { dimension: string; left: Cell; right: Cell }[];
  dimensions: { key: string; label: string; similarity: number | null; entity_overlap: { shared: string[]; only_left: string[]; only_right: string[] } }[];
  inferred: { similarities: string[]; differences: string[]; note: string };
  provenance: Record<string, string>;
  narrative: { status: string; generated: boolean; text?: string; message?: string } | null;
};

type Counted = { name: string; papers: string[]; count: number; common: boolean };
type Reported = { paper_id: string; type: string; evidence: { text: string; section_name: string; page_start: number }[] };
export type InsightsResponse = {
  paper_count: number; papers: { paper_id: string; title: string | null; filename: string | null }[];
  similarity_matrix: { paper_ids: string[]; values: number[][]; basis: string };
  common_methodologies: { terms: { term: string; papers: string[] }[]; reported: Reported[] };
  common_datasets: Counted[]; common_models: Counted[]; common_algorithms: Counted[]; common_metrics: Counted[];
  performance_patterns: { metrics: { metric: string; papers: string[]; note: string; reports: { paper_id: string; value: string; sentence: string; section_name: string; page: number }[] }[] };
  recurring_problems: { shared_terms: { term: string; papers: string[] }[]; reported: Reported[] };
  common_limitations: { shared_terms: { term: string; papers: string[] }[]; reported: Reported[] };
  recurring_themes: { terms: { term: string; papers: string[] }[]; note: string };
  research_gaps: { reported_future_work: Reported[]; reported_limitations: Reported[]; inferred: { text: string }[]; note: string };
  caveats: string[]; narrative: { status: string; text?: string; message?: string } | null;
};

export type Health = { status: 'ok' | 'degraded'; warnings: string[]; components: Record<string, any> };

const apiBaseUrl = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '').replace(/\/$/, '');

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, options);
  } catch {
    throw new Error('Unable to reach the backend. Check that the API is running and VITE_API_BASE_URL is correct.');
  }
  const payload = (await response.json().catch(() => null)) as { detail?: string; errors?: { field: string; message: string }[] } | null;
  if (!response.ok) {
    const errorDetails = payload?.errors?.map(error => error.message).join(', ');
    throw new Error(errorDetails ? `${payload?.detail || 'Error'}: ${errorDetails}` : (payload?.detail || `Request failed with status ${response.status}.`));
  }
  return payload as T;
}

const json = (body: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const enc = encodeURIComponent;

export const getHealth = () => request<Health>('/api/health');
export const listPapers = () => request<PaperRow[]>('/api/papers');
export const deletePaper = (id: string) => request<{ deleted: string }>(`/api/papers/${enc(id)}`, { method: 'DELETE' });
export const getJob = (id: string) => request<Job>(`/api/ingestion/${enc(id)}`);

export async function uploadPapers(files: File[]): Promise<{ jobs: Job[]; rejected: { filename: string; error: string }[] }> {
  const form = new FormData();
  files.forEach(file => form.append('files', file));
  return request('/api/papers/upload', { method: 'POST', body: form });
}

/** Poll a job until it reaches a terminal state, reporting progress. */
export async function waitForJob(job: Job, onUpdate: (job: Job) => void, intervalMs = 1000, timeoutMs = 15 * 60 * 1000): Promise<Job> {
  const started = Date.now();
  let current = job;
  onUpdate(current);
  while (current.status === 'queued' || current.status === 'processing') {
    if (Date.now() - started > timeoutMs) throw new Error('Processing is taking too long. Check the backend logs.');
    await new Promise(resolve => setTimeout(resolve, intervalMs));
    current = await getJob(current.job_id);
    onUpdate(current);
  }
  return current;
}

export const askPapers = (query: string, paperIds: string[], mode?: 'dense' | 'lexical' | 'hybrid', retrievalId?: string) =>
  request<QAResponse>('/api/qa', json({ query, paper_ids: paperIds.length ? paperIds : undefined, mode, retrieval_id: retrievalId }));
export const searchPapers = (query: string, paperIds: string[], mode?: 'dense' | 'lexical' | 'hybrid') =>
  request<SearchResponse>('/api/search', json({ query, paper_ids: paperIds.length ? paperIds : undefined, mode, top_k: 6 }));
export const summarizePaper = (paperId: string, sectionName?: string) =>
  request<SummaryResponse>('/api/summarize', json({ paper_id: paperId, section_name: sectionName }));
export const comparePapers = (paperIds: [string, string], useLlm = false) => request<CompareResponse>('/api/compare', json({ paper_ids: paperIds, use_llm: useLlm }));
export const getInsights = (paperIds: string[], useLlm = false) => request<InsightsResponse>('/api/insights', json({ paper_ids: paperIds, use_llm: useLlm }));
