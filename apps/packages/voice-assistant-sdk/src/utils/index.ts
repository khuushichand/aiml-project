/**
 * Utility functions for voice assistant SDK
 */

/**
 * Convert Float32Array audio to base64-encoded PCM.
 *
 * @param audioData - Float32Array of audio samples
 * @returns Base64-encoded string
 */
export function float32ToBase64(audioData: Float32Array): string {
  const buffer = new ArrayBuffer(audioData.length * 4);
  const view = new DataView(buffer);
  for (let i = 0; i < audioData.length; i++) {
    view.setFloat32(i * 4, audioData[i], true);
  }
  return arrayBufferToBase64(buffer);
}

/**
 * Convert ArrayBuffer to base64 string.
 *
 * @param buffer - ArrayBuffer to convert
 * @returns Base64-encoded string
 */
export function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Convert base64 string to ArrayBuffer.
 *
 * @param base64 - Base64-encoded string
 * @returns ArrayBuffer
 */
export function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binaryString = atob(base64);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes.buffer;
}

/**
 * Calculate RMS (Root Mean Square) of audio samples.
 *
 * @param samples - Float32Array of audio samples
 * @returns RMS value (0.0 - 1.0)
 */
export function calculateRMS(samples: Float32Array): number {
  let sum = 0;
  for (let i = 0; i < samples.length; i++) {
    sum += samples[i] * samples[i];
  }
  return Math.sqrt(sum / samples.length);
}

/**
 * Convert RMS to decibels.
 *
 * @param rms - RMS value
 * @returns Decibel value
 */
export function rmsToDb(rms: number): number {
  return 20 * Math.log10(Math.max(rms, 1e-10));
}

/**
 * Detect silence in audio samples.
 *
 * @param samples - Float32Array of audio samples
 * @param threshold - RMS threshold for silence (default: 0.01)
 * @returns true if the audio is silent
 */
export function isSilent(samples: Float32Array, threshold = 0.01): boolean {
  return calculateRMS(samples) < threshold;
}

/**
 * Resample audio data to a target sample rate.
 *
 * @param audioData - Source audio samples
 * @param sourceSampleRate - Source sample rate
 * @param targetSampleRate - Target sample rate
 * @returns Resampled Float32Array
 */
export function resample(
  audioData: Float32Array,
  sourceSampleRate: number,
  targetSampleRate: number
): Float32Array {
  if (sourceSampleRate === targetSampleRate) {
    return audioData;
  }

  const ratio = sourceSampleRate / targetSampleRate;
  const newLength = Math.round(audioData.length / ratio);
  const result = new Float32Array(newLength);

  for (let i = 0; i < newLength; i++) {
    const srcIndex = i * ratio;
    const srcIndexFloor = Math.floor(srcIndex);
    const srcIndexCeil = Math.min(srcIndexFloor + 1, audioData.length - 1);
    const t = srcIndex - srcIndexFloor;

    // Linear interpolation
    result[i] = audioData[srcIndexFloor] * (1 - t) + audioData[srcIndexCeil] * t;
  }

  return result;
}

/**
 * Check if the browser supports required audio APIs.
 *
 * @returns Object with support flags
 */
export function checkAudioSupport(): {
  mediaDevices: boolean;
  audioContext: boolean;
  audioWorklet: boolean;
  webAudio: boolean;
} {
  const hasMediaDevices = typeof navigator !== 'undefined' &&
    'mediaDevices' in navigator &&
    'getUserMedia' in navigator.mediaDevices;

  const hasAudioContext = typeof AudioContext !== 'undefined' ||
    typeof (window as unknown as { webkitAudioContext?: AudioContext }).webkitAudioContext !== 'undefined';

  const hasAudioWorklet = hasAudioContext &&
    typeof AudioWorkletNode !== 'undefined';

  return {
    mediaDevices: hasMediaDevices,
    audioContext: hasAudioContext,
    audioWorklet: hasAudioWorklet,
    webAudio: hasAudioContext,
  };
}

/**
 * Request microphone permissions.
 *
 * @returns Promise resolving to permission state
 */
export async function requestMicrophonePermission(): Promise<'granted' | 'denied' | 'prompt'> {
  try {
    const result = await navigator.permissions.query({ name: 'microphone' as PermissionName });
    return result.state as 'granted' | 'denied' | 'prompt';
  } catch {
    // Permissions API not supported, try getUserMedia
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(track => track.stop());
      return 'granted';
    } catch {
      return 'denied';
    }
  }
}

/**
 * Format duration in milliseconds to human-readable string.
 *
 * @param ms - Duration in milliseconds
 * @returns Formatted string (e.g., "2.5s", "1m 30s")
 */
export function formatDuration(ms: number): string {
  if (ms < 1000) {
    return `${ms}ms`;
  }

  const seconds = ms / 1000;
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return `${minutes}m ${remainingSeconds}s`;
}
