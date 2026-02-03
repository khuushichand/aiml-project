import { describe, expect, it } from "vitest"
import { buildStepRegistry, humanizeStepType } from "../step-registry"
import { schemaToConfigFields } from "../schema-utils"
import type { WorkflowStepSchema } from "@/types/workflow-editor"

const sampleSchema: WorkflowStepSchema = {
  type: "object",
  properties: {
    url: { type: "string", description: "Target URL" },
    count: { type: "integer", default: 2 },
    enabled: { type: "boolean", default: true },
    mode: { type: "string", enum: ["fast", "safe"] },
    tags: { type: "array", items: { type: "string", enum: ["a", "b"] } }
  },
  required: ["url"]
}

describe("workflow step registry", () => {
  it("builds registry entries for server-provided steps", () => {
    const registry = buildStepRegistry([
      { name: "foo_step", description: "Foo step", schema: sampleSchema }
    ])

    expect(registry.foo_step).toBeDefined()
    expect(registry.foo_step.label).toBe(humanizeStepType("foo_step"))
    expect(registry.foo_step.description).toBe("Foo step")
  })
})

describe("schemaToConfigFields", () => {
  it("maps JSON schema properties to config fields", () => {
    const fields = schemaToConfigFields(sampleSchema)
    const byKey = Object.fromEntries(fields.map((field) => [field.key, field]))

    expect(byKey.url.type).toBe("url")
    expect(byKey.url.required).toBe(true)
    expect(byKey.count.type).toBe("number")
    expect(byKey.enabled.type).toBe("checkbox")
    expect(byKey.mode.type).toBe("select")
    expect(byKey.tags.type).toBe("multiselect")
  })

  it("assigns dynamic field types for common resource references", () => {
    const schema: WorkflowStepSchema = {
      type: "object",
      properties: {
        model: { type: "string" },
        prompt_id: { type: "string" },
        collection_id: { type: "string" },
        provider: { type: "string" },
        voice: { type: "string" },
        dataset_id: { type: "string" },
        run_id: { type: "string" },
        item_id: { type: "string" },
        output_id: { type: "string" },
        run_ids: { type: "array", items: { type: "string" } },
        item_ids: { type: "array", items: { type: "string" } }
      }
    }
    const fields = schemaToConfigFields(schema)
    const byKey = Object.fromEntries(fields.map((field) => [field.key, field]))

    expect(byKey.model.type).toBe("model-picker")
    expect(byKey.prompt_id.type).toBe("select")
    expect(byKey.collection_id.type).toBe("collection-picker")
    expect(byKey.provider.type).toBe("select")
    expect(byKey.voice.type).toBe("select")
    expect(byKey.dataset_id.type).toBe("select")
    expect(byKey.run_id.type).toBe("select")
    expect(byKey.item_id.type).toBe("select")
    expect(byKey.output_id.type).toBe("select")
    expect(byKey.run_ids.type).toBe("multiselect")
    expect(byKey.item_ids.type).toBe("multiselect")
  })
})
