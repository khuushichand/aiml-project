import { RouteRedirect } from "@web/components/navigation/RouteRedirect"

export default function MediaItemRedirectPage() {
  return <RouteRedirect to="/media" preserveParams={false} />
}
