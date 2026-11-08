'use client';

import { useCallback, useState, type ReactNode } from 'react';
import { usePathname } from 'next/navigation';

import Header from '@/components/layout/Header';
import Modal from '@/components/common/Modal';
import Sidebar from '@/components/layout/Sidebar';
import { navigationGroups } from '@/components/layout/navigation';

interface DashboardLayoutProps {
  children: ReactNode;
}

function getNavigationState(pathname: string): { label: string; href: string } {
  for (const group of navigationGroups) {
    const item = group.items.find((candidate) => candidate.href === pathname);
    if (item) return { label: item.label, href: item.href };
  }
  return { label: 'Overview', href: '/dashboard' };
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const activePage = getNavigationState(pathname);

  const handleNavigate = useCallback((_label: string, _href: string) => {
    setMobileNavigationOpen(false);
  }, []);
  const closeMobileNavigation = useCallback(() => setMobileNavigationOpen(false), []);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="fixed inset-y-0 left-0 z-30 hidden lg:block">
        <Sidebar
          collapsed={collapsed}
          activeHref={activePage.href}
          onCollapse={() => setCollapsed((current) => !current)}
          onNavigate={handleNavigate}
        />
      </div>
      <div className={`min-h-screen transition-[padding] duration-200 ${collapsed ? 'lg:pl-[76px]' : 'lg:pl-[264px]'}`}>
        <Header
          pageLabel={activePage.label}
          onOpenMobileNavigation={() => setMobileNavigationOpen(true)}
          onNavigate={handleNavigate}
        />
        <main className="mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6 sm:py-8 xl:px-8">
          {children}
        </main>
      </div>
      <Modal
        open={mobileNavigationOpen}
        title="Navigation"
        onClose={closeMobileNavigation}
        hideHeader
        className="lg:hidden"
      >
        <Sidebar
          collapsed={false}
          activeHref={activePage.href}
          mobile
          onClose={closeMobileNavigation}
          onNavigate={handleNavigate}
        />
      </Modal>
    </div>
  );
}
