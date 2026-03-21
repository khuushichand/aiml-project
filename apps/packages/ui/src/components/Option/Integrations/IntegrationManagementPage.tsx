import React, { useMemo, useState } from "react"
import { Alert, Button, Card, Col, Row, Skeleton, Space, Tag, Typography, message } from "antd"
import { useQuery } from "@tanstack/react-query"
import {
  connectPersonalIntegration,
  deletePersonalIntegration,
  createWorkspaceTelegramPairingCode,
  getWorkspaceDiscordPolicy,
  getWorkspaceSlackPolicy,
  getWorkspaceTelegramBot,
  listPersonalIntegrations,
  listWorkspaceIntegrations,
  listWorkspaceTelegramLinkedActors,
  revokeWorkspaceTelegramLinkedActor,
  updatePersonalIntegration,
  updateWorkspaceDiscordPolicy,
  updateWorkspaceSlackPolicy,
  updateWorkspaceTelegramBot,
  type IntegrationConnection,
  type IntegrationProvider,
  type PersonalIntegrationProvider,
  type IntegrationScope
} from "@/services/integrations-control-plane"
import { IntegrationConnectionDrawer } from "./IntegrationConnectionDrawer"
import { IntegrationPolicyPanel } from "./IntegrationPolicyPanel"
import { IntegrationProviderCard } from "./IntegrationProviderCard"

type IntegrationManagementPageProps = {
  scope: IntegrationScope
}

const PERSONAL_PROVIDERS: IntegrationProvider[] = ["slack", "discord"]
const WORKSPACE_PROVIDERS: IntegrationProvider[] = ["slack", "discord", "telegram"]

const providerLabel: Record<IntegrationProvider, string> = {
  slack: "Slack",
  discord: "Discord",
  telegram: "Telegram"
}

const sortConnections = (connections: IntegrationConnection[]): IntegrationConnection[] =>
  [...connections].sort((left, right) => left.display_name.localeCompare(right.display_name))

const isPersonalProvider = (provider: IntegrationProvider): provider is PersonalIntegrationProvider =>
  provider === "slack" || provider === "discord"

const PERSONAL_INTEGRATIONS_UNSUPPORTED_TITLE = "Personal integrations unavailable"
const PERSONAL_INTEGRATIONS_UNSUPPORTED_DESCRIPTION =
  "This server does not expose the personal integrations control-plane yet."

const isUnsupportedOverviewError = (scope: IntegrationScope, error: unknown): boolean => {
  if (scope !== "personal" || !error || typeof error !== "object") {
    return false
  }
  const maybeError = error as {
    status?: number
    message?: string
  }
  if (maybeError.status === 404) {
    return true
  }
  return typeof maybeError.message === "string" && maybeError.message.includes("/api/v1/integrations/personal")
}

export const IntegrationManagementPage: React.FC<IntegrationManagementPageProps> = ({ scope }) => {
  const [selectedConnection, setSelectedConnection] = useState<IntegrationConnection | null>(null)
  const [activePersonalActionKey, setActivePersonalActionKey] = useState<string | null>(null)

  const overviewQuery = useQuery({
    queryKey: ["integrations", scope, "overview"],
    queryFn: scope === "workspace" ? listWorkspaceIntegrations : listPersonalIntegrations,
    retry: (failureCount, error) =>
      !isUnsupportedOverviewError(scope, error) && failureCount < 3
  })

  const slackPolicyQuery = useQuery({
    queryKey: ["integrations", "workspace", "slack-policy"],
    queryFn: getWorkspaceSlackPolicy,
    enabled: scope === "workspace"
  })

  const discordPolicyQuery = useQuery({
    queryKey: ["integrations", "workspace", "discord-policy"],
    queryFn: getWorkspaceDiscordPolicy,
    enabled: scope === "workspace"
  })

  const telegramBotQuery = useQuery({
    queryKey: ["integrations", "workspace", "telegram-bot"],
    queryFn: getWorkspaceTelegramBot,
    enabled: scope === "workspace"
  })

  const telegramActorsQuery = useQuery({
    queryKey: ["integrations", "workspace", "telegram-linked-actors"],
    queryFn: listWorkspaceTelegramLinkedActors,
    enabled: scope === "workspace"
  })

  const connectionsByProvider = useMemo(() => {
    const supportedProviders = scope === "workspace" ? WORKSPACE_PROVIDERS : PERSONAL_PROVIDERS
    const items = overviewQuery.data?.items ?? []
    return supportedProviders.map((provider) => ({
      provider,
      connections: sortConnections(
        items.filter(
          (item) => item.provider === provider && item.scope === scope
        )
      )
    }))
  }, [overviewQuery.data?.items, scope])

  const refreshAll = async () => {
    await Promise.all([
      overviewQuery.refetch(),
      scope === "workspace" ? slackPolicyQuery.refetch() : Promise.resolve(),
      scope === "workspace" ? discordPolicyQuery.refetch() : Promise.resolve(),
      scope === "workspace" ? telegramBotQuery.refetch() : Promise.resolve(),
      scope === "workspace" ? telegramActorsQuery.refetch() : Promise.resolve()
    ])
  }

  const isWorkspace = scope === "workspace"
  const slackPolicyError =
    slackPolicyQuery.isError && slackPolicyQuery.error instanceof Error
      ? slackPolicyQuery.error.message
      : slackPolicyQuery.isError
        ? "Slack policy could not be loaded."
        : null
  const discordPolicyError =
    discordPolicyQuery.isError && discordPolicyQuery.error instanceof Error
      ? discordPolicyQuery.error.message
      : discordPolicyQuery.isError
        ? "Discord policy could not be loaded."
        : null
  const telegramBotError =
    telegramBotQuery.isError && telegramBotQuery.error instanceof Error
      ? telegramBotQuery.error.message
      : telegramBotQuery.isError
        ? "Telegram bot settings could not be loaded."
        : null
  const telegramActorsError =
    telegramActorsQuery.isError && telegramActorsQuery.error instanceof Error
      ? telegramActorsQuery.error.message
      : telegramActorsQuery.isError
        ? "Telegram linked actors could not be loaded."
        : null
  const personalIntegrationsUnsupported = isUnsupportedOverviewError(scope, overviewQuery.error)

  const handlePersonalAction = async (connection: IntegrationConnection, action: string) => {
    if (scope !== "personal" || !isPersonalProvider(connection.provider)) {
      return
    }

    const actionKey = `${connection.id}:${action}`
    setActivePersonalActionKey(actionKey)

    try {
      if (action === "connect" || action === "reconnect") {
        const response = await connectPersonalIntegration(connection.provider)
        if (typeof window !== "undefined") {
          window.open(response.auth_url, "_blank", "noopener,noreferrer")
        }
        message.success(`${providerLabel[connection.provider]} authorization opened`)
      } else if (action === "enable" || action === "disable") {
        const updated = await updatePersonalIntegration(connection.provider, connection.id, {
          enabled: action === "enable"
        })
        setSelectedConnection(updated)
        message.success(`${providerLabel[connection.provider]} ${action}d`)
      } else if (action === "remove") {
        await deletePersonalIntegration(connection.provider, connection.id)
        setSelectedConnection(null)
        message.success(`${providerLabel[connection.provider]} removed`)
      } else {
        return
      }

      await overviewQuery.refetch()
    } catch (error: any) {
      message.error(error?.message || `Unable to ${action} ${providerLabel[connection.provider]}`)
    } finally {
      setActivePersonalActionKey(null)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-6">
      <Card>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
            <div>
              <Typography.Title level={2} style={{ marginBottom: 0 }}>
                {isWorkspace ? "Workspace integrations" : "Personal integrations"}
              </Typography.Title>
              <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                {isWorkspace
                  ? "Manage workspace policies, installation inventory, and Telegram bot settings."
                  : "Review your Slack and Discord connections from one shared surface."}
              </Typography.Paragraph>
            </div>
            <Button onClick={() => void refreshAll()}>Refresh all</Button>
          </div>
          <Space wrap>
            {connectionsByProvider.map((group) => (
              <Tag key={group.provider} color={group.connections.length > 0 ? "green" : "default"}>
                {providerLabel[group.provider]}: {group.connections.length}
              </Tag>
            ))}
          </Space>
        </div>
      </Card>

      {overviewQuery.isLoading && !overviewQuery.data ? <Skeleton active paragraph={{ rows: 6 }} /> : null}
      {personalIntegrationsUnsupported ? (
        <Alert
          type="info"
          showIcon
          title={PERSONAL_INTEGRATIONS_UNSUPPORTED_TITLE}
          description={PERSONAL_INTEGRATIONS_UNSUPPORTED_DESCRIPTION}
        />
      ) : null}
      {overviewQuery.isError && !overviewQuery.data && !personalIntegrationsUnsupported ? (
        <Alert
          type="error"
          showIcon
          title="Unable to load integrations"
          description={overviewQuery.error instanceof Error ? overviewQuery.error.message : "The integrations overview could not be loaded."}
        />
      ) : null}

      {!personalIntegrationsUnsupported ? (
        <Row gutter={[16, 16]}>
          {connectionsByProvider.map((group) => (
            <Col key={group.provider} xs={24} lg={8}>
              <IntegrationProviderCard
                title={providerLabel[group.provider]}
                provider={group.provider}
                scope={scope}
                connections={group.connections}
                onInspect={(connection) => setSelectedConnection(connection)}
              />
            </Col>
          ))}
        </Row>
      ) : null}

      {isWorkspace ? (
        <>
          {telegramActorsError ? (
            <Alert
              type="warning"
              showIcon
              title="Unable to load Telegram linked actors"
              description={telegramActorsError}
            />
          ) : null}

          <Typography.Title level={4} style={{ marginBottom: 0 }}>
            Workspace policy
          </Typography.Title>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={12}>
              <IntegrationPolicyPanel
                provider="slack"
                policy={slackPolicyQuery.data}
                errorMessage={slackPolicyError ? "Unable to load Slack policy" : undefined}
                loading={slackPolicyQuery.isLoading}
                onSave={updateWorkspaceSlackPolicy}
                onRefresh={() => void slackPolicyQuery.refetch()}
              />
            </Col>
            <Col xs={24} lg={12}>
              <IntegrationPolicyPanel
                provider="discord"
                policy={discordPolicyQuery.data}
                errorMessage={discordPolicyError ? "Unable to load Discord policy" : undefined}
                loading={discordPolicyQuery.isLoading}
                onSave={updateWorkspaceDiscordPolicy}
                onRefresh={() => void discordPolicyQuery.refetch()}
              />
            </Col>
          </Row>

          <Typography.Title level={4} style={{ marginBottom: 0 }}>
            Telegram workspace bot
          </Typography.Title>
          <IntegrationPolicyPanel
            provider="telegram"
            bot={telegramBotQuery.data}
            linkedActors={telegramActorsQuery.data?.items ?? []}
            errorMessage={telegramBotError ? "Unable to load Telegram bot settings" : undefined}
            loading={telegramBotQuery.isLoading || telegramActorsQuery.isLoading}
            onSave={updateWorkspaceTelegramBot}
            onGeneratePairingCode={createWorkspaceTelegramPairingCode}
            onRevokeActor={revokeWorkspaceTelegramLinkedActor}
            onRefresh={() => {
              void telegramBotQuery.refetch()
              void telegramActorsQuery.refetch()
            }}
          />
        </>
      ) : null}

      <IntegrationConnectionDrawer
        open={selectedConnection !== null}
        connection={selectedConnection}
        activeActionKey={activePersonalActionKey}
        onClose={() => setSelectedConnection(null)}
        onRunAction={scope === "personal" ? handlePersonalAction : undefined}
      />
    </div>
  )
}

export default IntegrationManagementPage
