import Link from 'next/link';
import { useRouter } from 'next/router';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/useAuth';
import { useIsAdmin } from '@/hooks/useIsAdmin';
import { toBool } from '@/lib/authz';

/**
 * Render the application's top navigation header with logo, primary links, and user controls.
 *
 * The rendered header includes a logo linking to home, a set of navigation links, and a user area that
 * shows the signed-in username or a Login link. The "Runs" navigation link is included only when the
 * NEXT_PUBLIC_ENABLE_RUNS_LINK environment flag is enabled and, if NEXT_PUBLIC_RUNS_REQUIRE_ADMIN is set,
 * only when the current user is determined to be an admin (checks multiple user fields and roles).
 *
 * @returns The header element containing the logo, navigation links, and user session controls.
 */
export function Header() {
  const router = useRouter();
  const { isAuthenticated, user, logout } = useAuth();

  const handleLogout = () => {
    logout();
  };

  const showRunsEnv = (process.env.NEXT_PUBLIC_ENABLE_RUNS_LINK ?? '1').toString().toLowerCase() !== '0' && (process.env.NEXT_PUBLIC_ENABLE_RUNS_LINK ?? '1').toString().toLowerCase() !== 'false';
  const runsRequireAdmin = toBool(process.env.NEXT_PUBLIC_RUNS_REQUIRE_ADMIN);
  const userIsAdmin = useIsAdmin();
  const showRuns = showRunsEnv && (!runsRequireAdmin || userIsAdmin);
  const navLinks = [
    { href: '/', label: 'Home' },
    { href: '/media', label: 'Media' },
    { href: '/items', label: 'Items' },
    { href: '/reading', label: 'Reading' },
    { href: '/watchlists', label: 'Watchlists' },
    ...(showRuns ? [{ href: '/admin/watchlists-runs', label: 'Runs' } as const] : []),
    { href: '/chat', label: 'Chat' },
    { href: '/search', label: 'Search' },
    { href: '/audio', label: 'Audio' },
    { href: '/evaluations', label: 'Evals' },
    { href: '/config', label: 'Config' },
  ];

  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <div className="flex items-center">
            <Link href="/" className="text-xl font-bold text-gray-900">
              TLDW
            </Link>
          </div>

          {/* Navigation */}
          <nav className="hidden md:flex md:space-x-8">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  'inline-flex items-center px-1 pt-1 text-sm font-medium',
                  router.pathname === link.href
                    ? 'border-b-2 border-blue-500 text-gray-900'
                    : 'text-gray-500 hover:text-gray-900'
                )}
              >
                {link.label}
              </Link>
            ))}
          </nav>

          {/* User menu */}
          <div className="flex items-center space-x-4">
            {isAuthenticated ? (
              <>
                <span className="text-sm text-gray-700">
                  {user?.username || 'User'}
                </span>
                {/* Only show logout when using session-based auth */}
                {!process.env.NEXT_PUBLIC_X_API_KEY && !process.env.NEXT_PUBLIC_API_BEARER && (
                  <button
                    onClick={handleLogout}
                    className="rounded-md bg-gray-100 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200"
                  >
                    Logout
                  </button>
                )}
              </>
            ) : (
              <Link
                href="/login"
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Login
              </Link>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
