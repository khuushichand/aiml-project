import { RoutePlaceholder } from '@web/components/navigation/RoutePlaceholder';

export default function AdminOrgsRedirectPage() {
  return (
    <RoutePlaceholder
      title="Organization Management Is Coming Soon"
      description="Organization and tenant administration workflows are planned for this route."
      plannedPath="/admin/orgs"
      primaryCtaHref="/admin/server"
      primaryCtaLabel="Open Server Admin"
    />
  );
}
