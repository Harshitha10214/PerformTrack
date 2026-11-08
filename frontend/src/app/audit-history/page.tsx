'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Eye, Search } from 'lucide-react';

import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import DataTable, { type DataTableColumn } from '@/components/common/DataTable';
import EmptyState from '@/components/common/EmptyState';
import Loading from '@/components/common/Loading';
import Modal from '@/components/common/Modal';
import TextInput from '@/components/common/TextInput';
import {
  getAuditHistory,
  getAuditHistoryRecord,
  type AuditEntityType,
  type AuditHistoryRecord,
  type AuditOperation,
  type PageResult,
} from '@/services/api';

const pageSize = 25;

const entityTypes: AuditEntityType[] = [
  'Employee',
  'Manager',
  'ReviewCycle',
  'Goal',
  'KeyResult',
  'CheckIn',
  'Competency',
  'Feedback',
  'Review',
  'DevelopmentPlan',
  'Evidence',
];

const operations: AuditOperation[] = [
  'INSERT',
  'UPDATE',
  'DELETE',
  'RELATIONSHIP_INSERTED',
  'RELATIONSHIP_UPDATED',
  'RELATIONSHIP_DELETED',
];

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'medium',
  }).format(new Date(value));
}

function displayOperation(operation: AuditOperation): string {
  return operation.replaceAll('_', ' ').toLowerCase();
}

function ChangeData({ value }: { value: Record<string, unknown> | null }) {
  if (!value) {
    return <p className="text-sm italic text-slate-400">No snapshot recorded</p>;
  }
  return (
    <pre className="max-h-96 overflow-auto rounded-lg bg-slate-950 p-4 text-xs leading-5 text-slate-100">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

export default function AuditHistoryPage() {
  const [result, setResult] = useState<PageResult<AuditHistoryRecord> | null>(null);
  const [entityType, setEntityType] = useState<AuditEntityType | ''>('');
  const [entityId, setEntityId] = useState('');
  const [operation, setOperation] = useState<AuditOperation | ''>('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<AuditHistoryRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setResult(await getAuditHistory({
        entity_type: entityType || undefined,
        entity_id: entityId.trim() || undefined,
        operation: operation || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        page,
        page_size: pageSize,
      }));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load audit history.');
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, entityId, entityType, operation, page]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), entityId ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [entityId, load]);

  async function showDetails(eventId: string) {
    setSelected(null);
    setError(null);
    try {
      setSelected(await getAuditHistoryRecord(eventId));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load audit event details.');
    }
  }

  const columns = useMemo<DataTableColumn<AuditHistoryRecord>[]>(() => [
    { key: 'recorded_at', header: 'Timestamp', render: (record) => <span className="whitespace-nowrap">{formatTimestamp(record.recorded_at)}</span> },
    { key: 'entity_type', header: 'Entity type', render: (record) => <Badge tone={record.entity_type === 'Evidence' ? 'info' : 'neutral'}>{record.entity_type}</Badge> },
    { key: 'entity_id', header: 'Entity ID', render: (record) => <span className="font-mono text-xs font-medium text-slate-800">{record.entity_id}</span> },
    { key: 'operation', header: 'Operation', render: (record) => <span className="capitalize">{displayOperation(record.operation)}</span> },
    { key: 'actor', header: 'Actor', render: (record) => record.actor_attribution_available ? record.actor_name ?? record.actor_id : <span className="text-slate-500" title="Authentication is not implemented; no individual actor was recorded.">SYSTEM · unattributed</span> },
    { key: 'details', header: '', className: 'text-right', render: (record) => <Button size="sm" onClick={() => void showDetails(record.event_id)}><Eye className="h-3.5 w-3.5" /> Changes</Button> },
  ], []);

  const totalPages = result ? Math.max(1, Math.ceil(result.total / result.page_size)) : 1;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Audit History</h1>
          <p className="mt-2 text-sm text-slate-500">Chronological, read-only history of changes to workspace records.</p>
        </div>
        <Badge tone="neutral">Read only</Badge>
      </header>
      <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        Authentication is not implemented. Events marked “SYSTEM · unattributed” have no individual actor recorded; attributed employee IDs do not establish who authenticated.
      </p>
      <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <label className="space-y-1.5 text-xs font-medium text-slate-500">
            Entity type
            <select className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800" value={entityType} onChange={(event) => { setEntityType(event.target.value as AuditEntityType | ''); setPage(1); }}>
              <option value="">All entity types</option>
              {entityTypes.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="space-y-1.5 text-xs font-medium text-slate-500">
            Operation
            <select className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800" value={operation} onChange={(event) => { setOperation(event.target.value as AuditOperation | ''); setPage(1); }}>
              <option value="">All operations</option>
              {operations.map((value) => <option key={value} value={value}>{displayOperation(value)}</option>)}
            </select>
          </label>
          <div className="space-y-1.5 text-xs font-medium text-slate-500">
            Entity ID
            <TextInput value={entityId} onChange={(event) => { setEntityId(event.target.value); setPage(1); }} placeholder="Filter by exact entity ID" aria-label="Filter by entity ID" leadingIcon={<Search className="h-4 w-4" />} />
          </div>
          <label className="space-y-1.5 text-xs font-medium text-slate-500">
            From date
            <input type="date" value={dateFrom} onChange={(event) => { setDateFrom(event.target.value); setPage(1); }} className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800" />
          </label>
          <label className="space-y-1.5 text-xs font-medium text-slate-500">
            To date
            <input type="date" value={dateTo} onChange={(event) => { setDateTo(event.target.value); setPage(1); }} className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800" />
          </label>
          <div className="flex items-end">
            <Button className="w-full" onClick={() => { setEntityType(''); setEntityId(''); setOperation(''); setDateFrom(''); setDateTo(''); setPage(1); }}>Clear filters</Button>
          </div>
        </div>
        {error && !selected && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}
        {loading ? <Loading /> : result?.items.length ? (
          <>
            <DataTable columns={columns} rows={result.items} getRowKey={(record) => record.event_id} label="Audit history records" />
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4 text-sm text-slate-500">
              <span>{result.total.toLocaleString()} audit events · newest first</span>
              <div className="flex items-center gap-2">
                <Button size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button>
                <span>Page {page} of {totalPages}</span>
                <Button size="sm" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>Next</Button>
              </div>
            </div>
          </>
        ) : (
          <EmptyState title="No audit events found" description="Change or clear the filters to see matching history." />
        )}
      </section>

      <Modal open={selected !== null} title="Audit event details" onClose={() => setSelected(null)} className="w-full max-w-3xl">
        {selected && (
          <div className="flex-1 space-y-5 overflow-y-auto p-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="info">{selected.entity_type}</Badge>
              <Badge tone="neutral">{displayOperation(selected.operation)}</Badge>
              <span className="font-mono text-sm text-slate-700">{selected.entity_id}</span>
            </div>
            <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
              <div><dt className="text-slate-500">Timestamp</dt><dd className="mt-1 font-medium text-slate-800">{formatTimestamp(selected.recorded_at)}</dd></div>
              <div><dt className="text-slate-500">Event ID</dt><dd className="mt-1 break-all font-mono text-xs text-slate-800">{selected.event_id}</dd></div>
              <div><dt className="text-slate-500">Actor</dt><dd className="mt-1 font-medium text-slate-800">{selected.actor_attribution_available ? `${selected.actor_name ?? selected.actor_id} (${selected.actor_id})` : 'SYSTEM · unattributed'}</dd></div>
              <div><dt className="text-slate-500">Actor employee ID</dt><dd className="mt-1 font-medium text-slate-800">{selected.actor_employee_id ?? 'Not recorded'}</dd></div>
            </dl>
            {!selected.actor_attribution_available && <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">Authentication is not implemented; this event cannot be tied to a verified user.</p>}
            <div className="grid gap-4 lg:grid-cols-2">
              <section className="space-y-2"><h3 className="text-sm font-semibold text-slate-800">Before</h3><ChangeData value={selected.before_data} /></section>
              <section className="space-y-2"><h3 className="text-sm font-semibold text-slate-800">After</h3><ChangeData value={selected.after_data} /></section>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
