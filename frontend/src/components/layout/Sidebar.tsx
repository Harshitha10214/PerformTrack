'use client';

import Link from 'next/link';
import { CircleHelp, PanelLeftClose, PanelLeftOpen, X } from 'lucide-react';

import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import { navigationGroups } from '@/components/layout/navigation';

interface SidebarProps {
  collapsed: boolean;
  activeHref: string;
  mobile?: boolean;
  onCollapse?: () => void;
  onClose?: () => void;
  onNavigate?: (label: string, href: string) => void;
}

export default function Sidebar({
  collapsed,
  activeHref,
  mobile = false,
  onCollapse,
  onClose,
  onNavigate,
}: SidebarProps) {
  return (
    <aside
      className={`flex h-full flex-col overflow-y-auto border-r border-slate-200 bg-white transition-[width] duration-200 ${
        collapsed && !mobile ? 'w-[76px]' : 'w-[264px]'
      }`}
    >
      <div
        className={`flex h-[72px] shrink-0 items-center border-b border-slate-100 ${
          collapsed && !mobile ? 'justify-center px-2' : 'justify-between px-5'
        }`}
      >
        <Link
          href="/dashboard"
          onClick={() => onNavigate?.('Overview', '/dashboard')}
          className="flex min-w-0 items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          aria-label="PerformTrack overview"
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-600 text-base font-bold text-white">
            P
          </span>
          {(!collapsed || mobile) && (
            <span className="min-w-0">
              <span className="block truncate text-sm font-bold tracking-tight text-slate-900">
                PerformTrack
              </span>
              <span className="mt-0.5 block text-[10px] font-medium uppercase tracking-[0.14em] text-slate-400">
                People operations
              </span>
            </span>
          )}
        </Link>
        {!mobile && onCollapse ? (
          <Button
            variant="ghost"
            size="icon"
            onClick={onCollapse}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className={collapsed ? 'hidden' : ''}
          >
            {collapsed ? (
              <PanelLeftOpen className="h-4 w-4" aria-hidden="true" />
            ) : (
              <PanelLeftClose className="h-4 w-4" aria-hidden="true" />
            )}
          </Button>
        ) : null}
        {mobile && onClose ? (
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label="Close navigation"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </Button>
        ) : null}
      </div>

      {collapsed && !mobile && onCollapse ? (
        <div className="flex justify-center border-b border-slate-100 py-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={onCollapse}
            aria-label="Expand sidebar"
            title="Expand sidebar"
          >
            <PanelLeftOpen className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      ) : null}

      <nav className="flex-1 space-y-5 px-3 py-5" aria-label="Main navigation">
        {navigationGroups.map((group) => (
          <div key={group.label}>
            {(!collapsed || mobile) && (
              <h2 className="mb-1.5 px-2.5 text-[10px] font-semibold uppercase tracking-[0.13em] text-slate-400">
                {group.label}
              </h2>
            )}
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon;
                const active = activeHref === item.href;
                const itemClass = `group flex min-h-9 w-full items-center gap-3 rounded-lg px-2.5 text-left text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
                  active
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                } ${collapsed && !mobile ? 'justify-center px-0' : ''}`;

                return (
                  <li key={item.label}>
                    <Link
                      href={item.href}
                      onClick={() => onNavigate?.(item.label, item.href)}
                      className={itemClass}
                      aria-current={active ? 'page' : undefined}
                      title={collapsed && !mobile ? item.label : undefined}
                    >
                      <Icon className="h-[17px] w-[17px] shrink-0" strokeWidth={1.8} aria-hidden="true" />
                      {(!collapsed || mobile) && <span className="truncate">{item.label}</span>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {(!collapsed || mobile) && (
        <div className="m-3 mt-0 rounded-xl border border-slate-200 bg-slate-50 p-3.5">
          <div className="flex items-center gap-2 text-slate-700">
            <CircleHelp className="h-4 w-4 shrink-0" aria-hidden="true" />
            <p className="text-xs font-semibold">Need help?</p>
            <Badge className="ml-auto">Support</Badge>
          </div>
          <p className="mt-1.5 text-[11px] leading-4 text-slate-500">
            Contact your PerformTrack administrator for workspace access.
          </p>
        </div>
      )}
    </aside>
  );
}
