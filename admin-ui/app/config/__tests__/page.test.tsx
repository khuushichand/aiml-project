/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import ConfigPage from '../page';
import { api } from '@/lib/api-client';

vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock('@/components/PermissionGuard', () => ({
  PermissionGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/ResponsiveLayout', () => ({
  ResponsiveLayout: ({ children }: { children: ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

vi.mock('@/lib/api-client', () => ({
  api: {
    getHealth: vi.fn(),
    getDashboardStats: vi.fn(),
    getFeatureFlags: vi.fn(),
    getLLMProviders: vi.fn(),
  },
}));

type ApiMock = {
  getHealth: ReturnType<typeof vi.fn>;
  getDashboardStats: ReturnType<typeof vi.fn>;
  getFeatureFlags: ReturnType<typeof vi.fn>;
  getLLMProviders: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

beforeEach(() => {
  apiMock.getHealth.mockResolvedValue({
    status: 'ok',
    auth_mode: 'multi_user',
    version: '0.1.0',
    uptime_seconds: 7200,
    python_version: '3.12.2',
    os: 'linux',
    deployment_mode: 'production',
    timestamp: '2026-02-17T19:00:00Z',
    checks: {
      database: { status: 'healthy', backend: 'postgresql' },
      metrics: { status: 'healthy' },
      rag: { status: 'healthy' },
      tts: { status: 'healthy' },
      stt: { status: 'healthy' },
      mcp: { status: 'healthy' },
      chacha_notes: { status: 'healthy', db_path: 'Databases/user_databases' },
    },
  });

  apiMock.getDashboardStats.mockResolvedValue({
    storage: {
      total_used_mb: 256,
      total_quota_mb: 1024,
    },
    sessions: {
      active: 14,
      unique_users: 9,
    },
  });

  apiMock.getFeatureFlags.mockResolvedValue({
    items: [
      {
        key: 'require_mfa',
        scope: 'global',
        enabled: true,
        rollout_percent: 100,
        target_user_ids: [],
      },
      {
        key: 'release_candidate_ui',
        scope: 'global',
        enabled: false,
        rollout_percent: 50,
        target_user_ids: [11, 22],
      },
    ],
    total: 2,
  });

  apiMock.getLLMProviders.mockResolvedValue({
    providers: [
      {
        name: 'openai',
        enabled: true,
        models: ['gpt-4o'],
      },
      {
        name: 'anthropic',
        enabled: false,
        models: ['claude-3-5-sonnet', 'claude-3-5-haiku'],
      },
    ],
    default_provider: 'openai',
    total_configured: 2,
  });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('ConfigPage system overview', () => {
  it('renders all overview sections with endpoint data', async () => {
    render(<ConfigPage />);

    expect(await screen.findByRole('heading', { name: 'System Configuration Overview' })).toBeInTheDocument();

    await waitFor(() => {
      expect(apiMock.getHealth).toHaveBeenCalled();
      expect(apiMock.getDashboardStats).toHaveBeenCalled();
      expect(apiMock.getFeatureFlags).toHaveBeenCalled();
      expect(apiMock.getLLMProviders).toHaveBeenCalled();
    });

    expect(screen.getByRole('heading', { name: 'Authentication' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Storage' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Features' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Providers' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Services' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Server' })).toBeInTheDocument();

    expect(screen.getByText('multi_user')).toBeInTheDocument();
    expect(screen.getByText('14 active / 9 unique users')).toBeInTheDocument();
    expect(screen.getByText('1 enabled of 2 total')).toBeInTheDocument();
    expect(screen.getByText('1 enabled of 2 configured')).toBeInTheDocument();
    expect(screen.getByText('Openai (1 model)')).toBeInTheDocument();
    expect(screen.getByText('Anthropic (2 models)')).toBeInTheDocument();
    expect(screen.getByText('postgresql')).toBeInTheDocument();
    expect(screen.getByText('256 MB / 1,024 MB (25%)')).toBeInTheDocument();

    expect(screen.getByRole('link', { name: 'Manage feature flags' }).getAttribute('href')).toBe('/flags');
    expect(screen.getByRole('link', { name: 'Manage providers' }).getAttribute('href')).toBe('/providers');
    expect(screen.getByRole('link', { name: 'Open monitoring' }).getAttribute('href')).toBe('/monitoring');
  });

  it('renders fallback values when endpoints are missing or unavailable', async () => {
    apiMock.getHealth.mockRejectedValueOnce(new Error('health down'));
    apiMock.getDashboardStats.mockResolvedValueOnce({});
    apiMock.getFeatureFlags.mockResolvedValueOnce({ items: [], total: 0 });
    apiMock.getLLMProviders.mockResolvedValueOnce({ providers: [], total_configured: 0 });

    render(<ConfigPage />);

    expect(await screen.findByText('Some configuration data could not be loaded:')).toBeInTheDocument();
    expect(screen.getByText('Health endpoint unavailable: health down')).toBeInTheDocument();
    expect(screen.getByText('No feature flags configured')).toBeInTheDocument();
    expect(screen.getByText('No providers configured')).toBeInTheDocument();
    expect(screen.getByText('No providers configured.')).toBeInTheDocument();
    expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0);
  });
});
