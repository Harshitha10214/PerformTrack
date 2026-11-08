'use client';

import { useEffect, useMemo, useState } from 'react';
import { Download, FileArchive, FileJson, FileSpreadsheet, FileText, RefreshCw } from 'lucide-react';

import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import DataTable, { type DataTableColumn } from '@/components/common/DataTable';
import EmptyState from '@/components/common/EmptyState';
import Loading from '@/components/common/Loading';
import {
  getDataExportStatus,
  getExportDownloadUrl,
  type DataExportStatus,
  type ExportArtifact,
  type ExportTableFiles,
} from '@/services/api';

type ExportSelection = 'csv' | 'json' | 'sql';

const selectionDetails: Record<ExportSelection, { label: string; description: string }> = {
  csv: { label: 'CSV', description: 'One CSV file per database table, preserving IDs and foreign-key columns.' },
  json: { label: 'JSON', description: 'Table JSON files plus the aggregate dataset and validation reports.' },
  sql: { label: 'SQL', description: 'Transactional INSERT script for the prepared baseline data.' },
};

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(timestamp: number): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(timestamp * 1000));
}

function shortChecksum(checksum: string): string {
  return `${checksum.slice(0, 12)}…`;
}

export default function DataExportsPage() {
  const [status, setStatus] = useState<DataExportStatus | null>(null);
  const [selection, setSelection] = useState<ExportSelection>('csv');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setStatus(await getDataExportStatus());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load export status.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const columns = useMemo<DataTableColumn<ExportTableFiles>[]>(() => [
    { key: 'table', header: 'Table', render: (row) => <span className="font-medium text-slate-800">{row.table}</span> },
    { key: 'rows', header: 'Rows', render: (row) => row.rows.toLocaleString() },
    {
      key: 'file',
      header: 'Export file',
      render: (row) => {
        const artifact = selection === 'csv' ? row.csv : row.json;
        const icon = selection === 'csv'
          ? <FileSpreadsheet className="h-4 w-4" />
          : <FileJson className="h-4 w-4" />;
        return (
          <a
            href={getExportDownloadUrl(artifact)}
            className="inline-flex items-center gap-2 font-medium text-indigo-700 hover:text-indigo-900"
          >
            {icon}{artifact.file_name}<Download className="h-3.5 w-3.5" />
          </a>
        );
      },
    },
    { key: 'size', header: 'Size', render: (row) => formatBytes(selection === 'csv' ? row.csv.size_bytes : row.json.size_bytes) },
    { key: 'sha256', header: 'SHA-256', render: (row) => <span className="font-mono text-xs" title={selection === 'csv' ? row.csv.sha256 : row.json.sha256}>{shortChecksum(selection === 'csv' ? row.csv.sha256 : row.json.sha256)}</span> },
  ], [selection]);

  const selectedFileCount = selection === 'csv' ? status?.tables.length ?? 0 : selection === 'json' ? (status?.tables.length ?? 0) + (status?.supplementary.length ?? 0) : 1;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Data &amp; Exports</h1>
          <p className="mt-2 text-sm text-slate-500">Download the prepared PostgreSQL baseline and its validation reports.</p>
        </div>
        <Button onClick={() => void load()} disabled={loading}><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> Refresh status</Button>
      </header>

      {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}
      {loading ? <Loading /> : status ? (
        <>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Generation status</p>
              <div className="mt-2 flex items-center gap-2"><Badge tone="success">Ready</Badge><span className="text-sm text-slate-600">{selectedFileCount} {selectionDetails[selection].label} files</span></div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Prepared records</p>
              <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-900">{status.total_rows.toLocaleString()}</p>
              <p className="mt-1 text-xs text-slate-500">Across {status.tables.length} tables</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Source</p>
              <p className="mt-2 font-medium text-slate-900">{status.source_database}</p>
              <p className="mt-1 text-xs text-slate-500">{status.preparation_mode.replaceAll('_', ' ')}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Prepared</p>
              <p className="mt-2 font-medium text-slate-900">{formatDate(status.generated_at)}</p>
              <p className="mt-1 font-mono text-xs text-slate-500" title={status.dataset_sha256}>SHA-256 {shortChecksum(status.dataset_sha256)}</p>
            </div>
          </section>

          <section className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
            Validation passed: {status.validation.duplicate_primary_keys.toLocaleString()} duplicate primary keys,
            {' '}{status.validation.foreign_key_columns_validated.toLocaleString()} foreign-key columns checked,
            {' '}{status.validation.goal_progress_count.toLocaleString()} goal progress values.
          </section>

          <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold text-slate-900">Available exports</h2>
                <p className="mt-1 text-sm text-slate-500">{selectionDetails[selection].description}</p>
              </div>
              <label className="space-y-1 text-xs font-medium text-slate-500">
                Export format
                <select
                  aria-label="Export format"
                  className="block h-10 min-w-36 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800"
                  value={selection}
                  onChange={(event) => setSelection(event.target.value as ExportSelection)}
                >
                  <option value="csv">CSV</option>
                  <option value="json">JSON</option>
                  <option value="sql">SQL</option>
                </select>
              </label>
            </div>

            {selection === 'sql' ? (
              <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-slate-100 bg-slate-50 p-4">
                <div className="flex items-center gap-3">
                  <FileText className="h-5 w-5 text-indigo-600" />
                  <div><p className="font-medium text-slate-800">{status.sql.file_name}</p><p className="text-xs text-slate-500">{formatBytes(status.sql.size_bytes)} · {status.sql.rows?.toLocaleString()} INSERT rows · SHA-256 {shortChecksum(status.sql.sha256)}</p></div>
                </div>
                <a href={getExportDownloadUrl(status.sql)} className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-indigo-600 px-3.5 text-sm font-medium text-white hover:bg-indigo-700"><Download className="h-4 w-4" /> Download SQL</a>
              </div>
            ) : (
              <>
                <DataTable columns={columns} rows={status.tables} getRowKey={(row) => row.table} label={`${selectionDetails[selection].label} export files`} />
                {selection === 'json' && (
                  <div className="space-y-2 border-t border-slate-100 pt-4">
                    <h3 className="text-sm font-semibold text-slate-800">Summary files</h3>
                    <div className="flex flex-wrap gap-x-5 gap-y-2">
                      {status.supplementary.map((artifact) => (
                        <a key={artifact.file_name} href={getExportDownloadUrl(artifact)} className="inline-flex items-center gap-2 text-sm font-medium text-indigo-700 hover:text-indigo-900">
                          <FileJson className="h-4 w-4" />{artifact.file_name}<span className="text-xs text-slate-400">{formatBytes(artifact.size_bytes)}</span>
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
            <h2 className="text-base font-semibold text-slate-900">Documentation and validation</h2>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
              {[...status.documentation, ...status.supplementary.filter((file) => file.file_name === 'validation_report.json' || file.file_name === 'generation_summary.json')].map((artifact) => (
                <a key={`${artifact.format}-${artifact.file_name}`} href={getExportDownloadUrl(artifact)} className="inline-flex items-center gap-2 text-sm font-medium text-indigo-700 hover:text-indigo-900">
                  {artifact.format === 'docs' ? <FileText className="h-4 w-4" /> : <FileArchive className="h-4 w-4" />}
                  {artifact.file_name}<span className="text-xs text-slate-400">{formatBytes(artifact.size_bytes)}</span>
                </a>
              ))}
            </div>
          </section>
        </>
      ) : (
        <EmptyState title="Exports are unavailable" description="Prepared export files or validation reports could not be found." />
      )}
    </div>
  );
}
