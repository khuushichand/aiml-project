import OptionLayout from "@/components/Layouts/Layout"
import { IntegrationManagementPage } from "@/components/Option/Integrations/IntegrationManagementPage"

const OptionIntegrations = () => {
  return (
    <OptionLayout>
      <IntegrationManagementPage scope="personal" />
    </OptionLayout>
  )
}

export default OptionIntegrations
