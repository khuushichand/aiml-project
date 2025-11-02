import React, { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

export interface HotkeyEntry {
  keys: string;
  description: string;
}

export function HotkeysOverlay({ entries, title = 'Keyboard Shortcuts' }: { entries: HotkeyEntry[]; title?: string }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const key = e.key;
      // '?' usually requires Shift + '/'
      if ((key === '?' || (key === '/' && e.shiftKey)) && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-xl rounded-md bg-white p-4 shadow-xl">
        <div className="mb-2 flex items-center justify-between">
          <div className="text-lg font-semibold text-gray-900">{title}</div>
          <button className="rounded bg-gray-100 px-2 py-1 text-sm text-gray-700 hover:bg-gray-200" onClick={() => setOpen(false)}>Close (Esc)</button>
        </div>
        <div className="max-h-[60vh] overflow-auto">
          <table className="w-full table-auto text-sm">
            <tbody>
              {entries.map((e, i) => (
                <tr key={i} className={cn('border-t', i === 0 && 'border-t-0')}>
                  <td className="px-2 py-2 font-mono text-xs text-gray-800 whitespace-nowrap">{e.keys}</td>
                  <td className="px-2 py-2 text-gray-700">{e.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-3 text-xs text-gray-500">Press '?' to toggle this dialog.</div>
      </div>
    </div>
  );
}

export default HotkeysOverlay;
