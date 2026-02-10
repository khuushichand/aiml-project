import React, { useState } from 'react';

function isObject(val: unknown): val is Record<string, unknown> {
  return val !== null && typeof val === 'object' && !Array.isArray(val);
}

export function JsonTree({ data, level = 0 }: { data: unknown; level?: number }) {
  if (!isObject(data) && !Array.isArray(data)) {
    return <span className="font-mono text-sm">{String(data)}</span>;
  }
  const entries = Array.isArray(data) ? data.map((v, i) => [i, v] as const) : Object.entries(data);
  return (
    <div className="font-mono text-sm">
      {entries.map(([k, v]) => (
        <TreeRow key={String(k)} k={k as string | number} v={v} level={level} />
      ))}
    </div>
  );
}

function TreeRow({ k, v, level }: { k: string | number; v: unknown; level: number }) {
  const [open, setOpen] = useState(true);
  const complex = v !== null && typeof v === 'object';
  return (
    <div className="py-0.5">
      <div className="flex items-start">
        {complex ? (
          <button className="mr-1 mt-0.5 inline-flex h-4 w-4 items-center justify-center rounded border text-[10px] text-text-muted" onClick={() => setOpen(!open)} aria-label={open ? 'Collapse' : 'Expand'}>
            {open ? '-' : '+'}
          </button>
        ) : (
          <span className="mr-1 inline-block h-4 w-4" />
        )}
        <div>
          <span className="text-text-muted">{String(k)}:</span>{' '}
          {!complex && <span className="text-text">{formatValue(v)}</span>}
        </div>
      </div>
      {complex && open && (
        <div className="ml-6 border-l border-border pl-2">
          <JsonTree data={v} level={level + 1} />
        </div>
      )}
    </div>
  );
}

function formatValue(v: unknown) {
  if (v === null) return <span className="json-null">null</span>;
  if (typeof v === 'string') return <span className="json-string">"{v}"</span>;
  if (typeof v === 'number') return <span className="json-number">{v}</span>;
  if (typeof v === 'boolean') return <span className="json-boolean">{String(v)}</span>;
  return <span className="text-text">{String(v)}</span>;
}

export default JsonTree;
