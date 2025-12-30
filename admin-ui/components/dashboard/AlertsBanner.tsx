'use client';

import Link from 'next/link';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertTriangle } from 'lucide-react';

type AlertsBannerProps = {
  count: number;
};

export const AlertsBanner = ({ count }: AlertsBannerProps) => {
  if (count <= 0) return null;

  return (
    <Alert className="mb-6 bg-yellow-50 border-yellow-200">
      <AlertTriangle className="h-4 w-4 text-yellow-600" />
      <AlertDescription className="text-yellow-800">
        {count} active alert{count !== 1 ? 's' : ''} require attention.{' '}
        <Link href="/monitoring" className="underline font-medium">View all</Link>
      </AlertDescription>
    </Alert>
  );
};
