'use client';

import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { Check, Eye, FilePlus2, Pencil, Search, X } from 'lucide-react';

import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import DataTable, { type DataTableColumn } from '@/components/common/DataTable';
import EmptyState from '@/components/common/EmptyState';
import Loading from '@/components/common/Loading';
import Modal from '@/components/common/Modal';
import TextInput from '@/components/common/TextInput';
import {
  createReview,
  createReviewCycle,
  decideReviewApproval,
  getEmployees,
  getReviewCycle,
  getReview,
  getReviewCycles,
  getReviews,
  getManager,
  getManagers,
  getCompetencies,
  updateReview,
  updateReviewCycle,
  type CompetencyRecord,
  type EmployeeRecord,
  type ManagerRecord,
  type PageResult,
  type ReviewCycleRecord,
  type ReviewRecord,
} from '@/services/api';

type ViewTab = 'reviews' | 'cycles';

const initialCycle = {
  year: 2027,
  half: 'H1' as 'H1' | 'H2',
  name: '2027 H1 Performance Cycle',
  starts_on: '2027-01-01',
  ends_on: '2027-06-30',
};

const initialReview = {
  employee: null as EmployeeRecord | null,
  reviewer: null as ManagerRecord | null,
  review_cycle_id: '',
  summary: '',
  rating: '',
  effective_from: '',
  effective_to: '',
  competency_ids: [] as string[],
};

function displayStatus(status: string) {
  return status.replaceAll('_', ' ');
}

function statusTone(status: string): 'neutral' | 'success' | 'warning' | 'info' {
  if (['approved', 'acknowledged', 'open'].includes(status)) return 'success';
  if (['draft', 'pending', 'in_progress'].includes(status)) return 'warning';
  if (['submitted'].includes(status)) return 'info';
  return 'neutral';
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(`${value}T00:00:00`));
}

function TextArea({
  label,
  value,
  onChange,
  required = false,
  rows = 4,
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  rows?: number;
  disabled?: boolean;
}) {
  return (
    <label className="block space-y-1.5 text-sm font-medium text-slate-700">
      <span>{label}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required={required}
        rows={rows}
        disabled={disabled}
        className="block w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500"
      />
    </label>
  );
}

function EmployeePicker({
  selected,
  onSelect,
}: {
  selected: EmployeeRecord | null;
  onSelect: (employee: EmployeeRecord | null) => void;
}) {
  const [query, setQuery] = useState('');
  const [matches, setMatches] = useState<EmployeeRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (selected || query.trim().length < 2) {
      setMatches([]);
      return;
    }
    let active = true;
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await getEmployees({ search: query.trim(), page: 1, page_size: 10 });
        if (active) setMatches(result.items);
      } catch (loadError) {
        if (active) setError(loadError instanceof Error ? loadError.message : 'Could not search employees.');
      } finally {
        if (active) setLoading(false);
      }
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [query, selected]);

  if (selected) {
    return (
      <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
        <span className="text-sm font-medium text-slate-800">
          {selected.first_name} {selected.last_name}
          <span className="ml-2 text-xs font-normal text-slate-500">{selected.department}</span>
        </span>
        <Button size="sm" aria-label="Change employee" onClick={() => { onSelect(null); setQuery(''); }}>
          Change
        </Button>
      </div>
    );
  }

  return (
    <div className="relative space-y-1.5">
      <label className="block text-sm font-medium text-slate-700" htmlFor="review-employee-search">Employee</label>
      <TextInput
        id="review-employee-search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search by employee name, email or ID"
        autoComplete="off"
      />
      {loading && <p className="text-xs text-slate-500">Searching employees…</p>}
      {error && <p role="alert" className="text-xs text-rose-700">{error}</p>}
      {matches.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
          {matches.map((employee) => (
            <li key={employee.id}>
              <button
                type="button"
                className="w-full px-3 py-2 text-left text-sm hover:bg-indigo-50"
                onClick={() => { onSelect(employee); setMatches([]); }}
              >
                <span className="font-medium text-slate-800">{employee.first_name} {employee.last_name}</span>
                <span className="ml-2 text-xs text-slate-500">{employee.department} · {employee.email}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {!loading && query.trim().length >= 2 && matches.length === 0 && !error && (
        <p className="text-xs text-slate-500">No matching employees found.</p>
      )}
    </div>
  );
}

function ManagerPicker({
  selected,
  employeeId,
  onSelect,
}: {
  selected: ManagerRecord | null;
  employeeId: string;
  onSelect: (manager: ManagerRecord | null) => void;
}) {
  const [query, setQuery] = useState('');
  const [matches, setMatches] = useState<ManagerRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (selected || query.trim().length < 2) {
      setMatches([]);
      return;
    }
    let active = true;
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await getManagers({ search: query.trim(), status: 'active', page: 1, page_size: 10 });
        if (active) setMatches(result.items.filter((manager) => manager.employee_id !== employeeId));
      } catch (loadError) {
        if (active) setError(loadError instanceof Error ? loadError.message : 'Could not search managers.');
      } finally {
        if (active) setLoading(false);
      }
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [employeeId, query, selected]);

  if (selected) {
    return (
      <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
        <span className="text-sm font-medium text-slate-800">
          {selected.employee_name}<span className="ml-2 text-xs font-normal text-slate-500">{selected.department}</span>
        </span>
        <Button size="sm" aria-label="Change reviewer" onClick={() => { onSelect(null); setQuery(''); }}>
          Change
        </Button>
      </div>
    );
  }

  return (
    <div className="relative space-y-1.5">
      <label className="block text-sm font-medium text-slate-700" htmlFor="review-manager-search">Reviewer (manager)</label>
      <TextInput
        id="review-manager-search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search by manager name, email or ID"
        autoComplete="off"
      />
      {loading && <p className="text-xs text-slate-500">Searching managers…</p>}
      {error && <p role="alert" className="text-xs text-rose-700">{error}</p>}
      {matches.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
          {matches.map((manager) => (
            <li key={manager.id}>
              <button type="button" className="w-full px-3 py-2 text-left text-sm hover:bg-indigo-50" onClick={() => onSelect(manager)}>
                <span className="font-medium text-slate-800">{manager.employee_name}</span>
                <span className="ml-2 text-xs text-slate-500">{manager.department} · {manager.email}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {!loading && query.trim().length >= 2 && matches.length === 0 && !error && (
        <p className="text-xs text-slate-500">No matching managers found.</p>
      )}
    </div>
  );
}

export default function ReviewsPage() {
  const [tab, setTab] = useState<ViewTab>('reviews');
  const [cycleResult, setCycleResult] = useState<PageResult<ReviewCycleRecord> | null>(null);
  const [reviewResult, setReviewResult] = useState<PageResult<ReviewRecord> | null>(null);
  const [cycleSearch, setCycleSearch] = useState('');
  const [cycleStatus, setCycleStatus] = useState('');
  const [reviewSearch, setReviewSearch] = useState('');
  const [reviewStatus, setReviewStatus] = useState('');
  const [reviewCycleFilter, setReviewCycleFilter] = useState('');
  const [cyclePage, setCyclePage] = useState(1);
  const [reviewPage, setReviewPage] = useState(1);
  const [cycles, setCycles] = useState<ReviewCycleRecord[]>([]);
  const [competencies, setCompetencies] = useState<CompetencyRecord[]>([]);
  const [loadingCycles, setLoadingCycles] = useState(true);
  const [loadingReviews, setLoadingReviews] = useState(true);
  const [saving, setSaving] = useState(false);
  const [cycleCreating, setCycleCreating] = useState(false);
  const [reviewCreating, setReviewCreating] = useState(false);
  const [cycleForm, setCycleForm] = useState(initialCycle);
  const [reviewForm, setReviewForm] = useState(initialReview);
  const [reviewEmployeeIsManager, setReviewEmployeeIsManager] = useState(false);
  const [reviewEmployeeHasManagerProfile, setReviewEmployeeHasManagerProfile] = useState<boolean | null>(null);
  const [selectedCycle, setSelectedCycle] = useState<ReviewCycleRecord | null>(null);
  const [cycleEdit, setCycleEdit] = useState({ name: '', starts_on: '', ends_on: '' });
  const [selectedReview, setSelectedReview] = useState<ReviewRecord | null>(null);
  const [reviewSummary, setReviewSummary] = useState('');
  const [reviewRating, setReviewRating] = useState('');
  const [reviewCompetencies, setReviewCompetencies] = useState<string[]>([]);
  const [approvalComments, setApprovalComments] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadCycles = useCallback(async () => {
    setLoadingCycles(true);
    setError(null);
    try {
      const [page, all] = await Promise.all([
        getReviewCycles({ search: cycleSearch, status: cycleStatus, page: cyclePage, page_size: 25 }),
        getReviewCycles({ page: 1, page_size: 100 }),
      ]);
      setCycleResult(page);
      setCycles(all.items);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load review cycles.');
    } finally {
      setLoadingCycles(false);
    }
  }, [cyclePage, cycleSearch, cycleStatus]);

  const loadReviews = useCallback(async () => {
    setLoadingReviews(true);
    setError(null);
    try {
      setReviewResult(await getReviews({
        search: reviewSearch,
        status: reviewStatus,
        review_cycle_id: reviewCycleFilter,
        page: reviewPage,
        page_size: 25,
      }));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load performance reviews.');
    } finally {
      setLoadingReviews(false);
    }
  }, [reviewCycleFilter, reviewPage, reviewSearch, reviewStatus]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadCycles(), cycleSearch ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [cycleSearch, loadCycles]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadReviews(), reviewSearch ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [loadReviews, reviewSearch]);

  useEffect(() => {
    let active = true;
    void getCompetencies({ page: 1, page_size: 100 }).then((result) => {
      if (active) setCompetencies(result.items.filter((item) => item.status === 'active'));
    }).catch((loadError: unknown) => {
      if (active) setError(loadError instanceof Error ? loadError.message : 'Could not load competencies.');
    });
    return () => { active = false; };
  }, []);

  async function createCycle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const created = await createReviewCycle(cycleForm);
      setCycleCreating(false);
      setCycleForm(initialCycle);
      setNotice(`${created.name} created as a draft cycle.`);
      setTab('cycles');
      setCyclePage(1);
      await loadCycles();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not create the review cycle.');
    } finally {
      setSaving(false);
    }
  }

  async function createReviewRecord(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reviewForm.employee || !reviewForm.reviewer) {
      setError('Choose an employee with an assigned manager before creating a review.');
      return;
    }
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const created = await createReview({
        employee_id: reviewForm.employee.id,
        reviewer_manager_id: reviewForm.reviewer.id,
        review_cycle_id: reviewForm.review_cycle_id,
        summary: reviewForm.summary,
        rating: reviewForm.rating || null,
        effective_from: reviewForm.effective_from,
        effective_to: reviewForm.effective_to || null,
        competency_ids: reviewForm.competency_ids,
      });
      setReviewCreating(false);
      setReviewForm(initialReview);
      setNotice(`Review ${created.id} created as a draft.`);
      setReviewPage(1);
      await Promise.all([loadReviews(), loadCycles()]);
      setSelectedReview(created);
      setReviewSummary(created.summary);
      setReviewRating(created.rating ?? '');
      setReviewCompetencies(created.competencies.map((item) => item.id));
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not create the review.');
    } finally {
      setSaving(false);
    }
  }

  async function chooseReviewEmployee(employee: EmployeeRecord | null) {
    setReviewForm((current) => ({ ...current, employee, reviewer: null }));
    setReviewEmployeeIsManager(false);
    setReviewEmployeeHasManagerProfile(null);
    if (!employee) return;
    try {
      if (employee.manager_id) {
        const manager = await getManager(employee.manager_id);
        setReviewForm((current) => current.employee?.id === employee.id ? { ...current, reviewer: manager } : current);
        return;
      }
      const managers = await getManagers({ search: employee.id, status: 'active', page: 1, page_size: 10 });
      const profile = managers.items.find((manager) => manager.employee_id === employee.id);
      setReviewEmployeeHasManagerProfile(profile !== undefined);
      setReviewEmployeeIsManager(profile !== undefined);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load the employee’s reviewer relationship.');
    }
  }

  async function showReview(id: string) {
    setError(null);
    try {
      const review = await getReview(id);
      setSelectedReview(review);
      setReviewSummary(review.summary);
      setReviewRating(review.rating ?? '');
      setReviewCompetencies(review.competencies.map((item) => item.id));
      setApprovalComments('');
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load review details.');
    }
  }

  async function showCycle(id: string) {
    setError(null);
    try {
      const cycle = await getReviewCycle(id);
      setSelectedCycle(cycle);
      setCycleEdit({ name: cycle.name, starts_on: cycle.starts_on, ends_on: cycle.ends_on });
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load review cycle details.');
    }
  }

  async function saveReviewChanges() {
    if (!selectedReview) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const review = await updateReview(selectedReview.id, {
        summary: reviewSummary,
        rating: reviewRating || null,
        competency_ids: reviewCompetencies,
      });
      setSelectedReview(review);
      setNotice('Review changes saved.');
      await Promise.all([loadReviews(), loadCycles()]);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not save review changes.');
    } finally {
      setSaving(false);
    }
  }

  async function changeReviewStatus(status: ReviewRecord['status']) {
    if (!selectedReview) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const review = await updateReview(selectedReview.id, { status });
      setSelectedReview(review);
      setReviewSummary(review.summary);
      setReviewRating(review.rating ?? '');
      setReviewCompetencies(review.competencies.map((item) => item.id));
      setNotice(`Review status changed to ${displayStatus(status)}.`);
      await Promise.all([loadReviews(), loadCycles()]);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not update review status.');
    } finally {
      setSaving(false);
    }
  }

  async function decideApproval(status: 'approved' | 'rejected') {
    if (!selectedReview) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const review = await decideReviewApproval(selectedReview.id, {
        approver_manager_id: selectedReview.reviewer_manager_id,
        status,
        comments: approvalComments || null,
      });
      setSelectedReview(review);
      setNotice(status === 'approved' ? 'Review approved.' : 'Review returned for updates.');
      setApprovalComments('');
      await Promise.all([loadReviews(), loadCycles()]);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not record the approval decision.');
    } finally {
      setSaving(false);
    }
  }

  async function saveCycle() {
    if (!selectedCycle) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const changes: { name?: string; starts_on?: string; ends_on?: string } = {};
      if (cycleEdit.name !== selectedCycle.name) changes.name = cycleEdit.name;
      if (cycleEdit.starts_on !== selectedCycle.starts_on) changes.starts_on = cycleEdit.starts_on;
      if (cycleEdit.ends_on !== selectedCycle.ends_on) changes.ends_on = cycleEdit.ends_on;
      const updated = await updateReviewCycle(selectedCycle.id, changes);
      setSelectedCycle(updated);
      setNotice('Review cycle details saved.');
      await loadCycles();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not update the review cycle.');
    } finally {
      setSaving(false);
    }
  }

  async function changeCycleStatus(status: ReviewCycleRecord['status']) {
    if (!selectedCycle) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await updateReviewCycle(selectedCycle.id, { status });
      setSelectedCycle(updated);
      setNotice(`Cycle status changed to ${status}.`);
      await Promise.all([loadCycles(), loadReviews()]);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not update the review cycle status.');
    } finally {
      setSaving(false);
    }
  }

  const cycleColumns = useMemo<DataTableColumn<ReviewCycleRecord>[]>(() => [
    { key: 'name', header: 'Review cycle', render: (cycle) => <><span className="font-medium text-slate-800">{cycle.name}</span><span className="block text-xs text-slate-500">{cycle.id}</span></> },
    { key: 'dates', header: 'Dates', render: (cycle) => <span className="whitespace-nowrap">{formatDate(cycle.starts_on)} – {formatDate(cycle.ends_on)}</span> },
    { key: 'status', header: 'Status', render: (cycle) => <Badge tone={statusTone(cycle.status)}>{displayStatus(cycle.status)}</Badge> },
    { key: 'review_count', header: 'Reviews', render: (cycle) => <span className="tabular-nums">{cycle.review_count.toLocaleString()}</span> },
    { key: 'pending', header: 'Pending', render: (cycle) => <span className="tabular-nums">{cycle.pending_review_count.toLocaleString()}</span> },
    { key: 'approved', header: 'Approved', render: (cycle) => <span className="tabular-nums">{cycle.approved_review_count.toLocaleString()}</span> },
    { key: 'actions', header: 'Details', className: 'text-right', render: (cycle) => <Button size="sm" onClick={() => void showCycle(cycle.id)}><Eye className="h-3.5 w-3.5" /> View</Button> },
  ], []);

  const reviewColumns = useMemo<DataTableColumn<ReviewRecord>[]>(() => [
    { key: 'employee_name', header: 'Employee', render: (review) => <><span className="font-medium text-slate-800">{review.employee_name}</span><span className="block text-xs text-slate-500">{review.department}</span></> },
    { key: 'cycle', header: 'Review cycle', render: (review) => <span className="whitespace-nowrap">{review.review_cycle_name}</span> },
    { key: 'reviewer_name', header: 'Reviewer', render: (review) => review.reviewer_name },
    { key: 'rating', header: 'Rating', render: (review) => review.rating === null ? '—' : `${Number(review.rating).toFixed(2)} / 5` },
    { key: 'status', header: 'Review status', render: (review) => <Badge tone={statusTone(review.status)}>{displayStatus(review.status)}</Badge> },
    { key: 'approval', header: 'Approval', render: (review) => <Badge tone={statusTone(review.approvals[0]?.status ?? 'pending')}>{displayStatus(review.approvals[0]?.status ?? 'not assigned')}</Badge> },
    { key: 'actions', header: 'Details', className: 'text-right', render: (review) => <Button size="sm" onClick={() => void showReview(review.id)}><Eye className="h-3.5 w-3.5" /> View</Button> },
  ], []);

  const cycleTotalPages = cycleResult ? Math.max(1, Math.ceil(cycleResult.total / cycleResult.page_size)) : 1;
  const reviewTotalPages = reviewResult ? Math.max(1, Math.ceil(reviewResult.total / reviewResult.page_size)) : 1;
  const editableCycleDetails = selectedCycle?.status === 'draft';

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Review Cycles & Performance Reviews</h1>
          <p className="mt-2 text-sm text-slate-500">Manage review periods, employee reviews, manager decisions, and acknowledgement.</p>
        </div>
        <div className="flex gap-2">
          {tab === 'cycles' && <Button variant="primary" onClick={() => { setError(null); setCycleCreating(true); }}><FilePlus2 className="h-4 w-4" /> Create cycle</Button>}
          {tab === 'reviews' && <Button variant="primary" onClick={() => { setError(null); setReviewForm(initialReview); setReviewCreating(true); }}><FilePlus2 className="h-4 w-4" /> Create review</Button>}
        </div>
      </header>

      <aside className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-5 text-amber-900" role="note">
        Authentication and role-based reviewer authorization are not configured. Review relationships and approval assignments are validated against manager records, but the API cannot verify the caller’s identity.
      </aside>
      {notice && <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</p>}
      {error && !cycleCreating && !reviewCreating && !selectedCycle && !selectedReview && (
        <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>
      )}

      <div className="flex gap-2 border-b border-slate-200" role="tablist" aria-label="Review workspace views">
        <button type="button" role="tab" aria-selected={tab === 'reviews'} onClick={() => setTab('reviews')} className={`border-b-2 px-4 py-3 text-sm font-medium ${tab === 'reviews' ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>Performance reviews</button>
        <button type="button" role="tab" aria-selected={tab === 'cycles'} onClick={() => setTab('cycles')} className={`border-b-2 px-4 py-3 text-sm font-medium ${tab === 'cycles' ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>Review cycles</button>
      </div>

      {tab === 'reviews' ? (
        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
          <div className="grid gap-3 md:grid-cols-[minmax(220px,1fr)_190px_220px]">
            <TextInput type="search" value={reviewSearch} onChange={(event) => { setReviewSearch(event.target.value); setReviewPage(1); }} placeholder="Search employees, reviewers or reviews" aria-label="Search performance reviews" leadingIcon={<Search className="h-4 w-4" />} />
            <select className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm" aria-label="Filter review status" value={reviewStatus} onChange={(event) => { setReviewStatus(event.target.value); setReviewPage(1); }}>
              <option value="">All statuses</option>{['draft', 'in_progress', 'submitted', 'approved', 'acknowledged'].map((value) => <option key={value} value={value}>{displayStatus(value)}</option>)}
            </select>
            <select className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm" aria-label="Filter by review cycle" value={reviewCycleFilter} onChange={(event) => { setReviewCycleFilter(event.target.value); setReviewPage(1); }}>
              <option value="">All review cycles</option>{cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}
            </select>
          </div>
          {loadingReviews ? <Loading /> : reviewResult?.items.length ? <>
            <DataTable columns={reviewColumns} rows={reviewResult.items} getRowKey={(review) => review.id} label="Performance reviews" />
            <Pagination page={reviewPage} totalPages={reviewTotalPages} total={reviewResult.total} itemLabel="reviews" onPage={setReviewPage} />
          </> : <EmptyState title="No performance reviews found" description="Change your filters or create a review in an open cycle." />}
        </section>
      ) : (
        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
          <div className="grid gap-3 md:grid-cols-[minmax(240px,1fr)_200px]">
            <TextInput type="search" value={cycleSearch} onChange={(event) => { setCycleSearch(event.target.value); setCyclePage(1); }} placeholder="Search cycle name or ID" aria-label="Search review cycles" leadingIcon={<Search className="h-4 w-4" />} />
            <select className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm" aria-label="Filter cycle status" value={cycleStatus} onChange={(event) => { setCycleStatus(event.target.value); setCyclePage(1); }}>
              <option value="">All cycle statuses</option>{['draft', 'open', 'closed', 'archived'].map((value) => <option key={value} value={value}>{displayStatus(value)}</option>)}
            </select>
          </div>
          {loadingCycles ? <Loading /> : cycleResult?.items.length ? <>
            <DataTable columns={cycleColumns} rows={cycleResult.items} getRowKey={(cycle) => cycle.id} label="Review cycles" />
            <Pagination page={cyclePage} totalPages={cycleTotalPages} total={cycleResult.total} itemLabel="review cycles" onPage={setCyclePage} />
          </> : <EmptyState title="No review cycles found" description="Change the filters or create a new cycle." />}
        </section>
      )}

      <Modal open={cycleCreating} title="Create review cycle" onClose={() => setCycleCreating(false)} className="w-full max-w-2xl">
        <form className="flex-1 space-y-4 overflow-y-auto p-5" onSubmit={(event) => void createCycle(event)}>
          {error && <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block space-y-1.5 text-sm font-medium text-slate-700">Year
              <TextInput type="number" min="1" max="9999" required value={cycleForm.year} onChange={(event) => setCycleForm((current) => {
                const year = Number(event.target.value);
                const startMonth = current.half === 'H1' ? '01' : '07';
                const endMonth = current.half === 'H1' ? '06' : '12';
                return {
                  ...current,
                  year,
                  name: `${year} ${current.half} Performance Cycle`,
                  starts_on: `${year}-${startMonth}-01`,
                  ends_on: `${year}-${endMonth}-${current.half === 'H1' ? '30' : '31'}`,
                };
              })} />
            </label>
            <label className="block space-y-1.5 text-sm font-medium text-slate-700">Half
              <select className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm" value={cycleForm.half} onChange={(event) => {
                const half = event.target.value as 'H1' | 'H2';
                const startMonth = half === 'H1' ? '01' : '07';
                const endMonth = half === 'H1' ? '06' : '12';
                setCycleForm((current) => ({ ...current, half, starts_on: `${current.year}-${startMonth}-01`, ends_on: `${current.year}-${endMonth}-${half === 'H1' ? '30' : '31'}` }));
              }}><option value="H1">H1</option><option value="H2">H2</option></select>
            </label>
          </div>
          <label className="block space-y-1.5 text-sm font-medium text-slate-700">Cycle name
            <TextInput required maxLength={120} value={cycleForm.name} onChange={(event) => setCycleForm((current) => ({ ...current, name: event.target.value }))} />
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block space-y-1.5 text-sm font-medium text-slate-700">Starts on
              <TextInput type="date" required value={cycleForm.starts_on} onChange={(event) => setCycleForm((current) => ({ ...current, starts_on: event.target.value }))} />
            </label>
            <label className="block space-y-1.5 text-sm font-medium text-slate-700">Ends on
              <TextInput type="date" required value={cycleForm.ends_on} onChange={(event) => setCycleForm((current) => ({ ...current, ends_on: event.target.value }))} />
            </label>
          </div>
          <p className="text-xs text-slate-500">New cycles start as drafts. Cycle dates must stay within the selected half-year.</p>
          <div className="flex justify-end gap-2 border-t border-slate-100 pt-4">
            <Button onClick={() => setCycleCreating(false)}>Cancel</Button>
            <Button variant="primary" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Create cycle'}</Button>
          </div>
        </form>
      </Modal>

      <Modal open={reviewCreating} title="Create performance review" onClose={() => setReviewCreating(false)} className="w-full max-w-2xl">
        <form className="flex-1 space-y-4 overflow-y-auto p-5" onSubmit={(event) => void createReviewRecord(event)}>
          {error && <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
          <EmployeePicker selected={reviewForm.employee} onSelect={(employee) => void chooseReviewEmployee(employee)} />
          {reviewForm.employee && (
            <p className={`text-xs ${reviewForm.reviewer ? 'text-slate-500' : 'text-amber-700'}`}>
              {reviewForm.reviewer
                ? `Assigned reviewer: ${reviewForm.reviewer.employee_name} · ${reviewForm.reviewer.department}`
                : reviewForm.employee.manager_id
                  ? 'Loading the employee’s assigned manager…'
                  : reviewEmployeeHasManagerProfile === null
                    ? 'Checking the employee’s manager profile…'
                    : reviewEmployeeIsManager
                      ? 'This employee is a manager; select another active manager as the reviewer.'
                      : 'This employee has no assigned manager or manager profile and cannot be reviewed.'}
            </p>
          )}
          {reviewForm.employee && reviewEmployeeIsManager && (
            <ManagerPicker
              selected={reviewForm.reviewer}
              employeeId={reviewForm.employee.id}
              onSelect={(manager) => setReviewForm((current) => ({ ...current, reviewer: manager }))}
            />
          )}
          <label className="block space-y-1.5 text-sm font-medium text-slate-700">Review cycle
            <select required className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm" value={reviewForm.review_cycle_id} onChange={(event) => {
              const cycle = cycles.find((item) => item.id === event.target.value);
              setReviewForm((current) => ({ ...current, review_cycle_id: event.target.value, effective_from: cycle?.starts_on ?? '' }));
            }}>
              <option value="">Select an open cycle</option>{cycles.filter((cycle) => ['draft', 'open'].includes(cycle.status)).map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name} · {cycle.status}</option>)}
            </select>
          </label>
          <TextArea label="Review summary" required value={reviewForm.summary} onChange={(value) => setReviewForm((current) => ({ ...current, summary: value }))} />
          <div className="grid gap-4 sm:grid-cols-3">
            <label className="block space-y-1.5 text-sm font-medium text-slate-700">Rating (0–5)
              <TextInput type="number" min="0" max="5" step="0.01" value={reviewForm.rating} onChange={(event) => setReviewForm((current) => ({ ...current, rating: event.target.value }))} />
            </label>
            <label className="block space-y-1.5 text-sm font-medium text-slate-700">Effective from
              <TextInput type="date" required value={reviewForm.effective_from} onChange={(event) => setReviewForm((current) => ({ ...current, effective_from: event.target.value }))} />
            </label>
            <label className="block space-y-1.5 text-sm font-medium text-slate-700">Effective to
              <TextInput type="date" value={reviewForm.effective_to} onChange={(event) => setReviewForm((current) => ({ ...current, effective_to: event.target.value }))} />
            </label>
          </div>
          <CompetencySelector competencies={competencies} selected={reviewForm.competency_ids} onChange={(ids) => setReviewForm((current) => ({ ...current, competency_ids: ids }))} />
          <div className="flex justify-end gap-2 border-t border-slate-100 pt-4">
            <Button onClick={() => setReviewCreating(false)}>Cancel</Button>
            <Button variant="primary" type="submit" disabled={saving || !reviewForm.reviewer}>{saving ? 'Saving…' : 'Create draft review'}</Button>
          </div>
        </form>
      </Modal>

      <Modal open={selectedCycle !== null} title="Review cycle details" onClose={() => setSelectedCycle(null)} className="w-full max-w-2xl">
        {selectedCycle && <div className="flex-1 space-y-5 overflow-y-auto p-5">
          {error && <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div><p className="text-xs text-slate-500">{selectedCycle.id} · {selectedCycle.year} {selectedCycle.half}</p><h3 className="mt-1 text-lg font-semibold text-slate-900">{selectedCycle.name}</h3></div>
            <Badge tone={statusTone(selectedCycle.status)}>{displayStatus(selectedCycle.status)}</Badge>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Metric label="Reviews" value={selectedCycle.review_count} />
            <Metric label="Pending" value={selectedCycle.pending_review_count} />
            <Metric label="Approved" value={selectedCycle.approved_review_count} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block space-y-1.5 text-sm font-medium text-slate-700">Cycle name
              <TextInput disabled={!editableCycleDetails || saving} value={cycleEdit.name} onChange={(event) => setCycleEdit((current) => ({ ...current, name: event.target.value }))} />
            </label>
            <div className="hidden sm:block" />
            <label className="block space-y-1.5 text-sm font-medium text-slate-700">Starts on
              <TextInput type="date" disabled={!editableCycleDetails || saving} value={cycleEdit.starts_on} onChange={(event) => setCycleEdit((current) => ({ ...current, starts_on: event.target.value }))} />
            </label>
            <label className="block space-y-1.5 text-sm font-medium text-slate-700">Ends on
              <TextInput type="date" disabled={!editableCycleDetails || saving} value={cycleEdit.ends_on} onChange={(event) => setCycleEdit((current) => ({ ...current, ends_on: event.target.value }))} />
            </label>
          </div>
          {!editableCycleDetails && <p className="text-xs text-slate-500">Cycle details are editable only while the cycle is a draft.</p>}
          <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-4">
            {editableCycleDetails && <Button variant="primary" disabled={saving} onClick={() => void saveCycle()}><Pencil className="h-4 w-4" /> Save details</Button>}
            {selectedCycle.status === 'draft' && <Button variant="primary" disabled={saving} onClick={() => void changeCycleStatus('open')}>Open cycle</Button>}
            {selectedCycle.status === 'open' && <Button variant="primary" disabled={saving} onClick={() => void changeCycleStatus('closed')}>Close cycle</Button>}
            {selectedCycle.status === 'closed' && <Button disabled={saving} onClick={() => void changeCycleStatus('archived')}>Archive cycle</Button>}
          </div>
        </div>}
      </Modal>

      <Modal open={selectedReview !== null} title="Performance review details" onClose={() => setSelectedReview(null)} className="w-full max-w-3xl">
        {selectedReview && <div className="flex-1 space-y-5 overflow-y-auto p-5">
          {error && <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs text-slate-500">{selectedReview.id} · {selectedReview.review_cycle_name}</p>
              <h3 className="mt-1 text-lg font-semibold text-slate-900">{selectedReview.employee_name}</h3>
              <p className="mt-1 text-sm text-slate-500">{selectedReview.department} · Reviewer: {selectedReview.reviewer_name}</p>
            </div>
            <Badge tone={statusTone(selectedReview.status)}>{displayStatus(selectedReview.status)}</Badge>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Metric label="Rating" value={selectedReview.rating === null ? 'Not rated' : `${Number(selectedReview.rating).toFixed(2)} / 5`} />
            <Metric label="Effective from" value={formatDate(selectedReview.effective_from)} />
            <Metric label="Effective to" value={selectedReview.effective_to ? formatDate(selectedReview.effective_to) : '—'} />
          </div>
          <div className="space-y-4">
            <TextArea label="Review summary" value={reviewSummary} onChange={setReviewSummary} required={selectedReview.editable} disabled={!selectedReview.editable || saving} />
            {selectedReview.editable && (
              <>
                <label className="block max-w-xs space-y-1.5 text-sm font-medium text-slate-700">Rating (0–5)
                  <TextInput type="number" min="0" max="5" step="0.01" value={reviewRating} onChange={(event) => setReviewRating(event.target.value)} />
                </label>
                <CompetencySelector competencies={competencies} selected={reviewCompetencies} onChange={setReviewCompetencies} />
              </>
            )}
          </div>
          <section className="space-y-3 rounded-xl border border-slate-200 p-4">
            <h4 className="text-sm font-semibold text-slate-800">Approval workflow</h4>
            {selectedReview.approvals.length ? selectedReview.approvals.map((approval) => (
              <div key={approval.approver_manager_id} className="flex flex-wrap items-start justify-between gap-3 rounded-lg bg-slate-50 p-3">
                <div>
                  <p className="text-sm font-medium text-slate-800">{approval.approver_name}</p>
                  <p className="mt-1 text-xs text-slate-500">{approval.approver_employee_id} · {approval.decided_at ? new Date(approval.decided_at).toLocaleString() : 'Decision pending'}</p>
                  {approval.comments && <p className="mt-2 text-sm text-slate-600">{approval.comments}</p>}
                </div>
                <Badge tone={statusTone(approval.status)}>{displayStatus(approval.status)}</Badge>
              </div>
            )) : <p className="text-sm text-slate-500">No approval has been assigned.</p>}
            {selectedReview.approval_actionable && <>
              <TextArea label="Decision comments (optional)" value={approvalComments} onChange={setApprovalComments} rows={2} />
              <div className="flex flex-wrap justify-end gap-2">
                <Button disabled={saving} onClick={() => void decideApproval('rejected')}><X className="h-4 w-4" /> Return for updates</Button>
                <Button variant="primary" disabled={saving} onClick={() => void decideApproval('approved')}><Check className="h-4 w-4" /> Approve review</Button>
              </div>
            </>}
          </section>
          <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-4">
            {selectedReview.editable && <Button variant="primary" disabled={saving} onClick={() => void saveReviewChanges()}><Pencil className="h-4 w-4" /> Save changes</Button>}
            {selectedReview.status === 'draft' && <Button variant="primary" disabled={saving} onClick={() => void changeReviewStatus('in_progress')}>Start review</Button>}
            {selectedReview.status === 'in_progress' && <Button variant="primary" disabled={saving} onClick={() => void changeReviewStatus('submitted')}>Submit for approval</Button>}
            {selectedReview.acknowledgeable && <Button variant="primary" disabled={saving} onClick={() => void changeReviewStatus('acknowledged')}>Acknowledge review</Button>}
          </div>
        </div>}
      </Modal>
    </div>
  );
}

function Pagination({
  page,
  totalPages,
  total,
  itemLabel,
  onPage,
}: {
  page: number;
  totalPages: number;
  total: number;
  itemLabel: string;
  onPage: (page: number) => void;
}) {
  return (
    <div className="flex items-center justify-between border-t border-slate-100 pt-4 text-sm text-slate-500">
      <span>{total.toLocaleString()} {itemLabel}</span>
      <div className="flex items-center gap-2">
        <Button size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</Button>
        <span>Page {page} of {totalPages}</span>
        <Button size="sm" disabled={page >= totalPages} onClick={() => onPage(page + 1)}>Next</Button>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-900">{typeof value === 'number' ? value.toLocaleString() : value}</p>
    </div>
  );
}

function CompetencySelector({
  competencies,
  selected,
  onChange,
}: {
  competencies: CompetencyRecord[];
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium text-slate-700">Related competencies</legend>
      {competencies.length ? (
        <div className="grid max-h-44 gap-2 overflow-y-auto rounded-lg border border-slate-200 p-3 sm:grid-cols-2">
          {competencies.map((competency) => (
            <label key={competency.id} className="flex items-start gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                className="mt-0.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                checked={selected.includes(competency.id)}
                onChange={(event) => onChange(event.target.checked
                  ? [...selected, competency.id]
                  : selected.filter((id) => id !== competency.id))}
              />
              <span>{competency.name}<span className="ml-1 text-xs text-slate-500">{competency.category}</span></span>
            </label>
          ))}
        </div>
      ) : <p className="text-xs text-slate-500">No active competencies are available.</p>}
    </fieldset>
  );
}
