import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { AlertTriangle, CheckCircle, Clock, Eye, Plus, Trash2 } from 'lucide-react';
import type { Watchlist, WatchlistDraft } from '../types';

type WatchlistsPanelProps = {
  watchlists: Watchlist[];
  loading: boolean;
  showCreateWatchlist: boolean;
  setShowCreateWatchlist: (open: boolean) => void;
  newWatchlist: WatchlistDraft;
  setNewWatchlist: (next: WatchlistDraft) => void;
  onCreate: () => void;
  onDelete: (watchlist: Watchlist) => void;
  deletingWatchlistId?: string | null;
};

const getStatusIcon = (status?: string) => {
  switch (status) {
    case 'healthy':
    case 'active':
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case 'warning':
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    case 'critical':
    case 'error':
      return <AlertTriangle className="h-4 w-4 text-red-500" />;
    default:
      return <Clock className="h-4 w-4 text-muted-foreground" />;
  }
};

const formatTimestamp = (timestamp?: string) => {
  if (!timestamp) return '-';
  return new Date(timestamp).toLocaleString();
};

export default function WatchlistsPanel({
  watchlists,
  loading,
  showCreateWatchlist,
  setShowCreateWatchlist,
  newWatchlist,
  setNewWatchlist,
  onCreate,
  onDelete,
  deletingWatchlistId,
}: WatchlistsPanelProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Eye className="h-5 w-5" />
            Watchlists
          </CardTitle>
          <CardDescription>
            {watchlists.length} watchlist{watchlists.length !== 1 ? 's' : ''} configured
          </CardDescription>
        </div>
        <Dialog open={showCreateWatchlist} onOpenChange={setShowCreateWatchlist}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="mr-2 h-4 w-4" />
              Add
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create Watchlist</DialogTitle>
              <DialogDescription>
                Configure a new resource or metric to monitor
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="watchName">Name</Label>
                <Input
                  id="watchName"
                  placeholder="e.g., API Response Time"
                  value={newWatchlist.name}
                  onChange={(event) =>
                    setNewWatchlist({ ...newWatchlist, name: event.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="watchDescription">Description</Label>
                <Input
                  id="watchDescription"
                  placeholder="What this watchlist monitors..."
                  value={newWatchlist.description}
                  onChange={(event) =>
                    setNewWatchlist({
                      ...newWatchlist,
                      description: event.target.value,
                    })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="watchTarget">Target</Label>
                <Input
                  id="watchTarget"
                  placeholder="e.g., /api/v1/chat, cpu_usage"
                  value={newWatchlist.target}
                  onChange={(event) =>
                    setNewWatchlist({ ...newWatchlist, target: event.target.value })
                  }
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="watchType">Type</Label>
                  <select
                    id="watchType"
                    value={newWatchlist.type}
                    onChange={(event) =>
                      setNewWatchlist({ ...newWatchlist, type: event.target.value })
                    }
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    <option value="resource">Resource</option>
                    <option value="metric">Metric</option>
                    <option value="endpoint">Endpoint</option>
                    <option value="user">User Activity</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="watchThreshold">Threshold (%)</Label>
                  <Input
                    id="watchThreshold"
                    type="number"
                    min="0"
                    max="100"
                    value={newWatchlist.threshold}
                    onChange={(event) =>
                      setNewWatchlist({
                        ...newWatchlist,
                        threshold: parseInt(event.target.value, 10) || 80,
                      })
                    }
                  />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowCreateWatchlist(false)}>
                Cancel
              </Button>
              <Button onClick={onCreate}>Create Watchlist</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="text-center text-muted-foreground py-8">Loading...</div>
        ) : watchlists.length === 0 ? (
          <div className="text-center text-muted-foreground py-8">
            <Eye className="h-12 w-12 mx-auto mb-2 opacity-50" />
            <p>No watchlists configured</p>
            <p className="text-sm mt-1">Create one to start monitoring resources</p>
          </div>
        ) : (
          <div className="space-y-3">
            {watchlists.map((watchlist) => {
              const isDeleting = deletingWatchlistId === String(watchlist.id);
              return (
                <div
                  key={watchlist.id}
                  className="flex items-start justify-between p-3 rounded-lg border"
                >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    {getStatusIcon(watchlist.status)}
                    <span className="font-medium">{watchlist.name}</span>
                    <Badge variant="outline" className="text-xs">{watchlist.type}</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground truncate">
                    Target: <code className="bg-muted px-1 rounded">{watchlist.target}</code>
                  </p>
                  {watchlist.last_checked && (
                    <p className="text-xs text-muted-foreground">
                      Last checked: {formatTimestamp(watchlist.last_checked)}
                    </p>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onDelete(watchlist)}
                  title="Delete watchlist"
                  disabled={isDeleting}
                >
                  <Trash2 className="h-4 w-4 text-red-500" />
                </Button>
              </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
