import React from "react"
import { Button, Tooltip } from "antd"
import { CircleHelp, ExternalLink } from "lucide-react"
import { useTranslation } from "react-i18next"
import { WATCHLISTS_HELP_DOCS, type WatchlistsHelpTopic } from "./help-docs"

interface WatchlistsHelpTooltipProps {
  topic: WatchlistsHelpTopic
  className?: string
  testId?: string
}

const TOPIC_FALLBACKS: Record<
  WatchlistsHelpTopic,
  { label: string; title: string; description: string }
> = {
  opml: {
    label: "OPML feed import",
    title: "Import many feeds quickly",
    description:
      "Use OPML when moving feed lists from another reader so setup takes minutes instead of manual entry."
  },
  cron: {
    label: "advanced schedule timing",
    title: "Choose preset schedules first",
    description:
      "Use preset timing for most monitors. Switch to custom cron only for uncommon timing windows."
  },
  ttl: {
    label: "retention window",
    title: "Control how long outputs stay available",
    description:
      "Set retention to keep briefings only as long as your review workflow needs before automatic cleanup."
  },
  jinja2: {
    label: "briefing templates",
    title: "Shape briefing format with templates",
    description:
      "Start with a preset template to control sections and tone, then customize only if you need advanced formatting."
  },
  claimClusters: {
    label: "claim tracking",
    title: "Track repeating claims across sources",
    description:
      "Subscribe to claim clusters to follow how the same claim evolves across feeds without manual tagging."
  }
}

export const WatchlistsHelpTooltip: React.FC<WatchlistsHelpTooltipProps> = ({
  topic,
  className,
  testId
}) => {
  const { t } = useTranslation(["watchlists"])
  const fallback = TOPIC_FALLBACKS[topic]
  const docsHref = WATCHLISTS_HELP_DOCS[topic]
  const topicLabel = t(
    `watchlists:help.topics.${topic}.label`,
    fallback.label
  )
  const title = t(
    `watchlists:help.topics.${topic}.title`,
    fallback.title
  )
  const description = t(
    `watchlists:help.topics.${topic}.description`,
    fallback.description
  )
  const ariaLabel = t("watchlists:help.openTopic", "Open help for {{topic}}", {
    topic: topicLabel
  })

  return (
    <Tooltip
      trigger={["hover", "focus"]}
      title={
        <div className="max-w-[280px] space-y-2">
          <div className="text-sm font-medium">{title}</div>
          <div className="text-xs text-text-muted">{description}</div>
          <a
            href={docsHref}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
          >
            {t("watchlists:help.learnMore", "Learn more")}
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      }
    >
      <Button
        type="text"
        size="small"
        icon={<CircleHelp className="h-3.5 w-3.5" />}
        aria-label={ariaLabel}
        data-testid={testId || `watchlists-help-${topic}`}
        className={`!h-6 !w-6 !p-0 text-text-muted ${className || ""}`}
      />
    </Tooltip>
  )
}
