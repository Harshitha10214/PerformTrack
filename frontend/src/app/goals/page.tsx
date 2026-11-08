'use client';

import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { Eye, Plus, Search } from 'lucide-react';

import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import DataTable, { type DataTableColumn } from '@/components/common/DataTable';
import EmptyState from '@/components/common/EmptyState';
import Loading from '@/components/common/Loading';
import Modal from '@/components/common/Modal';
import TextInput from '@/components/common/TextInput';
import {
  createGoal,
  getGoal,
  getGoals,
  updateGoal,
  updateKeyResult,
  type GoalRecord,
  type KeyResultRecord,
  type PageResult,
} from '@/services/api';

const initialForm = {
  employee_id: '',
  review_cycle_id: '',
  owner_manager_id: '',
  title: '',
  description: '',
  effective_from: '',
  due_date: '',
  status: 'active',
  kr_title: '',
  kr_description: '',
  unit: 'items',
  target_value: '',
  current_value: '',
};

function Field({
  label,
  value,
  onChange,
  type = 'text',
  required = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  required?: boolean;
}) {
  return (
    <label className="block space-y-1.5 text-sm font-medium text-slate-700">
      <span>{label}</span>
      <TextInput type={type} required={required} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

export default function GoalsPage() {
  const [result, setResult] = useState<PageResult<GoalRecord> | null>(null);
  const [selected, setSelected] = useState<GoalRecord | null>(null);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setResult(await getGoals({ search: query, status, page, page_size: 25 }));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load goals.');
    } finally {
      setLoading(false);
    }
  }, [page, query, status]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), query ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [load, query]);

  async function showDetails(id: string) {
    setError(null);
    try {
      setSelected(await getGoal(id));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load goal details.');
    }
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await createGoal({
        employee_id: form.employee_id.trim(),
        review_cycle_id: form.review_cycle_id.trim(),
        owner_manager_id: form.owner_manager_id.trim() || null,
        title: form.title.trim(),
        description: form.description.trim(),
        effective_from: form.effective_from,
        effective_to: null,
        due_date: form.due_date,
        status: form.status,
        key_results: [{
          title: form.kr_title.trim(),
          description: form.kr_description.trim(),
          unit: form.unit.trim(),
          target_value: form.target_value,
          current_value: form.current_value || null,
          weight: '100',
          effective_from: form.effective_from,
          effective_to: null,
          due_date: form.due_date,
          status: 'active',
        }],
      });
      setCreating(false);
      setForm(initialForm);
      setNotice('Goal and key result created.');
      setPage(1);
      await load();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not create the goal.');
    } finally {
      setSaving(false);
    }
  }

  async function saveProgress(keyResult: KeyResultRecord, value: string) {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await updateKeyResult(keyResult.id, { current_value: value || null });
      const refreshed = await getGoal(keyResult.goal_id);
      setSelected(refreshed);
      setNotice('Key result progress updated from its latest source value.');
      await load();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not update key result.');
    } finally {
      setSaving(false);
    }
  }

  async function changeGoalStatus(goal: GoalRecord, nextStatus: string) {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await updateGoal(goal.id, { status: nextStatus });
      setSelected(updated);
      setNotice('Goal status updated.');
      await load();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not update goal status.');
    } finally {
      setSaving(false);
    }
  }

  const columns = useMemo<DataTableColumn<GoalRecord>[]>(() => [
    { key: 'id', header: 'Goal ID', render: (goal) => <span className="font-medium text-slate-800">{goal.id}</span> },
    { key: 'title', header: 'Goal', render: (goal) => <span className="block max-w-[260px] truncate" title={goal.title}>{goal.title}</span> },
    { key: 'employee_name', header: 'Employee', render: (goal) => goal.employee_name },
    { key: 'review_cycle_name', header: 'Review cycle', render: (goal) => goal.review_cycle_name },
    { key: 'progress', header: 'Progress', render: (goal) => <span className="font-semibold tabular-nums text-slate-800">{Number(goal.progress).toFixed(1)}%</span> },
    { key: 'status', header: 'Status', render: (goal) => <Badge tone={goal.status === 'completed' ? 'success' : 'neutral'}>{goal.status.replaceAll('_', ' ')}</Badge> },
    { key: 'actions', header: 'Details', className: 'text-right', render: (goal) => <Button size="sm" onClick={() => void showDetails(goal.id)}><Eye className="h-3.5 w-3.5" /> View</Button> },
  ], []);

  const totalPages = result ? Math.max(1, Math.ceil(result.total / result.page_size)) : 1;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Goals & Key Results</h1>
          <p className="mt-2 text-sm text-slate-500">Track goals and calculate progress directly from key-result actuals and targets.</p>
        </div>
        <Button variant="primary" onClick={() => { setError(null); setCreating(true); }}><Plus className="h-4 w-4" /> Add goal</Button>
      </header>
      {notice && <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</p>}
      {error && !creating && !selected && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}
      <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        <div className="grid gap-3 md:grid-cols-[minmax(240px,1fr)_200px]">
          <TextInput type="search" value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder="Search goals, employees or IDs" aria-label="Search goals" leadingIcon={<Search className="h-4 w-4" />} />
          <select className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm" aria-label="Filter goal status" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            {['draft', 'active', 'on_track', 'at_risk', 'completed', 'cancelled'].map((value) => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}
          </select>
        </div>
        {loading ? <Loading /> : result?.items.length ? <>
          <DataTable columns={columns} rows={result.items} getRowKey={(goal) => goal.id} label="Goals" />
          <div className="flex items-center justify-between border-t border-slate-100 pt-4 text-sm text-slate-500">
            <span>{result.total.toLocaleString()} goals</span>
            <div className="flex items-center gap-2">
              <Button size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button>
              <span>Page {page} of {totalPages}</span>
              <Button size="sm" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>Next</Button>
            </div>
          </div>
        </> : <EmptyState title="No goals found" description="Change the filters or add a goal to this workspace." />}
      </section>

      <Modal open={creating} title="Create goal and key result" onClose={() => setCreating(false)} className="w-full max-w-2xl">
        <form className="flex-1 space-y-4 overflow-y-auto p-5" onSubmit={(event) => void create(event)}>
          {error && <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Employee ID" required value={form.employee_id} onChange={(value) => setForm((current) => ({ ...current, employee_id: value }))} />
            <Field label="Review cycle ID" required value={form.review_cycle_id} onChange={(value) => setForm((current) => ({ ...current, review_cycle_id: value }))} />
            <Field label="Owner manager ID (optional)" value={form.owner_manager_id} onChange={(value) => setForm((current) => ({ ...current, owner_manager_id: value }))} />
            <Field label="Goal title" required value={form.title} onChange={(value) => setForm((current) => ({ ...current, title: value }))} />
            <Field label="Effective from" type="date" required value={form.effective_from} onChange={(value) => setForm((current) => ({ ...current, effective_from: value }))} />
            <Field label="Due date" type="date" required value={form.due_date} onChange={(value) => setForm((current) => ({ ...current, due_date: value }))} />
            <Field label="Key result title" required value={form.kr_title} onChange={(value) => setForm((current) => ({ ...current, kr_title: value }))} />
            <Field label="Measurement unit" required value={form.unit} onChange={(value) => setForm((current) => ({ ...current, unit: value }))} />
            <Field label="Target value" type="number" required value={form.target_value} onChange={(value) => setForm((current) => ({ ...current, target_value: value }))} />
            <Field label="Current value (optional)" type="number" value={form.current_value} onChange={(value) => setForm((current) => ({ ...current, current_value: value }))} />
          </div>
          <Field label="Goal description" required value={form.description} onChange={(value) => setForm((current) => ({ ...current, description: value }))} />
          <Field label="Key result description" required value={form.kr_description} onChange={(value) => setForm((current) => ({ ...current, kr_description: value }))} />
          <div className="flex justify-end gap-2 border-t border-slate-100 pt-4">
            <Button onClick={() => setCreating(false)}>Cancel</Button>
            <Button variant="primary" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Create goal'}</Button>
          </div>
        </form>
      </Modal>

      <Modal open={selected !== null} title="Goal details" onClose={() => setSelected(null)} className="w-full max-w-3xl">
        {selected && <div className="flex-1 space-y-5 overflow-y-auto p-5">
          {error && <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs text-slate-500">{selected.id} · {selected.employee_name} · {selected.review_cycle_name}</p>
              <h3 className="mt-1 text-lg font-semibold text-slate-900">{selected.title}</h3>
              <p className="mt-2 text-sm text-slate-600">{selected.description}</p>
            </div>
            <label className="text-xs font-medium text-slate-500">Goal status
              <select className="mt-1 block h-9 rounded-lg border border-slate-200 bg-white px-2 text-sm text-slate-800" value={selected.status} disabled={saving} onChange={(event) => void changeGoalStatus(selected, event.target.value)}>
                {['draft', 'active', 'on_track', 'at_risk', 'completed', 'cancelled'].map((value) => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}
              </select>
            </label>
          </div>
          <div className="rounded-lg bg-indigo-50 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-indigo-700">Calculated goal progress</p>
            <p className="mt-1 text-2xl font-semibold text-indigo-900">{Number(selected.progress).toFixed(1)}%</p>
          </div>
          <h4 className="text-sm font-semibold text-slate-800">Key results</h4>
          {selected.key_results.map((keyResult) => <KeyResultProgress key={keyResult.id} keyResult={keyResult} saving={saving} onSave={saveProgress} />)}
        </div>}
      </Modal>
    </div>
  );
}

function KeyResultProgress({
  keyResult,
  saving,
  onSave,
}: {
  keyResult: KeyResultRecord;
  saving: boolean;
  onSave: (keyResult: KeyResultRecord, value: string) => Promise<void>;
}) {
  const [value, setValue] = useState(keyResult.current_value ?? '');
  return (
    <form className="space-y-3 rounded-xl border border-slate-200 p-4" onSubmit={(event) => { event.preventDefault(); void onSave(keyResult, value); }}>
      <div className="flex flex-wrap justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-slate-800">{keyResult.title}</p>
          <p className="mt-1 text-xs text-slate-500">{keyResult.id} · target {keyResult.target_value} {keyResult.unit}</p>
          <p className="mt-1 text-sm text-slate-600">{keyResult.description}</p>
        </div>
        <Badge>{Number(keyResult.progress).toFixed(1)}%</Badge>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-40 flex-1 text-xs font-medium text-slate-600">Actual value
          <TextInput type="number" min="0" step="any" value={value} onChange={(event) => setValue(event.target.value)} />
        </label>
        <Button type="submit" variant="primary" size="sm" disabled={saving}>{saving ? 'Saving…' : 'Update actual'}</Button>
      </div>
    </form>
  );
}
