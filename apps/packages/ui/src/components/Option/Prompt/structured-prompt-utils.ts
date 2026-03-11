import type { StructuredPromptDefinition } from "@/services/prompt-studio"

type StructuredPromptBlock = {
  id: string
  name: string
  role: "system" | "developer" | "user" | "assistant"
  kind?: string
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

type StructuredPromptAssemblyConfig = {
  legacy_system_roles: string[]
  legacy_user_roles: string[]
  block_separator: string
}

const LEGACY_TEMPLATE_PATTERN =
  /{{\s*([a-zA-Z0-9_]+)\s*}}|\{([a-zA-Z0-9_]+)\}|\$([a-zA-Z0-9_]+)|<([a-zA-Z0-9_]+)>/g

const DEFAULT_ASSEMBLY_CONFIG: StructuredPromptAssemblyConfig = {
  legacy_system_roles: ["system", "developer"],
  legacy_user_roles: ["user"],
  block_separator: "\n\n"
}

const matchVariableName = (
  groups: Array<string | undefined>
): string => {
  for (const group of groups) {
    if (group) return group
  }
  return ""
}

export const extractLegacyPromptVariables = (
  ...templates: Array<string | null | undefined>
): string[] => {
  const variables: string[] = []

  for (const template of templates) {
    LEGACY_TEMPLATE_PATTERN.lastIndex = 0
    let match = LEGACY_TEMPLATE_PATTERN.exec(template || "")
    while (match) {
      const variableName = matchVariableName(match.slice(1))
      if (variableName && !variables.includes(variableName)) {
        variables.push(variableName)
      }
      match = LEGACY_TEMPLATE_PATTERN.exec(template || "")
    }
  }

  return variables
}

export const normalizeLegacyPromptTemplate = (
  template?: string | null
): string => {
  if (!template) return ""

  LEGACY_TEMPLATE_PATTERN.lastIndex = 0
  return template.replace(LEGACY_TEMPLATE_PATTERN, (...args) => {
    const groups = args.slice(1, 5) as Array<string | undefined>
    return `{{${matchVariableName(groups)}}}`
  })
}

export const createDefaultStructuredPromptDefinition =
  (): StructuredPromptDefinition => ({
    schema_version: 1,
    format: "structured",
    assembly_config: { ...DEFAULT_ASSEMBLY_CONFIG },
    variables: [],
    blocks: [
      {
        id: "task",
        name: "Task",
        role: "user",
        kind: "task",
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
  assembly_config: { ...DEFAULT_ASSEMBLY_CONFIG },
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
  const variables = extractLegacyPromptVariables(systemPrompt, userPrompt)
  const blocks: StructuredPromptBlock[] = []
  const normalizedSystemPrompt = normalizeLegacyPromptTemplate(systemPrompt)
  const normalizedUserPrompt = normalizeLegacyPromptTemplate(userPrompt)

  if (normalizedSystemPrompt.trim()) {
    blocks.push({
      id: "legacy_system",
      name: "System Instructions",
      role: "system",
      kind: "instructions",
      content: normalizedSystemPrompt.trim(),
      enabled: true,
      order: 10,
      is_template: normalizedSystemPrompt.includes("{{")
    })
  }

  if (normalizedUserPrompt.trim()) {
    blocks.push({
      id: "legacy_user",
      name: "User Prompt",
      role: "user",
      kind: "task",
      content: normalizedUserPrompt.trim(),
      enabled: true,
      order: blocks.length === 0 ? 10 : 20,
      is_template: normalizedUserPrompt.includes("{{")
    })
  }

  return {
    schema_version: 1,
    format: "structured",
    assembly_config: { ...DEFAULT_ASSEMBLY_CONFIG },
    variables: variables.map((variableName) => ({
      name: variableName,
      label: variableName.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase()),
      required: true,
      input_type: "textarea"
    })),
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

  const assemblyConfig = (
    definition?.assembly_config &&
    typeof definition.assembly_config === "object" &&
    !Array.isArray(definition.assembly_config)
      ? definition.assembly_config
      : DEFAULT_ASSEMBLY_CONFIG
  ) as Partial<StructuredPromptAssemblyConfig>
  const separator =
    typeof assemblyConfig.block_separator === "string"
      ? assemblyConfig.block_separator
      : DEFAULT_ASSEMBLY_CONFIG.block_separator
  const systemRoles = Array.isArray(assemblyConfig.legacy_system_roles)
    ? assemblyConfig.legacy_system_roles.map((role) => String(role))
    : DEFAULT_ASSEMBLY_CONFIG.legacy_system_roles
  const userRoles = Array.isArray(assemblyConfig.legacy_user_roles)
    ? assemblyConfig.legacy_user_roles.map((role) => String(role))
    : DEFAULT_ASSEMBLY_CONFIG.legacy_user_roles

  const pickContent = (roles: string[]) =>
    blocks
      .filter((block: any) => roles.includes(String(block?.role || "")))
      .map((block: any) =>
        typeof block?.content === "string" ? block.content.trim() : ""
      )
      .filter((content: string) => content.length > 0)
      .join(separator)

  const systemPrompt = pickContent(systemRoles)
  const userPrompt = pickContent(userRoles)

  return {
    systemPrompt,
    userPrompt,
    content: userPrompt || systemPrompt || ""
  }
}

const normalizeForStableComparison = (value: unknown): unknown => {
  if (Array.isArray(value)) {
    return value.map((item) => normalizeForStableComparison(item))
  }

  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .filter(([, item]) => item !== undefined)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, normalizeForStableComparison(item)])
    )
  }

  return value
}

export const stableSerializePromptSnapshot = (value: unknown): string =>
  JSON.stringify(normalizeForStableComparison(value)) ?? ""
