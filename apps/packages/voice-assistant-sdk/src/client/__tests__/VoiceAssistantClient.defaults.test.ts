import { describe, expect, it } from "vitest";

import { VoiceAssistantClient } from "../VoiceAssistantClient";

describe("VoiceAssistantClient constructor defaults", () => {
  it("defaults TTS provider and voice to the canonical Kitten values", () => {
    const client = new VoiceAssistantClient({
      wsUrl: "ws://localhost:8000/ws",
      token: "test-token",
    });

    const config = (client as unknown as {
      config: { ttsProvider: string; ttsVoice: string };
    }).config;

    expect(config.ttsProvider).toBe("kitten_tts");
    expect(config.ttsVoice).toBe("Bella");
  });
});
