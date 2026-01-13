import Link from 'next/link';
import { Layout } from '@/components/layout/Layout';
import { useIsAdmin } from '@/hooks/useIsAdmin';
import { toBool } from '@/lib/authz';

const adminCards = [
  {
    title: 'Data Ops',
    description: 'Backups, retention policies, and exports.',
    href: '/admin/data-ops',
    enabled: true,
  },
  {
    title: 'Maintenance',
    description: 'Operational controls and config snapshots.',
    href: '/admin/maintenance',
    enabled: true,
  },
  {
    title: 'Organizations',
    description: 'Review organization accounts and metadata.',
    href: '/admin/orgs',
    enabled: true,
  },
  {
    title: 'Watchlists Runs',
    description: 'Inspect watchlist runs and export data.',
    href: '/admin/watchlists-runs',
    enabled: true,
  },
  {
    title: 'Watchlists Items',
    description: 'Inspect watchlist run items.',
    href: '/admin/watchlists-items',
    enabled: true,
  },
];

export default function AdminIndexPage() {
  const isAdmin = useIsAdmin();
  const showRunsEnv =
    (process.env.NEXT_PUBLIC_ENABLE_RUNS_LINK ?? '1').toString().toLowerCase() !== '0' &&
    (process.env.NEXT_PUBLIC_ENABLE_RUNS_LINK ?? '1').toString().toLowerCase() !== 'false';
  const runsRequireAdmin = toBool(process.env.NEXT_PUBLIC_RUNS_REQUIRE_ADMIN);
  const showRuns = showRunsEnv && (!runsRequireAdmin || isAdmin);

  if (!isAdmin) {
    return (
      <Layout>
        <div className="mx-auto max-w-3xl">
          <h1 className="mb-4 text-2xl font-bold text-gray-900">Admin</h1>
          <div className="rounded-md border bg-white p-4 text-sm text-gray-700">
            Admin access required.
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-800">Admin</h1>
          <p className="mt-1 text-sm text-gray-600">Admin UI entry point for operational tools.</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {adminCards
            .filter((card) => (card.href === '/admin/watchlists-runs' ? showRuns : card.enabled))
            .map((card) => (
              <Link
                key={card.href}
                href={card.href}
                className="rounded-lg border border-gray-200 bg-white p-4 transition hover:border-blue-200 hover:shadow-sm"
              >
                <div className="text-lg font-semibold text-gray-800">{card.title}</div>
                <p className="mt-1 text-sm text-gray-600">{card.description}</p>
              </Link>
            ))}
        </div>
      </div>
    </Layout>
  );
}
