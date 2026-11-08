import type { LucideIcon } from 'lucide-react';
import {
  Activity,
  Archive,
  BarChart3,
  CalendarDays,
  FileClock,
  FolderKanban,
  Goal,
  MessageSquareText,
  Network,
  Paperclip,
  Users,
} from 'lucide-react';

export interface NavigationItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

export interface NavigationGroup {
  label: string;
  items: NavigationItem[];
}

export const navigationGroups: NavigationGroup[] = [
  {
    label: 'Workspace',
    items: [{ label: 'Overview', href: '/dashboard', icon: BarChart3 }],
  },
  {
    label: 'People',
    items: [
      { label: 'Employees', href: '/employees', icon: Users },
      { label: 'Managers', href: '/managers', icon: Network },
    ],
  },
  {
    label: 'Performance',
    items: [
      { label: 'Goals & Key Results', href: '/goals', icon: Goal },
      { label: 'Check-ins', href: '/check-ins', icon: MessageSquareText },
      { label: 'Competencies & Feedback', href: '/feedback', icon: Activity },
      { label: 'Review Cycles & Reviews', href: '/reviews', icon: CalendarDays },
    ],
  },
  {
    label: 'Growth',
    items: [{ label: 'Development Plans', href: '/development-plans', icon: FolderKanban }],
  },
  {
    label: 'Administration',
    items: [
      { label: 'Evidence', href: '/evidence', icon: Paperclip },
      { label: 'Audit History', href: '/audit-history', icon: FileClock },
      { label: 'Data & Exports', href: '/data-exports', icon: Archive },
    ],
  },
];

export const availableNavigationItems = navigationGroups.flatMap((group) => group.items);
