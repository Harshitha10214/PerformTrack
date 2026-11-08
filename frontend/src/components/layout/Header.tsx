'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import {
  Bell,
  ChevronDown,
  Command,
  Menu,
  Search,
  UserRound,
  X,
} from 'lucide-react';

import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import Dropdown from '@/components/common/Dropdown';
import TextInput from '@/components/common/TextInput';
import { navigationGroups } from '@/components/layout/navigation';

interface HeaderProps {
  pageLabel: string;
  onOpenMobileNavigation: () => void;
  onNavigate: (label: string, href: string) => void;
}

export default function Header({
  pageLabel,
  onOpenMobileNavigation,
  onNavigate,
}: HeaderProps) {
  const [query, setQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const mobileSearchRef = useRef<HTMLDivElement>(null);
  const searchResults = navigationGroups
    .flatMap((group) => group.items.map((item) => ({ ...item, group: group.label })))
    .filter((item) => item.label.toLowerCase().includes(query.trim().toLowerCase()));

  useEffect(() => {
    const closeSearch = (event: PointerEvent) => {
      if (
        event.target instanceof Node &&
        !searchRef.current?.contains(event.target) &&
        !mobileSearchRef.current?.contains(event.target)
      ) {
        setSearchOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSearchOpen(false);
    };

    document.addEventListener('pointerdown', closeSearch);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeSearch);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, []);

  const searchResultsList = searchResults.length ? (
    <ul aria-label="Navigation search results">
      {searchResults.map((item) => {
        const Icon = item.icon;
        return (
          <li key={item.label}>
            <Link
              href={item.href}
              onClick={() => {
                onNavigate(item.label, item.href);
                setSearchOpen(false);
                setMobileSearchOpen(false);
                setQuery('');
              }}
              className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              <Icon className="h-4 w-4 text-slate-400" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate">{item.label}</span>
              <span className="text-[10px] text-slate-400">{item.group}</span>
            </Link>
          </li>
        );
      })}
    </ul>
  ) : (
    <p className="px-2.5 py-3 text-xs text-slate-500">No navigation matches found.</p>
  );

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white">
      <div className="flex min-h-[68px] items-center justify-between gap-3 px-4 sm:px-6 xl:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={onOpenMobileNavigation}
            aria-label="Open navigation"
          >
            <Menu className="h-[18px] w-[18px]" aria-hidden="true" />
          </Button>
          <div className="min-w-0">
            <nav aria-label="Breadcrumb" className="mb-0.5 hidden items-center gap-1.5 text-[11px] sm:flex">
              <span className="text-slate-400">Workspace</span>
              <span className="text-slate-300" aria-hidden="true">/</span>
              <span className="truncate font-medium text-slate-500">{pageLabel}</span>
            </nav>
            <p className="truncate text-sm font-semibold text-slate-900">{pageLabel}</p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
          <div ref={searchRef} className="relative hidden w-52 md:block xl:w-64">
            <TextInput
              type="search"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setSearchOpen(true);
              }}
              onFocus={() => setSearchOpen(true)}
              placeholder="Search navigation"
              aria-label="Search navigation"
              aria-expanded={searchOpen}
              aria-controls="navigation-search-results"
              leadingIcon={<Search className="h-4 w-4" aria-hidden="true" />}
              className="h-9 bg-slate-50 text-xs focus:bg-white"
            />
            {searchOpen && query.trim() ? (
              <div
                id="navigation-search-results"
                className="absolute right-0 top-full z-50 mt-2 max-h-80 w-72 overflow-y-auto rounded-xl border border-slate-200 bg-white p-2 shadow-lg shadow-slate-900/10"
              >
                {searchResultsList}
              </div>
            ) : null}
          </div>

          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => {
              setMobileSearchOpen((current) => !current);
              setSearchOpen(true);
            }}
            aria-label={mobileSearchOpen ? 'Close navigation search' : 'Open navigation search'}
            aria-expanded={mobileSearchOpen}
          >
            {mobileSearchOpen ? (
              <X className="h-4 w-4" aria-hidden="true" />
            ) : (
              <Search className="h-4 w-4" aria-hidden="true" />
            )}
          </Button>

          <Dropdown
            label="Notifications"
            trigger={({ expanded, controls, onClick }) => (
              <Button
                variant="ghost"
                size="icon"
                onClick={onClick}
                aria-label="Notifications"
                aria-expanded={expanded}
                aria-controls={controls}
              >
                <Bell className="h-[17px] w-[17px]" aria-hidden="true" />
              </Button>
            )}
          >
            <div className="flex items-center justify-between px-1 pb-2">
              <p className="text-sm font-semibold text-slate-800">Notifications</p>
              <Badge>Updates</Badge>
            </div>
            <div className="rounded-lg bg-slate-50 px-3 py-4 text-center">
              <Bell className="mx-auto h-5 w-5 text-slate-400" aria-hidden="true" />
              <p className="mt-2 text-xs font-medium text-slate-700">No notifications to show</p>
              <p className="mt-1 text-[11px] text-slate-500">
                Notification updates are not available in this workspace yet.
              </p>
            </div>
          </Dropdown>

          <Dropdown
            label="Account menu"
            trigger={({ expanded, controls, onClick }) => (
              <Button
                variant="ghost"
                onClick={onClick}
                aria-label="Open account menu"
                aria-expanded={expanded}
                aria-controls={controls}
                className="gap-2 px-1.5 sm:px-2"
              >
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-600">
                  <UserRound className="h-4 w-4" aria-hidden="true" />
                </span>
                <span className="hidden text-xs font-medium text-slate-700 sm:inline">Account</span>
                <ChevronDown className="hidden h-3.5 w-3.5 text-slate-400 sm:block" aria-hidden="true" />
              </Button>
            )}
          >
            <div className="flex items-center gap-2.5 border-b border-slate-100 px-1 pb-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-600">
                <UserRound className="h-4 w-4" aria-hidden="true" />
              </span>
              <div>
                <p className="text-sm font-medium text-slate-800">Workspace account</p>
                <p className="text-xs text-slate-500">Account management is not configured.</p>
              </div>
            </div>
            <div className="flex items-center gap-2 px-1 pt-3 text-[11px] text-slate-500">
              <Command className="h-3.5 w-3.5" aria-hidden="true" />
              Use the sidebar to navigate available workspace views.
            </div>
          </Dropdown>
        </div>
      </div>
      {mobileSearchOpen ? (
        <div ref={mobileSearchRef} className="relative border-t border-slate-100 px-4 py-3 md:hidden">
          <TextInput
            autoFocus
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setSearchOpen(true);
            }}
            onFocus={() => setSearchOpen(true)}
            placeholder="Search navigation"
            aria-label="Search navigation"
            aria-expanded={searchOpen}
            aria-controls="mobile-navigation-search-results"
            leadingIcon={<Search className="h-4 w-4" aria-hidden="true" />}
            className="bg-slate-50"
          />
          {searchOpen && query.trim() ? (
            <div
              id="mobile-navigation-search-results"
              className="absolute left-4 right-4 top-full z-50 mt-1 max-h-72 overflow-y-auto rounded-xl border border-slate-200 bg-white p-2 shadow-lg shadow-slate-900/10"
            >
              {searchResultsList}
            </div>
          ) : null}
        </div>
      ) : null}
    </header>
  );
}
