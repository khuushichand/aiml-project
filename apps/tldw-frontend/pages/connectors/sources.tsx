import { RoutePlaceholder } from '@web/components/navigation/RoutePlaceholder';

export default function ConnectorSourcesRedirectPage() {
  return (
    <RoutePlaceholder
      title="Connector Sources Is Coming Soon"
      description="Source-specific connector workflows are not yet available on this route."
      plannedPath="/connectors/sources"
      primaryCtaHref="/connectors"
      primaryCtaLabel="Open Connectors Hub"
    />
  );
}
