'use client';

import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { Eye, MessageSquarePlus, Pencil, Search, UsersRound } from 'lucide-react';

import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import DataTable, { type DataTableColumn } from '@/components/common/DataTable';
import EmptyState from '@/components/common/EmptyState';
import Loading from '@/components/common/Loading';
import Modal from '@/components/common/Modal';
import TextInput from '@/components/common/TextInput';
import {
  createFeedback,
  getCompetencies,
  getEmployeeCompetencies,
  getEmployees,
  getFeedback,
  getFeedbackRecord,
  updateFeedback,
  type CompetencyRecord,
  type EmployeeCompetencyRecord,
  type EmployeeRecord,
  type FeedbackRecord,
  type PageResult,
} from '@/services/api';

type Tab = 'competencies' | 'feedback';
type PersonRole = 'author' | 'subject';

const emptyDraft = {
  author: null as EmployeeRecord | null,
  subject: null as EmployeeRecord | null,
  content: '',
  visibility: 'private' as FeedbackRecord['visibility'],
  status: 'draft' as 'draft' | 'submitted',
  competencyIds: [] as string[],
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value));
}

export default function FeedbackPage() {
  const [tab, setTab] = useState<Tab>('competencies');
  const [competencyResult, setCompetencyResult] = useState<PageResult<CompetencyRecord> | null>(null);
  const [competencySearch, setCompetencySearch] = useState('');
  const [competencyCategory, setCompetencyCategory] = useState('');
  const [competencyPage, setCompetencyPage] = useState(1);
  const [competencies, setCompetencies] = useState<CompetencyRecord[]>([]);
  const [selectedCompetency, setSelectedCompetency] = useState<CompetencyRecord | null>(null);
  const [employeeCompetencies, setEmployeeCompetencies] = useState<EmployeeCompetencyRecord[] | null>(null);
  const [ratingEmployee, setRatingEmployee] = useState<EmployeeRecord | null>(null);
  const [feedbackResult, setFeedbackResult] = useState<PageResult<FeedbackRecord> | null>(null);
  const [feedbackSearch, setFeedbackSearch] = useState('');
  const [feedbackStatus, setFeedbackStatus] = useState('');
  const [feedbackVisibility, setFeedbackVisibility] = useState('');
  const [feedbackRelationship, setFeedbackRelationship] = useState('');
  const [feedbackPage, setFeedbackPage] = useState(1);
  const [selectedFeedback, setSelectedFeedback] = useState<FeedbackRecord | null>(null);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(emptyDraft);
  const [loadingCompetencies, setLoadingCompetencies] = useState(true);
  const [loadingFeedback, setLoadingFeedback] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadCompetencies = useCallback(async () => {
    setLoadingCompetencies(true);
    setError(null);
    try {
      const [page, all] = await Promise.all([
        getCompetencies({
          search: competencySearch,
          category: competencyCategory,
          status: 'active',
          page: competencyPage,
          page_size: 25,
        }),
        getCompetencies({ page: 1, page_size: 100 }),
      ]);
      setCompetencyResult(page);
      setCompetencies(all.items.filter((item) => item.status === 'active'));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load competencies.');
    } finally {
      setLoadingCompetencies(false);
    }
  }, [competencyCategory, competencyPage, competencySearch]);

  const loadFeedback = useCallback(async () => {
    setLoadingFeedback(true);
    setError(null);
    try {
      setFeedbackResult(await getFeedback({
        search: feedbackSearch,
        status: feedbackStatus,
        visibility: feedbackVisibility,
        relationship: feedbackRelationship ? (feedbackRelationship as 'manager' | 'peer') : undefined,
        page: feedbackPage,
        page_size: 25,
      }));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load feedback.');
    } finally {
      setLoadingFeedback(false);
    }
  }, [feedbackPage, feedbackRelationship, feedbackSearch, feedbackStatus, feedbackVisibility]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadCompetencies(), competencySearch ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [loadCompetencies, competencySearch]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadFeedback(), feedbackSearch ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [loadFeedback, feedbackSearch]);

  const categories = useMemo(
    () => Array.from(new Set(competencies.map((item) => item.category))).sort(),
    [competencies],
  );

  async function loadEmployeeCompetencies(employee: EmployeeRecord) {
    setError(null);
    setRatingEmployee(employee);
    setEmployeeCompetencies(null);
    try {
      setEmployeeCompetencies(await getEmployeeCompetencies(employee.id));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load employee competency ratings.');
    }
  }

  async function openFeedback(id: string): Promise<FeedbackRecord | null> {
    setError(null);
    setSelectedFeedback(null);
    try {
      const feedback = await getFeedbackRecord(id);
      setSelectedFeedback(feedback);
      return feedback;
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load feedback details.');
      return null;
    }
  }

  function startCreate() {
    setDraft(emptyDraft);
    setError(null);
    setNotice(null);
    setCreating(true);
    setEditing(false);
  }

  function startEdit(feedback = selectedFeedback) {
    if (!feedback?.editable) return;
    setSelectedFeedback(feedback);
    setDraft({
      author: null,
      subject: null,
      content: feedback.content,
      visibility: feedback.visibility,
      status: feedback.status === 'submitted' ? 'submitted' : 'draft',
      competencyIds: feedback.competencies.map((item) => item.id),
    });
    setError(null);
    setEditing(true);
  }

  async function saveFeedback(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      if (editing && selectedFeedback) {
        await updateFeedback(selectedFeedback.id, {
          content: draft.content.trim(),
          visibility: draft.visibility,
          status: draft.status,
          competency_ids: draft.competencyIds,
        });
        setEditing(false);
        await openFeedback(selectedFeedback.id);
        setNotice('Draft feedback updated.');
      } else {
        if (!draft.author || !draft.subject) {
          setError('Select both the reviewer and the employee receiving feedback.');
          return;
        }
        await createFeedback({
          author_employee_id: draft.author.id,
          subject_employee_id: draft.subject.id,
          content: draft.content.trim(),
          visibility: draft.visibility,
          status: draft.status,
          competency_ids: draft.competencyIds,
        });
        setCreating(false);
        setDraft(emptyDraft);
        setFeedbackPage(1);
        setNotice('Feedback created and recorded in history.');
        await loadFeedback();
      }
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not save feedback.');
    } finally {
      setSaving(false);
    }
  }

  async function changeFeedbackStatus(status: 'submitted' | 'withdrawn') {
    if (!selectedFeedback) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateFeedback(selectedFeedback.id, { status });
      setSelectedFeedback(updated);
      setNotice(status === 'submitted' ? 'Feedback submitted.' : 'Feedback withdrawn.');
      await loadFeedback();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not update feedback status.');
    } finally {
      setSaving(false);
    }
  }

  const competencyColumns: DataTableColumn<CompetencyRecord>[] = [
    { key: 'name', header: 'Competency', render: (item) => <><span className="font-medium text-slate-800">{item.name}</span><span className="mt-1 block max-w-[360px] text-xs leading-5 text-slate-500">{item.description}</span></> },
    { key: 'category', header: 'Category', render: (item) => <Badge tone="info">{item.category}</Badge> },
    { key: 'employee_count', header: 'Employees rated', render: (item) => item.employee_count.toLocaleString() },
    { key: 'actions', header: 'Details', className: 'text-right', render: (item) => <Button size="sm" onClick={() => setSelectedCompetency(item)}><Eye className="h-3.5 w-3.5" /> View</Button> },
  ];

  const feedbackColumns: DataTableColumn<FeedbackRecord>[] = [
    { key: 'created_at', header: 'Date', render: (item) => formatDate(item.created_at) },
    { key: 'subject_name', header: 'Employee', render: (item) => <><span className="font-medium text-slate-800">{item.subject_name}</span><span className="block text-xs text-slate-500">{item.subject_employee_id}</span></> },
    { key: 'author_name', header: 'Reviewer', render: (item) => <><span className="text-slate-700">{item.author_name}</span><span className="block text-xs capitalize text-slate-500">{item.reviewer_relationship} feedback</span></> },
    { key: 'competencies', header: 'Competencies', render: (item) => <span className="block max-w-[240px] truncate" title={item.competencies.map((competency) => competency.name).join(', ')}>{item.competencies.map((competency) => competency.name).join(', ') || '—'}</span> },
    { key: 'visibility', header: 'Visibility', render: (item) => <Badge>{item.visibility.replaceAll('_', ' ')}</Badge> },
    { key: 'status', header: 'Status', render: (item) => <Badge tone={item.status === 'submitted' ? 'success' : item.status === 'withdrawn' ? 'warning' : 'neutral'}>{item.status}</Badge> },
    { key: 'actions', header: 'Details', className: 'text-right', render: (item) => <div className="flex justify-end gap-1"><Button size="sm" onClick={() => void openFeedback(item.id)} aria-label={`View feedback by ${item.author_name}`}><Eye className="h-3.5 w-3.5" /> View</Button>{item.editable && <Button size="sm" onClick={() => void openFeedback(item.id).then((record) => { if (record?.editable) startEdit(record); })} aria-label={`Edit feedback ${item.id}`}><Pencil className="h-3.5 w-3.5" /> Edit</Button>}</div> },
  ];

  const createOpen = creating || editing;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Competencies & Feedback</h1>
          <p className="mt-2 text-sm text-slate-500">Explore competency definitions and ratings, and manage employee feedback.</p>
        </div>
        {tab === 'feedback' && <Button variant="primary" onClick={startCreate}><MessageSquarePlus className="h-4 w-4" /> Give feedback</Button>}
      </header>

      <aside className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-5 text-amber-900" role="note">
        Authentication and reviewer authorization are not configured. Reviewer selections are recorded for audit attribution, but feedback visibility labels are not access-controlled.
      </aside>
      {notice && <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</p>}
      {error && !createOpen && !selectedFeedback && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}

      <div className="flex gap-2 border-b border-slate-200" role="tablist" aria-label="Competency and feedback views">
        <button type="button" role="tab" aria-selected={tab === 'competencies'} onClick={() => setTab('competencies')} className={`border-b-2 px-4 py-3 text-sm font-medium ${tab === 'competencies' ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-slate-500 hover:text-slate-800'}`}><UsersRound className="mr-2 inline h-4 w-4" />Competencies</button>
        <button type="button" role="tab" aria-selected={tab === 'feedback'} onClick={() => setTab('feedback')} className={`border-b-2 px-4 py-3 text-sm font-medium ${tab === 'feedback' ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-slate-500 hover:text-slate-800'}`}><MessageSquarePlus className="mr-2 inline h-4 w-4" />Feedback</button>
      </div>

      {tab === 'competencies' ? (
        <section className="space-y-5">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
            <div className="mb-4">
              <h2 className="text-base font-semibold text-slate-900">Competency library</h2>
              <p className="mt-1 text-sm text-slate-500">Definitions and the number of employees with recorded proficiency.</p>
            </div>
            <div className="mb-4 grid gap-3 md:grid-cols-[minmax(240px,1fr)_220px]">
              <TextInput type="search" value={competencySearch} onChange={(event) => { setCompetencySearch(event.target.value); setCompetencyPage(1); }} placeholder="Search competency name or description" aria-label="Search competencies" leadingIcon={<Search className="h-4 w-4" />} />
              <select className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm" aria-label="Filter by competency category" value={competencyCategory} onChange={(event) => { setCompetencyCategory(event.target.value); setCompetencyPage(1); }}>
                <option value="">All categories</option>{categories.map((category) => <option key={category} value={category}>{category}</option>)}
              </select>
            </div>
            {loadingCompetencies ? <Loading /> : competencyResult?.items.length ? <>
              <DataTable columns={competencyColumns} rows={competencyResult.items} getRowKey={(item) => item.id} label="Competency library" />
              <Pagination page={competencyPage} result={competencyResult} onPage={setCompetencyPage} itemLabel="competencies" />
            </> : <EmptyState title="No competencies found" description="Try a different search or category." />}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
            <div className="mb-4">
              <h2 className="text-base font-semibold text-slate-900">Employee competency ratings</h2>
              <p className="mt-1 text-sm text-slate-500">Search an employee to see proficiency ratings from PostgreSQL.</p>
            </div>
            <EmployeePicker label="Find employee" selected={ratingEmployee} onSelect={(employee) => { if (employee) void loadEmployeeCompetencies(employee); else { setRatingEmployee(null); setEmployeeCompetencies(null); } }} />
            {ratingEmployee && employeeCompetencies === null ? <div className="mt-4"><Loading /></div> : null}
            {ratingEmployee && employeeCompetencies && (
              employeeCompetencies.length ? <div className="mt-4 space-y-3">
                <p className="text-sm font-medium text-slate-700">{ratingEmployee.first_name} {ratingEmployee.last_name} · {ratingEmployee.department}</p>
                <DataTable
                  label={`${ratingEmployee.first_name} ${ratingEmployee.last_name} competency ratings`}
                  getRowKey={(item) => item.competency_id}
                  rows={employeeCompetencies}
                  columns={[
                    { key: 'name', header: 'Competency', render: (item) => <><span className="font-medium text-slate-800">{item.name}</span><span className="block text-xs text-slate-500">{item.description}</span></> },
                    { key: 'category', header: 'Category', render: (item) => item.category },
                    { key: 'proficiency', header: 'Proficiency', render: (item) => <Proficiency value={Number(item.proficiency)} /> },
                    { key: 'effective_from', header: 'Effective from', render: (item) => item.effective_from },
                  ]}
                />
              </div> : <div className="mt-4"><EmptyState title="No competency ratings" description="No employee competency relationships are recorded for this employee." /></div>
            )}
          </div>
        </section>
      ) : (
        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
          <div className="grid gap-3 md:grid-cols-[minmax(220px,1fr)_160px_170px_170px]">
            <TextInput type="search" value={feedbackSearch} onChange={(event) => { setFeedbackSearch(event.target.value); setFeedbackPage(1); }} placeholder="Search feedback, reviewer or employee" aria-label="Search feedback" leadingIcon={<Search className="h-4 w-4" />} />
            <select className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm" aria-label="Filter feedback status" value={feedbackStatus} onChange={(event) => { setFeedbackStatus(event.target.value); setFeedbackPage(1); }}><option value="">All statuses</option>{['draft', 'submitted', 'withdrawn'].map((value) => <option key={value}>{value}</option>)}</select>
            <select className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm" aria-label="Filter feedback visibility" value={feedbackVisibility} onChange={(event) => { setFeedbackVisibility(event.target.value); setFeedbackPage(1); }}><option value="">All visibility</option>{['private', 'manager', 'review_cycle'].map((value) => <option key={value}>{value.replaceAll('_', ' ')}</option>)}</select>
            <select className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm" aria-label="Filter reviewer relationship" value={feedbackRelationship} onChange={(event) => { setFeedbackRelationship(event.target.value); setFeedbackPage(1); }}><option value="">All reviewers</option><option value="manager">Manager</option><option value="peer">Peer</option></select>
          </div>
          {loadingFeedback ? <Loading /> : feedbackResult?.items.length ? <>
            <DataTable columns={feedbackColumns} rows={feedbackResult.items} getRowKey={(item) => item.id} label="Employee feedback records" />
            <Pagination page={feedbackPage} result={feedbackResult} onPage={setFeedbackPage} itemLabel="feedback records" />
          </> : <EmptyState title="No feedback found" description="Try changing the filters or give feedback to an employee." />}
        </section>
      )}

      <Modal open={creating} title="Give employee feedback" onClose={() => setCreating(false)} className="w-full max-w-2xl">
        <FeedbackForm
          draft={draft}
          setDraft={setDraft}
          competencies={competencies}
          error={error}
          saving={saving}
          onSubmit={saveFeedback}
          onCancel={() => setCreating(false)}
        />
      </Modal>

      <Modal open={editing} title="Edit draft feedback" onClose={() => setEditing(false)} className="w-full max-w-2xl">
        <FeedbackForm
          draft={draft}
          setDraft={setDraft}
          competencies={competencies}
          error={error}
          saving={saving}
          onSubmit={saveFeedback}
          onCancel={() => setEditing(false)}
          editMode
        />
      </Modal>

      <Modal open={selectedCompetency !== null} title="Competency details" onClose={() => setSelectedCompetency(null)} className="w-full max-w-xl">
        {selectedCompetency && <dl className="grid flex-1 content-start gap-4 overflow-y-auto p-5">
          <div><dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Competency</dt><dd className="mt-1 text-lg font-semibold text-slate-900">{selectedCompetency.name}</dd></div>
          <div><dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Category</dt><dd className="mt-1 text-sm text-slate-800">{selectedCompetency.category}</dd></div>
          <div><dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Description</dt><dd className="mt-1 text-sm leading-6 text-slate-700">{selectedCompetency.description}</dd></div>
          <div><dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Employees with a rating</dt><dd className="mt-1 text-sm text-slate-800">{selectedCompetency.employee_count.toLocaleString()}</dd></div>
        </dl>}
      </Modal>

      <Modal open={selectedFeedback !== null} title="Feedback details" onClose={() => setSelectedFeedback(null)} className="w-full max-w-2xl">
        {selectedFeedback && <div className="flex-1 space-y-5 overflow-y-auto p-5">
          {error && <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
          {notice && <p role="status" className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{notice}</p>}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><p className="text-xs text-slate-500">{selectedFeedback.id} · {formatDate(selectedFeedback.created_at)}</p><h3 className="mt-1 text-lg font-semibold text-slate-900">{selectedFeedback.subject_name}</h3></div>
            <Badge tone={selectedFeedback.status === 'submitted' ? 'success' : selectedFeedback.status === 'withdrawn' ? 'warning' : 'neutral'}>{selectedFeedback.status}</Badge>
          </div>
          <dl className="grid gap-3 sm:grid-cols-2">
            <Detail label="Reviewer" value={selectedFeedback.author_name} />
            <Detail label="Reviewer relationship" value={selectedFeedback.reviewer_relationship} />
            <Detail label="Visibility" value={selectedFeedback.visibility.replaceAll('_', ' ')} />
            <Detail label="Review cycle" value={selectedFeedback.review_cycle_name ?? 'Not associated with a cycle'} />
          </dl>
          <div><h4 className="text-xs font-medium uppercase tracking-wide text-slate-500">Feedback</h4><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{selectedFeedback.content}</p></div>
          <div><h4 className="text-xs font-medium uppercase tracking-wide text-slate-500">Related competencies</h4><div className="mt-2 flex flex-wrap gap-2">{selectedFeedback.competencies.map((item) => <Badge key={item.id} tone="info">{item.name}</Badge>)}</div></div>
          <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-4">
            {selectedFeedback.editable && <Button onClick={() => startEdit()}><Pencil className="h-3.5 w-3.5" /> Edit draft</Button>}
            {selectedFeedback.status === 'draft' && selectedFeedback.editable && <Button variant="primary" disabled={saving} onClick={() => void changeFeedbackStatus('submitted')}>{saving ? 'Saving…' : 'Submit feedback'}</Button>}
            {selectedFeedback.withdrawable && selectedFeedback.status !== 'withdrawn' && <Button variant="danger" disabled={saving} onClick={() => void changeFeedbackStatus('withdrawn')}>Withdraw</Button>}
          </div>
        </div>}
      </Modal>
    </div>
  );
}

function Pagination<T>({
  page,
  result,
  itemLabel,
  onPage,
}: {
  page: number;
  result: PageResult<T>;
  itemLabel: string;
  onPage: (page: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(result.total / result.page_size));
  return <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4 text-sm text-slate-500">
    <span>{result.total.toLocaleString()} {itemLabel}</span>
    <div className="flex items-center gap-2"><Button size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</Button><span>Page {page} of {totalPages}</span><Button size="sm" disabled={page >= totalPages} onClick={() => onPage(page + 1)}>Next</Button></div>
  </div>;
}

function Proficiency({ value }: { value: number }) {
  return <div className="flex items-center gap-2" aria-label={`Proficiency ${value} out of 5`}>
    <span className="w-8 font-semibold tabular-nums text-slate-800">{value}/5</span>
    <span className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100"><span className="block h-full rounded-full bg-indigo-500" style={{ width: `${Math.min(100, Math.max(0, value / 5 * 100))}%` }} /></span>
  </div>;
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg bg-slate-50 p-3"><dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt><dd className="mt-1 text-sm capitalize text-slate-800">{value}</dd></div>;
}

function EmployeePicker({
  label,
  selected,
  onSelect,
}: {
  label: string;
  selected: EmployeeRecord | null;
  onSelect: (employee: EmployeeRecord | null) => void;
}) {
  const [query, setQuery] = useState(selected ? `${selected.first_name} ${selected.last_name}` : '');
  const [options, setOptions] = useState<EmployeeRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (query.trim().length < 2 || (selected && query === `${selected.first_name} ${selected.last_name}`)) {
      setOptions([]);
      return;
    }
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      getEmployees({ search: query.trim(), page: 1, page_size: 10 })
        .then((result) => setOptions(result.items))
        .catch((loadError: unknown) => setError(loadError instanceof Error ? loadError.message : 'Could not search employees.'))
        .finally(() => setLoading(false));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [query, selected]);

  return <div className="space-y-1.5">
    <label className="block text-sm font-medium text-slate-700">{label}
      <TextInput value={query} autoComplete="off" placeholder="Type an employee name or email" onChange={(event) => { setQuery(event.target.value); if (selected) onSelect(null); }} aria-label={label} />
    </label>
    {selected && <p className="text-xs text-emerald-700">Selected: {selected.first_name} {selected.last_name} · {selected.department}</p>}
    {loading && <p className="text-xs text-slate-500">Searching employees…</p>}
    {error && <p role="alert" className="text-xs text-rose-700">{error}</p>}
    {options.length > 0 && <ul className="max-h-44 overflow-y-auto rounded-lg border border-slate-200 bg-white p-1 shadow-sm" aria-label={`${label} search results`}>
      {options.map((employee) => <li key={employee.id}><button type="button" className="w-full rounded-md px-3 py-2 text-left hover:bg-slate-50" onClick={() => { onSelect(employee); setQuery(`${employee.first_name} ${employee.last_name}`); setOptions([]); }}>
        <span className="block text-sm font-medium text-slate-800">{employee.first_name} {employee.last_name}</span><span className="block text-xs text-slate-500">{employee.job_title} · {employee.department} · {employee.email}</span>
      </button></li>)}
    </ul>}
  </div>;
}

function FeedbackForm({
  draft,
  setDraft,
  competencies,
  error,
  saving,
  onSubmit,
  onCancel,
  editMode = false,
}: {
  draft: typeof emptyDraft;
  setDraft: (value: typeof emptyDraft | ((current: typeof emptyDraft) => typeof emptyDraft)) => void;
  competencies: CompetencyRecord[];
  error: string | null;
  saving: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancel: () => void;
  editMode?: boolean;
}) {
  return <form className="flex-1 space-y-4 overflow-y-auto p-5" onSubmit={onSubmit}>
    {error && <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
    {!editMode && <>
      <EmployeePicker label="Reviewer (feedback author)" selected={draft.author} onSelect={(employee) => setDraft((current) => ({ ...current, author: employee }))} />
      <EmployeePicker label="Employee receiving feedback" selected={draft.subject} onSelect={(employee) => setDraft((current) => ({ ...current, subject: employee }))} />
      <p className="text-xs leading-5 text-slate-500">Manager or peer relationship is derived and verified from the selected employees’ reporting relationship.</p>
    </>}
    <label className="block space-y-1.5 text-sm font-medium text-slate-700">Feedback
      <textarea required minLength={1} rows={5} value={draft.content} onChange={(event) => setDraft((current) => ({ ...current, content: event.target.value }))} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100" placeholder="Share specific observations and actionable feedback." />
    </label>
    <label className="block space-y-1.5 text-sm font-medium text-slate-700">Visibility
      <select className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm" value={draft.visibility} onChange={(event) => setDraft((current) => ({ ...current, visibility: event.target.value as FeedbackRecord['visibility'] }))}>
        <option value="private">Private</option><option value="manager">Manager</option><option value="review_cycle">Review cycle</option>
      </select>
    </label>
    {!editMode && <label className="block space-y-1.5 text-sm font-medium text-slate-700">Save as
      <select className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm" value={draft.status} onChange={(event) => setDraft((current) => ({ ...current, status: event.target.value as 'draft' | 'submitted' }))}>
        <option value="draft">Draft (editable)</option><option value="submitted">Submit immediately</option>
      </select>
    </label>}
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium text-slate-700">Related competencies *</legend>
      <div className="max-h-44 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2">
        {competencies.map((competency) => <label key={competency.id} className="flex items-start gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-slate-50">
          <input type="checkbox" className="mt-0.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" checked={draft.competencyIds.includes(competency.id)} onChange={(event) => setDraft((current) => ({ ...current, competencyIds: event.target.checked ? [...current.competencyIds, competency.id] : current.competencyIds.filter((id) => id !== competency.id) }))} />
          <span><span className="font-medium text-slate-800">{competency.name}</span><span className="ml-2 text-xs text-slate-500">{competency.category}</span></span>
        </label>)}
      </div>
      {draft.competencyIds.length === 0 && <p className="text-xs text-rose-600">Select at least one active competency.</p>}
    </fieldset>
    <div className="flex justify-end gap-2 border-t border-slate-100 pt-4">
      <Button onClick={onCancel}>Cancel</Button>
      <Button variant="primary" type="submit" disabled={saving || draft.competencyIds.length === 0 || (!editMode && (!draft.author || !draft.subject))}>{saving ? 'Saving…' : editMode ? 'Save changes' : 'Save feedback'}</Button>
    </div>
  </form>;
}
