import { RouteRedirect } from '@web/components/navigation/RouteRedirect';

export default function ConnectorsRedirectPage() {
  return (
    <RouteRedirect
      to="/settings"
      title="Connectors are managed in Settings"
      description="Connector configuration is available in the Settings page."
    />
  );
}
