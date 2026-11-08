import Badge from '@/components/common/Badge';
import EmptyState from '@/components/common/EmptyState';

interface ModuleComingSoonProps {
  title: string;
  description: string;
}

export default function ModuleComingSoon({
  title,
  description,
}: ModuleComingSoonProps) {
  return (
    <div className="space-y-6">
      <header>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
          <Badge tone="neutral">Coming soon</Badge>
        </div>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">{description}</p>
      </header>
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <EmptyState
          title="This module is not available yet"
          description="Its API and interactive workflows have not been implemented. No sample records or simulated actions are shown."
        />
      </section>
    </div>
  );
}
