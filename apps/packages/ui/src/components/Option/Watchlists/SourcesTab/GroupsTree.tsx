import React, { useMemo, useState } from "react"
import { Button, Empty, Form, Input, Modal, Popconfirm, Select, Skeleton, Tooltip, Tree, message } from "antd"
import { FolderPlus, Pencil, Trash2 } from "lucide-react"
import { useTranslation } from "react-i18next"
import {
  createWatchlistGroup,
  deleteWatchlistGroup,
  updateWatchlistGroup
} from "@/services/watchlists"
import type { WatchlistGroup } from "@/types/watchlists"
import {
  collectDescendantGroupIds,
  isGroupParentAssignmentCyclic
} from "./group-hierarchy"
import { trackWatchlistsPreventionTelemetry } from "@/utils/watchlists-prevention-telemetry"

interface GroupsTreeProps {
  groups: WatchlistGroup[]
  selectedGroupId: number | null
  loading: boolean
  onSelect: (groupId: number | null) => void
  onRefresh: () => void
}

type TreeNode = {
  title: string
  key: string
  children?: TreeNode[]
}

const buildTree = (groups: WatchlistGroup[]): TreeNode[] => {
  const nodes = new Map<number, TreeNode>()
  const roots: TreeNode[] = []

  groups.forEach((group) => {
    nodes.set(group.id, { title: group.name, key: String(group.id), children: [] })
  })

  groups.forEach((group) => {
    const node = nodes.get(group.id)
    if (!node) return
    if (group.parent_group_id && nodes.has(group.parent_group_id)) {
      const parent = nodes.get(group.parent_group_id)
      if (parent) parent.children?.push(node)
    } else {
      roots.push(node)
    }
  })

  return roots
}

export const GroupsTree: React.FC<GroupsTreeProps> = ({
  groups,
  selectedGroupId,
  loading,
  onSelect,
  onRefresh
}) => {
  const { t } = useTranslation(["watchlists", "common"])
  const [editorOpen, setEditorOpen] = useState(false)
  const [editorMode, setEditorMode] = useState<"create" | "edit">("create")
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()

  const treeData = useMemo(() => buildTree(groups), [groups])
  const selectedGroup = useMemo(
    () => groups.find((group) => group.id === selectedGroupId) ?? null,
    [groups, selectedGroupId]
  )
  const blockedParentIds = useMemo(() => {
    if (editorMode !== "edit" || !selectedGroup) return new Set<number>()
    const blocked = collectDescendantGroupIds(groups, selectedGroup.id)
    blocked.add(selectedGroup.id)
    return blocked
  }, [editorMode, groups, selectedGroup])
  const parentOptions = useMemo(
    () =>
      groups
        .filter((group) => !blockedParentIds.has(group.id))
        .map((group) => ({
          label: group.name,
          value: group.id
        })),
    [blockedParentIds, groups]
  )

  const openCreateEditor = () => {
    setEditorMode("create")
    form.resetFields()
    setEditorOpen(true)
  }

  const openEditEditor = () => {
    if (!selectedGroup) return
    setEditorMode("edit")
    form.setFieldsValue({
      name: selectedGroup.name,
      description: selectedGroup.description || undefined,
      parent_group_id: selectedGroup.parent_group_id || undefined
    })
    setEditorOpen(true)
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)

      if (editorMode === "edit" && selectedGroup) {
        const nextParentGroupId =
          typeof values.parent_group_id === "number" ? values.parent_group_id : undefined
        if (
          isGroupParentAssignmentCyclic(
            groups,
            selectedGroup.id,
            nextParentGroupId
          )
        ) {
          void trackWatchlistsPreventionTelemetry({
            type: "watchlists_validation_blocked",
            surface: "groups_tree",
            rule: "group_cycle_parent",
            remediation: "choose_non_descendant_parent"
          })
          message.error(
            t(
              "watchlists:groups.parentCycleError",
              "Cannot move a group into itself or one of its descendants."
            )
          )
          return
        }
        await updateWatchlistGroup(selectedGroup.id, {
          name: values.name,
          description: values.description || undefined,
          parent_group_id: nextParentGroupId
        })
        message.success(t("watchlists:groups.updated", "Group updated"))
      } else {
        await createWatchlistGroup({
          name: values.name,
          description: values.description || undefined,
          parent_group_id: values.parent_group_id || undefined
        })
        message.success(t("watchlists:groups.created", "Group created"))
      }

      setEditorOpen(false)
      form.resetFields()
      onRefresh()
    } catch (err) {
      if (err && typeof err === "object" && "errorFields" in err) return
      if (editorMode === "edit") {
        console.error("Failed to update group:", err)
        message.error(t("watchlists:groups.updateError", "Failed to update group"))
      } else {
        console.error("Failed to create group:", err)
        message.error(t("watchlists:groups.createError", "Failed to create group"))
      }
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!selectedGroupId) return
    try {
      await deleteWatchlistGroup(selectedGroupId)
      message.success(t("watchlists:groups.deleted", "Group deleted"))
      onSelect(null)
      onRefresh()
    } catch (err) {
      console.error("Failed to delete group:", err)
      message.error(t("watchlists:groups.deleteError", "Failed to delete group"))
    }
  }

  return (
    <div className="rounded-lg border border-border p-3 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">
          {t("watchlists:groups.title", "Groups")}
        </div>
        <Tooltip title={t("watchlists:groups.create", "Create Group")}>
          <Button
            size="small"
            type="text"
            aria-label={t("watchlists:groups.create", "Create Group")}
            icon={<FolderPlus className="h-4 w-4" />}
            onClick={openCreateEditor}
          />
        </Tooltip>
      </div>

      <div className="flex items-center justify-between gap-2">
        <Button
          size="small"
          onClick={() => onSelect(null)}
          disabled={!selectedGroupId}
        >
          {t("watchlists:groups.all", "All Sources")}
        </Button>
        <div className="flex items-center gap-2">
          {selectedGroupId && (
            <Button
              size="small"
              icon={<Pencil className="h-3.5 w-3.5" />}
              onClick={openEditEditor}
            >
              {t("watchlists:groups.edit", "Edit Group")}
            </Button>
          )}
          {selectedGroupId && (
            <Popconfirm
              title={t("watchlists:groups.deleteConfirm", "Delete this group?")}
              onConfirm={handleDelete}
              okText={t("common:yes", "Yes")}
              cancelText={t("common:no", "No")}
            >
              <Button size="small" danger icon={<Trash2 className="h-3.5 w-3.5" />}>
                {t("common:delete", "Delete")}
              </Button>
            </Popconfirm>
          )}
        </div>
      </div>

      {loading ? (
        <Skeleton active paragraph={{ rows: 4 }} />
      ) : treeData.length === 0 ? (
        <Empty
          description={t("watchlists:groups.empty", "No groups yet")}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      ) : (
        <Tree
          treeData={treeData}
          selectedKeys={selectedGroupId ? [String(selectedGroupId)] : []}
          onSelect={(keys) => {
            const next = keys.length ? Number(keys[0]) : null
            onSelect(Number.isNaN(next as number) ? null : next)
          }}
          showLine
        />
      )}

      <Modal
        title={
          editorMode === "edit"
            ? t("watchlists:groups.edit", "Edit Group")
            : t("watchlists:groups.create", "Create Group")
        }
        open={editorOpen}
        onCancel={() => setEditorOpen(false)}
        onOk={handleSubmit}
        okText={
          editorMode === "edit"
            ? t("common:save", "Save")
            : t("common:create", "Create")
        }
        cancelText={t("common:cancel", "Cancel")}
        confirmLoading={saving}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item
            name="name"
            label={t("watchlists:groups.fields.name", "Name")}
            rules={[
              {
                required: true,
                message: t("watchlists:groups.nameRequired", "Please enter a name")
              }
            ]}
          >
            <Input placeholder={t("watchlists:groups.namePlaceholder", "News Sources")} />
          </Form.Item>
          <Form.Item
            name="description"
            label={t("watchlists:groups.fields.description", "Description")}
          >
            <Input placeholder={t("watchlists:groups.descriptionPlaceholder", "Optional description")} />
          </Form.Item>
          <Form.Item
            name="parent_group_id"
            label={t("watchlists:groups.fields.parent", "Parent Group")}
          >
            <Select
              allowClear={editorMode === "create"}
              placeholder={t("watchlists:groups.none", "None")}
              options={parentOptions}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
