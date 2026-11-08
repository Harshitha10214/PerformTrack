import type { DepartmentPerformance } from '@/services/api';
import Badge from '@/components/common/Badge';
import DataTable, { type DataTableColumn } from '@/components/common/DataTable';
import EmptyState from '@/components/common/EmptyState';

interface ReviewSummaryProps {
  departments: DepartmentPerformance[];
}

const columns: DataTableColumn<DepartmentPerformance>[] = [
  {
    key: 'department',
    header: 'Department',
    render: (department) => (
      <span className="font-medium text-slate-800">{department.department}</span>
    ),
  },
  {
    key: 'employees',
    header: 'Employees',
    className: 'text-right tabular-nums',
    render: (department) => department.employee_count.toLocaleString(),
  },
  {
    key: 'goals',
    header: 'Goals completed',
    render: (department) => (
      <Badge tone={department.completed_goals > 0 ? 'success' : 'neutral'}>
        {department.completed_goals.toLocaleString()} / {department.goal_count.toLocaleString()}
      </Badge>
    ),
  },
  {
    key: 'progress',
    header: 'Avg. progress',
    className: 'text-right tabular-nums',
    render: (department) =>
      department.average_goal_progress === null
        ? '—'
        : `${department.average_goal_progress.toFixed(1)}%`,
  },
];

export default function ReviewSummary({ departments }: ReviewSummaryProps) {
  return (
    <section id="reviews" className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm sm:p-6">
      <div>
        <h2 className="text-base font-semibold text-slate-900">Employee performance analytics</h2>
        <p className="mt-1 text-sm text-slate-500">Goal progress by department</p>
      </div>

      {departments.length === 0 ? (
        <div className="mt-6">
          <EmptyState title="No department data" description="Department analytics will appear when employee goals are available." />
        </div>
      ) : (
        <div className="mt-5">
          <DataTable
            columns={columns}
            rows={departments}
            getRowKey={(department) => department.department}
            label="Department performance analytics"
          />
        </div>
      )}
    </section>
  );
}
