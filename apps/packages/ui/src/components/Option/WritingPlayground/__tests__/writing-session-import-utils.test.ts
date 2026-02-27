import { describe, expect, it } from "vitest"
import {
  extractImportedSessionItems,
  getImportedSessionModelHint,
  getImportedSessionProviderHint,
  parseImportedSessionPayload
} from "../writing-session-import-utils"

describe("writing session import utils", () => {
  it("extracts session items from array payloads", () => {
    const items = extractImportedSessionItems([
      { name: "A" },
      { name: "B" },
      "skip"
    ])
    expect(items).toEqual([{ name: "A" }, { name: "B" }])
  })

  it("extracts session items from sessions object maps", () => {
    const items = extractImportedSessionItems({
      sessions: {
        one: { name: "A", prompt: "x" },
        two: { name: "B", prompt: "y" }
      }
    })
    expect(items).toEqual([
      { name: "A", prompt: "x" },
      { name: "B", prompt: "y" }
    ])
  })

  it("extracts session items from mikupad database exports", () => {
    const items = extractImportedSessionItems({
      Sessions: [
        { key: "nextSessionId", value: 3 },
        { key: 1, value: { prompt: "First prompt", temperature: "0.7" } },
        { key: 2, value: { prompt: "Second prompt", topP: "0.9" } }
      ],
      Names: [
        { key: 1, value: "Session 1" },
        { key: 2, value: "Session 2" }
      ]
    })

    expect(items).toEqual([
      { name: "Session 1", prompt: "First prompt", temperature: "0.7" },
      { name: "Session 2", prompt: "Second prompt", topP: "0.9" }
    ])
  })

  it("extracts session items from direct object maps", () => {
    const items = extractImportedSessionItems({
      "0": { name: "A", prompt: "x" },
      "1": { name: "B", prompt: "y" }
    })
    expect(items).toEqual([
      { name: "A", prompt: "x" },
      { name: "B", prompt: "y" }
    ])
  })

  it("prefers explicit payload objects", () => {
    const payload = parseImportedSessionPayload({
      name: "Imported",
      payload: {
        prompt: "Hello",
        settings: { temperature: 0.8 }
      },
      prompt: "ignored"
    })

    expect(payload).toEqual({
      prompt: "Hello",
      settings: { temperature: 0.8 }
    })
  })

  it("parses explicit payload_json strings", () => {
    const payload = parseImportedSessionPayload({
      payload_json: '{"prompt":"Hello","settings":{"temperature":0.4}}'
    })

    expect(payload).toEqual({
      prompt: "Hello",
      settings: { temperature: 0.4 }
    })
  })

  it("parses explicit payload strings", () => {
    const payload = parseImportedSessionPayload({
      payload: '{"prompt":"From payload"}'
    })

    expect(payload).toEqual({
      prompt: "From payload"
    })
  })

  it("parses mikupad-style stringified session fields", () => {
    const payload = parseImportedSessionPayload({
      name: "Miku Session",
      prompt: '[{"role":"user","content":"Hi"}]',
      temperature: "0.7",
      top_p: "0.9",
      maxPredictTokens: "128",
      stop: '["</s>"]'
    })

    expect(payload).toEqual({
      prompt: "Hi",
      settings: {
        temperature: 0.7,
        top_p: 0.9,
        max_tokens: 128,
        stop: ["</s>"]
      }
    })
  })

  it("maps mikupad root fields into settings and advanced_extra_body", () => {
    const payload = parseImportedSessionPayload({
      name: "Miku Session",
      chatMode: "true",
      template: "Llama 3",
      dynaTempRange: "0.2",
      dynaTempExp: "1.5",
      repeatPenalty: "1.1",
      repeatLastN: "256",
      penalizeNl: "true",
      ignoreEos: "true",
      stoppingStrings: '["### User:"]'
    })

    expect(payload).toEqual({
      chat_mode: true,
      template_name: "Llama 3",
      settings: {
        stop: ["### User:"],
        advanced_extra_body: {
          dynatemp_range: 0.2,
          dynatemp_exponent: 1.5,
          repeat_penalty: 1.1,
          repeat_last_n: 256,
          penalize_nl: true,
          ignore_eos: true
        }
      }
    })
  })

  it("maps mikupad basic stopping mode settings", () => {
    const payload = parseImportedSessionPayload({
      useBasicStoppingMode: "true",
      basicStoppingModeType: "new_line"
    })

    expect(payload).toEqual({
      settings: {
        use_basic_stopping_mode: true,
        basic_stopping_mode_type: "new_line"
      }
    })
  })

  it("maps mikupad dry penalty range and nested logit bias shape", () => {
    const payload = parseImportedSessionPayload({
      dryPenaltyRange: "1024",
      postSamplingProbs: "true",
      logitBias:
        '{"bias":{"ban":{"ids":["50256"],"power":"-100"},"favor":{"ids":[198],"power":"2.5"}},"model":"none"}'
    })

    expect(payload).toEqual({
      settings: {
        advanced_extra_body: {
          dry_penalty_last_n: 1024,
          post_sampling_probs: true,
          logit_bias: {
            "198": 2.5,
            "50256": -100
          }
        }
      }
    })
  })

  it("respects mikupad enabled samplers to avoid importing inactive sampler defaults", () => {
    const payload = parseImportedSessionPayload({
      enabledSamplers:
        '["temperature","top_p","pres_pen","freq_pen","ban_tokens"]',
      temperature: "0.8",
      topP: "0.95",
      topK: "40",
      presencePenalty: "0.3",
      frequencyPenalty: "0.2",
      dynaTempRange: "0.2",
      bannedTokens: '["<BOS>","<EOS>"]'
    })

    expect(payload).toEqual({
      settings: {
        temperature: 0.8,
        top_p: 0.95,
        presence_penalty: 0.3,
        frequency_penalty: 0.2,
        advanced_extra_body: {
          banned_tokens: ["<BOS>", "<EOS>"]
        }
      }
    })
  })

  it("respects openai presets mode and strips non-openai sampler extras", () => {
    const payload = parseImportedSessionPayload({
      endpointAPI: "3",
      openaiPresets: "true",
      topK: "40",
      dynaTempRange: "0.5",
      repeatPenalty: "1.2",
      ignoreEos: "true",
      grammar: "root ::= 'test'",
      logitBias: '{"50256":-100}'
    })

    expect(payload).toEqual({
      settings: {
        advanced_extra_body: {
          logit_bias: {
            "50256": -100
          }
        }
      },
      provider: "openai"
    })
  })

  it("treats mikupad sentinel values as unset for max tokens and seed", () => {
    const payload = parseImportedSessionPayload({
      maxPredictTokens: "-1",
      seed: "-1"
    })

    expect(payload).toEqual({})
  })

  it("maps memory/author note and world info blocks", () => {
    const payload = parseImportedSessionPayload({
      name: "Miku Session",
      memoryTokens: '{"prefix":"MEM\\n","text":"fact","suffix":"\\nEND"}',
      authorNoteTokens: '{"prefix":"AN\\n","text":"style","suffix":"\\nEND"}',
      authorNoteDepth: "3",
      worldInfo:
        '{"prefix":"WI:\\n","suffix":"\\n<END>","entries":[{"key":["hero"],"content":"Hero lore"}]}'
    })

    expect(payload).toEqual({
      settings: {
        memory_block: {
          enabled: true,
          prefix: "MEM\n",
          text: "fact",
          suffix: "\nEND"
        },
        author_note: {
          enabled: true,
          prefix: "AN\n",
          text: "style",
          suffix: "\nEND",
          insertion_depth: 3
        },
        world_info: {
          enabled: true,
          prefix: "WI:\n",
          suffix: "\n<END>",
          search_range: 2000,
          entries: [
            {
              id: "imported-1",
              enabled: true,
              keys: ["hero"],
              content: "Hero lore",
              use_regex: false,
              case_sensitive: false
            }
          ]
        }
      }
    })
  })

  it("drops metadata fields from fallback payload extraction", () => {
    const payload = parseImportedSessionPayload({
      id: "session-1",
      name: "Imported",
      title: "Ignored",
      schema_version: 2,
      version: 10,
      payload_json: null,
      created_at: "2026-02-26T00:00:00Z",
      chat_mode: "true"
    })

    expect(payload).toEqual({
      chat_mode: true
    })
  })

  it("drops known endpoint credential fields from imports", () => {
    const payload = parseImportedSessionPayload({
      endpoint: "https://example.com/v1",
      endpointAPIKey: "secret",
      endpoint_api_key: "secret2",
      apiKey: "secret3",
      prompt: "safe"
    })

    expect(payload).toEqual({
      prompt: "safe"
    })
  })

  it("keeps plain strings that are not valid json", () => {
    const payload = parseImportedSessionPayload({
      name: "Imported",
      endpointModel: "gpt-4o-mini",
      notes: "some literal text"
    })

    expect(payload).toEqual({
      model: "gpt-4o-mini",
      notes: "some literal text"
    })
  })

  it("maps model/provider hints from imported fields", () => {
    const payload = parseImportedSessionPayload({
      name: "Imported",
      endpointModel: "gpt-4o-mini",
      endpointAPI: "3"
    })

    expect(payload).toEqual({
      model: "gpt-4o-mini",
      provider: "openai"
    })
    expect(getImportedSessionModelHint(payload)).toBe("gpt-4o-mini")
    expect(getImportedSessionProviderHint(payload)).toBe("openai")
  })

  it("maps selectedTemplate and chatAPI into writing payload fields", () => {
    const payload = parseImportedSessionPayload({
      selectedTemplate: "Mistral",
      chatAPI: "true"
    })

    expect(payload).toEqual({
      template_name: "Mistral",
      chat_mode: true
    })
  })

  it("prefers chat mode enabled when chatMode and chatAPI conflict", () => {
    const payload = parseImportedSessionPayload({
      chatMode: "false",
      chatAPI: "true"
    })

    expect(payload).toEqual({
      chat_mode: true
    })
  })

  it("extracts normalized hints from mixed payload keys", () => {
    expect(
      getImportedSessionModelHint({ model_id: "  mistral-small  " })
    ).toBe("mistral-small")
    expect(
      getImportedSessionProviderHint({ api_provider: "  OpenAI  " })
    ).toBe("openai")
    expect(
      getImportedSessionProviderHint({ apiProvider: "custom_openai_api" })
    ).toBe("custom-openai-api")
    expect(
      getImportedSessionProviderHint({ provider: "llamacpp" })
    ).toBe("llama.cpp")
    expect(
      getImportedSessionProviderHint({ provider: "tabbyapi" })
    ).toBe("tabby")
    expect(
      getImportedSessionProviderHint({ provider: "oobabooga" })
    ).toBe("ooba")
    expect(
      getImportedSessionProviderHint({ provider: "koboldcpp" })
    ).toBe("kobold")
    expect(
      getImportedSessionProviderHint({ endpointAPI: 2 })
    ).toBe("kobold")
    expect(
      getImportedSessionProviderHint({ endpointAPI: 4 })
    ).toBeNull()
  })
})
