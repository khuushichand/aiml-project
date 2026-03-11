import React from "react"
import { Button, Empty, Input, List, Modal, Space, Typography } from "antd"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import {
  tldwLlamaGrammars,
  type LlamaGrammarRecord
} from "@/services/tldw/TldwLlamaGrammars"

const { TextArea } = Input
const { Text } = Typography

type Props = {
  open: boolean
  onClose: () => void
  selectedGrammarId?: string | null
  onSelectGrammar?: (grammar: LlamaGrammarRecord) => void
}

export function LlamaGrammarLibraryModal({
  open,
  onClose,
  selectedGrammarId,
  onSelectGrammar
}: Props) {
  const { t } = useTranslation(["common", "sidepanel"])
  const queryClient = useQueryClient()
  const [editingId, setEditingId] = React.useState<string | null>(null)
  const [name, setName] = React.useState("")
  const [description, setDescription] = React.useState("")
  const [grammarText, setGrammarText] = React.useState("")

  const grammarsQuery = useQuery({
    queryKey: ["tldw:llama-grammars"],
    queryFn: () => tldwLlamaGrammars.list(),
    enabled: open
  })

  const invalidate = React.useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["tldw:llama-grammars"] })
  }, [queryClient])

  const createMutation = useMutation({
    mutationFn: tldwLlamaGrammars.create,
    onSuccess: async () => {
      await invalidate()
      setName("")
      setDescription("")
      setGrammarText("")
    }
  })

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      version,
      payload
    }: {
      id: string
      version?: number
      payload: {
        name: string
        description?: string
        grammar_text: string
      }
    }) => tldwLlamaGrammars.update(id, { version, ...payload }),
    onSuccess: async () => {
      await invalidate()
      setEditingId(null)
      setName("")
      setDescription("")
      setGrammarText("")
    }
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => tldwLlamaGrammars.remove(id),
    onSuccess: invalidate
  })

  const items = grammarsQuery.data?.items ?? []
  const editingRecord = items.find((item) => item.id === editingId) ?? null

  React.useEffect(() => {
    if (!open) return
    if (!editingRecord) return
    setName(editingRecord.name || "")
    setDescription(editingRecord.description || "")
    setGrammarText(editingRecord.grammar_text || "")
  }, [editingRecord, open])

  const isSaving = createMutation.isPending || updateMutation.isPending

  const handleSubmit = async () => {
    const payload = {
      name: name.trim(),
      description: description.trim() || undefined,
      grammar_text: grammarText
    }
    if (!payload.name || !payload.grammar_text.trim()) {
      return
    }
    if (editingRecord) {
      await updateMutation.mutateAsync({
        id: editingRecord.id,
        version: editingRecord.version,
        payload
      })
      return
    }
    await createMutation.mutateAsync(payload)
  }

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={900}
      title={t("sidepanel:llamaGrammarLibrary.title", "Saved grammars")}
    >
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Text strong>
              {t("sidepanel:llamaGrammarLibrary.saved", "Library")}
            </Text>
            <Button
              size="small"
              onClick={() => {
                setEditingId(null)
                setName("")
                setDescription("")
                setGrammarText("")
              }}
            >
              {t("common:new", "New")}
            </Button>
          </div>
          <div className="max-h-[28rem] overflow-y-auto rounded-lg border border-border/70 bg-surface/50">
            {items.length === 0 ? (
              <div className="p-6">
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description={t(
                    "sidepanel:llamaGrammarLibrary.empty",
                    "No saved grammars yet."
                  )}
                />
              </div>
            ) : (
              <List
                dataSource={items}
                renderItem={(item) => (
                  <List.Item
                    actions={[
                      <Button
                        key="use"
                        size="small"
                        type={item.id === selectedGrammarId ? "primary" : "default"}
                        onClick={() => onSelectGrammar?.(item)}
                      >
                        {t("common:use", "Use")}
                      </Button>,
                      <Button
                        key="edit"
                        size="small"
                        onClick={() => setEditingId(item.id)}
                      >
                        {t("common:edit", "Edit")}
                      </Button>,
                      <Button
                        key="delete"
                        size="small"
                        danger
                        onClick={() => void deleteMutation.mutateAsync(item.id)}
                      >
                        {t("common:delete", "Delete")}
                      </Button>
                    ]}
                  >
                    <List.Item.Meta
                      title={item.name}
                      description={item.description || item.id}
                    />
                  </List.Item>
                )}
              />
            )}
          </div>
        </div>

        <div className="space-y-3">
          <Text strong>
            {editingRecord
              ? t("sidepanel:llamaGrammarLibrary.edit", "Edit grammar")
              : t("sidepanel:llamaGrammarLibrary.create", "Create grammar")}
          </Text>
          <Input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={t("sidepanel:llamaGrammarLibrary.name", "Grammar name")}
          />
          <Input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder={t(
              "sidepanel:llamaGrammarLibrary.description",
              "Short description"
            )}
          />
          <TextArea
            value={grammarText}
            onChange={(event) => setGrammarText(event.target.value)}
            rows={16}
            className="font-mono text-xs"
            placeholder={'root ::= "ok"'}
          />
          <Space>
            <Button type="primary" loading={isSaving} onClick={() => void handleSubmit()}>
              {editingRecord
                ? t("common:save", "Save")
                : t("common:create", "Create")}
            </Button>
            {editingRecord ? (
              <Button
                onClick={() => {
                  setEditingId(null)
                  setName("")
                  setDescription("")
                  setGrammarText("")
                }}
              >
                {t("common:cancel", "Cancel")}
              </Button>
            ) : null}
          </Space>
        </div>
      </div>
    </Modal>
  )
}
