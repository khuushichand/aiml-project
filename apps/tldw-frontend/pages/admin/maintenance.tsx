import { RoutePlaceholder } from '@web/components/navigation/RoutePlaceholder';

export default function AdminMaintenanceRedirectPage() {
  return (
    <RoutePlaceholder
      title="Maintenance Console Is Coming Soon"
      description="Advanced maintenance tooling will be available on this route."
      plannedPath="/admin/maintenance"
      primaryCtaHref="/admin/server"
      primaryCtaLabel="Open Server Admin"
    />
  );
}
