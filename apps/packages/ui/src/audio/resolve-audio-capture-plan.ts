import type {
  AudioCaptureReason,
  AudioCaptureRequestedSource,
  AudioFeatureGroup,
  AudioSpeechPath,
  ResolveAudioCapturePlanInput,
  ResolvedAudioCapturePlan
} from "./source-types"

const resolveDictationSpeechPath = (
  requestedSource: AudioCaptureRequestedSource,
  requestedSpeechPath: AudioSpeechPath,
  serverDictationSupported: boolean
): {
  resolvedSpeechPath: AudioSpeechPath
  reason: AudioCaptureReason
} => {
  if (
    requestedSpeechPath === "browser_dictation" &&
    requestedSource.sourceKind === "mic_device"
  ) {
    return {
      resolvedSpeechPath: serverDictationSupported
        ? "server_dictation"
        : "browser_dictation",
      reason: serverDictationSupported
        ? "browser_dictation_incompatible_with_selected_source"
        : "selected_source_unavailable"
    }
  }

  return {
    resolvedSpeechPath: requestedSpeechPath,
    reason: "resolved_as_requested"
  }
}

const resolveSpeechPathForFeatureGroup = (
  featureGroup: AudioFeatureGroup,
  requestedSource: AudioCaptureRequestedSource,
  requestedSpeechPath: AudioSpeechPath,
  capabilities: ResolveAudioCapturePlanInput["capabilities"]
): {
  resolvedSpeechPath: AudioSpeechPath
  reason: AudioCaptureReason
} => {
  if (featureGroup === "dictation") {
    return resolveDictationSpeechPath(
      requestedSource,
      requestedSpeechPath,
      capabilities.serverDictationSupported
    )
  }

  return {
    resolvedSpeechPath: requestedSpeechPath,
    reason: "resolved_as_requested"
  }
}

export const resolveAudioCapturePlan = (
  input: ResolveAudioCapturePlanInput
): ResolvedAudioCapturePlan => {
  const { requestedSource, requestedSpeechPath, capabilities, featureGroup } =
    input

  const { resolvedSpeechPath, reason } = resolveSpeechPathForFeatureGroup(
    featureGroup,
    requestedSource,
    requestedSpeechPath,
    capabilities
  )

  return {
    requestedSource,
    resolvedSource: requestedSource,
    resolvedDeviceId: requestedSource.deviceId ?? null,
    requestedSourceKind: requestedSource.sourceKind,
    resolvedSourceKind: requestedSource.sourceKind,
    requestedSpeechPath,
    resolvedSpeechPath,
    reason
  }
}
