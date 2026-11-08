'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Plus, Search } from 'lucide-react';

import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import DataTable, { type DataTableColumn } from '@/components/common/DataTable';
import EmptyState from '@/components/common/EmptyState';
import Loading from '@/components/common/Loading';
import Modal from '@/components/common/Modal';
import TextInput from '@/components/common/TextInput';
import { createCheckIn, getCheckIns, updateCheckIn, type CheckInRecord, type PageResult } from '@/services/api';

const blank = { employee_id: '', manager_id: '', review_cycle_id: '', checkin_date: '', notes: '' };

export default function CheckInsPage() {
  const [result, setResult] = useState<PageResult<CheckInRecord> | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [form, setForm] = useState(blank);
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setResult(await getCheckIns({ search, status: statusFilter, page, page_size: 25 }));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load check-ins.');
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter]);
  useEffect(() => { const timer = window.setTimeout(() => void load(), search ? 250 : 0); return () => window.clearTimeout(timer); }, [load, search]);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await createCheckIn({
        employee_id: form.employee_id.trim(),
        manager_id: form.manager_id.trim(),
        review_cycle_id: form.review_cycle_id.trim() || null,
        checkin_date: form.checkin_date,
        notes: form.notes.trim(),
        status: 'scheduled',
        key_result_ids: [],
      });
      setCreating(false);
      setForm(blank);
      setNotice('Check-in scheduled.');
      setPage(1);
      await load();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not schedule check-in.');
    } finally {
      setSaving(false);
    }
  }

  async function changeStatus(item: CheckInRecord, status: string) {
    setSaving(true);
    setError(null);
    try {
      await updateCheckIn(item.id, { status });
      setNotice('Check-in status updated and recorded in history.');
      await load();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not update check-in.');
    } finally {
      setSaving(false);
    }
  }

  const columns: DataTableColumn<CheckInRecord>[] = [
    { key: 'id', header: 'ID', render: (row) => row.id },
    { key: 'employee_name', header: 'Employee', render: (row) => <><span className="block font-medium text-slate-800">{row.employee_name}</span><span className="text-xs text-slate-500">{row.employee_id}</span></> },
    { key: 'manager_name', header: 'Manager', render: (row) => row.manager_name ?? '—' },
    { key: 'checkin_date', header: 'Date', render: (row) => row.checkin_date },
    { key: 'notes', header: 'Notes', render: (row) => <span className="block max-w-[260px] truncate" title={row.notes}>{row.notes}</span> },
    { key: 'status', header: 'Status', render: (row) => <select className="h-8 rounded-md border border-slate-200 bg-white px-2 text-xs" aria-label={`Status for ${row.id}`} value={row.status} disabled={saving} onChange={(event) => void changeStatus(row, event.target.value)}>{['scheduled', 'completed', 'missed', 'cancelled'].map((status) => <option key={status} value={status}>{status}</option>)}</select> },
  ];

  return <div className="space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div><h1 className="text-2xl font-semibold tracking-tight text-slate-900">Check-ins</h1><p className="mt-2 text-sm text-slate-500">Schedule and track employee check-ins with their assigned manager.</p></div>
      <Button variant="primary" onClick={() => { setError(null); setCreating(true); }}><Plus className="h-4 w-4" /> Schedule check-in</Button>
    </header>
    {notice && <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</p>}
    {error && !creating && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}
    <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
      <div className="grid gap-3 md:grid-cols-[minmax(240px,1fr)_200px]">
        <TextInput type="search" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search employee or check-in ID" aria-label="Search check-ins" leadingIcon={<Search className="h-4 w-4" />} />
        <select className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm" aria-label="Filter check-in status" value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setPage(1); }}><option value="">All statuses</option>{['scheduled', 'completed', 'missed', 'cancelled'].map((status) => <option key={status}>{status}</option>)}</select>
      </div>
      {loading ? <Loading /> : result?.items.length ? <><DataTable columns={columns} rows={result.items} getRowKey={(row) => row.id} label="Employee check-ins" /><div className="flex justify-between border-t border-slate-100 pt-4 text-sm text-slate-500"><span>{result.total.toLocaleString()} check-ins</span><div className="flex items-center gap-2"><Button size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button><span>Page {page} of {Math.max(1, Math.ceil(result.total / result.page_size))}</span><Button size="sm" disabled={page * result.page_size >= result.total} onClick={() => setPage((value) => value + 1)}>Next</Button></div></div></> : <EmptyState title="No check-ins found" description="Change the filters or schedule a new check-in." />}
    </section>
    <Modal open={creating} title="Schedule check-in" onClose={() => setCreating(false)} className="w-full max-w-xl">
      <form className="flex-1 space-y-4 overflow-y-auto p-5" onSubmit={(event) => void create(event)}>
        {error && <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
        {[['employee_id', 'Employee ID'], ['manager_id', 'Assigned manager ID'], ['review_cycle_id', 'Review cycle ID (optional)'], ['checkin_date', 'Check-in date'], ['notes', 'Notes']].map(([key, label]) => <label key={key} className="block space-y-1.5 text-sm font-medium text-slate-700">{label}<TextInput type={key === 'checkin_date' ? 'date' : 'text'} required={key !== 'review_cycle_id'} value={form[key as keyof typeof form]} onChange={(event) => setForm((current) => ({ ...current, [key]: event.target.value }))} /></label>)}
        <div className="flex justify-end gap-2 border-t border-slate-100 pt-4"><Button onClick={() => setCreating(false)}>Cancel</Button><Button type="submit" variant="primary" disabled={saving}>{saving ? 'Saving…' : 'Schedule'}</Button></div>
      </form>
    </Modal>
  </div>;
}
