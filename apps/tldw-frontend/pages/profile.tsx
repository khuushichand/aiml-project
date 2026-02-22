import { RoutePlaceholder } from '@web/components/navigation/RoutePlaceholder';

export default function ProfileRedirectPage() {
  return (
    <RoutePlaceholder
      title="Profile Page Is Coming Soon"
      description="Dedicated profile management is not yet available on this route."
      plannedPath="/profile"
      primaryCtaHref="/settings"
      primaryCtaLabel="Open Settings"
    />
  );
}
