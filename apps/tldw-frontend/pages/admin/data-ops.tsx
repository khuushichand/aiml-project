import { RoutePlaceholder } from '@web/components/navigation/RoutePlaceholder';

export default function AdminDataOpsRedirectPage() {
  return (
    <RoutePlaceholder
      title="Data Operations Is Coming Soon"
      description="Bulk maintenance and data-ops tooling will be surfaced on this admin route."
      plannedPath="/admin/data-ops"
      primaryCtaHref="/admin/server"
      primaryCtaLabel="Open Server Admin"
    />
  );
}
