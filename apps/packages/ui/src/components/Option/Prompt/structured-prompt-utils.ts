import type { StructuredPromptDefinition } from "@/services/prompt-studio"

type StructuredPromptBlock = {
  id: string
  name: string
  role: "system" | "developer" | "user" | "assistant"
  content: string
  enabled: boolean
  order: number
  is_template: boolean
}

type StructuredPromptVariable = {
  name: string
  label?: string
  description?: string
  required?: boolean
  input_type?: string
}

export const createDefaultStructuredPromptDefinition =
  (): StructuredPromptDefinition => ({
    schema_version: 1,
    format: "structured",
    variables: [],
    blocks: [
      {
        id: "task",
        name: "Task",
        role: "user",
        content: "Describe the task here.",
        enabled: true,
        order: 10,
        is_template: false
      }
    ]
  })

export const createStructuredPromptDefinition = ({
  variables = [],
  blocks
}: {
  variables?: StructuredPromptVariable[]
  blocks: Array<
    Omit<StructuredPromptBlock, "order" | "enabled" | "is_template"> &
      Partial<Pick<StructuredPromptBlock, "order" | "enabled" | "is_template">>
  >
}): StructuredPromptDefinition => ({
  schema_version: 1,
  format: "structured",
  variables: variables.map((variable) => ({
    name: variable.name,
    label: variable.label,
    description: variable.description,
    required: variable.required === true,
    input_type: variable.input_type || "text"
  })),
  blocks: blocks.map((block, index) => ({
    ...block,
    enabled: block.enabled !== false,
    order:
      typeof block.order === "number" && Number.isFinite(block.order)
        ? block.order
        : (index + 1) * 10,
    is_template: block.is_template === true
  }))
})

export const convertLegacyPromptToStructuredDefinition = (
  systemPrompt?: string | null,
  userPrompt?: string | null
): StructuredPromptDefinition => {
  const blocks: StructuredPromptBlock[] = []

  if (systemPrompt?.trim()) {
    blocks.push({
      id: "system",
      name: "System Instructions",
      role: "system",
      content: systemPrompt.trim(),
      enabled: true,
      order: 10,
      is_template: false
    })
  }

  if (userPrompt?.trim()) {
    blocks.push({
      id: "task",
      name: "Task",
      role: "user",
      content: userPrompt.trim(),
      enabled: true,
      order: blocks.length === 0 ? 10 : 20,
      is_template: true
    })
  }

  return {
    schema_version: 1,
    format: "structured",
    variables: [],
    blocks:
      blocks.length > 0
        ? blocks
        : (createDefaultStructuredPromptDefinition().blocks as StructuredPromptBlock[])
  }
}

export const renderStructuredPromptLegacySnapshot = (
  definition: StructuredPromptDefinition | null | undefined
): {
  systemPrompt: string
  userPrompt: string
  content: string
} => {
  const blocks = Array.isArray(definition?.blocks)
    ? [...definition.blocks]
        .filter((block: any) => block?.enabled !== false)
        .sort((left: any, right: any) => {
          const leftOrder =
            typeof left?.order === "number" && Number.isFinite(left.order)
              ? left.order
              : 0
          const rightOrder =
            typeof right?.order === "number" && Number.isFinite(right.order)
              ? right.order
              : 0
          return leftOrder - rightOrder
        })
    : []

  const pickContent = (roles: string[]) =>
    blocks
      .filter((block: any) => roles.includes(String(block?.role || "")))
      .map((block: any) =>
        typeof block?.content === "string" ? block.content.trim() : ""
      )
      .filter((content: string) => content.length > 0)
      .join("\n\n")

  const systemPrompt = pickContent(["system", "developer"])
  const userPrompt = pickContent(["user"])

  return {
    systemPrompt,
    userPrompt,
    content: userPrompt || systemPrompt || ""
  }
}
