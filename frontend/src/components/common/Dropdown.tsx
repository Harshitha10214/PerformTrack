'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';

interface DropdownProps {
  label: string;
  trigger: (props: {
    expanded: boolean;
    controls: string;
    onClick: () => void;
  }) => ReactNode;
  children: ReactNode;
  align?: 'left' | 'right';
  className?: string;
}

export default function Dropdown({
  label,
  trigger,
  children,
  align = 'right',
  className = '',
}: DropdownProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const panelId = `dropdown-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;

  useEffect(() => {
    if (!open) return;

    const closeOnOutsideClick = (event: PointerEvent) => {
      if (event.target instanceof Node && !rootRef.current?.contains(event.target)) {
        setOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };

    document.addEventListener('pointerdown', closeOnOutsideClick);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsideClick);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [open]);

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      {trigger({
        expanded: open,
        controls: panelId,
        onClick: () => setOpen((current) => !current),
      })}
      {open ? (
        <div
          id={panelId}
          role="region"
          aria-label={label}
          className={`absolute top-full z-50 mt-2 min-w-64 rounded-xl border border-slate-200 bg-white p-3 shadow-lg shadow-slate-900/10 ${
            align === 'right' ? 'right-0' : 'left-0'
          }`}
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}
