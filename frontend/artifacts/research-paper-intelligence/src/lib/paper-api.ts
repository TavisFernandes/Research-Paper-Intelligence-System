export type PaperPage = {
  paper_id: string;
  page_number: number;
  extraction_method: string;
  raw_text: string;
  cleaned_text: string;
};

export type PaperSection = {
  paper_id: string;
  section_name: string;
  page_start: number;
  page_end: number;
  text: string;
};

export type PaperChunk = {
  paper_id: string;
  chunk_id: string;
  section_name: string;
  page_start: number;
  page_end: number;
  text: string;
};

export type ProcessedPaper = {
  paper_id: string;
  filename: string;
  total_pages: number;
  pages: PaperPage[];
  sections: PaperSection[];
  chunks: PaperChunk[];
};

type UploadResponse = Pick<ProcessedPaper, 'paper_id' | 'filename' | 'total_pages'>;

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, options);
  } catch {
    throw new Error('Unable to reach the paper processing backend.');
  }

  const payload = await response.json().catch(() => null) as { detail?: string } | null;
  if (!response.ok) {
    throw new Error(payload?.detail || `Request failed with status ${response.status}.`);
  }
  return payload as T;
}

export async function uploadPaper(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  return request<UploadResponse>('/api/papers/upload', { method: 'POST', body: formData });
}

export function processPaper(paperId: string): Promise<ProcessedPaper> {
  return request<ProcessedPaper>(`/api/papers/process/${encodeURIComponent(paperId)}`, { method: 'POST' });
}

export function getPaper(paperId: string): Promise<ProcessedPaper> {
  return request<ProcessedPaper>(`/api/papers/${encodeURIComponent(paperId)}`);
}

export async function uploadAndProcessPaper(file: File): Promise<ProcessedPaper> {
  const uploaded = await uploadPaper(file);
  await processPaper(uploaded.paper_id);
  return getPaper(uploaded.paper_id);
}
