'use client';

import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { loginWithPassword, loginWithApiKey, isSingleUserMode } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';

type AuthMode = 'password' | 'apikey';

export default function LoginPage() {
  const router = useRouter();
  const [authMode, setAuthMode] = useState<AuthMode>('password');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  // Password login form state
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  // API key login form state
  const [apiKey, setApiKey] = useState('');

  const handlePasswordLogin = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const result = await loginWithPassword(username, password);
      if (result) {
        router.push('/');
      } else {
        setError('Invalid username or password.');
      }
    } catch (err) {
      setError('Authentication failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleApiKeyLogin = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const result = await loginWithApiKey(apiKey);
      if (result) {
        router.push('/');
      } else {
        setError('Invalid API key.');
      }
    } catch (err) {
      setError('Authentication failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>tldw Admin</CardTitle>
          <CardDescription>
            Sign in to access the tldw_server Admin Panel
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Auth mode tabs */}
          <div className="flex mb-6 border-b">
            <button
              type="button"
              onClick={() => setAuthMode('password')}
              className={`flex-1 pb-2 text-sm font-medium ${
                authMode === 'password'
                  ? 'border-b-2 border-primary text-primary'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Username & Password
            </button>
            <button
              type="button"
              onClick={() => setAuthMode('apikey')}
              className={`flex-1 pb-2 text-sm font-medium ${
                authMode === 'apikey'
                  ? 'border-b-2 border-primary text-primary'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              API Key
            </button>
          </div>

          {authMode === 'password' ? (
            <form onSubmit={handlePasswordLogin} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="username">Username or Email</Label>
                <Input
                  id="username"
                  type="text"
                  placeholder="admin"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  disabled={isLoading}
                  autoComplete="username"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  disabled={isLoading}
                  autoComplete="current-password"
                />
              </div>

              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? 'Signing in...' : 'Sign In'}
              </Button>
            </form>
          ) : (
            <form onSubmit={handleApiKeyLogin} className="space-y-4">
              <Alert className="mb-4">
                <AlertDescription>
                  Use an API key for single-user mode authentication. The key will be stored locally.
                </AlertDescription>
              </Alert>

              <div className="space-y-2">
                <Label htmlFor="apiKey">API Key</Label>
                <Input
                  id="apiKey"
                  type="password"
                  placeholder="Enter your API key"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  required
                  disabled={isLoading}
                  autoComplete="off"
                />
              </div>

              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? 'Validating...' : 'Connect with API Key'}
              </Button>
            </form>
          )}

          <p className="mt-6 text-center text-xs text-muted-foreground">
            Manage users, organizations, API keys, and system configuration.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
