import type { WorkflowStepSchema } from "@/types/workflow-editor"
import type { ConfigFieldSchema } from "./step-registry"
import { humanizeStepType } from "./step-registry"

const resolveSchemaType = (schema?: WorkflowStepSchema): string | undefined => {
  if (!schema) return undefined
  if (Array.isArray(schema.type)) {
    return schema.type.find((t) => t !== "null") || schema.type[0]
  }
  return schema.type
}

const normalizeKey = (key: string) =>
  key.toLowerCase().replace(/[^a-z0-9]/g, "")

const isPromptIdKey = (key: string) => {
  const compact = normalizeKey(key)
  return (
    compact === "promptid" ||
    compact.endsWith("promptid") ||
    compact === "promptidentifier" ||
    compact.endsWith("promptidentifier")
  )
}

const isEvaluationIdKey = (key: string) => {
  const compact = normalizeKey(key)
  return (
    compact === "evalid" ||
    compact.endsWith("evalid") ||
    compact === "evaluationid" ||
    compact.endsWith("evaluationid")
  )
}

const isDatasetIdKey = (key: string) => {
  const compact = normalizeKey(key)
  return (
    compact === "datasetid" ||
    compact.endsWith("datasetid")
  )
}

const isRunIdKey = (key: string) => {
  const compact = normalizeKey(key)
  return compact === "runid" || compact.endsWith("runid")
}

const isItemIdKey = (key: string) => {
  const compact = normalizeKey(key)
  return compact === "itemid" || compact.endsWith("itemid")
}

const isOutputIdKey = (key: string) => {
  const compact = normalizeKey(key)
  return (
    compact === "outputid" ||
    compact.endsWith("outputid") ||
    compact === "artifactid" ||
    compact.endsWith("artifactid")
  )
}

const isFileIdKey = (key: string) => {
  const compact = normalizeKey(key)
  return compact === "fileid" || compact.endsWith("fileid")
}

const isCollectionKey = (key: string) => {
  const compact = normalizeKey(key)
  return (
    compact === "collection" ||
    compact.endsWith("collection") ||
    compact === "collectionid" ||
    compact.endsWith("collectionid")
  )
}

const isModelKey = (key: string) => {
  const compact = normalizeKey(key)
  return (
    compact === "model" ||
    compact.endsWith("model") ||
    compact.endsWith("modelid")
  )
}

const isProviderKey = (key: string) => {
  const compact = normalizeKey(key)
  return (
    compact === "provider" ||
    compact.endsWith("provider") ||
    compact === "apiname" ||
    compact.endsWith("apiname")
  )
}

const isVoiceKey = (key: string) => {
  const compact = normalizeKey(key)
  return compact === "voice" || compact.endsWith("voice")
}

const isIdListKey = (key: string) => {
  const compact = normalizeKey(key)
  return compact.endsWith("ids") || compact.endsWith("idlist")
}

const isScalarItemType = (schema?: WorkflowStepSchema): boolean => {
  if (!schema) return false
  const t = resolveSchemaType(schema)
  return t === "string" || t === "integer" || t === "number"
}

const inferFieldType = (
  key: string,
  schema: WorkflowStepSchema
): ConfigFieldSchema["type"] => {
  const normalizedKey = key.toLowerCase()
  const schemaType = resolveSchemaType(schema)

  if (schema.enum && schema.enum.length > 0) {
    if (schemaType === "array") return "multiselect"
    return "select"
  }
  if (schemaType === "array" && schema.items?.enum && schema.items.enum.length > 0) {
    return "multiselect"
  }

  if (schemaType === "boolean") return "checkbox"
  if (schemaType === "integer" || schemaType === "number") return "number"
  if (
    schemaType === "array" &&
    (isIdListKey(key) ||
      isItemIdKey(key) ||
      isOutputIdKey(key) ||
      isFileIdKey(key) ||
      isDatasetIdKey(key) ||
      isRunIdKey(key)) &&
    isScalarItemType(schema.items)
  ) {
    return "multiselect"
  }
  if (schemaType === "array" || schemaType === "object") return "json-editor"

  if (
    isPromptIdKey(key) ||
    isEvaluationIdKey(key) ||
    isDatasetIdKey(key) ||
    isRunIdKey(key) ||
    isItemIdKey(key) ||
    isOutputIdKey(key) ||
    isFileIdKey(key) ||
    isProviderKey(key)
  ) {
    return "select"
  }
  if (isCollectionKey(key)) {
    return "collection-picker"
  }
  if (isModelKey(key)) {
    return "model-picker"
  }
  if (isVoiceKey(key)) {
    return "select"
  }

  if (normalizedKey.includes("url") || normalizedKey.includes("uri")) {
    return "url"
  }
  if (normalizedKey.includes("prompt") || normalizedKey.includes("template")) {
    return "template-editor"
  }
  if (
    normalizedKey.includes("message") ||
    normalizedKey.includes("instruction") ||
    normalizedKey.includes("content") ||
    normalizedKey.includes("text")
  ) {
    return "textarea"
  }

  return "text"
}

const schemaToOptions = (
  schema: WorkflowStepSchema
): Array<{ value: any; label: string }> | undefined => {
  if (schema.enum && Array.isArray(schema.enum)) {
    return schema.enum.map((value) => ({ value, label: String(value) }))
  }
  if (schema.items?.enum && Array.isArray(schema.items.enum)) {
    return schema.items.enum.map((value) => ({ value, label: String(value) }))
  }
  return undefined
}

export const schemaHasProperties = (schema?: WorkflowStepSchema): boolean => {
  if (!schema) return false
  const props = schema.properties
  if (props && typeof props === "object" && Object.keys(props).length > 0) return true
  return false
}

export const schemaToConfigFields = (
  schema?: WorkflowStepSchema
): ConfigFieldSchema[] => {
  if (!schema || typeof schema !== "object") return []
  const props = schema.properties
  if (!props || typeof props !== "object") return []
  const required = new Set(schema.required || [])

  return Object.entries(props).map(([key, value]) => {
    const label = humanizeStepType(key)
    const fieldSchema = value || {}
    return {
      key,
      type: inferFieldType(key, fieldSchema),
      label,
      description: fieldSchema.description,
      required: required.has(key),
      default: fieldSchema.default,
      options: schemaToOptions(fieldSchema)
    }
  })
}
