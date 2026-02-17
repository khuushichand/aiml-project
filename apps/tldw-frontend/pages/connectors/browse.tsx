import { RoutePlaceholder } from '@web/components/navigation/RoutePlaceholder';

export default function ConnectorBrowseRedirectPage() {
  return (
    <RoutePlaceholder
      title="Connector Browse Is Coming Soon"
      description="Connector catalog browsing is planned for this route."
      plannedPath="/connectors/browse"
      primaryCtaHref="/connectors"
      primaryCtaLabel="Open Connectors Hub"
    />
  );
}
