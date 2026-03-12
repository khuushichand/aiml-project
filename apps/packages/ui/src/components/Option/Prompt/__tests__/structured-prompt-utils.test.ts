import { describe, expect, it } from "vitest"
import {
  convertLegacyPromptToStructuredDefinition,
  renderStructuredPromptLegacySnapshot,
  stableSerializePromptSnapshot
} from "../structured-prompt-utils"

describe("structured-prompt-utils", () => {
  it("converts legacy prompts into the backend-canonical structured shape", () => {
    expect(
      convertLegacyPromptToStructuredDefinition(
        "Be precise about {{topic}}.",
        "Summarize {{topic}} against {{baseline}}."
      )
    ).toEqual({
      schema_version: 1,
      format: "structured",
      assembly_config: {
        legacy_system_roles: ["system", "developer"],
        legacy_user_roles: ["user"],
        block_separator: "\n\n"
      },
      variables: [
        {
          name: "topic",
          label: "Topic",
          required: true,
          input_type: "textarea"
        },
        {
          name: "baseline",
          label: "Baseline",
          required: true,
          input_type: "textarea"
        }
      ],
      blocks: [
        {
          id: "legacy_system",
          name: "System Instructions",
          role: "system",
          kind: "instructions",
          content: "Be precise about {{topic}}.",
          enabled: true,
          order: 10,
          is_template: true
        },
        {
          id: "legacy_user",
          name: "User Prompt",
          role: "user",
          kind: "task",
          content: "Summarize {{topic}} against {{baseline}}.",
          enabled: true,
          order: 20,
          is_template: true
        }
      ]
    })
  })

  it("renders legacy snapshots using assembly_config role mapping and separators", () => {
    expect(
      renderStructuredPromptLegacySnapshot({
        schema_version: 1,
        format: "structured",
        assembly_config: {
          legacy_system_roles: ["developer"],
          legacy_user_roles: ["assistant"],
          block_separator: "\n--\n"
        },
        variables: [],
        blocks: [
          {
            id: "dev_one",
            name: "Developer One",
            role: "developer",
            content: "Rule one",
            enabled: true,
            order: 10,
            is_template: false
          },
          {
            id: "dev_two",
            name: "Developer Two",
            role: "developer",
            content: "Rule two",
            enabled: true,
            order: 20,
            is_template: false
          },
          {
            id: "assistant_example",
            name: "Assistant Example",
            role: "assistant",
            content: "Worked example",
            enabled: true,
            order: 30,
            is_template: false
          }
        ]
      })
    ).toEqual({
      systemPrompt: "Rule one\n--\nRule two",
      userPrompt: "Worked example",
      content: "Worked example"
    })
  })

  it("serializes equivalent prompt snapshots stably regardless of object key order", () => {
    const first = {
      promptFormat: "structured",
      structuredPromptDefinition: {
        format: "structured",
        schema_version: 1,
        blocks: [
          {
            role: "user",
            id: "task",
            content: "Summarize {{topic}}",
            order: 10,
            enabled: true,
            is_template: true,
            name: "Task"
          }
        ],
        assembly_config: {
          block_separator: "\n\n",
          legacy_user_roles: ["user"],
          legacy_system_roles: ["system", "developer"]
        }
      }
    }
    const second = {
      structuredPromptDefinition: {
        schema_version: 1,
        format: "structured",
        assembly_config: {
          legacy_system_roles: ["system", "developer"],
          legacy_user_roles: ["user"],
          block_separator: "\n\n"
        },
        blocks: [
          {
            name: "Task",
            is_template: true,
            enabled: true,
            order: 10,
            content: "Summarize {{topic}}",
            id: "task",
            role: "user"
          }
        ]
      },
      promptFormat: "structured"
    }

    expect(stableSerializePromptSnapshot(first)).toBe(
      stableSerializePromptSnapshot(second)
    )
  })
})
