import OptionLayout from "@web/components/layout/WebLayout"
import LlamacppAdminPage from "@/components/Option/Admin/LlamacppAdminPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionAdminLlamacpp = () => {
  return (
    <RouteErrorBoundary routeId="admin-llamacpp" routeLabel="Llama.cpp Admin">
      <OptionLayout>
        <LlamacppAdminPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionAdminLlamacpp
