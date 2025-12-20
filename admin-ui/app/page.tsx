'use client';

import { useEffect, useState } from 'react';
import Sidebar from '@/components/Sidebar';
import ProtectedRoute from '@/components/ProtectedRoute';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Building2, Users, Key, Cpu, HardDrive, Activity } from 'lucide-react';
import { api } from '@/lib/api-client';

interface DashboardStats {
  users: number;
  organizations: number;
  teams: number;
  apiKeys: number;
  providers: number;
  storageUsedMb: number;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats>({
    users: 0,
    organizations: 0,
    teams: 0,
    apiKeys: 0,
    providers: 0,
    storageUsedMb: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadStats = async () => {
      try {
        setLoading(true);
        setError(null);

        // Try to fetch dashboard stats - fall back to individual calls if needed
        try {
          const data = await api.getDashboardStats();
          setStats(data);
        } catch (statsError) {
          // Dashboard stats endpoint might not exist yet
          // Try to gather stats from individual endpoints
          const [usersData, orgsData, providersData] = await Promise.allSettled([
            api.getUsers(),
            api.getOrganizations(),
            api.getLLMProviders(),
          ]);

          setStats({
            users: usersData.status === 'fulfilled' ? (usersData.value?.length || 0) : 0,
            organizations: orgsData.status === 'fulfilled' ? (orgsData.value?.length || 0) : 0,
            teams: 0, // Would need org-specific calls
            apiKeys: 0,
            providers: providersData.status === 'fulfilled' ? (Object.keys(providersData.value || {}).length) : 0,
            storageUsedMb: 0,
          });
        }
      } catch (err) {
        console.error('Failed to load dashboard stats:', err);
        setError('Failed to load dashboard statistics');
      } finally {
        setLoading(false);
      }
    };

    loadStats();
  }, []);

  return (
    <ProtectedRoute>
      <div className="flex h-screen bg-background">
        <Sidebar />

        <main className="flex-1 overflow-y-auto">
          <div className="p-8">
            <div className="mb-8">
              <h1 className="text-3xl font-bold">Dashboard</h1>
              <p className="text-muted-foreground">Overview of your tldw_server instance</p>
            </div>

            {error && (
              <div className="mb-6 p-4 bg-destructive/10 border border-destructive/20 rounded-lg text-destructive">
                {error}
              </div>
            )}

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Users</CardTitle>
                  <Users className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {loading ? '...' : stats.users}
                  </div>
                  <p className="text-xs text-muted-foreground">Registered users</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Organizations</CardTitle>
                  <Building2 className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {loading ? '...' : stats.organizations}
                  </div>
                  <p className="text-xs text-muted-foreground">Active organizations</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Teams</CardTitle>
                  <Users className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {loading ? '...' : stats.teams}
                  </div>
                  <p className="text-xs text-muted-foreground">Total teams</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">API Keys</CardTitle>
                  <Key className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {loading ? '...' : stats.apiKeys}
                  </div>
                  <p className="text-xs text-muted-foreground">Active keys</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">LLM Providers</CardTitle>
                  <Cpu className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {loading ? '...' : stats.providers}
                  </div>
                  <p className="text-xs text-muted-foreground">Configured providers</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Storage Used</CardTitle>
                  <HardDrive className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {loading ? '...' : `${(stats.storageUsedMb / 1024).toFixed(1)} GB`}
                  </div>
                  <p className="text-xs text-muted-foreground">Total storage</p>
                </CardContent>
              </Card>
            </div>

            <div className="mt-8">
              <Card>
                <CardHeader>
                  <CardTitle>Quick Actions</CardTitle>
                  <CardDescription>Common administrative tasks</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                    <a
                      href="/users"
                      className="flex items-center gap-3 p-4 rounded-lg border hover:bg-muted transition-colors"
                    >
                      <Users className="h-5 w-5 text-primary" />
                      <div>
                        <p className="font-medium">Manage Users</p>
                        <p className="text-xs text-muted-foreground">Add, edit, or remove users</p>
                      </div>
                    </a>
                    <a
                      href="/api-keys"
                      className="flex items-center gap-3 p-4 rounded-lg border hover:bg-muted transition-colors"
                    >
                      <Key className="h-5 w-5 text-primary" />
                      <div>
                        <p className="font-medium">API Keys</p>
                        <p className="text-xs text-muted-foreground">Create or revoke keys</p>
                      </div>
                    </a>
                    <a
                      href="/providers"
                      className="flex items-center gap-3 p-4 rounded-lg border hover:bg-muted transition-colors"
                    >
                      <Cpu className="h-5 w-5 text-primary" />
                      <div>
                        <p className="font-medium">LLM Providers</p>
                        <p className="text-xs text-muted-foreground">Configure AI providers</p>
                      </div>
                    </a>
                    <a
                      href="/audit"
                      className="flex items-center gap-3 p-4 rounded-lg border hover:bg-muted transition-colors"
                    >
                      <Activity className="h-5 w-5 text-primary" />
                      <div>
                        <p className="font-medium">Audit Logs</p>
                        <p className="text-xs text-muted-foreground">View system activity</p>
                      </div>
                    </a>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </main>
      </div>
    </ProtectedRoute>
  );
}
