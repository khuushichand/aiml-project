import React from "react"
import { Skeleton } from "antd"
import { useTranslation } from "react-i18next"
import ConnectFeatureBanner from "@/components/Common/ConnectFeatureBanner"
import { PageShell } from "@/components/Common/PageShell"
import { useServerOnline } from "@/hooks/useServerOnline"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import { SkillsManager } from "./Manager"

export const SkillsWorkspace: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  const isOnline = useServerOnline()
  const { capabilities, loading: capsLoading } = useServerCapabilities()
  const hasSkills = capabilities?.hasSkills

  if (!isOnline) {
    return (
      <ConnectFeatureBanner
        title={t("option:skillsEmpty.connectTitle", {
          defaultValue: "Connect to use Skills"
        })}
        description={t("option:skillsEmpty.connectDescription", {
          defaultValue:
            "To use Skills, connect to your tldw server so skill definitions can be stored and executed."
        })}
        examples={[
          t("option:skillsEmpty.connectExample1", {
            defaultValue: "Open Settings to add your server URL."
          })
        ]}
      />
    )
  }

  if (capsLoading) {
    return (
      <PageShell>
        <Skeleton active />
      </PageShell>
    )
  }

  if (!hasSkills) {
    return (
      <PageShell>
        <ConnectFeatureBanner
          title={t("option:skillsEmpty.unavailableTitle", {
            defaultValue: "Skills not available"
          })}
          description={t("option:skillsEmpty.unavailableDescription", {
            defaultValue:
              "The connected server does not support the Skills API. Update the server to enable this feature."
          })}
          examples={[]}
        />
      </PageShell>
    )
  }

  return (
    <PageShell>
      <SkillsManager />
    </PageShell>
  )
}
