import { RoutePlaceholder } from '@web/components/navigation/RoutePlaceholder';

export default function ConfigRedirectPage() {
  return (
    <RoutePlaceholder
      title="Configuration Center Is Coming Soon"
      description="Unified configuration workflows are planned for this route."
      plannedPath="/config"
      primaryCtaHref="/settings"
      primaryCtaLabel="Open Settings"
    />
  );
}
