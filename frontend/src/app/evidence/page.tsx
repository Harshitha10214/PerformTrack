'use client';

import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { Download, Eye, Paperclip, Search, Upload } from 'lucide-react';

import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import DataTable, { type DataTableColumn } from '@/components/common/DataTable';
import EmptyState from '@/components/common/EmptyState';
import Loading from '@/components/common/Loading';
import Modal from '@/components/common/Modal';
import TextInput from '@/components/common/TextInput';
import {
  downloadEvidenceFile,
  getEvidence,
  getEvidenceRecord,
  uploadEvidence,
  type EvidenceRecord,
  type EvidenceTargetType,
  type PageResult,
} from '@/services/api';

const pageSize = 25;

const initialUpload = {
  employee_id: '',
  target_type: 'key_result' as EvidenceTargetType,
  target_id: '',
  description: '',
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

function formatSize(size: number | null): string {
  if (size === null) return '—';
  return size < 1024 * 1024
    ? `${(size / 1024).toFixed(1)} KB`
    : `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export default function EvidencePage() {
  const [result, setResult] = useState<PageResult<EvidenceRecord> | null>(null);
  const [search, setSearch] = useState('');
  const [targetType, setTargetType] = useState<EvidenceTargetType | ''>('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [upload, setUpload] = useState(initialUpload);
  const [file, setFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [selected, setSelected] = useState<EvidenceRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async (requestedPage = page) => {
    setLoading(true);
    setError(null);
    try {
      setResult(await getEvidence({
        search,
        target_type: targetType || undefined,
        page: requestedPage,
        page_size: pageSize,
      }));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load evidence records.');
    } finally {
      setLoading(false);
    }
  }, [page, search, targetType]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), search ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [load, search]);

  async function showDetails(id: string) {
    setSelected(null);
    setError(null);
    try {
      setSelected(await getEvidenceRecord(id));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load evidence details.');
    }
  }

  async function submitUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError('Choose a file to upload.');
      return;
    }
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const created = await uploadEvidence({ ...upload, file });
      setNotice(`Uploaded ${created.file_name} and linked it to ${created.linked_record_id}.`);
      setUploadOpen(false);
      setUpload(initialUpload);
      setFile(null);
      setPage(1);
      await load(1);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not upload evidence.');
    } finally {
      setSaving(false);
    }
  }

  async function downloadSelected() {
    if (!selected?.downloadable) return;
    setDownloading(true);
    setError(null);
    try {
      const blob = await downloadEvidenceFile(selected.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = selected.file_name;
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : 'Could not download evidence.');
    } finally {
      setDownloading(false);
    }
  }

  const columns = useMemo<DataTableColumn<EvidenceRecord>[]>(() => [
    { key: 'file_name', header: 'Filename', render: (item) => <><span className="block font-medium text-slate-800">{item.file_name}</span><span className="text-xs text-slate-500">{item.media_type}</span></> },
    { key: 'employee_name', header: 'Employee', render: (item) => <><span className="block font-medium text-slate-800">{item.employee_name}</span><span className="text-xs text-slate-500">{item.employee_id}</span></> },
    { key: 'linked_record_label', header: 'Linked record', render: (item) => <span className="block max-w-[300px] truncate" title={item.linked_record_label}>{item.linked_record_label}</span> },
    { key: 'created_at', header: 'Uploaded', render: (item) => formatDate(item.created_at) },
    { key: 'size_bytes', header: 'Size', render: (item) => formatSize(item.size_bytes) },
    { key: 'sha256', header: 'SHA-256', render: (item) => <span className="font-mono text-xs" title={item.sha256 ?? undefined}>{item.sha256 ? `${item.sha256.slice(0, 12)}…` : '—'}</span> },
    { key: 'actions', header: '', className: 'text-right', render: (item) => <Button size="sm" onClick={() => void showDetails(item.id)}><Eye className="h-3.5 w-3.5" /> Details</Button> },
  ], []);

  const totalPages = result ? Math.max(1, Math.ceil(result.total / result.page_size)) : 1;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Evidence Attachments</h1>
          <p className="mt-2 text-sm text-slate-500">Browse evidence linked to goals, check-ins, feedback, and reviews.</p>
        </div>
        <Button variant="primary" onClick={() => { setError(null); setUploadOpen(true); }}>
          <Upload className="h-4 w-4" /> Upload evidence
        </Button>
      </header>
      <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        Authentication is not enabled. Evidence API access is not restricted by user identity.
      </p>
      {notice && <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</p>}
      {error && !uploadOpen && !selected && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}
      <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        <div className="grid gap-3 md:grid-cols-[minmax(240px,1fr)_220px]">
          <TextInput
            type="search"
            value={search}
            onChange={(event) => { setSearch(event.target.value); setPage(1); }}
            placeholder="Search files, employees or linked IDs"
            aria-label="Search evidence"
            leadingIcon={<Search className="h-4 w-4" />}
          />
          <select
            className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm"
            aria-label="Filter evidence link type"
            value={targetType}
            onChange={(event) => { setTargetType(event.target.value as EvidenceTargetType | ''); setPage(1); }}
          >
            <option value="">All linked records</option>
            <option value="key_result">Goal key results</option>
            <option value="checkin">Check-ins</option>
            <option value="feedback">Feedback</option>
            <option value="review">Reviews</option>
          </select>
        </div>
        {loading ? <Loading /> : result?.items.length ? (
          <>
            <DataTable columns={columns} rows={result.items} getRowKey={(item) => item.id} label="Evidence attachments" />
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4 text-sm text-slate-500">
              <span>{result.total.toLocaleString()} evidence records</span>
              <div className="flex items-center gap-2">
                <Button size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button>
                <span>Page {page} of {totalPages}</span>
                <Button size="sm" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>Next</Button>
              </div>
            </div>
          </>
        ) : (
          <EmptyState title="No evidence found" description="Change the search or linked-record filter, or upload an attachment." />
        )}
      </section>

      <Modal open={uploadOpen} title="Upload evidence" onClose={() => setUploadOpen(false)} className="w-full max-w-2xl">
        <form className="flex-1 space-y-4 overflow-y-auto p-5" onSubmit={(event) => void submitUpload(event)}>
          {error && uploadOpen && <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
          <label className="block space-y-1.5 text-sm font-medium text-slate-700">
            Employee ID
            <TextInput required value={upload.employee_id} placeholder="EMP-000001" onChange={(event) => setUpload((current) => ({ ...current, employee_id: event.target.value }))} />
          </label>
          <label className="block space-y-1.5 text-sm font-medium text-slate-700">
            Link type
            <select className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm" value={upload.target_type} onChange={(event) => setUpload((current) => ({ ...current, target_type: event.target.value as EvidenceTargetType, target_id: '' }))}>
              <option value="key_result">Goal key result</option>
              <option value="checkin">Check-in</option>
              <option value="feedback">Feedback</option>
              <option value="review">Review</option>
            </select>
          </label>
          <label className="block space-y-1.5 text-sm font-medium text-slate-700">
            Linked record ID
            <TextInput required value={upload.target_id} placeholder={upload.target_type === 'key_result' ? 'KR-GOAL-EMP-000001-001-01' : upload.target_type === 'checkin' ? 'CHK-000001' : upload.target_type === 'feedback' ? 'FB-000001' : 'REV-2026-000001'} onChange={(event) => setUpload((current) => ({ ...current, target_id: event.target.value }))} />
            <span className="block text-xs font-normal text-slate-500">Key results link evidence to their parent goal. The API verifies the linked record belongs to this employee.</span>
          </label>
          <label className="block space-y-1.5 text-sm font-medium text-slate-700">
            Description
            <textarea required maxLength={4000} value={upload.description} onChange={(event) => setUpload((current) => ({ ...current, description: event.target.value }))} className="min-h-24 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100" />
          </label>
          <label className="block space-y-1.5 text-sm font-medium text-slate-700">
            Attachment
            <input required type="file" accept=".pdf,.txt,.png,.jpg,.jpeg,application/pdf,text/plain,image/png,image/jpeg" onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-indigo-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-indigo-700" />
            <span className="block text-xs font-normal text-slate-500">PDF, UTF-8 text, PNG, or JPEG; maximum 10 MB.</span>
          </label>
          <div className="flex justify-end gap-2 border-t border-slate-100 pt-4">
            <Button onClick={() => setUploadOpen(false)}>Cancel</Button>
            <Button type="submit" variant="primary" disabled={saving}><Paperclip className="h-4 w-4" />{saving ? 'Uploading…' : 'Upload file'}</Button>
          </div>
        </form>
      </Modal>

      <Modal open={selected !== null} title="Evidence details" onClose={() => setSelected(null)} className="w-full max-w-2xl">
        {selected && (
          <div className="flex-1 space-y-5 overflow-y-auto p-5">
            <div>
              <h2 className="break-all text-lg font-semibold text-slate-900">{selected.file_name}</h2>
              <p className="mt-1 text-sm text-slate-500">{selected.id} · {selected.media_type}</p>
            </div>
            <dl className="grid gap-x-6 gap-y-4 text-sm sm:grid-cols-2">
              <div><dt className="text-slate-500">Employee</dt><dd className="mt-1 font-medium text-slate-800">{selected.employee_name} ({selected.employee_id})</dd></div>
              <div><dt className="text-slate-500">Linked record</dt><dd className="mt-1 font-medium text-slate-800">{selected.linked_record_label}</dd></div>
              <div><dt className="text-slate-500">Uploaded</dt><dd className="mt-1 font-medium text-slate-800">{formatDate(selected.created_at)}</dd></div>
              <div><dt className="text-slate-500">File size</dt><dd className="mt-1 font-medium text-slate-800">{formatSize(selected.size_bytes)}</dd></div>
              <div className="sm:col-span-2"><dt className="text-slate-500">Description</dt><dd className="mt-1 whitespace-pre-wrap text-slate-800">{selected.description}</dd></div>
              <div className="sm:col-span-2"><dt className="text-slate-500">SHA-256</dt><dd className="mt-1 break-all font-mono text-xs text-slate-800">{selected.sha256 ?? 'Not recorded'}</dd></div>
            </dl>
            <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-4">
              {selected.downloadable
                ? <Button variant="primary" disabled={downloading} onClick={() => void downloadSelected()}><Download className="h-4 w-4" />{downloading ? 'Verifying…' : 'Verify and download'}</Button>
                : <Badge tone="neutral">Generated metadata only; no file is stored</Badge>}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
