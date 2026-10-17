import { useRef, useState, type DragEvent } from 'react';
import { CheckCircle2, CloudUpload, FolderOpen, X, XCircle } from 'lucide-react';
import { uploadPapers, waitForJob, type Job } from '@/lib/paper-api';

const STAGES: Record<string, string> = {
  queued: 'Queued', starting: 'Starting', extracting_text: 'Extracting text (OCR if scanned)', preprocessing: 'Cleaning & segmenting',
  section_detection: 'Detecting sections', analysis: 'Entities & keywords', embedding_and_indexing: 'Embedding & indexing', done: 'Done', failed: 'Failed', duplicate: 'Already uploaded',
};
const MAX_BYTES = 20 * 1024 * 1024;

export function UploadPanel({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: (paperIds: string[]) => void }) {
  const [dragging, setDragging] = useState(false);
  const [jobs, setJobs] = useState<Record<string, Job>>({});
  const [errors, setErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  if (!open) return null;

  async function handle(fileList: FileList | File[]) {
    const files = Array.from(fileList);
    const problems: string[] = [];
    const valid = files.filter(file => {
      if (!file.name.toLowerCase().endsWith('.pdf')) { problems.push(`${file.name}: only PDF files are supported.`); return false; }
      if (file.size > MAX_BYTES) { problems.push(`${file.name}: larger than the 20 MB limit.`); return false; }
      return true;
    });
    setErrors(problems);
    if (!valid.length) return;
    setBusy(true);
    try {
      const { jobs: started, rejected } = await uploadPapers(valid);
      setErrors(prev => [...prev, ...rejected.map(r => `${r.filename}: ${r.error}`)]);
      const finished = await Promise.all(started.map(job => waitForJob(job, update => setJobs(prev => ({ ...prev, [update.job_id]: update })))));
      const ids = finished.filter(j => j.status === 'completed' || j.status === 'duplicate').map(j => (j.duplicate_of ?? j.paper_id) as string);
      if (ids.length) onDone(ids);
    } catch (error) {
      setErrors(prev => [...prev, error instanceof Error ? error.message : 'Upload failed.']);
    } finally {
      setBusy(false);
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) { event.preventDefault(); setDragging(false); void handle(event.dataTransfer.files); }

  return (
    <div className="absolute right-3 top-16 z-30 w-[min(420px,calc(100vw-24px))] rounded-[7px] border border-[#d5c9b8] bg-[#fffaf2] p-5 shadow-[0_18px_45px_rgba(44,58,62,.18)]" role="dialog" aria-label="Upload papers">
      <div className="flex items-start justify-between">
        <div><p className="serif text-[25px] tracking-[-.03em] text-[#29475a]">Add papers</p><p className="mt-1 text-[11px] text-[#7b8881]">One or more PDFs · up to 20 MB each · scanned pages use OCR when installed</p></div>
        <button onClick={onClose} className="focus-ring rounded p-1 text-[#81908b] hover:bg-[#eee4d6]" aria-label="Close upload panel"><X size={16} /></button>
      </div>
      <div onDragOver={e => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}
        className={`mt-5 rounded-[5px] border border-dashed p-6 text-center ${dragging ? 'border-[#c57950] bg-[#f6e9d8]' : 'border-[#cfc2b0] bg-[#f7f1e8]'}`}>
        <CloudUpload size={26} className="mx-auto text-[#b76e4a]" strokeWidth={1.5} />
        <p className="mt-3 text-[12px] font-semibold text-[#425c68]">{dragging ? 'Release to upload' : 'Drop PDFs here'}</p>
        <input ref={inputRef} type="file" multiple accept=".pdf,application/pdf" className="sr-only" data-testid="input-paper-file"
          onChange={e => { if (e.target.files?.length) void handle(e.target.files); e.target.value = ''; }} />
        <button disabled={busy} onClick={() => inputRef.current?.click()} className="focus-ring mt-4 rounded-full border border-[#29475a]/20 bg-[#fffaf2] px-4 py-2 text-[11px] font-semibold text-[#29475a] hover:border-[#c57950] disabled:opacity-50">
          <FolderOpen size={13} className="mr-1.5 inline" /> Choose PDFs
        </button>
      </div>
      <ul className="mt-4 space-y-3">
        {Object.values(jobs).map(job => (
          <li key={job.job_id} className="text-[11px]" data-testid={`job-${job.job_id}`}>
            <div className="flex items-center justify-between gap-2">
              <span className="truncate font-medium text-[#425c68]">{job.filename}</span>
              {job.status === 'completed' && <CheckCircle2 size={14} className="shrink-0 text-[#5c8a6b]" />}
              {job.status === 'failed' && <XCircle size={14} className="shrink-0 text-[#a55743]" />}
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-[#e9dfcf]" role="progressbar" aria-valuenow={job.progress} aria-valuemin={0} aria-valuemax={100}>
              <div className={`h-full transition-all ${job.status === 'failed' ? 'bg-[#c87a63]' : 'bg-[#c57950]'}`} style={{ width: `${job.progress}%` }} />
            </div>
            <p className={`mt-1 ${job.status === 'failed' ? 'text-[#a55743]' : 'text-[#7b8881]'}`}>
              {job.status === 'failed' ? job.error : job.status === 'duplicate' ? `Already ingested as ${job.duplicate_of}.` : STAGES[job.stage] ?? job.stage}
            </p>
          </li>
        ))}
      </ul>
      {errors.map((message, index) => <p key={index} className="mt-3 text-[11px] leading-4 text-[#a55743]" role="alert">{message}</p>)}
    </div>
  );
}
