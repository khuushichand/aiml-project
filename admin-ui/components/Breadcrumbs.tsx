'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { buildBreadcrumbs } from '@/lib/navigation';

export function Breadcrumbs() {
  const pathname = usePathname() || '/';
  const items = buildBreadcrumbs(pathname);

  // Show breadcrumbs only on nested/detail routes.
  if (items.length < 3) {
    return null;
  }

  return (
    <nav aria-label="Breadcrumbs" className="text-sm text-muted-foreground" data-testid="breadcrumbs-nav">
      <ol className="flex flex-wrap items-center gap-2">
        {items.map((item, index) => (
          <li key={`${item.label}-${index}`} className="flex items-center gap-2">
            {item.current ? (
              <span aria-current="page" className="font-medium text-foreground">
                {item.label}
              </span>
            ) : item.href ? (
              <Link href={item.href} className="hover:text-foreground hover:underline">
                {item.label}
              </Link>
            ) : (
              <span>{item.label}</span>
            )}
            {index < items.length - 1 && <span aria-hidden="true">&gt;</span>}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export default Breadcrumbs;
