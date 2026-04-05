import { useQuery } from "@tanstack/react-query"
import { Empty, Modal, Timeline, Tag, Typography } from "antd"
import { useWritingPlaygroundStore } from "@/store/writing-playground"
import { listManuscriptPlotLines } from "@/services/writing-playground"

type EventLineModalProps = {
  open: boolean
  onClose: () => void
}

const EVENT_TYPE_COLORS: Record<string, string> = {
  setup: "blue",
  conflict: "red",
  action: "orange",
  emotional: "purple",
  plot: "gray",
  resolution: "green",
}

export function EventLineModal({ open, onClose }: EventLineModalProps) {
  const { activeProjectId } = useWritingPlaygroundStore()

  const { data: plotLinesData } = useQuery({
    queryKey: ["manuscript-plot-lines", activeProjectId],
    queryFn: () => listManuscriptPlotLines(activeProjectId!),
    enabled: open && !!activeProjectId,
  })

  const plotLines = (plotLinesData as any)?.plot_lines || []

  const allEvents = plotLines.flatMap((pl: any) =>
    (pl.events || []).map((ev: any) => ({
      ...ev,
      plotLineTitle: pl.title,
    }))
  )

  // Sort events by sequence or created_at if available
  const sortedEvents = [...allEvents].sort((a: any, b: any) => {
    if (a.sequence != null && b.sequence != null) return a.sequence - b.sequence
    const aTime = a.created_at || ""
    const bTime = b.created_at || ""
    return aTime.localeCompare(bTime)
  })

  return (
    <Modal title="Event Line" open={open} onCancel={onClose} footer={null} width={600}>
      {!activeProjectId ? (
        <Empty description="Select a project first" />
      ) : sortedEvents.length === 0 ? (
        <Empty description="No plot events yet. Add events to your plot lines to see the timeline." />
      ) : (
        <div className="max-h-[500px] overflow-y-auto pr-2">
          <Timeline
            items={sortedEvents.map((ev: any, idx: number) => ({
              key: ev.id || idx,
              color: EVENT_TYPE_COLORS[ev.event_type] || "gray",
              children: (
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <Typography.Text strong>{ev.title || ev.description || "Untitled event"}</Typography.Text>
                    {ev.event_type && (
                      <Tag color={EVENT_TYPE_COLORS[ev.event_type] || "default"} className="!text-[10px]">
                        {ev.event_type}
                      </Tag>
                    )}
                  </div>
                  {ev.description && ev.title && (
                    <Typography.Text type="secondary" className="text-xs">
                      {ev.description}
                    </Typography.Text>
                  )}
                  <Typography.Text type="secondary" className="text-[10px]">
                    Plot line: {ev.plotLineTitle}
                  </Typography.Text>
                </div>
              ),
            }))}
          />
        </div>
      )}
    </Modal>
  )
}

export default EventLineModal
