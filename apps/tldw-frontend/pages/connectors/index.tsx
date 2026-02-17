import { RoutePlaceholder } from '@web/components/navigation/RoutePlaceholder';

export default function ConnectorsRedirectPage() {
  return (
    <RoutePlaceholder
      title="Connectors Hub Is Coming Soon"
      description="Connector onboarding and management will live on this route. Use Settings for current server configuration."
      plannedPath="/connectors"
      primaryCtaHref="/settings"
      primaryCtaLabel="Open Settings"
    />
  );
}
