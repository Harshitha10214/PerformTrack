import type { GoalProgressBand } from '@/services/api';
import EmptyState from '@/components/common/EmptyState';

interface GoalProgressChartProps {
  bands: GoalProgressBand[];
}

const bandColors = [
  'bg-rose-400',
  'bg-amber-400',
  'bg-sky-400',
  'bg-indigo-500',
  'bg-emerald-500',
];

export default function GoalProgressChart({ bands }: GoalProgressChartProps) {
  const maximum = Math.max(...bands.map((band) => band.count), 0);
  const total = bands.reduce((sum, band) => sum + band.count, 0);

  return (
    <section id="goals" className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Goal progress distribution</h2>
          <p className="mt-1 text-sm text-slate-500">Goals grouped by calculated progress</p>
        </div>
        <span className="rounded-lg bg-slate-50 px-2.5 py-1.5 text-xs font-semibold text-slate-500">
          {total.toLocaleString()} goals
        </span>
      </div>

      {total === 0 ? (
        <div className="mt-6">
          <EmptyState title="No goal progress yet" description="Progress appears when goals have key results." />
        </div>
      ) : (
        <div className="mt-8 space-y-5">
          {bands.map((band, index) => {
            const width = maximum === 0 ? 0 : (band.count / maximum) * 100;
            return (
              <div key={band.label} className="grid grid-cols-[52px_minmax(0,1fr)_44px] items-center gap-3">
                <span className="text-xs font-medium tabular-nums text-slate-500">{band.label}</span>
                <div
                  className="h-2.5 overflow-hidden rounded-full bg-slate-100"
                  role="img"
                  aria-label={`${band.label}: ${band.count} goals`}
                >
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${bandColors[index % bandColors.length]}`}
                    style={{ width: `${width}%` }}
                  />
                </div>
                <span className="text-right text-xs font-semibold tabular-nums text-slate-700">
                  {band.count.toLocaleString()}
                </span>
              </div>
            );
          })}
        </div>
      )}
      <div className="mt-7 flex items-center gap-2 border-t border-slate-100 pt-4 text-xs text-slate-400">
        <span className="h-2 w-2 rounded-full bg-indigo-500" />
        Progress is calculated from key result actuals and targets
      </div>
    </section>
  );
}
