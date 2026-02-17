import { RouteRedirect } from '@web/components/navigation/RouteRedirect';

export default function ChatSettingsRedirectPage() {
  return <RouteRedirect to="/settings/chat" preserveParams={false} />;
}
