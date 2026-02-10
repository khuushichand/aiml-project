import React, { ReactNode, UIEvent, useMemo, useRef, useState } from 'react';
import { cn } from '@web/lib/utils';

export interface VirtualizedColumn<T> {
  key: string;
  label: string;
  width?: number | string;
  className?: string;
  render?: (row: T, index: number) => ReactNode;
}

interface VirtualizedTableProps<T> {
  data: T[];
  columns: VirtualizedColumn<T>[];
  rowHeight?: number;
  height?: number;
  className?: string;
  emptyState?: ReactNode;
}

/**
 * Lightweight virtualized table with fixed-height rows.
 * Avoids extra dependencies while keeping large datasets responsive.
 */
export function VirtualizedTable<T>({
  data,
  columns,
  rowHeight = 44,
  height = 360,
  className,
  emptyState,
}: VirtualizedTableProps<T>) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);

  const totalHeight = useMemo(() => data.length * rowHeight, [data.length, rowHeight]);
  const visibleCount = useMemo(() => Math.ceil(height / rowHeight) + 4, [height, rowHeight]);
  const startIndex = Math.max(0, Math.floor(scrollTop / rowHeight));
  const endIndex = Math.min(data.length, startIndex + visibleCount);
  const offsetY = startIndex * rowHeight;
  const visibleRows = data.slice(startIndex, endIndex);

  const handleScroll = (event: UIEvent<HTMLDivElement>) => {
    setScrollTop(event.currentTarget.scrollTop);
  };

  const columnStyles = columns.map((column) => {
    if (column.width === undefined) {
      return { flex: 1 } as React.CSSProperties;
    }
    if (typeof column.width === 'number') {
      return { flex: '0 0 auto', width: `${column.width}px` } as React.CSSProperties;
    }
    return { flex: '0 0 auto', width: column.width } as React.CSSProperties;
  });

  if (!data.length && emptyState) {
    return <div className={cn('border border-dashed border-border rounded-md p-6 text-sm text-text-muted', className)}>{emptyState}</div>;
  }

  return (
    <div className={cn('border border-border rounded-md bg-surface', className)}>
      <div className="border-b border-border bg-bg px-3 py-2 text-xs font-semibold text-text-muted">
        <div className="flex gap-3">
          {columns.map((column, idx) => (
            <div
              key={column.key}
              className={cn('uppercase tracking-wide', column.className)}
              style={columnStyles[idx]}
            >
              {column.label}
            </div>
          ))}
        </div>
      </div>
      <div
        ref={containerRef}
        className="relative overflow-y-auto"
        style={{ maxHeight: height }}
        onScroll={handleScroll}
      >
        <div style={{ height: totalHeight }}>
          <div style={{ transform: `translateY(${offsetY}px)` }}>
            {visibleRows.map((row, index) => {
              const rowIndex = startIndex + index;
              return (
                <div
                  key={`${rowIndex}-${columns[0]?.key ?? 'col'}`}
                  className={cn('flex gap-3 px-3 py-2 text-sm text-text hover:bg-elevated transition-colors')}
                  style={{ height: rowHeight }}
                >
                  {columns.map((column, colIdx) => (
                    <div key={column.key} className={cn('truncate', column.className)} style={columnStyles[colIdx]}>
                      {column.render ? column.render(row, rowIndex) : String((row as Record<string, unknown>)[column.key] ?? '')}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

export default VirtualizedTable;
