'use client';

import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import type { AuditLog } from '@/types';
import { Activity, ArrowRight, FileText } from 'lucide-react';

type RecentActivityCardProps = {
  loading: boolean;
  recentActivity: AuditLog[];
  formatTimeAgo: (dateStr: string) => string;
};

export const RecentActivityCard = ({
  loading,
  recentActivity,
  formatTimeAgo,
}: RecentActivityCardProps) => (
  <Card>
    <CardHeader className="flex flex-row items-center justify-between">
      <div>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          Recent Activity
        </CardTitle>
        <CardDescription>Latest system events</CardDescription>
      </div>
      <Link href="/audit">
        <Button variant="ghost" size="sm">
          View All
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </Link>
    </CardHeader>
    <CardContent>
      {loading ? (
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-start gap-3">
              <Skeleton className="h-8 w-8 rounded-full" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            </div>
          ))}
        </div>
      ) : recentActivity.length === 0 ? (
        <p className="text-center text-muted-foreground py-8">No recent activity</p>
      ) : (
        <div className="space-y-4">
          {recentActivity.map((log) => (
            <div key={log.id} className="flex items-start gap-3">
              <div className="p-2 rounded-full bg-muted">
                <Activity className="h-3 w-3" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">
                  {log.action} on {log.resource}
                </p>
                <p className="text-xs text-muted-foreground">
                  User {log.user_id} • {formatTimeAgo(log.timestamp)}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </CardContent>
  </Card>
);
