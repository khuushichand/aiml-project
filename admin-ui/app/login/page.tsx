'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm, FormProvider } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { loginWithPassword, loginWithApiKey } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { apiKeySchema, ApiKeyFormData, loginSchema, LoginFormData } from '@/lib/validations';
import {
  DEFAULT_POST_LOGIN_REDIRECT,
  getRedirectTargetFromSearch,
} from '@/lib/auth-navigation';

type AuthMode = 'password' | 'apikey';

const DEFAULT_AUTH_MODE: AuthMode =
  process.env.NEXT_PUBLIC_DEFAULT_AUTH_MODE === 'apikey' ? 'apikey' : 'password';
const APIKEY_MODE_VALUES = new Set(['apikey', 'api_key', 'api-key']);

export default function LoginPage() {
  const router = useRouter();
  const [authMode, setAuthMode] = useState<AuthMode>(DEFAULT_AUTH_MODE);
  const [isLoading, setIsLoading] = useState(false);
  const [serverError, setServerError] = useState('');
  const [redirectTarget, setRedirectTarget] = useState(DEFAULT_POST_LOGIN_REDIRECT);

  // Password login form
  const passwordForm = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      username: '',
      password: '',
    },
  });

  // API key login form
  const apiKeyForm = useForm<ApiKeyFormData>({
    resolver: zodResolver(apiKeySchema),
    defaultValues: {
      apiKey: '',
    },
  });

  const handlePasswordLogin = async (data: LoginFormData) => {
    setServerError('');
    setIsLoading(true);

    try {
      const result = await loginWithPassword(data.username, data.password);
      if (result) {
        router.push(redirectTarget);
      } else {
        setServerError('Invalid username or password.');
      }
    } catch (error) {
      console.error('Password authentication failed:', error);
      setServerError('Authentication failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleApiKeyLogin = async (data: ApiKeyFormData) => {
    setServerError('');
    setIsLoading(true);

    try {
      const result = await loginWithApiKey(data.apiKey);
      if (result) {
        router.push(redirectTarget);
      } else {
        setServerError('Invalid API key.');
      }
    } catch (error) {
      console.error('API key authentication failed:', error);
      setServerError('Authentication failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const clearServerError = () => {
    if (serverError) {
      setServerError('');
    }
  };

  const handleModeChange = (mode: AuthMode) => {
    setAuthMode(mode);
    setServerError('');
  };

  useEffect(() => {
    if (typeof window === 'undefined') return;
    document.body.dataset.loginHydrated = 'true';
    const params = new URLSearchParams(window.location.search);
    const modeParam = params.get('mode') || params.get('auth');
    if (modeParam && APIKEY_MODE_VALUES.has(modeParam.toLowerCase())) {
      setAuthMode('apikey');
    }
    setRedirectTarget(getRedirectTargetFromSearch(window.location.search));
  }, []);

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
          <div className="flex mb-6 border-b" role="tablist">
            <button
              type="button"
              id="password-tab"
              role="tab"
              aria-selected={authMode === 'password'}
              aria-controls="password-panel"
              onClick={() => handleModeChange('password')}
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
              id="apikey-tab"
              role="tab"
              aria-selected={authMode === 'apikey'}
              aria-controls="apikey-panel"
              onClick={() => handleModeChange('apikey')}
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
            <FormProvider {...passwordForm}>
              <form
                id="password-panel"
                role="tabpanel"
                aria-labelledby="password-tab"
                onSubmit={passwordForm.handleSubmit(handlePasswordLogin)}
                className="space-y-4"
              >
                <div className="space-y-2">
                  <Label htmlFor="username">Username or Email</Label>
                  <Input
                    id="username"
                    type="text"
                    placeholder="admin"
                    disabled={isLoading}
                    autoComplete="username"
                    {...passwordForm.register('username', {
                      onChange: clearServerError,
                    })}
                    className={passwordForm.formState.errors.username ? 'border-destructive' : ''}
                  />
                  {passwordForm.formState.errors.username && (
                    <p className="text-xs text-destructive">
                      {passwordForm.formState.errors.username.message}
                    </p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    placeholder="Enter your password"
                    disabled={isLoading}
                    autoComplete="current-password"
                    {...passwordForm.register('password', {
                      onChange: clearServerError,
                    })}
                    className={passwordForm.formState.errors.password ? 'border-destructive' : ''}
                  />
                  {passwordForm.formState.errors.password && (
                    <p className="text-xs text-destructive">
                      {passwordForm.formState.errors.password.message}
                    </p>
                  )}
                </div>

                {serverError && (
                  <Alert variant="destructive">
                    <AlertDescription>{serverError}</AlertDescription>
                  </Alert>
                )}

                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading ? 'Signing in...' : 'Sign In'}
                </Button>
              </form>
            </FormProvider>
          ) : (
            <FormProvider {...apiKeyForm}>
              <form
                id="apikey-panel"
                role="tabpanel"
                aria-labelledby="apikey-tab"
                onSubmit={apiKeyForm.handleSubmit(handleApiKeyLogin)}
                className="space-y-4"
              >
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
                    disabled={isLoading}
                    autoComplete="off"
                    {...apiKeyForm.register('apiKey', {
                      onChange: clearServerError,
                    })}
                    className={apiKeyForm.formState.errors.apiKey ? 'border-destructive' : ''}
                  />
                  {apiKeyForm.formState.errors.apiKey && (
                    <p className="text-xs text-destructive">
                      {apiKeyForm.formState.errors.apiKey.message}
                    </p>
                  )}
                </div>

                {serverError && (
                  <Alert variant="destructive">
                    <AlertDescription>{serverError}</AlertDescription>
                  </Alert>
                )}

                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading ? 'Validating...' : 'Connect with API Key'}
                </Button>
              </form>
            </FormProvider>
          )}

          <p className="mt-6 text-center text-xs text-muted-foreground">
            Manage users, organizations, API keys, and system configuration.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
