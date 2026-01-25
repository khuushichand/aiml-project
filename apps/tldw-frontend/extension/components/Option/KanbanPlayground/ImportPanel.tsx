import { useState, useCallback } from "react"
import { useMutation } from "@tanstack/react-query"
import { Upload, Button, message, Card, Alert, Descriptions } from "antd"
import type { UploadProps } from "antd"
import { Upload as UploadIcon, FileJson, CheckCircle } from "lucide-react"

import { importBoard } from "@/services/kanban"
import type { BoardImportResponse } from "@/types/kanban"

interface ImportPanelProps {
  onImported: (boardId: number) => void
}

interface TrelloPreview {
  name: string
  desc?: string
  lists: number
  cards: number
  labels: number
  checklists: number
  isTrello: boolean
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

export const ImportPanel = ({ onImported }: ImportPanelProps) => {
  const [fileData, setFileData] = useState<Record<string, unknown> | null>(null)
  const [preview, setPreview] = useState<TrelloPreview | null>(null)
  const [importResult, setImportResult] = useState<BoardImportResponse | null>(null)

  // Import mutation
  const importMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => importBoard(data),
    onSuccess: (result) => {
      message.success("Board imported successfully!")
      setImportResult(result)
      onImported(result.board.id)
    },
    onError: (err) => {
      message.error(
        `Import failed: ${err instanceof Error ? err.message : "Unknown error"}`
      )
    }
  })

  // Parse and preview the uploaded file
  const parseFile = useCallback((data: Record<string, unknown>): TrelloPreview | null => {
    const listsValue = data.lists
    const cardsValue = data.cards
    const labelsValue = data.labels
    const checklistsValue = data.checklists
    const formatValue = typeof data.format === "string" ? data.format : null
    const boardValue = isRecord(data.board) ? data.board : null

    const nameFromBoard =
      boardValue && typeof boardValue.name === "string" ? boardValue.name : undefined
    const descFromBoard =
      boardValue && typeof boardValue.description === "string"
        ? boardValue.description
        : undefined

    const name =
      typeof data.name === "string" ? data.name : nameFromBoard ?? "Imported Board"
    const desc =
      typeof data.desc === "string"
        ? data.desc
        : typeof data.description === "string"
          ? data.description
          : descFromBoard

    // Check if it's a Trello export
    const isTrello = Array.isArray(listsValue) && Array.isArray(cardsValue) && !formatValue

    // Check if it's our own format
    const isOwnFormat = formatValue === "tldw_kanban_v1"

    if (isTrello) {
      // Trello format
      return {
        name,
        desc,
        lists: Array.isArray(listsValue) ? listsValue.length : 0,
        cards: Array.isArray(cardsValue) ? cardsValue.length : 0,
        labels: Array.isArray(labelsValue) ? labelsValue.length : 0,
        checklists: Array.isArray(checklistsValue)
          ? checklistsValue.length
          : 0,
        isTrello: true
      }
    }

    if (isOwnFormat) {
      // Our format
      const lists = Array.isArray(listsValue) ? listsValue : []
      let cardCount = 0
      for (const list of lists) {
        if (!isRecord(list)) continue
        const listCards = list.cards
        if (Array.isArray(listCards)) {
          cardCount += listCards.length
        }
      }
      return {
        name,
        desc,
        lists: lists.length,
        cards: cardCount,
        labels: Array.isArray(labelsValue) ? labelsValue.length : 0,
        checklists: 0,
        isTrello: false
      }
    }

    // Unknown format - try to make sense of it
    return {
      name,
      desc,
      lists: Array.isArray(listsValue) ? listsValue.length : 0,
      cards: Array.isArray(cardsValue) ? cardsValue.length : 0,
      labels: Array.isArray(labelsValue) ? labelsValue.length : 0,
      checklists: 0,
      isTrello: false
    }
  }, [])

  const handleFileRead = useCallback(
    (file: File) => {
      const reader = new FileReader()
      reader.onload = (e) => {
        const content = e.target?.result as string
        try {
          const data = JSON.parse(content) as unknown
          if (!isRecord(data)) {
            message.error("Invalid JSON file")
            setFileData(null)
            setPreview(null)
            return
          }
          setFileData(data)
          const previewData = parseFile(data)
          if (previewData) {
            setPreview(previewData)
          } else {
            message.error("Could not parse file. Please ensure it's a valid Trello or tldw export.")
            setFileData(null)
            setPreview(null)
          }
        } catch {
          message.error("Invalid JSON file")
          setFileData(null)
          setPreview(null)
        }
      }
      reader.readAsText(file)
      return false // Prevent upload
    },
    [parseFile]
  )

  const uploadProps: UploadProps = {
    name: "file",
    accept: ".json",
    showUploadList: false,
    beforeUpload: handleFileRead
  }

  const handleImport = useCallback(() => {
    if (!fileData) return
    importMutation.mutate(fileData)
  }, [fileData, importMutation])

  const handleReset = useCallback(() => {
    setFileData(null)
    setPreview(null)
    setImportResult(null)
  }, [])

  return (
    <div className="import-panel max-w-2xl">
      <h3 className="text-lg font-medium mb-4">Import Board</h3>

      <Alert
        type="info"
        className="mb-4"
        message="Supported formats"
        description={
          <ul className="list-disc ml-4 mt-2">
            <li>
              <strong>Trello JSON export</strong> - Export your board from Trello
              (Menu → More → Print, export, and share → Export as JSON)
            </li>
            <li>
              <strong>tldw Kanban export</strong> - Our native format
            </li>
          </ul>
        }
      />

      {/* Import result */}
      {importResult && (
        <Card className="mb-4 border-green-300 bg-green-50 dark:bg-green-900/20">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle className="w-5 h-5 text-green-600" />
            <span className="font-medium text-green-700 dark:text-green-400">
              Import Successful!
            </span>
          </div>
          <Descriptions size="small" column={2}>
            <Descriptions.Item label="Board">
              {importResult.board.name}
            </Descriptions.Item>
            <Descriptions.Item label="Lists">
              {importResult.import_stats.lists_imported}
            </Descriptions.Item>
            <Descriptions.Item label="Cards">
              {importResult.import_stats.cards_imported}
            </Descriptions.Item>
            <Descriptions.Item label="Labels">
              {importResult.import_stats.labels_imported}
            </Descriptions.Item>
            <Descriptions.Item label="Checklists">
              {importResult.import_stats.checklists_imported}
            </Descriptions.Item>
            <Descriptions.Item label="Comments">
              {importResult.import_stats.comments_imported}
            </Descriptions.Item>
          </Descriptions>
          <Button className="mt-3" onClick={handleReset}>
            Import Another
          </Button>
        </Card>
      )}

      {/* File preview */}
      {preview && !importResult && (
        <Card className="mb-4">
          <div className="flex items-center gap-2 mb-3">
            <FileJson className="w-5 h-5 text-blue-500" />
            <span className="font-medium">File Preview</span>
            {preview.isTrello && (
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
                Trello Format
              </span>
            )}
          </div>

          <Descriptions size="small" column={2}>
            <Descriptions.Item label="Board Name">
              {preview.name}
            </Descriptions.Item>
            {preview.desc && (
              <Descriptions.Item label="Description">
                {preview.desc.slice(0, 100)}
                {preview.desc.length > 100 ? "..." : ""}
              </Descriptions.Item>
            )}
            <Descriptions.Item label="Lists">{preview.lists}</Descriptions.Item>
            <Descriptions.Item label="Cards">{preview.cards}</Descriptions.Item>
            <Descriptions.Item label="Labels">
              {preview.labels}
            </Descriptions.Item>
            <Descriptions.Item label="Checklists">
              {preview.checklists}
            </Descriptions.Item>
          </Descriptions>

          <div className="flex gap-2 mt-4">
            <Button
              type="primary"
              onClick={handleImport}
              loading={importMutation.isPending}
            >
              Import Board
            </Button>
            <Button onClick={handleReset}>Cancel</Button>
          </div>
        </Card>
      )}

      {/* Upload area */}
      {!preview && !importResult && (
        <Upload.Dragger {...uploadProps} className="mb-4">
          <p className="ant-upload-drag-icon">
            <UploadIcon className="w-12 h-12 mx-auto text-gray-400" />
          </p>
          <p className="ant-upload-text">
            Click or drag JSON file to this area
          </p>
          <p className="ant-upload-hint">
            Supports Trello exports and tldw Kanban exports
          </p>
        </Upload.Dragger>
      )}
    </div>
  )
}
