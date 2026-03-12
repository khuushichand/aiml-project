import React from "react"
import { Button, Empty } from "antd"
import {
  CalendarClock,
  FileOutput,
  FileText,
  Newspaper,
  Play,
  Plus,
  Rss
} from "lucide-react"
import { useTranslation } from "react-i18next"

type EntityType = "feeds" | "monitors" | "activity" | "articles" | "reports" | "templates"

interface WatchlistsEmptyStateProps {
  entity: EntityType
  onPrimaryAction?: () => void
  onSecondaryAction?: () => void
  /** Override the primary CTA label */
  primaryLabel?: string
  /** Override the secondary CTA label */
  secondaryLabel?: string
  /** Contextual hint for cross-entity guidance */
  contextHint?: string
}

const entityConfig: Record<
  EntityType,
  {
    icon: React.ReactNode
    descriptionKey: string
    descriptionDefault: string
    primaryCtaKey: string
    primaryCtaDefault: string
    secondaryCtaKey?: string
    secondaryCtaDefault?: string
  }
> = {
  feeds: {
    icon: <Rss className="h-8 w-8 text-text-muted" />,
    descriptionKey: "watchlists:emptyState.feeds.description",
    descriptionDefault: "Feeds are the sources your monitors check for new content.",
    primaryCtaKey: "watchlists:emptyState.feeds.primaryCta",
    primaryCtaDefault: "Add your first feed",
    secondaryCtaKey: "watchlists:emptyState.feeds.secondaryCta",
    secondaryCtaDefault: "Import from OPML"
  },
  monitors: {
    icon: <CalendarClock className="h-8 w-8 text-text-muted" />,
    descriptionKey: "watchlists:emptyState.monitors.description",
    descriptionDefault:
      "Monitors run on a schedule to fetch and process content from your feeds.",
    primaryCtaKey: "watchlists:emptyState.monitors.primaryCta",
    primaryCtaDefault: "Create your first monitor"
  },
  activity: {
    icon: <Play className="h-8 w-8 text-text-muted" />,
    descriptionKey: "watchlists:emptyState.activity.description",
    descriptionDefault:
      "Activity shows the history of monitor runs. Set up a monitor to start seeing activity here.",
    primaryCtaKey: "watchlists:emptyState.activity.primaryCta",
    primaryCtaDefault: "Set up a monitor"
  },
  articles: {
    icon: <Newspaper className="h-8 w-8 text-text-muted" />,
    descriptionKey: "watchlists:emptyState.articles.description",
    descriptionDefault:
      "Articles are captured content from successful monitor runs, ready for review.",
    primaryCtaKey: "watchlists:emptyState.articles.primaryCta",
    primaryCtaDefault: "Set up a monitor to start capturing articles"
  },
  reports: {
    icon: <FileOutput className="h-8 w-8 text-text-muted" />,
    descriptionKey: "watchlists:emptyState.reports.description",
    descriptionDefault:
      "Reports are generated briefings from monitor runs using your templates.",
    primaryCtaKey: "watchlists:emptyState.reports.primaryCta",
    primaryCtaDefault: "Run a monitor to generate your first report"
  },
  templates: {
    icon: <FileText className="h-8 w-8 text-text-muted" />,
    descriptionKey: "watchlists:emptyState.templates.description",
    descriptionDefault:
      "Templates define the format and structure of your generated reports.",
    primaryCtaKey: "watchlists:emptyState.templates.primaryCta",
    primaryCtaDefault: "Create a template"
  }
}

export const WatchlistsEmptyState: React.FC<WatchlistsEmptyStateProps> = ({
  entity,
  onPrimaryAction,
  onSecondaryAction,
  primaryLabel,
  secondaryLabel,
  contextHint
}) => {
  const { t } = useTranslation(["watchlists"])
  const config = entityConfig[entity]

  return (
    <Empty
      image={config.icon}
      imageStyle={{ height: 48, display: "flex", justifyContent: "center", alignItems: "center" }}
      description={
        <div className="space-y-2">
          <p className="text-sm text-text-muted">
            {t(config.descriptionKey, config.descriptionDefault)}
          </p>
          {contextHint && (
            <p className="text-xs text-text-muted italic">{contextHint}</p>
          )}
        </div>
      }
      data-testid={`watchlists-empty-state-${entity}`}
    >
      <div className="flex flex-wrap justify-center gap-2">
        {onPrimaryAction && (
          <Button
            type="primary"
            icon={<Plus className="h-4 w-4" />}
            onClick={onPrimaryAction}
            data-testid={`watchlists-empty-state-${entity}-primary`}
          >
            {primaryLabel || t(config.primaryCtaKey, config.primaryCtaDefault)}
          </Button>
        )}
        {onSecondaryAction && config.secondaryCtaKey && (
          <Button
            onClick={onSecondaryAction}
            data-testid={`watchlists-empty-state-${entity}-secondary`}
          >
            {secondaryLabel ||
              t(config.secondaryCtaKey, config.secondaryCtaDefault || "")}
          </Button>
        )}
      </div>
    </Empty>
  )
}
