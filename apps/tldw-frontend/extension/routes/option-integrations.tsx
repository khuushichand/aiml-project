import OptionLayout from "@web/components/layout/WebLayout"
import { IntegrationManagementPage } from "@/components/Option/Integrations/IntegrationManagementPage"

const OptionIntegrations = () => {
  return (
    <OptionLayout>
      <IntegrationManagementPage scope="personal" />
    </OptionLayout>
  )
}

export default OptionIntegrations
