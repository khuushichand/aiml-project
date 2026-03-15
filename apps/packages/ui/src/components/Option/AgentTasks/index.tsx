import React, { useEffect, useState, useCallback, useMemo } from "react"
import { useTranslation } from "react-i18next"
import { useStorage } from "@plasmohq/storage/hook"
import {
  Alert,
  Button,
  Card,
  Empty,
  Input,
  Modal,
  Select,
  Spin,
  Tag,
  Tooltip,
  Badge,
  Form,
  Collapse,
} from "antd"
import {
  FolderPlus,
  ListTodo,
  Play,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  RefreshCw,
  Plus,
  Trash2,
  ChevronRight,
} from "lucide-react"

// Types matching the backend orchestration API
type ProjectSummary = {
  id: number
  name: string
  description?: string
  user_id: number
  created_at: string
  task_summary?: {
    total_tasks: number
    status_counts: Record<string, number>
  }
}

type TaskItem = {
  id: number
  project_id: number
  title: string
  description?: string
  status: string
  agent_type?: string
  dependency_id?: number | null
  review_count: number
  max_review_attempts: number
  created_at: string
  updated_at: string
  runs?: RunItem[]
}

type RunItem = {
  id: number
  task_id: number
  session_id?: string
  agent_type?: string
  status: string
  result_summary?: string
  error?: string
  started_at: string
  completed_at?: string
}

const STATUS_COLORS: Record<string, string> = {
  todo: "default",
  inprogress: "processing",
  review: "warning",
  complete: "success",
  triage: "error",
}

const STATUS_ICONS: Record<string, React.ReactNode> = {
  todo: <Clock className="h-3.5 w-3.5" />,
  inprogress: <Play className="h-3.5 w-3.5" />,
  review: <AlertTriangle className="h-3.5 w-3.5" />,
  complete: <CheckCircle className="h-3.5 w-3.5" />,
  triage: <XCircle className="h-3.5 w-3.5" />,
}

export const AgentTasksPage: React.FC = () => {
  const { t } = useTranslation(["option", "common"])

  const [serverUrl] = useStorage("serverUrl", "http://localhost:8000")
  const [authMode] = useStorage("authMode", "single-user")
  const [apiKey] = useStorage("apiKey", "")
  const [accessToken] = useStorage("accessToken", "")

  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null)
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [loading, setLoading] = useState(true)
  const [tasksLoading, setTasksLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Modal states
  const [showProjectModal, setShowProjectModal] = useState(false)
  const [showTaskModal, setShowTaskModal] = useState(false)
  const [projectForm] = Form.useForm()
  const [taskForm] = Form.useForm()

  const getHeaders = useCallback(async () => {
    const headers: Record<string, string> = { "Content-Type": "application/json" }
    if (authMode === "single-user" && apiKey) {
      headers["X-API-KEY"] = apiKey
    } else if (authMode === "multi-user" && accessToken) {
      headers.Authorization = `Bearer ${accessToken}`
    }
    return headers
  }, [authMode, apiKey, accessToken])

  const apiBase = `${serverUrl}/api/v1/agent-orchestration`

  const fetchProjects = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const headers = await getHeaders()
      const res = await fetch(`${apiBase}/projects`, { headers })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setProjects(data.projects ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects")
    } finally {
      setLoading(false)
    }
  }, [apiBase, getHeaders])

  const fetchTasks = useCallback(
    async (projectId: number) => {
      setTasksLoading(true)
      try {
        const headers = await getHeaders()
        const res = await fetch(`${apiBase}/projects/${projectId}/tasks`, { headers })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        setTasks(data.tasks ?? [])
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load tasks")
      } finally {
        setTasksLoading(false)
      }
    },
    [apiBase, getHeaders]
  )

  useEffect(() => {
    void fetchProjects()
  }, [fetchProjects])

  useEffect(() => {
    if (selectedProjectId !== null) {
      void fetchTasks(selectedProjectId)
    } else {
      setTasks([])
    }
  }, [selectedProjectId, fetchTasks])

  const handleCreateProject = async (values: { name: string; description?: string }) => {
    try {
      const headers = await getHeaders()
      const res = await fetch(`${apiBase}/projects`, {
        method: "POST",
        headers,
        body: JSON.stringify(values),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setShowProjectModal(false)
      projectForm.resetFields()
      void fetchProjects()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project")
    }
  }

  const handleCreateTask = async (values: {
    title: string
    description?: string
    agent_type?: string
    dependency_id?: number
    max_review_attempts?: number
  }) => {
    if (selectedProjectId === null) return
    try {
      const headers = await getHeaders()
      const body = {
        ...values,
        dependency_id: values.dependency_id || undefined,
        max_review_attempts: values.max_review_attempts || 3,
      }
      const res = await fetch(`${apiBase}/projects/${selectedProjectId}/tasks`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setShowTaskModal(false)
      taskForm.resetFields()
      void fetchTasks(selectedProjectId)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create task")
    }
  }

  const handleDispatchRun = async (taskId: number) => {
    try {
      const headers = await getHeaders()
      const res = await fetch(`${apiBase}/tasks/${taskId}/run`, {
        method: "POST",
        headers,
        body: JSON.stringify({}),
      })
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `HTTP ${res.status}`)
      }
      if (selectedProjectId !== null) {
        void fetchTasks(selectedProjectId)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to dispatch run")
    }
  }

  const handleSubmitReview = async (taskId: number, approved: boolean) => {
    try {
      const headers = await getHeaders()
      const res = await fetch(`${apiBase}/tasks/${taskId}/review`, {
        method: "POST",
        headers,
        body: JSON.stringify({ approved }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      if (selectedProjectId !== null) {
        void fetchTasks(selectedProjectId)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit review")
    }
  }

  const handleDeleteProject = async (projectId: number) => {
    try {
      const headers = await getHeaders()
      const res = await fetch(`${apiBase}/projects/${projectId}`, {
        method: "DELETE",
        headers,
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      if (selectedProjectId === projectId) {
        setSelectedProjectId(null)
      }
      void fetchProjects()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete project")
    }
  }

  const selectedProject = projects.find((p) => p.id === selectedProjectId)

  return (
    <div className="space-y-6">
      {error && (
        <Alert type="error" message={error} closable onClose={() => setError(null)} />
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Projects Panel */}
        <Card
          title={
            <span className="flex items-center gap-2">
              <FolderPlus className="h-4 w-4" />
              Projects
            </span>
          }
          extra={
            <div className="flex gap-1">
              <Button
                size="small"
                icon={<RefreshCw className="h-3.5 w-3.5" />}
                onClick={() => void fetchProjects()}
              />
              <Button
                size="small"
                type="primary"
                icon={<Plus className="h-3.5 w-3.5" />}
                onClick={() => setShowProjectModal(true)}
              >
                New
              </Button>
            </div>
          }
          className="lg:col-span-1"
          styles={{ body: { padding: 0 } }}
        >
          {loading ? (
            <div className="flex justify-center py-8">
              <Spin />
            </div>
          ) : projects.length === 0 ? (
            <Empty
              description="No projects yet"
              className="py-8"
            >
              <Button type="primary" onClick={() => setShowProjectModal(true)}>
                Create Project
              </Button>
            </Empty>
          ) : (
            <div className="divide-y divide-border">
              {projects.map((project) => (
                <div
                  key={project.id}
                  className={`flex cursor-pointer items-center gap-2 px-4 py-3 transition-colors hover:bg-surface-hover ${
                    selectedProjectId === project.id ? "bg-surface-hover" : ""
                  }`}
                  onClick={() => setSelectedProjectId(project.id)}
                >
                  <ChevronRight
                    className={`h-4 w-4 shrink-0 transition-transform ${
                      selectedProjectId === project.id ? "rotate-90" : ""
                    }`}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="font-medium truncate">{project.name}</div>
                    {project.task_summary && (
                      <div className="flex gap-1 text-xs text-muted-foreground mt-0.5">
                        <span>{project.task_summary.total_tasks} tasks</span>
                        {project.task_summary.status_counts?.complete > 0 && (
                          <span className="text-green-600">
                            {project.task_summary.status_counts.complete} done
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  <Tooltip title="Delete project">
                    <Button
                      size="small"
                      type="text"
                      danger
                      icon={<Trash2 className="h-3.5 w-3.5" />}
                      onClick={(e) => {
                        e.stopPropagation()
                        void handleDeleteProject(project.id)
                      }}
                    />
                  </Tooltip>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Tasks Panel */}
        <Card
          title={
            <span className="flex items-center gap-2">
              <ListTodo className="h-4 w-4" />
              Tasks
              {selectedProject && (
                <span className="text-sm font-normal text-muted-foreground">
                  — {selectedProject.name}
                </span>
              )}
            </span>
          }
          extra={
            selectedProjectId !== null && (
              <div className="flex gap-1">
                <Button
                  size="small"
                  icon={<RefreshCw className="h-3.5 w-3.5" />}
                  onClick={() => void fetchTasks(selectedProjectId)}
                />
                <Button
                  size="small"
                  type="primary"
                  icon={<Plus className="h-3.5 w-3.5" />}
                  onClick={() => setShowTaskModal(true)}
                >
                  New Task
                </Button>
              </div>
            )
          }
          className="lg:col-span-2"
        >
          {selectedProjectId === null ? (
            <Empty description="Select a project to view tasks" className="py-8" />
          ) : tasksLoading ? (
            <div className="flex justify-center py-8">
              <Spin />
            </div>
          ) : tasks.length === 0 ? (
            <Empty description="No tasks yet" className="py-8">
              <Button type="primary" onClick={() => setShowTaskModal(true)}>
                Create Task
              </Button>
            </Empty>
          ) : (
            <div className="space-y-3">
              {tasks.map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  allTasks={tasks}
                  onDispatchRun={handleDispatchRun}
                  onReview={handleSubmitReview}
                />
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Create Project Modal */}
      <Modal
        title="Create Project"
        open={showProjectModal}
        onCancel={() => setShowProjectModal(false)}
        onOk={() => projectForm.submit()}
        okText="Create"
      >
        <Form form={projectForm} layout="vertical" onFinish={handleCreateProject}>
          <Form.Item
            name="name"
            label="Project Name"
            rules={[{ required: true, message: "Project name is required" }]}
          >
            <Input placeholder="My Agent Project" />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea placeholder="Optional description..." rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Create Task Modal */}
      <Modal
        title="Create Task"
        open={showTaskModal}
        onCancel={() => setShowTaskModal(false)}
        onOk={() => taskForm.submit()}
        okText="Create"
      >
        <Form form={taskForm} layout="vertical" onFinish={handleCreateTask}>
          <Form.Item
            name="title"
            label="Task Title"
            rules={[{ required: true, message: "Task title is required" }]}
          >
            <Input placeholder="Implement feature X" />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea placeholder="Detailed task description..." rows={3} />
          </Form.Item>
          <Form.Item name="agent_type" label="Agent Type">
            <Select
              placeholder="Default agent"
              allowClear
              options={[
                { value: "claude_code", label: "Claude Code" },
                { value: "codex", label: "Codex CLI" },
                { value: "opencode", label: "OpenCode" },
              ]}
            />
          </Form.Item>
          <Form.Item name="dependency_id" label="Depends On">
            <Select
              placeholder="No dependency"
              allowClear
              options={tasks.map((t) => ({
                value: t.id,
                label: `#${t.id}: ${t.title}`,
              }))}
            />
          </Form.Item>
          <Form.Item name="max_review_attempts" label="Max Review Attempts">
            <Select
              defaultValue={3}
              options={[
                { value: 1, label: "1" },
                { value: 2, label: "2" },
                { value: 3, label: "3" },
                { value: 5, label: "5" },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

const TaskCard: React.FC<{
  task: TaskItem
  allTasks: TaskItem[]
  onDispatchRun: (taskId: number) => Promise<void>
  onReview: (taskId: number, approved: boolean) => Promise<void>
}> = ({ task, allTasks, onDispatchRun, onReview }) => {
  const depTask = task.dependency_id
    ? allTasks.find((t) => t.id === task.dependency_id)
    : null

  return (
    <div className="rounded-lg border border-border p-4">
      <div className="mb-2 flex items-start justify-between">
        <div className="flex items-center gap-2">
          {STATUS_ICONS[task.status] ?? <Clock className="h-3.5 w-3.5" />}
          <h4 className="font-medium">{task.title}</h4>
          <Tag color={STATUS_COLORS[task.status] ?? "default"}>
            {task.status}
          </Tag>
        </div>
        <span className="text-xs text-muted-foreground">#{task.id}</span>
      </div>

      {task.description && (
        <p className="mb-2 text-sm text-muted-foreground">{task.description}</p>
      )}

      <div className="mb-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
        {task.agent_type && <Tag>{task.agent_type}</Tag>}
        {depTask && (
          <Tag color="blue">
            Depends on: #{depTask.id} ({depTask.status})
          </Tag>
        )}
        {task.review_count > 0 && (
          <Tag>
            Reviews: {task.review_count}/{task.max_review_attempts}
          </Tag>
        )}
      </div>

      <div className="flex items-center gap-2">
        {task.status === "todo" && (
          <Button
            size="small"
            type="primary"
            icon={<Play className="h-3 w-3" />}
            onClick={() => void onDispatchRun(task.id)}
          >
            Run
          </Button>
        )}
        {task.status === "review" && (
          <>
            <Button
              size="small"
              type="primary"
              icon={<CheckCircle className="h-3 w-3" />}
              onClick={() => void onReview(task.id, true)}
            >
              Approve
            </Button>
            <Button
              size="small"
              danger
              icon={<XCircle className="h-3 w-3" />}
              onClick={() => void onReview(task.id, false)}
            >
              Reject
            </Button>
          </>
        )}
        {task.status === "inprogress" && (
          <Tag color="processing">Running...</Tag>
        )}
        {task.status === "triage" && (
          <Tag color="error">Needs human attention</Tag>
        )}
      </div>
    </div>
  )
}

export default AgentTasksPage
