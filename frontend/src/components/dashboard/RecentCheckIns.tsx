import type { RecentCheckIn } from '@/services/api';
import EmptyState from '@/components/common/EmptyState';
import Badge from '@/components/common/Badge';

interface RecentCheckInsProps {
  checkIns: RecentCheckIn[];
}

function formatCheckInDate(value: string): string {
  const [year, month, day] = value.split('-').map(Number);
  return new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric' }).format(
    new Date(year, month - 1, day),
  );
}

function statusTone(status: string): 'success' | 'warning' | 'info' | 'neutral' {
  if (status === 'completed') return 'success';
  if (status === 'missed') return 'warning';
  if (status === 'scheduled') return 'info';
  return 'neutral';
}

export default function RecentCheckIns({ checkIns }: RecentCheckInsProps) {
  return (
    <section id="check-ins" className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Recent check-ins</h2>
          <p className="mt-1 text-sm text-slate-500">Latest employee and manager conversations</p>
        </div>
        <span className="rounded-lg bg-indigo-50 px-2.5 py-1.5 text-xs font-semibold text-indigo-600">
          Latest {checkIns.length}
        </span>
      </div>

      {checkIns.length === 0 ? (
        <div className="mt-5">
          <EmptyState title="No check-ins recorded" description="New check-ins will appear here as they are logged." />
        </div>
      ) : (
        <div className="mt-4 divide-y divide-slate-100">
          {checkIns.map((checkIn) => (
            <article key={checkIn.id} className="flex items-center gap-3 py-3.5 first:pt-1 last:pb-1">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-bold uppercase text-slate-600">
                {checkIn.employee_name
                  .split(' ')
                  .map((part) => part[0])
                  .slice(0, 2)
                  .join('')}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-slate-800">
                  {checkIn.employee_name}
                </p>
                <p className="mt-1 truncate text-xs text-slate-400">
                  {checkIn.manager_name ? `with ${checkIn.manager_name}` : 'Manager not assigned'}
                  <span className="mx-1.5">·</span>
                  {formatCheckInDate(checkIn.checkin_date)}
                </p>
              </div>
              <Badge tone={statusTone(checkIn.status)} className="shrink-0 capitalize">
                {checkIn.status.replace('_', ' ')}
              </Badge>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
