import type { ReactNode } from 'react';

export interface DataTableColumn<Row> {
  key: string;
  header: string;
  render: (row: Row) => ReactNode;
  className?: string;
}

interface DataTableProps<Row> {
  columns: DataTableColumn<Row>[];
  rows: Row[];
  getRowKey: (row: Row) => string;
  label: string;
}

export default function DataTable<Row>({
  columns,
  rows,
  getRowKey,
  label,
}: DataTableProps<Row>) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] text-left text-sm" aria-label={label}>
        <thead>
          <tr className="border-b border-slate-100 text-[11px] font-medium uppercase tracking-wide text-slate-400">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={`px-3 py-2.5 first:pl-0 last:pr-0 ${column.className ?? ''}`}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr key={getRowKey(row)} className="text-slate-600">
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={`px-3 py-3 first:pl-0 last:pr-0 ${column.className ?? ''}`}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
