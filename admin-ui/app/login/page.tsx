'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm, FormProvider } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { loginWithPassword, loginWithApiKey } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { loginSchema, LoginFormData } from '@/lib/validations';

// API key validation schema
const apiKeySchema = z.object({
  apiKey: z
    .string()
    .min(1, 'API key is required')
    .min(10, 'API key seems too short'),
});

type ApiKeyFormData = z.infer<typeof apiKeySchema>;

type AuthMode = 'password' | 'apikey';

export default function LoginPage() {
  const router = useRouter();
  const [authMode, setAuthMode] = useState<AuthMode>('password');
  const [isLoading, setIsLoading] = useState(false);
  const [serverError, setServerError] = useState('');

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
        router.push('/');
      } else {
        setServerError('Invalid username or password.');
      }
    } catch (err) {
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
        router.push('/');
      } else {
        setServerError('Invalid API key.');
      }
    } catch (err) {
      setServerError('Authentication failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleModeChange = (mode: AuthMode) => {
    setAuthMode(mode);
    setServerError('');
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
              <form onSubmit={passwordForm.handleSubmit(handlePasswordLogin)} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="username">Username or Email</Label>
                  <Input
                    id="username"
                    type="text"
                    placeholder="admin"
                    disabled={isLoading}
                    autoComplete="username"
                    {...passwordForm.register('username')}
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
                    {...passwordForm.register('password')}
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
              <form onSubmit={apiKeyForm.handleSubmit(handleApiKeyLogin)} className="space-y-4">
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
                    {...apiKeyForm.register('apiKey')}
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
