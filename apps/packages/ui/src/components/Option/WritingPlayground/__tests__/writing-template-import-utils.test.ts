import { describe, expect, it } from "vitest"
import { extractImportedTemplateItems } from "../writing-template-import-utils"

describe("writing template import utils", () => {
  it("extracts templates from array payloads", () => {
    const items = extractImportedTemplateItems([
      {
        name: "Alpaca",
        payload: { sys_pre: "### System:\n" },
        schema_version: 2,
        is_default: true
      }
    ])

    expect(items).toEqual([
      {
        name: "Alpaca",
        payload: { sys_pre: "### System:\n" },
        schemaVersion: 2,
        isDefault: true
      }
    ])
  })

  it("extracts templates from instructTemplates maps", () => {
    const items = extractImportedTemplateItems({
      instructTemplates: {
        Mistral: {
          sysPre: "<<SYS>>\n",
          instPre: "[INST]",
          instSuf: "[/INST]"
        },
        ChatML: {
          sysPre: "<|im_start|>system\n"
        }
      }
    })

    expect(items).toEqual([
      {
        name: "Mistral",
        payload: {
          sysPre: "<<SYS>>\n",
          instPre: "[INST]",
          instSuf: "[/INST]"
        },
        schemaVersion: 1,
        isDefault: false
      },
      {
        name: "ChatML",
        payload: {
          sysPre: "<|im_start|>system\n"
        },
        schemaVersion: 1,
        isDefault: false
      }
    ])
  })

  it("extracts templates from direct template maps", () => {
    const items = extractImportedTemplateItems({
      Alpaca: {
        sysPre: "### System:\n",
        instPre: "### Instruction:\n"
      },
      Mistral: {
        sysPre: "<<SYS>>\n",
        instPre: "[INST]"
      }
    })

    expect(items).toEqual([
      {
        name: "Alpaca",
        payload: {
          sysPre: "### System:\n",
          instPre: "### Instruction:\n"
        },
        schemaVersion: 1,
        isDefault: false
      },
      {
        name: "Mistral",
        payload: {
          sysPre: "<<SYS>>\n",
          instPre: "[INST]"
        },
        schemaVersion: 1,
        isDefault: false
      }
    ])
  })

  it("supports single template object with inline payload fields", () => {
    const items = extractImportedTemplateItems({
      name: "Llama 3",
      sysPre: "<|start_header_id|>system<|end_header_id|>\n\n",
      instPre: "<|start_header_id|>user<|end_header_id|>\n\n"
    })

    expect(items).toEqual([
      {
        name: "Llama 3",
        payload: {
          sysPre: "<|start_header_id|>system<|end_header_id|>\n\n",
          instPre: "<|start_header_id|>user<|end_header_id|>\n\n"
        },
        schemaVersion: 1,
        isDefault: false
      }
    ])
  })
})
