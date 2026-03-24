import React from "react"
import { Card, Space, Typography } from "antd"
import { useTranslation } from "react-i18next"

import { AudioInstallerPanel } from "@/components/Option/Setup/AudioInstallerPanel"

const { Text } = Typography

export const AdminAudioInstallerCard: React.FC = () => {
  const { t } = useTranslation(["settings"])

  return (
    <Card title={t("settings:audioInstaller.adminCardTitle", "Audio installer")} size="small">
      <Space orientation="vertical" size="small" className="w-full">
        <Text type="secondary">
          {t(
            "settings:audioInstaller.adminCardBody",
            "Install and verify server-side STT/TTS bundles for this connected server."
          )}
        </Text>
        <AudioInstallerPanel />
      </Space>
    </Card>
  )
}

export default AdminAudioInstallerCard
