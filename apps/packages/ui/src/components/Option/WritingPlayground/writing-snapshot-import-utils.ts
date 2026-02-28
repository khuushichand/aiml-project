export type SnapshotImportMode = "merge" | "replace"

export type SnapshotReplaceConfirmLabels = {
  title: string
  body: string
  action: string
  cancel: string
}

export type SnapshotImportAction =
  | {
      type: "open-picker"
      mode: "merge"
    }
  | {
      type: "confirm-replace"
      mode: "replace"
      title: string
      content: string
      okText: string
      cancelText: string
      danger: true
    }

export const resolveSnapshotImportAction = (
  mode: SnapshotImportMode,
  labels: SnapshotReplaceConfirmLabels
): SnapshotImportAction => {
  if (mode === "replace") {
    return {
      type: "confirm-replace",
      mode: "replace",
      title: labels.title,
      content: labels.body,
      okText: labels.action,
      cancelText: labels.cancel,
      danger: true
    }
  }
  return {
    type: "open-picker",
    mode: "merge"
  }
}
