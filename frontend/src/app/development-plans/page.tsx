'use client';

import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { Search } from 'lucide-react';

import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import DataTable, { type DataTableColumn } from '@/components/common/DataTable';
import EmptyState from '@/components/common/EmptyState';
import Loading from '@/components/common/Loading';
import TextInput from '@/components/common/TextInput';
import {
  createDevelopmentPlan,
  decideDevelopmentPlanApproval,
  getCompetencies,
  getDevelopmentPlan,
  getDevelopmentPlans,
  getEmployees,
  getGoals,
  getManager,
  getManagers,
  getReviewCycles,
  updateDevelopmentPlan,
  type CompetencyRecord,
  type DevelopmentPlanCreatePayload,
  type DevelopmentPlanRecord,
  type DevelopmentPlanUpdatePayload,
  type EmployeeRecord,
  type GoalRecord,
  type ManagerRecord,
  type PageResult,
  type ReviewCycleRecord,
} from '@/services/api';

const pageSize = 25;
const inputClass = 'mt-1 h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800';
const labelClass = 'block text-sm font-medium text-slate-600';

interface PlanForm {
  title: string;
  description: string;
  effective_from: string;
  effective_to: string;
  review_cycle_id: string;
  goal_ids: string[];
  competency_ids: string[];
}

const emptyPlanForm: PlanForm = {
  title: '',
  description: '',
  effective_from: new Date().toISOString().slice(0, 10),
  effective_to: '',
  review_cycle_id: '',
  goal_ids: [],
  competency_ids: [],
};

function toggleId(current: string[], id: string): string[] {
  return current.includes(id) ? current.filter((value) => value !== id) : [...current, id];
}

export default function DevelopmentPlansPage() {
  const [result, setResult] = useState<PageResult<DevelopmentPlanRecord> | null>(null);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [employeeSearch, setEmployeeSearch] = useState('');
  const [employeeOptions, setEmployeeOptions] = useState<EmployeeRecord[]>([]);
  const [selectedEmployee, setSelectedEmployee] = useState<EmployeeRecord | null>(null);
  const [managerSearch, setManagerSearch] = useState('');
  const [managerOptions, setManagerOptions] = useState<ManagerRecord[]>([]);
  const [ownerManagerId, setOwnerManagerId] = useState('');
  const [goalOptions, setGoalOptions] = useState<GoalRecord[]>([]);
  const [competencyOptions, setCompetencyOptions] = useState<CompetencyRecord[]>([]);
  const [cycleOptions, setCycleOptions] = useState<ReviewCycleRecord[]>([]);
  const [createForm, setCreateForm] = useState<PlanForm>(emptyPlanForm);
  const [selectedPlan, setSelectedPlan] = useState<DevelopmentPlanRecord | null>(null);
  const [editForm, setEditForm] = useState<PlanForm>(emptyPlanForm);
  const [approvalComments, setApprovalComments] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setResult(await getDevelopmentPlans({ search, status, page, page_size: pageSize }));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load development plans.');
    } finally {
      setLoading(false);
    }
  }, [page, search, status]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), search ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [load, search]);

  useEffect(() => {
    if (!creating) return;
    let active = true;
    const timer = window.setTimeout(() => {
      void getEmployees({ search: employeeSearch, page: 1, page_size: 10 })
        .then((response) => { if (active) setEmployeeOptions(response.items); })
        .catch((loadError: unknown) => {
          if (active) setError(loadError instanceof Error ? loadError.message : 'Could not search employees.');
        });
    }, employeeSearch ? 200 : 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [creating, employeeSearch]);

  useEffect(() => {
    if (!creating) return;
    let active = true;
    void Promise.all([
      getCompetencies({ page: 1, page_size: 100 }),
      getReviewCycles({ page: 1, page_size: 100 }),
    ]).then(([competencies, cycles]) => {
      if (!active) return;
      setCompetencyOptions(competencies.items);
      setCycleOptions(cycles.items.filter((cycle) => cycle.status === 'draft' || cycle.status === 'open'));
    }).catch((loadError: unknown) => {
      if (active) setError(loadError instanceof Error ? loadError.message : 'Could not load plan options.');
    });
    return () => { active = false; };
  }, [creating]);

  useEffect(() => {
    if (!creating) return;
    let active = true;
    void getManagers({ search: managerSearch, page: 1, page_size: 25 })
      .then(async (response) => {
        if (!active) return;
        const assignedManagerId = selectedEmployee?.manager_id;
        if (assignedManagerId && !response.items.some((manager) => manager.id === assignedManagerId)) {
          const assignedManager = await getManager(assignedManagerId);
          if (!active) return;
          setManagerOptions([assignedManager, ...response.items]);
        } else {
          setManagerOptions(response.items);
        }
      })
      .catch((loadError: unknown) => {
        if (active) setError(loadError instanceof Error ? loadError.message : 'Could not search plan owners.');
      });
    return () => { active = false; };
  }, [creating, managerSearch, selectedEmployee?.manager_id]);

  const selectEmployee = async (employee: EmployeeRecord) => {
    setSelectedEmployee(employee);
    setEmployeeSearch(`${employee.first_name} ${employee.last_name} (${employee.id})`);
    setOwnerManagerId(employee.manager_id ?? '');
    setCreateForm((form) => ({ ...form, goal_ids: [] }));
    setGoalOptions([]);
    if (employee.manager_id) {
      try {
        const manager = await getManager(employee.manager_id);
        setManagerOptions((options) => (
          options.some((option) => option.id === manager.id) ? options : [manager, ...options]
        ));
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Could not load the employee owner manager.');
      }
    }
    try {
      const goals = await getGoals({ employee_id: employee.id, page: 1, page_size: 100 });
      setGoalOptions(goals.items);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load employee goals.');
    }
  };

  const openPlan = useCallback(async (plan: DevelopmentPlanRecord) => {
    setError(null);
    setNotice(null);
    setCreating(false);
    setSelectedEmployee(null);
    setEmployeeSearch('');
    setOwnerManagerId('');
    setCreateForm(emptyPlanForm);
    try {
      const details = await getDevelopmentPlan(plan.id);
      setSelectedPlan(details);
      setEditForm({
        title: details.title,
        description: details.description,
        effective_from: details.effective_from,
        effective_to: details.effective_to ?? '',
        review_cycle_id: details.review_cycle_id ?? '',
        goal_ids: details.goals.map((goal) => goal.id),
        competency_ids: details.competencies.map((competency) => competency.id),
      });
      setApprovalComments('');
      setGoalOptions([]);
      setCompetencyOptions([]);
      const [goals, competencies] = await Promise.all([
        getGoals({ employee_id: details.employee_id, page: 1, page_size: 100 }),
        getCompetencies({ page: 1, page_size: 100 }),
      ]);
      setGoalOptions(goals.items);
      setCompetencyOptions(competencies.items);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load development plan details.');
    }
  }, []);

  const columns = useMemo<DataTableColumn<DevelopmentPlanRecord>[]>(() => [
    { key: 'id', header: 'Plan ID', render: (plan) => <span className="font-medium text-slate-800">{plan.id}</span> },
    { key: 'title', header: 'Development plan', render: (plan) => <span className="block max-w-[260px] truncate" title={plan.title}>{plan.title}</span> },
    { key: 'employee_name', header: 'Employee', render: (plan) => <><span className="block font-medium text-slate-800">{plan.employee_name}</span><span className="text-xs text-slate-500">{plan.employee_id}</span></> },
    { key: 'owner_manager_name', header: 'Owner', render: (plan) => plan.owner_manager_name },
    { key: 'review_cycle_name', header: 'Review cycle', render: (plan) => plan.review_cycle_name ?? '—' },
    { key: 'status', header: 'Status', render: (plan) => <Badge tone={plan.status === 'completed' ? 'success' : plan.status === 'active' ? 'info' : plan.status === 'cancelled' ? 'warning' : 'neutral'}>{plan.status.replaceAll('_', ' ')}</Badge> },
    { key: 'actions', header: 'Details', render: (plan) => <Button size="sm" onClick={() => void openPlan(plan)}>Open</Button> },
  ], [openPlan]);

  const totalPages = result ? Math.max(1, Math.ceil(result.total / result.page_size)) : 1;
  const updateForm = (form: 'create' | 'edit', key: keyof PlanForm, value: string | string[]) => {
    const setter = form === 'create' ? setCreateForm : setEditForm;
    setter((current) => ({ ...current, [key]: value }));
  };
  const updatePlanForm = (form: 'create' | 'edit', values: PlanForm) => (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <label className={labelClass}>Title<input className={inputClass} value={values.title} onChange={(event) => updateForm(form, 'title', event.target.value)} required maxLength={240} /></label>
        <label className={labelClass}>Review cycle
          <select className={inputClass} value={values.review_cycle_id} disabled={form === 'edit'} onChange={(event) => updateForm(form, 'review_cycle_id', event.target.value)}>
            <option value="">No cycle</option>
            {cycleOptions.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}
          </select>
        </label>
        <label className={labelClass}>Start date<input type="date" className={inputClass} value={values.effective_from} onChange={(event) => updateForm(form, 'effective_from', event.target.value)} required /></label>
        <label className={labelClass}>End date<input type="date" className={inputClass} value={values.effective_to} onChange={(event) => updateForm(form, 'effective_to', event.target.value)} /></label>
      </div>
      <label className={labelClass}>Description<textarea className="mt-1 min-h-24 w-full rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-800" value={values.description} onChange={(event) => updateForm(form, 'description', event.target.value)} required /></label>
      <div className="grid gap-4 lg:grid-cols-2">
        <fieldset className="max-h-52 space-y-2 overflow-auto rounded-lg border border-slate-200 p-3">
          <legend className="px-1 text-sm font-semibold text-slate-700">Goals</legend>
          {goalOptions.length ? goalOptions.map((goal) => (
            <label key={goal.id} className="flex items-start gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={values.goal_ids.includes(goal.id)} onChange={() => updateForm(form, 'goal_ids', toggleId(values.goal_ids, goal.id))} />
              <span>{goal.title}<span className="ml-1 text-xs text-slate-400">{goal.id}</span></span>
            </label>
          )) : <p className="text-xs text-slate-500">{form === 'create' && !selectedEmployee ? 'Select an employee to view their goals.' : 'No goals available.'}</p>}
        </fieldset>
        <fieldset className="max-h-52 space-y-2 overflow-auto rounded-lg border border-slate-200 p-3">
          <legend className="px-1 text-sm font-semibold text-slate-700">Competencies</legend>
          {competencyOptions.map((competency) => (
            <label key={competency.id} className="flex items-start gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={values.competency_ids.includes(competency.id)} onChange={() => updateForm(form, 'competency_ids', toggleId(values.competency_ids, competency.id))} />
              <span>{competency.name}<span className="ml-1 text-xs text-slate-400">{competency.category}</span></span>
            </label>
          ))}
        </fieldset>
      </div>
    </div>
  );

  const submitCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedEmployee) {
      setError('Select an existing employee before creating a plan.');
      return;
    }
    const payload: DevelopmentPlanCreatePayload = {
      employee_id: selectedEmployee.id,
      owner_manager_id: ownerManagerId,
      review_cycle_id: createForm.review_cycle_id || null,
      title: createForm.title,
      description: createForm.description,
      effective_from: createForm.effective_from,
      effective_to: createForm.effective_to || null,
      goal_ids: createForm.goal_ids,
      competency_ids: createForm.competency_ids,
    };
    setSaving(true);
    setError(null);
    try {
      const created = await createDevelopmentPlan(payload);
      setCreating(false);
      setSelectedEmployee(null);
      setEmployeeSearch('');
      setCreateForm(emptyPlanForm);
      setNotice(`Created ${created.id}. It is awaiting approval from ${created.owner_manager_name}.`);
      await load();
      await openPlan(created);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not create development plan.');
    } finally {
      setSaving(false);
    }
  };

  const savePlan = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedPlan) return;
    const payload: DevelopmentPlanUpdatePayload = {
      title: editForm.title,
      description: editForm.description,
      effective_from: editForm.effective_from,
      effective_to: editForm.effective_to || null,
      goal_ids: editForm.goal_ids,
      competency_ids: editForm.competency_ids,
    };
    setSaving(true);
    setError(null);
    try {
      const updated = await updateDevelopmentPlan(selectedPlan.id, payload);
      setSelectedPlan(updated);
      setNotice(`Updated ${updated.id}.`);
      await load();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not update development plan.');
    } finally {
      setSaving(false);
    }
  };

  const approvePlan = async (status: 'approved' | 'rejected') => {
    if (!selectedPlan) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await decideDevelopmentPlanApproval(selectedPlan.id, {
        approver_manager_id: selectedPlan.owner_manager_id,
        status,
        comments: approvalComments || null,
      });
      setSelectedPlan(updated);
      setNotice(status === 'approved' ? `${updated.id} is now active.` : `${updated.id} was rejected and cancelled.`);
      await load();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not record approval decision.');
    } finally {
      setSaving(false);
    }
  };

  const closeActivePlan = async (nextStatus: 'completed' | 'cancelled') => {
    if (!selectedPlan) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateDevelopmentPlan(selectedPlan.id, { status: nextStatus });
      setSelectedPlan(updated);
      setNotice(`${updated.id} was marked ${nextStatus}.`);
      await load();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not update plan status.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Development Plans</h1>
          <p className="mt-2 text-sm text-slate-500">Review employee development plans, owners, goals, competencies, and approvals.</p>
        </div>
        <Button onClick={() => { setCreating((value) => !value); setError(null); setNotice(null); }}>
          {creating ? 'Close create form' : 'Create development plan'}
        </Button>
      </header>
      {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}
      {notice && <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</p>}

      {creating && (
        <form onSubmit={submitCreate} className="space-y-4 rounded-xl border border-indigo-200 bg-white p-4 shadow-sm sm:p-6">
          <h2 className="text-base font-semibold text-slate-900">New development plan</h2>
          <div className="grid gap-3 md:grid-cols-2">
            <label className={labelClass}>Find employee
              <input className={inputClass} value={employeeSearch} onChange={(event) => { setEmployeeSearch(event.target.value); setSelectedEmployee(null); setOwnerManagerId(''); }} placeholder="Search name or employee ID" />
              {employeeOptions.length > 0 && !selectedEmployee && (
                <select className={inputClass} size={Math.min(employeeOptions.length, 5)} aria-label="Select employee" onChange={(event) => {
                  const employee = employeeOptions.find((item) => item.id === event.target.value);
                  if (employee) void selectEmployee(employee);
                }}>
                  {employeeOptions.map((employee) => <option key={employee.id} value={employee.id}>{employee.first_name} {employee.last_name} · {employee.id}</option>)}
                </select>
              )}
            </label>
            <label className={labelClass}>Find plan owner
              <input className={inputClass} value={managerSearch} onChange={(event) => { setManagerSearch(event.target.value); setOwnerManagerId(''); }} placeholder="Search manager name or ID" disabled={Boolean(selectedEmployee?.manager_id)} />
              <select className={inputClass} value={ownerManagerId} onChange={(event) => setOwnerManagerId(event.target.value)} required>
                <option value="">Select owner manager</option>
                {managerOptions.map((manager) => <option key={manager.id} value={manager.id}>{manager.employee_name} · {manager.id}</option>)}
              </select>
              {selectedEmployee?.manager_id && <span className="mt-1 block text-xs text-slate-500">The employee&apos;s assigned manager is selected automatically.</span>}
            </label>
          </div>
          {selectedEmployee && <p className="text-sm text-slate-600">Employee: <span className="font-medium">{selectedEmployee.first_name} {selectedEmployee.last_name}</span> · {selectedEmployee.id}</p>}
          {updatePlanForm('create', createForm)}
          <p className="text-xs text-amber-700">New plans start as drafts and require owner-manager approval. The supplied manager identity is not authenticated.</p>
          <Button type="submit" disabled={saving || !selectedEmployee || !ownerManagerId}>{saving ? 'Creating…' : 'Create draft plan'}</Button>
        </form>
      )}

      <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        <div className="grid gap-3 md:grid-cols-[minmax(240px,1fr)_200px]">
          <TextInput
            type="search"
            value={search}
            onChange={(event) => { setSearch(event.target.value); setPage(1); }}
            placeholder="Search plans, employees or IDs"
            aria-label="Search development plans"
            leadingIcon={<Search className="h-4 w-4" />}
          />
          <select
            className={inputClass}
            aria-label="Filter development plan status"
            value={status}
            onChange={(event) => { setStatus(event.target.value); setPage(1); }}
          >
            <option value="">All statuses</option>
            {['draft', 'active', 'completed', 'cancelled'].map((value) => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}
          </select>
        </div>
        {loading ? <Loading /> : result?.items.length ? (
          <>
            <DataTable columns={columns} rows={result.items} getRowKey={(plan) => plan.id} label="Development plans" />
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4 text-sm text-slate-500">
              <span>{result.total.toLocaleString()} development plans</span>
              <div className="flex items-center gap-2">
                <Button size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button>
                <span>Page {page} of {totalPages}</span>
                <Button size="sm" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>Next</Button>
              </div>
            </div>
          </>
        ) : result ? <EmptyState title="No development plans found" description="Change the search or status filter and try again." /> : null}
      </section>

      {selectedPlan && (
        <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">{selectedPlan.title}</h2>
              <p className="mt-1 text-sm text-slate-500">{selectedPlan.id} · {selectedPlan.employee_name} · Owner {selectedPlan.owner_manager_name}</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone={selectedPlan.status === 'active' ? 'info' : selectedPlan.status === 'completed' ? 'success' : selectedPlan.status === 'cancelled' ? 'warning' : 'neutral'}>{selectedPlan.status}</Badge>
              <Button size="sm" onClick={() => setSelectedPlan(null)}>Close</Button>
            </div>
          </div>
          <p className="whitespace-pre-wrap text-sm text-slate-700">{selectedPlan.description}</p>
          <p className="text-sm text-slate-500">{selectedPlan.effective_from} – {selectedPlan.effective_to ?? 'No end date'} · {selectedPlan.review_cycle_name ?? 'No review cycle'}</p>

          {selectedPlan.editable && (
            <form onSubmit={savePlan} className="space-y-4 border-t border-slate-100 pt-4">
              <h3 className="font-semibold text-slate-800">Edit draft and relationships</h3>
              {updatePlanForm('edit', editForm)}
              <Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save changes'}</Button>
            </form>
          )}

          {selectedPlan.goals.length > 0 && <div><h3 className="text-sm font-semibold text-slate-800">Linked goals</h3><ul className="mt-2 list-inside list-disc text-sm text-slate-600">{selectedPlan.goals.map((goal) => <li key={goal.id}>{goal.title} <span className="text-xs text-slate-400">{goal.id}</span></li>)}</ul></div>}
          {selectedPlan.competencies.length > 0 && <div><h3 className="text-sm font-semibold text-slate-800">Linked competencies</h3><ul className="mt-2 list-inside list-disc text-sm text-slate-600">{selectedPlan.competencies.map((item) => <li key={item.id}>{item.name} · {item.category}</li>)}</ul></div>}

          <div className="space-y-3 border-t border-slate-100 pt-4">
            <h3 className="text-sm font-semibold text-slate-800">Approval history</h3>
            {selectedPlan.approvals.map((approval) => (
              <div key={approval.approver_manager_id} className="rounded-lg bg-slate-50 p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium text-slate-800">{approval.approver_name} · {approval.approver_employee_id}</span><Badge tone={approval.status === 'approved' ? 'success' : approval.status === 'rejected' ? 'warning' : 'neutral'}>{approval.status}</Badge></div>
                {approval.decided_at && <p className="mt-1 text-xs text-slate-500">{new Date(approval.decided_at).toLocaleString()}</p>}
                {approval.comments && <p className="mt-2 text-slate-600">{approval.comments}</p>}
              </div>
            ))}
            {selectedPlan.approval_actionable && (
              <div className="space-y-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
                <p className="text-xs text-amber-800">Approval uses the plan owner&apos;s manager ID but cannot verify the caller until authentication is implemented.</p>
                <label className={labelClass}>Decision comments<textarea className="mt-1 min-h-20 w-full rounded-lg border border-slate-200 bg-white p-3 text-sm" value={approvalComments} onChange={(event) => setApprovalComments(event.target.value)} maxLength={4000} /></label>
                <div className="flex flex-wrap gap-2"><Button disabled={saving} onClick={() => void approvePlan('approved')}>Approve plan</Button><Button variant="secondary" disabled={saving} onClick={() => void approvePlan('rejected')}>Reject plan</Button></div>
              </div>
            )}
          </div>

          {selectedPlan.status === 'active' && <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-4"><Button disabled={saving} onClick={() => void closeActivePlan('completed')}>Mark completed</Button><Button variant="secondary" disabled={saving} onClick={() => void closeActivePlan('cancelled')}>Cancel plan</Button></div>}
        </section>
      )}
    </div>
  );
}
