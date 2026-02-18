'use client';

import { useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Bug, Key, Wallet, Search } from 'lucide-react';
import { api } from '@/lib/api-client';
import { formatDateTime } from '@/lib/format';

type ApiKeyInfo = {
  user_id?: number;
  username?: string;
  email?: string;
  api_key_id?: number;
  name?: string;
  scopes?: string[];
  created_at?: string;
  expires_at?: string;
};

type BudgetSummary = {
  user_id?: number;
  total_budget?: number;
  used_budget?: number;
  remaining_budget?: number;
  budget_period?: string;
  reset_at?: string;
};

export default function DebugPage() {
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [apiKeyResult, setApiKeyResult] = useState<ApiKeyInfo | null>(null);
  const [apiKeyLoading, setApiKeyLoading] = useState(false);
  const [apiKeyError, setApiKeyError] = useState('');

  const [budgetKeyInput, setBudgetKeyInput] = useState('');
  const [budgetResult, setBudgetResult] = useState<BudgetSummary | null>(null);
  const [budgetLoading, setBudgetLoading] = useState(false);
  const [budgetError, setBudgetError] = useState('');

  const handleResolveApiKey = async () => {
    if (!apiKeyInput.trim()) {
      setApiKeyError('Please enter an API key');
      return;
    }

    try {
      setApiKeyLoading(true);
      setApiKeyError('');
      setApiKeyResult(null);
      const result = await api.debugResolveApiKey(apiKeyInput.trim());
      setApiKeyResult(result as ApiKeyInfo);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to resolve API key';
      setApiKeyError(message);
    } finally {
      setApiKeyLoading(false);
    }
  };

  const handleGetBudgetSummary = async () => {
    if (!budgetKeyInput.trim()) {
      setBudgetError('Please enter an API key');
      return;
    }

    try {
      setBudgetLoading(true);
      setBudgetError('');
      setBudgetResult(null);
      const result = await api.debugGetBudgetSummary(budgetKeyInput.trim());
      setBudgetResult(result as BudgetSummary);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to get budget summary';
      setBudgetError(message);
    } finally {
      setBudgetLoading(false);
    }
  };

  const formatDate = (dateStr?: string) => formatDateTime(dateStr, { fallback: '—' });

  const formatCurrency = (value?: number) => {
    if (value === undefined || value === null) return '—';
    return `$${value.toFixed(2)}`;
  };

  const budgetUsageRatio =
    budgetResult && budgetResult.total_budget !== undefined && budgetResult.used_budget !== undefined
      ? budgetResult.total_budget > 0
        ? budgetResult.used_budget / budgetResult.total_budget
        : 0
      : 0;

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
        <div className="p-4 lg:p-8">
          <div className="mb-8">
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Bug className="h-8 w-8" />
              Debug Tools
            </h1>
            <p className="text-muted-foreground">
              Admin-only diagnostic tools for troubleshooting authentication and billing issues
            </p>
          </div>

          <Alert className="mb-6 border-yellow-200 bg-yellow-50">
            <AlertDescription className="text-yellow-800">
              These tools are for debugging purposes only. Be careful with sensitive information.
            </AlertDescription>
          </Alert>

          <div className="grid gap-6 lg:grid-cols-2">
            {/* API Key Resolver */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Key className="h-5 w-5" />
                  API Key Resolver
                </CardTitle>
                <CardDescription>
                  Look up which user owns an API key and view key metadata
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="api-key-input">API Key</Label>
                  <div className="flex gap-2">
                    <Input
                      id="api-key-input"
                      type="password"
                      placeholder="tldw_..."
                      value={apiKeyInput}
                      onChange={(e) => setApiKeyInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleResolveApiKey()}
                    />
                    <Button onClick={handleResolveApiKey} disabled={apiKeyLoading} loading={apiKeyLoading} loadingText="Looking up...">
                      <Search className="mr-2 h-4 w-4" />
                      Resolve
                    </Button>
                  </div>
                </div>

                {apiKeyError && (
                  <Alert variant="destructive">
                    <AlertDescription>{apiKeyError}</AlertDescription>
                  </Alert>
                )}

                {apiKeyResult && (
                  <div className="rounded-lg border p-4 space-y-2">
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="text-muted-foreground">User ID:</div>
                      <div className="font-medium">{apiKeyResult.user_id ?? '—'}</div>

                      <div className="text-muted-foreground">Username:</div>
                      <div className="font-medium">{apiKeyResult.username ?? '—'}</div>

                      <div className="text-muted-foreground">Email:</div>
                      <div className="font-medium">{apiKeyResult.email ?? '—'}</div>

                      <div className="text-muted-foreground">Key ID:</div>
                      <div className="font-medium">{apiKeyResult.api_key_id ?? '—'}</div>

                      <div className="text-muted-foreground">Key Name:</div>
                      <div className="font-medium">{apiKeyResult.name ?? '—'}</div>

                      <div className="text-muted-foreground">Scopes:</div>
                      <div className="font-medium">
                        {apiKeyResult.scopes?.join(', ') || '—'}
                      </div>

                      <div className="text-muted-foreground">Created:</div>
                      <div className="font-medium">{formatDate(apiKeyResult.created_at)}</div>

                      <div className="text-muted-foreground">Expires:</div>
                      <div className="font-medium">{formatDate(apiKeyResult.expires_at)}</div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Budget Summary */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Wallet className="h-5 w-5" />
                  Budget Summary
                </CardTitle>
                <CardDescription>
                  View budget usage and limits for an API key
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="budget-key-input">API Key</Label>
                  <div className="flex gap-2">
                    <Input
                      id="budget-key-input"
                      type="password"
                      placeholder="tldw_..."
                      value={budgetKeyInput}
                      onChange={(e) => setBudgetKeyInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleGetBudgetSummary()}
                    />
                    <Button onClick={handleGetBudgetSummary} disabled={budgetLoading} loading={budgetLoading} loadingText="Loading...">
                      <Search className="mr-2 h-4 w-4" />
                      Check
                    </Button>
                  </div>
                </div>

                {budgetError && (
                  <Alert variant="destructive">
                    <AlertDescription>{budgetError}</AlertDescription>
                  </Alert>
                )}

                {budgetResult && (
                  <div className="rounded-lg border p-4 space-y-2">
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="text-muted-foreground">User ID:</div>
                      <div className="font-medium">{budgetResult.user_id ?? '—'}</div>

                      <div className="text-muted-foreground">Total Budget:</div>
                      <div className="font-medium">{formatCurrency(budgetResult.total_budget)}</div>

                      <div className="text-muted-foreground">Used:</div>
                      <div className="font-medium">{formatCurrency(budgetResult.used_budget)}</div>

                      <div className="text-muted-foreground">Remaining:</div>
                      <div className="font-medium">{formatCurrency(budgetResult.remaining_budget)}</div>

                      <div className="text-muted-foreground">Period:</div>
                      <div className="font-medium">{budgetResult.budget_period ?? '—'}</div>

                      <div className="text-muted-foreground">Resets At:</div>
                      <div className="font-medium">{formatDate(budgetResult.reset_at)}</div>
                    </div>

                    {budgetResult.total_budget !== undefined && budgetResult.used_budget !== undefined && (
                      <div className="mt-4">
                        <div className="flex justify-between text-xs text-muted-foreground mb-1">
                          <span>Usage</span>
                          <span>
                            {(budgetUsageRatio * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="h-2 bg-muted rounded-full overflow-hidden">
                          <div
                            className={`h-full transition-all ${
                              budgetUsageRatio > 0.9
                                ? 'bg-red-500'
                                : budgetUsageRatio > 0.7
                                  ? 'bg-yellow-500'
                                  : 'bg-green-500'
                            }`}
                            style={{
                              width: `${Math.min(100, budgetUsageRatio * 100)}%`,
                            }}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
