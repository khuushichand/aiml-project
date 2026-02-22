import { RoutePlaceholder } from '@web/components/navigation/RoutePlaceholder';

export default function ConnectorJobsRedirectPage() {
  return (
    <RoutePlaceholder
      title="Connector Jobs Is Coming Soon"
      description="Connector job orchestration is planned for this route."
      plannedPath="/connectors/jobs"
      primaryCtaHref="/connectors"
      primaryCtaLabel="Open Connectors Hub"
    />
  );
}
