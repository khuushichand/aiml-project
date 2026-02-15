import { RouteRedirect } from '@web/components/navigation/RouteRedirect';

export default function ConnectorBrowseRedirectPage() {
  return (
    <RouteRedirect
      to="/settings"
      title="Connectors are managed in Settings"
      description="Connector browsing is available in the Settings page."
    />
  );
}
