import { FamilyGuardrailsWizard } from "~/components/Option/Settings/FamilyGuardrailsWizard"

import { SettingsRoute } from "./settings-route"

const OptionFamilyGuardrailsWizard = () => {
  return (
    <SettingsRoute>
      <div style={{ maxWidth: 1120, margin: "0 auto", padding: "16px 0 32px" }}>
        <FamilyGuardrailsWizard />
      </div>
    </SettingsRoute>
  )
}

export default OptionFamilyGuardrailsWizard
