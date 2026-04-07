import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAudioSourcePreferences } from "../useAudioSourcePreferences";

const { storageValues, useStorageMock } = vi.hoisted(() => ({
  storageValues: new Map<string, unknown>(),
  useStorageMock: vi.fn(),
}));

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: useStorageMock,
}));

describe("useAudioSourcePreferences", () => {
  beforeEach(() => {
    storageValues.clear();
    useStorageMock.mockReset();
    useStorageMock.mockImplementation((key: string, defaultValue: unknown) => [
      storageValues.has(key) ? storageValues.get(key) : defaultValue,
      (nextValue: unknown) => storageValues.set(key, nextValue),
      { isLoading: false },
    ]);
  });

  it("stores separate source preferences for dictation and live voice", () => {
    const { result } = renderHook(() => useAudioSourcePreferences("dictation"));

    act(() => {
      result.current.setPreference({
        featureGroup: "dictation",
        sourceKind: "mic_device",
        deviceId: "usb-1",
        lastKnownLabel: "USB microphone",
      });
    });

    expect(storageValues.get("dictationAudioSourcePreference")).toMatchObject({
      sourceKind: "mic_device",
      deviceId: "usb-1",
    });
    expect(storageValues.has("liveVoiceAudioSourcePreference")).toBe(false);
  });

  it("normalizes invalid mic-device preferences back to default mic", () => {
    const { result } = renderHook(() => useAudioSourcePreferences("dictation"));

    act(() => {
      result.current.setPreference({
        featureGroup: "dictation",
        sourceKind: "mic_device",
        deviceId: "",
        lastKnownLabel: "Unknown microphone",
      });
    });

    expect(storageValues.get("dictationAudioSourcePreference")).toEqual({
      featureGroup: "dictation",
      sourceKind: "default_mic",
      deviceId: null,
      lastKnownLabel: null,
    });
  });
});
