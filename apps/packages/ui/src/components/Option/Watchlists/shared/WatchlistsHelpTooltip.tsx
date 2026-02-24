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
    label: "OPML imports",
    title: "What is OPML?",
    description:
      "OPML is a portable feed-list format. Import one file to add many RSS or site feeds at once."
  },
  cron: {
    label: "cron scheduling",
    title: "Set a reliable monitor schedule",
    description:
      "Start with presets for daily or weekday runs. Use cron only when you need exact custom timing."
  },
  ttl: {
    label: "retention TTL",
    title: "What retention TTL means",
    description:
      "TTL controls how long generated outputs are kept before they expire automatically."
  },
  jinja2: {
    label: "Jinja2 templates",
    title: "Customize briefing format",
    description:
      "Start from a preset report template, then edit sections to shape briefing tone, structure, and audio script text."
  },
  claimClusters: {
    label: "claim clusters",
    title: "What claim clusters are",
    description:
      "Claim clusters group similar claims across feeds so monitors can subscribe to related topic updates."
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
