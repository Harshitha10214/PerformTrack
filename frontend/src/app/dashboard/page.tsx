'use client';

import { useEffect, useState } from 'react';
import { Clock3 } from 'lucide-react';

import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import EmptyState from '@/components/common/EmptyState';
import Loading from '@/components/common/Loading';
import GoalProgressChart from '@/components/dashboard/GoalProgressChart';
import RecentCheckIns from '@/components/dashboard/RecentCheckIns';
import ReviewSummary from '@/components/dashboard/ReviewSummary';
import StatCard from '@/components/dashboard/StatCard';
import { getDashboardAnalytics, type DashboardAnalytics } from '@/services/api';

function formatNumber(value: number): string {
  return new Intl.NumberFormat('en').format(value);
}

export default function HomePage() {
  const [analytics, setAnalytics] = useState<DashboardAnalytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let active = true;
    setError(null);

    getDashboardAnalytics()
      .then((result) => {
        if (active) setAnalytics(result);
      })
      .catch((loadError: unknown) => {
        if (active) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : 'Unable to load dashboard analytics.',
          );
        }
      });

    return () => {
      active = false;
    };
  }, [retryCount]);

  return (
      <div className="space-y-7">
        <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="text-sm font-semibold text-indigo-600">Performance overview</p>
            <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-[30px]">
              Organization performance
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              A live snapshot of goals, reviews, and employee progress.
            </p>
          </div>
          <Badge className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-slate-500 shadow-sm">
            <Clock3 className="h-4 w-4 text-slate-400" aria-hidden="true" />
            Metrics from PostgreSQL
          </Badge>
        </section>

        {error ? (
          <div
            className="flex flex-col justify-between gap-4 rounded-2xl border border-rose-200 bg-rose-50 p-5 sm:flex-row sm:items-center"
            role="alert"
          >
            <div>
              <p className="text-sm font-semibold text-rose-800">Dashboard data could not be loaded</p>
              <p className="mt-1 text-sm text-rose-700">{error}</p>
            </div>
            <Button
              variant="danger"
              size="sm"
              onClick={() => setRetryCount((current) => current + 1)}
            >
              Try again
            </Button>
          </div>
        ) : !analytics ? (
          <Loading />
        ) : (
          <>
            <section aria-label="Organization statistics">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-700">Organization at a glance</h2>
                <span className="text-xs text-slate-400">Live totals</span>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard
                  label="Total employees"
                  value={formatNumber(analytics.overview.total_employees)}
                  detail="People in the organization"
                  icon="people"
                  tone="indigo"
                />
                <StatCard
                  label="Total managers"
                  value={formatNumber(analytics.overview.total_managers)}
                  detail="Manager profiles"
                  icon="managers"
                  tone="sky"
                />
                <StatCard
                  label="Total goals"
                  value={formatNumber(analytics.overview.total_goals)}
                  detail="Across all review cycles"
                  icon="goals"
                  tone="violet"
                />
                <StatCard
                  label="Completed goals"
                  value={formatNumber(analytics.overview.completed_goals)}
                  detail="Goals marked completed"
                  icon="complete"
                  tone="emerald"
                />
                <StatCard
                  label="Average goal progress"
                  value={
                    analytics.overview.average_goal_progress === null
                      ? '—'
                      : `${analytics.overview.average_goal_progress.toFixed(1)}%`
                  }
                  detail="Calculated from key result actuals"
                  icon="progress"
                  tone="indigo"
                />
                <StatCard
                  label="Active review cycles"
                  value={formatNumber(analytics.overview.active_review_cycles)}
                  detail="Cycles currently open"
                  icon="cycles"
                  tone="amber"
                />
                <StatCard
                  label="Pending reviews"
                  value={formatNumber(analytics.overview.pending_reviews)}
                  detail="Draft, in progress, or submitted"
                  icon="reviews"
                  tone="sky"
                />
              </div>
            </section>

            {analytics.overview.total_employees === 0 && analytics.overview.total_goals === 0 ? (
              <EmptyState
                title="Your dashboard is ready"
                description="There are no employee or goal records to analyze yet."
              />
            ) : null}

            <section className="grid gap-5 xl:grid-cols-2" aria-label="Performance analytics">
              <GoalProgressChart bands={analytics.goal_progress_distribution} />
              <ReviewSummary departments={analytics.department_performance} />
            </section>

            <section className="grid gap-5 xl:grid-cols-[1.4fr_0.8fr]">
              <RecentCheckIns checkIns={analytics.recent_check_ins} />
              <section className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm sm:p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-base font-semibold text-slate-900">Data quality</h2>
                    <p className="mt-1 text-sm text-slate-500">Relationship and source-record checks</p>
                  </div>
                  <Badge
                    tone={
                      analytics.data_quality.status === 'healthy' ? 'success' : 'warning'
                    }
                    className="capitalize"
                  >
                    {analytics.data_quality.status.replace('_', ' ')}
                  </Badge>
                </div>
                <div className="mt-5 flex items-center gap-4 rounded-xl bg-slate-50 p-4">
                  <div
                    className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-full border-[5px] text-sm font-bold ${
                      analytics.data_quality.status === 'healthy'
                        ? 'border-emerald-100 text-emerald-700'
                        : 'border-amber-100 text-amber-700'
                    }`}
                    aria-label={`${analytics.data_quality.checks_passed} of ${analytics.data_quality.checks_total} data quality checks passed`}
                  >
                    {analytics.data_quality.checks_passed}/{analytics.data_quality.checks_total}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-800">Quality checks passed</p>
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      Live checks across relationships and goal data.
                    </p>
                  </div>
                </div>
                <ul className="mt-4 space-y-3">
                  {analytics.data_quality.checks.map((check) => (
                    <li key={check.label} className="flex items-center justify-between gap-3 text-sm">
                      <span className="flex min-w-0 items-center gap-2.5 text-slate-600">
                        <span
                          className={`h-2 w-2 shrink-0 rounded-full ${
                            check.passed ? 'bg-emerald-500' : 'bg-amber-500'
                          }`}
                        />
                        <span className="truncate">{check.label}</span>
                      </span>
                      <span
                        className={`shrink-0 text-xs font-semibold tabular-nums ${
                          check.passed ? 'text-emerald-700' : 'text-amber-700'
                        }`}
                      >
                        {check.affected_records.toLocaleString()} affected
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            </section>
          </>
        )}
      </div>
  );
}
