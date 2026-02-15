import { RouteRedirect } from '@web/components/navigation/RouteRedirect';

export default function ConnectorJobsRedirectPage() {
  return (
    <RouteRedirect
      to="/settings"
      title="Connectors are managed in Settings"
      description="Connector jobs are available in the Settings page."
    />
  );
}
