import type {
  WritingSessionPayload,
  WritingTemplatePayload,
  WritingThemePayload
} from "@/types/writing"

export const DEFAULT_PROMPT = `[INST] <<SYS>>
You are a talented writing assistant. Always respond by incorporating the instructions into expertly written prose that is highly detailed, evocative, vivid and engaging.
<</SYS>>

Write a story about Hatsune Miku and Kagamine Rin. [/INST]  Sure, how about this:

Chapter 1
`

export const DEFAULT_TEMPLATES: Record<string, WritingTemplatePayload> = {
  Alpaca: {
    sysPre: "### System:\\n",
    sysSuf: "",
    instPre: "\\n\\n### Instruction:\\n",
    instSuf: "\\n\\n### Response:"
  },
  Mistral: {
    sysPre: "<<SYS>>\\n",
    sysSuf: "<</SYS>>\\n\\n",
    instPre: "</s>[INST]",
    instSuf: "[/INST]"
  },
  Codestral: {
    sysPre: "<<SYS>>\\n",
    sysSuf: "<</SYS>>\\n\\n",
    instPre: "</s>[INST]",
    instSuf: "[/INST]",
    fimTemplate: "[SUFFIX]{suffix}[PREFIX]{prefix}"
  },
  Dots1: {
    sysPre: "<|system|>",
    sysSuf: "<|endofsystem|>",
    instPre: "<|userprompt|>",
    instSuf: "<|endofuserprompt|><|response|>"
  },
  ChatML: {
    sysPre: "<|im_start|>system\\n",
    sysSuf: "",
    instPre: "<|im_end|>\\n<|im_start|>user\\n",
    instSuf: "<|im_end|>\\n<|im_start|>assistant\\n"
  },
  "Llama 3": {
    sysPre: "<|start_header_id|>system<|end_header_id|>\\n\\n",
    sysSuf: "",
    instPre: "<|eot_id|><|start_header_id|>user<|end_header_id|>\\n\\n",
    instSuf: "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\\n\\n"
  },
  "Phi 2": {
    sysPre: "",
    sysSuf: "",
    instPre: "\\nInstruct: ",
    instSuf: "\\nOutput: "
  },
  "Phi 3": {
    sysPre: "<|system|>\\n",
    sysSuf: "",
    instPre: "<|end|>\\n<|user|>\\n",
    instSuf: "<|end|>\\n<|assistant|>\\n"
  },
  "Command-R": {
    sysPre: "<|START_OF_TURN_TOKEN|><|SYSTEM_TOKEN|>",
    sysSuf: "",
    instPre: "<|END_OF_TURN_TOKEN|><|START_OF_TURN_TOKEN|><|USER_TOKEN|>",
    instSuf: "<|END_OF_TURN_TOKEN|><|START_OF_TURN_TOKEN|><|CHATBOT_TOKEN|>"
  },
  Metharme: {
    sysPre: "<|system|>",
    sysSuf: "",
    instPre: "<|user|>",
    instSuf: "<|model|>"
  },
  Vicuna: {
    sysPre: "",
    sysSuf: "\\n\\n",
    instPre: "</s>\\nUSER: ",
    instSuf: "\\nASSISTANT: "
  },
  Gemma: {
    sysPre: "",
    sysSuf: "",
    instPre: "<end_of_turn>\\n<start_of_turn>user\\n",
    instSuf: "<end_of_turn>\\n<start_of_turn>model\\n"
  },
  R1: {
    sysPre: "",
    sysSuf: "",
    instPre: "<|User|>",
    instSuf: "<|Assistant|><think>\\n"
  }
}

export const DEFAULT_THEMES: Record<string, WritingThemePayload> = {
  "Serif Dark": {
    order: 0,
    isDefault: true,
    className: "theme-serif-dark",
    css: `/* Serif Dark */
.writing-playground.theme-serif-dark {
  --writing-bg: #111111;
  --writing-fg: #f3efe6;
  --writing-muted: #c2b9ad;
  --writing-panel: #1a1a1a;
  --writing-border: #2a2a2a;
  --writing-accent: #14b8a6;
  --writing-font: Georgia, Times, serif;
}
`
  },
  "Monospace Dark": {
    order: 1,
    isDefault: true,
    className: "theme-monospace-dark",
    css: `/* Monospace Dark */
.writing-playground.theme-monospace-dark {
  --writing-bg: #151515;
  --writing-fg: #d8d8d8;
  --writing-muted: #a1a1a1;
  --writing-panel: #1e1e1e;
  --writing-border: #2f2f2f;
  --writing-accent: #22c55e;
  --writing-font: ui-monospace, SFMono-Regular, Menlo, monospace;
}
`
  },
  "NockoffAI": {
    order: 2,
    isDefault: true,
    className: "theme-nockoffai",
    css: `/* NockoffAI */
.writing-playground.theme-nockoffai {
  --writing-bg: #191b31;
  --writing-fg: #f8f8f2;
  --writing-muted: #b0b3c5;
  --writing-panel: #0e0f21;
  --writing-border: #2b2c41;
  --writing-accent: #6ee7b7;
  --writing-font: "Source Sans Pro", "Helvetica Neue", Arial, sans-serif;
}
`
  },
  "E-Reader": {
    order: 3,
    isDefault: true,
    className: "theme-ereader",
    css: `/* E-Reader */
.writing-playground.theme-ereader {
  --writing-bg: #f7f2e7;
  --writing-fg: #2f2a25;
  --writing-muted: #6e655b;
  --writing-panel: #efe8dc;
  --writing-border: #d8cfc1;
  --writing-accent: #0f766e;
  --writing-font: Georgia, "Times New Roman", serif;
}
`
  }
}

export const DEFAULT_SESSION: WritingSessionPayload = {
  schemaVersion: 1,
  prompt: [{ type: "user", content: DEFAULT_PROMPT }],
  seed: -1,
  maxPredictTokens: -1,
  temperature: 0.7,
  dynaTempRange: 0,
  dynaTempExp: 1,
  repeatPenalty: 1.1,
  repeatLastN: 256,
  penalizeNl: false,
  presencePenalty: 0,
  frequencyPenalty: 0,
  topK: 40,
  topP: 0.95,
  typicalP: 1,
  minP: 0,
  tfsZ: 1,
  mirostat: 0,
  mirostatTau: 5.0,
  mirostatEta: 0.1,
  xtcThreshold: 0.1,
  xtcProbability: 0,
  dryMultiplier: 0,
  dryBase: 1.75,
  dryAllowedLength: 2,
  dryPenaltyRange: 1024,
  drySequenceBreakers: "[\"\\n\", \":\", \"\\\"\", \"*\"]",
  bannedTokens: "[]",
  stoppingStrings: "[]",
  useBasicStoppingMode: true,
  basicStoppingModeType: "max_tokens",
  ignoreEos: false,
  openaiPresets: false,
  contextLength: 8192,
  tokenRatio: 3.3,
  memoryTokens: {
    contextOrder: "{memPrefix}{wiPrefix}{wiText}{wiSuffix}{memText}{memSuffix}{prompt}",
    prefix: "",
    text: "",
    suffix: ""
  },
  authorNoteTokens: {
    prefix: "",
    text: "",
    suffix: ""
  },
  authorNoteDepth: 3,
  worldInfo: {
    mikuPediaVersion: 1,
    entries: [],
    prefix: "",
    suffix: ""
  },
  logitBias: {
    bias: {},
    model: "none"
  },
  template: "Mistral",
  scrollTop: 0,
  enabledSamplers: [
    "temperature",
    "rep_pen",
    "pres_pen",
    "freq_pen",
    "mirostat",
    "top_k",
    "top_p",
    "min_p"
  ],
  grammar: "",
  chatMode: false,
  chatAPI: false,
  tokenStreaming: true,
  promptPreview: false,
  promptPreviewTokens: 20,
  themeName: "Serif Light",
  showMarkdownPreview: false,
  fontSizeMultiplier: 1,
  spellCheck: true,
  attachSidebar: false,
  preserveCursorPosition: true,
  tokenHighlightMode: 0,
  tokenColorMode: 0,
  showProbsMode: 0,
  provider: "",
  model: "",
  ttsEnabled: false,
  ttsVoiceId: 0,
  ttsPitch: 1,
  ttsRate: 1,
  ttsVolume: 1,
  ttsSpeakInputs: false,
  ttsMaxUserInput: 50
}
