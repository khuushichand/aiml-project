import type { WatchlistJob } from "@/types/watchlists"

export const JOB_DELETE_UNDO_WINDOW_SECONDS = 10

export const toJobRestoreId = (job: WatchlistJob): number => job.id
