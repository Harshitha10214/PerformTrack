import {
  Activity,
  CalendarDays,
  Check,
  CircleUserRound,
  FileCheck2,
  Flag,
  Users,
  type LucideIcon,
} from 'lucide-react';

type StatIcon = 'people' | 'managers' | 'goals' | 'complete' | 'progress' | 'cycles' | 'reviews';

interface StatCardProps {
  label: string;
  value: string;
  detail: string;
  icon: StatIcon;
  tone: 'indigo' | 'sky' | 'violet' | 'emerald' | 'amber';
}

const icons: Record<StatIcon, LucideIcon> = {
  people: Users,
  managers: CircleUserRound,
  goals: Flag,
  complete: Check,
  progress: Activity,
  cycles: CalendarDays,
  reviews: FileCheck2,
};

const toneStyles = {
  indigo: 'bg-indigo-50 text-indigo-600',
  sky: 'bg-sky-50 text-sky-600',
  violet: 'bg-violet-50 text-violet-600',
  emerald: 'bg-emerald-50 text-emerald-600',
  amber: 'bg-amber-50 text-amber-600',
};

export default function StatCard({ label, value, detail, icon, tone }: StatCardProps) {
  const Icon = icons[icon];
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-slate-500">{label}</p>
          <p className="mt-3 text-[27px] font-bold leading-none tracking-tight text-slate-900">
            {value}
          </p>
        </div>
        <span className={`flex h-9 w-9 items-center justify-center rounded-lg ${toneStyles[tone]}`}>
          <Icon className="h-[18px] w-[18px]" strokeWidth={1.8} aria-hidden="true" />
        </span>
      </div>
      <p className="mt-4 text-xs leading-5 text-slate-400">{detail}</p>
    </article>
  );
}
