import { useStorage } from "@plasmohq/storage/hook";
import type { AudioFeatureGroup, AudioSourceKind } from "@/audio";

export type StoredAudioSourcePreference = {
  featureGroup: AudioFeatureGroup;
  sourceKind: AudioSourceKind;
  deviceId?: string | null;
  lastKnownLabel?: string | null;
};

const STORAGE_KEYS = {
  dictation: "dictationAudioSourcePreference",
  live_voice: "liveVoiceAudioSourcePreference",
  speech_playground: "speechPlaygroundAudioSourcePreference",
} as const;

const buildDefaultPreference = (
  featureGroup: AudioFeatureGroup,
): StoredAudioSourcePreference => ({
  featureGroup,
  sourceKind: "default_mic",
  deviceId: null,
  lastKnownLabel: null,
});

const normalizePreference = (
  value: StoredAudioSourcePreference | null | undefined,
  featureGroup: AudioFeatureGroup,
): StoredAudioSourcePreference => {
  if (!value || typeof value !== "object") {
    return buildDefaultPreference(featureGroup);
  }

  const normalizedDeviceId =
    typeof value.deviceId === "string" ? value.deviceId.trim() : "";

  const sourceKind =
    value.sourceKind === "mic_device" &&
    normalizedDeviceId !== "" &&
    normalizedDeviceId !== "default"
      ? "mic_device"
      : "default_mic";

  return {
    featureGroup,
    sourceKind,
    deviceId: sourceKind === "mic_device" ? normalizedDeviceId : null,
    lastKnownLabel:
      sourceKind === "mic_device" ? (value.lastKnownLabel ?? null) : null,
  };
};

export function useAudioSourcePreferences(featureGroup: AudioFeatureGroup) {
  const [storedValue, setStoredValue, meta] =
    useStorage<StoredAudioSourcePreference | null>(
      STORAGE_KEYS[featureGroup],
      buildDefaultPreference(featureGroup),
    );

  const preference = normalizePreference(storedValue, featureGroup);

  const setPreference = (nextValue: StoredAudioSourcePreference) => {
    setStoredValue(normalizePreference(nextValue, featureGroup));
  };

  return {
    preference,
    setPreference,
    isLoading: Boolean(meta?.isLoading),
  };
}
