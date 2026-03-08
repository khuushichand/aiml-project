/* @vitest-environment jsdom */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LoginPage from '../page';

const routerPushMock = vi.hoisted(() => vi.fn());
const loginWithPasswordMock = vi.hoisted(() => vi.fn());
const loginWithApiKeyMock = vi.hoisted(() => vi.fn());
const completeMfaLoginMock = vi.hoisted(() => vi.fn());

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: routerPushMock,
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

vi.mock('@/lib/auth', () => ({
  loginWithPassword: loginWithPasswordMock,
  loginWithApiKey: loginWithApiKeyMock,
  completeMfaLogin: completeMfaLoginMock,
}));

vi.mock('@/components/ui/button', () => ({
  Button: ({
    children,
    loading,
    loadingText,
    ...props
  }: JSX.IntrinsicElements['button'] & { loading?: boolean; loadingText?: string }) => (
    <button type="button" {...props}>
      {loading ? loadingText || children : children}
    </button>
  ),
}));

describe('LoginPage', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    routerPushMock.mockReset();
    loginWithPasswordMock.mockReset();
    loginWithApiKeyMock.mockReset();
    completeMfaLoginMock.mockReset();
    window.history.replaceState({}, '', '/login');
  });

  it('hides API key login by default for enterprise admin deployments', () => {
    render(<LoginPage />);

    expect(screen.queryByRole('tab', { name: /api key/i })).not.toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /username & password/i })).toBeInTheDocument();
  });

  it('shows MFA challenge form instead of redirecting when password login requires MFA', async () => {
    loginWithPasswordMock.mockResolvedValue({
      status: 'mfa_required',
      sessionToken: 'mfa-session-token',
      expiresIn: 300,
      message: 'MFA required. Submit your TOTP or backup code.',
    });

    render(<LoginPage />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/username or email/i), 'admin');
    await user.type(screen.getByLabelText(/^password$/i), 'password123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText(/submit your totp or backup code/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/verification code/i)).toBeInTheDocument();
    expect(routerPushMock).not.toHaveBeenCalled();
  });
});
