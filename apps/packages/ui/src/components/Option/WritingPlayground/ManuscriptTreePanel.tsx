import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { Button, Tree, Typography, Empty, Spin } from "antd"
import type { DataNode } from "antd/es/tree"
import { BookOpen, FileText, FolderOpen, Layers, Plus } from "lucide-react"
import { useWritingPlaygroundStore } from "@/store/writing-playground"
import { getManuscriptStructure, listManuscriptProjects, createManuscriptProject } from "@/services/writing-playground"

type ManuscriptTreePanelProps = {
  isOnline: boolean
}

export function ManuscriptTreePanel({ isOnline }: ManuscriptTreePanelProps) {
  const {
    activeProjectId,
    setActiveProjectId,
    activeNodeId,
    setActiveNodeId,
  } = useWritingPlaygroundStore()

  // Fetch project list
  const { data: projectsData } = useQuery({
    queryKey: ["manuscript-projects"],
    queryFn: () => listManuscriptProjects({ limit: 50 }),
    enabled: isOnline,
    staleTime: 30_000,
  })

  // Fetch structure for active project
  const { data: structure, isLoading: structureLoading } = useQuery({
    queryKey: ["manuscript-structure", activeProjectId],
    queryFn: () => getManuscriptStructure(activeProjectId!),
    enabled: isOnline && !!activeProjectId,
    staleTime: 30_000,
  })

  const treeData = useMemo(() => buildTreeData(structure), [structure])

  if (!activeProjectId) {
    const projects = (projectsData as any)?.projects || []
    return (
      <div className="flex flex-col gap-3 p-3">
        <Typography.Text strong className="text-sm">
          Manuscripts
        </Typography.Text>
        {projects.length === 0 ? (
          <Empty
            image={<BookOpen className="mx-auto h-10 w-10 text-gray-300" />}
            description="No manuscripts yet"
          >
            <Button
              type="primary"
              size="small"
              icon={<Plus className="h-3 w-3" />}
              onClick={async () => {
                const result = await createManuscriptProject({ title: "Untitled Project" }) as any
                if (result?.id) setActiveProjectId(result.id)
              }}
            >
              New Project
            </Button>
          </Empty>
        ) : (
          <div className="flex flex-col gap-1">
            {projects.map((p: any) => (
              <div
                key={p.id}
                className="cursor-pointer rounded-md px-2 py-2 hover:bg-gray-100 dark:hover:bg-gray-800"
                onClick={() => setActiveProjectId(p.id)}
              >
                <Typography.Text className="text-sm">{p.title}</Typography.Text>
                <Typography.Text type="secondary" className="ml-2 text-xs">
                  {p.word_count} words
                </Typography.Text>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  if (structureLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Spin size="small" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2 p-2">
      <div className="flex items-center justify-between px-1">
        <Typography.Text
          type="secondary"
          className="cursor-pointer text-xs hover:underline"
          onClick={() => setActiveProjectId(null)}
        >
          &larr; All Projects
        </Typography.Text>
      </div>
      {treeData.length > 0 ? (
        <Tree
          treeData={treeData}
          selectedKeys={activeNodeId ? [activeNodeId] : []}
          onSelect={(keys) => setActiveNodeId((keys[0] as string) || null)}
          showIcon
          blockNode
          defaultExpandAll
          className="manuscript-tree"
        />
      ) : (
        <Empty description="Empty project" />
      )}
    </div>
  )
}

function buildTreeData(structure: any): DataNode[] {
  if (!structure) return []

  const sceneNode = (s: any): DataNode => ({
    key: s.id,
    title: `${s.title} (${s.word_count}w)`,
    icon: <FileText className="h-3.5 w-3.5" />,
    isLeaf: true,
  })

  const chapterNode = (ch: any): DataNode => ({
    key: ch.id,
    title: `${ch.title} (${ch.word_count}w)`,
    icon: <FolderOpen className="h-3.5 w-3.5" />,
    children: ch.scenes?.map(sceneNode) || [],
  })

  const partNodes: DataNode[] = (structure.parts || []).map((p: any) => ({
    key: p.id,
    title: `${p.title} (${p.word_count}w)`,
    icon: <Layers className="h-3.5 w-3.5" />,
    children: p.chapters?.map(chapterNode) || [],
  }))

  const unassigned: DataNode[] = (structure.unassigned_chapters || []).map(chapterNode)

  return [...partNodes, ...unassigned]
}

export default ManuscriptTreePanel
