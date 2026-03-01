import { Alert, Typography } from "antd"

import { SettingsRoute } from "./settings-route"

const { Paragraph, Title } = Typography

const OptionFamilyGuardrailsWizard = () => {
  return (
    <SettingsRoute>
      <div style={{ maxWidth: 960, margin: "0 auto", padding: "16px 0" }}>
        <Title level={4}>Family Guardrails Wizard</Title>
        <Paragraph type="secondary">
          Guided household setup for guardian relationships, templates, and acceptance tracking.
        </Paragraph>
        <Alert
          type="info"
          showIcon
          title="Wizard setup is in progress"
          description="Use Guardian & Self-Monitoring for advanced controls while the full wizard is being implemented."
        />
      </div>
    </SettingsRoute>
  )
}

export default OptionFamilyGuardrailsWizard
