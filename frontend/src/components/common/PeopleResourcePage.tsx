'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Eye, Pencil, Plus, Search } from 'lucide-react';

import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import DataTable, { type DataTableColumn } from '@/components/common/DataTable';
import EmptyState from '@/components/common/EmptyState';
import Loading from '@/components/common/Loading';
import Modal from '@/components/common/Modal';
import TextInput from '@/components/common/TextInput';
import type { PageResult } from '@/services/api';

export interface ResourceField {
  key: string;
  label: string;
  type?: 'text' | 'email' | 'date' | 'select';
  required?: boolean;
  options?: string[];
  nullable?: boolean;
}

export interface PeopleResourceConfig<Row extends { id: string }> {
  title: string;
  description: string;
  fields: ResourceField[];
  columns: Array<{ key: keyof Row & string; label: string }>;
  list: (query: { search: string; status: string; department: string; page: number; page_size: number }) => Promise<PageResult<Row>>;
  get: (id: string) => Promise<Row>;
  create: (payload: Record<string, string | null>) => Promise<Row>;
  update: (id: string, payload: Record<string, string | null>) => Promise<Row>;
}

export default function PeopleResourcePage<Row extends { id: string }>(
  { config }: { config: PeopleResourceConfig<Row> },
) {
  const [result, setResult] = useState<PageResult<Row> | null>(null);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [department, setDepartment] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [details, setDetails] = useState<Row | null>(null);
  const [editing, setEditing] = useState<Row | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setResult(await config.list({ search, status, department, page, page_size: 25 }));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load records.');
    } finally {
      setLoading(false);
    }
  }, [config, search, status, department, page]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), search ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [load, search]);

  const columns = useMemo<DataTableColumn<Row>[]>(() => [
    ...config.columns.map((column) => ({
      key: column.key,
      header: column.label,
      render: (row: Row) => {
        const value = row[column.key];
        if (column.key === 'status') {
          return <Badge tone={value === 'active' ? 'success' : 'neutral'}>{String(value ?? '—')}</Badge>;
        }
        return <span className="block max-w-[240px] truncate" title={String(value ?? '')}>{String(value ?? '—')}</span>;
      },
    })),
    {
      key: 'actions',
      header: 'Actions',
      className: 'text-right',
      render: (row: Row) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" onClick={() => void openDetails(row.id)} aria-label={`View ${row.id}`}>
            <Eye className="h-3.5 w-3.5" /> View
          </Button>
          <Button size="sm" onClick={() => openForm(row)} aria-label={`Edit ${row.id}`}>
            <Pencil className="h-3.5 w-3.5" /> Edit
          </Button>
        </div>
      ),
    },
  ], [config.columns]);

  async function openDetails(id: string) {
    setError(null);
    try {
      setDetails(await config.get(id));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load record details.');
    }
  }

  function openForm(row?: Row) {
    setEditing(row ?? null);
    setValues(Object.fromEntries(config.fields.map((field) => [
      field.key,
      row ? String((row as Record<string, unknown>)[field.key] ?? '') : '',
    ])));
    setError(null);
    setNotice(null);
    setFormOpen(true);
  }

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    const payload: Record<string, string | null> = {};
    for (const field of config.fields) {
      if (editing && !values[field.key] && !field.nullable) continue;
      payload[field.key] = values[field.key] || (field.nullable ? null : '');
    }
    try {
      if (editing) await config.update(editing.id, payload);
      else await config.create(payload);
      setFormOpen(false);
      setNotice(editing ? 'Record updated successfully.' : 'Record created successfully.');
      setPage(1);
      await load();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not save this record.');
    } finally {
      setSaving(false);
    }
  }

  const totalPages = result ? Math.max(1, Math.ceil(result.total / result.page_size)) : 1;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{config.title}</h1>
          <p className="mt-2 text-sm text-slate-500">{config.description}</p>
        </div>
        <Button variant="primary" onClick={() => openForm()}>
          <Plus className="h-4 w-4" /> Add {config.title === 'Employees' ? 'employee' : 'manager'}
        </Button>
      </header>

      {notice && <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</p>}
      {error && !formOpen && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}

      <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        <div className="grid gap-3 md:grid-cols-[minmax(240px,1fr)_180px_220px]">
          <TextInput
            type="search"
            value={search}
            onChange={(event) => { setSearch(event.target.value); setPage(1); }}
            placeholder="Search name, email or ID"
            aria-label="Search records"
            leadingIcon={<Search className="h-4 w-4" />}
          />
          <select className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }} aria-label="Filter by status">
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            {config.title === 'Employees' && <><option value="leave">On leave</option><option value="terminated">Terminated</option></>}
          </select>
          <TextInput value={department} onChange={(event) => { setDepartment(event.target.value); setPage(1); }} placeholder="Filter by department" aria-label="Filter by department" />
        </div>

        {loading ? <Loading /> : result?.items.length ? (
          <>
            <DataTable columns={columns} rows={result.items} getRowKey={(row) => row.id} label={`${config.title} records`} />
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4 text-sm text-slate-500">
              <span>{result.total.toLocaleString()} records</span>
              <div className="flex items-center gap-2">
                <Button size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button>
                <span>Page {page} of {totalPages}</span>
                <Button size="sm" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>Next</Button>
              </div>
            </div>
          </>
        ) : <EmptyState title={search || status || department ? 'No matching records' : `No ${config.title.toLowerCase()} found`} description="Try changing the filters or add a new record." />}
      </section>

      <Modal open={formOpen} title={editing ? `Edit ${config.title.slice(0, -1)}` : `Add ${config.title.slice(0, -1)}`} onClose={() => setFormOpen(false)} className="w-full max-w-xl">
        <form className="flex-1 space-y-4 overflow-y-auto p-5" onSubmit={(event) => void save(event)}>
          {error && <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
          {config.fields.map((field) => (
            <label key={field.key} className="block space-y-1.5 text-sm font-medium text-slate-700">
              <span>{field.label}{field.required && !editing ? ' *' : ''}</span>
              {field.type === 'select' ? (
                <select required={field.required && !editing} className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3" value={values[field.key] ?? ''} onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.target.value }))}>
                  <option value="">Select…</option>
                  {field.options?.map((option) => <option key={option} value={option}>{option}</option>)}
                </select>
              ) : (
                <TextInput type={field.type ?? 'text'} required={field.required && !editing} value={values[field.key] ?? ''} onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.target.value }))} />
              )}
            </label>
          ))}
          <div className="flex justify-end gap-2 border-t border-slate-100 pt-4">
            <Button onClick={() => setFormOpen(false)}>Cancel</Button>
            <Button variant="primary" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save record'}</Button>
          </div>
        </form>
      </Modal>

      <Modal open={details !== null} title="Record details" onClose={() => setDetails(null)} className="w-full max-w-xl">
        {details && <dl className="grid flex-1 content-start grid-cols-1 gap-3 overflow-y-auto p-5 sm:grid-cols-2">
          {Object.entries(details as Record<string, unknown>).map(([key, value]) => (
            <div key={key} className="rounded-lg bg-slate-50 p-3">
              <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{key.replaceAll('_', ' ')}</dt>
              <dd className="mt-1 break-words text-sm text-slate-900">{value === null ? '—' : String(value)}</dd>
            </div>
          ))}
        </dl>}
      </Modal>
    </div>
  );
}
