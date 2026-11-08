import type { InputHTMLAttributes, ReactNode } from 'react';

interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
  leadingIcon?: ReactNode;
}

export default function TextInput({ leadingIcon, className = '', ...props }: TextInputProps) {
  return (
    <span className="relative block">
      {leadingIcon ? (
        <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-400">
          {leadingIcon}
        </span>
      ) : null}
      <input
        className={`h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800 shadow-sm outline-none transition placeholder:text-slate-400 hover:border-slate-300 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 disabled:bg-slate-50 ${leadingIcon ? 'pl-9' : ''} ${className}`}
        {...props}
      />
    </span>
  );
}
