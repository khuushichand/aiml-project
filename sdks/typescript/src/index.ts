/**
 * tldw Voice Assistant SDK for TypeScript.
 *
 * @example
 * ```typescript
 * import {
 *   VoiceAssistantClient,
 *   AudioCapture,
 *   AudioPlayer,
 *   VoiceActivityDetector,
 * } from '@tldw/voice-assistant';
 *
 * // Create client
 * const client = new VoiceAssistantClient({
 *   wsUrl: 'ws://localhost:8000/api/v1/voice/assistant',
 *   token: 'your-api-key',
 * });
 *
 * // Set up audio
 * const player = new AudioPlayer();
 * const vad = new VoiceActivityDetector({
 *   onSpeechEnd: () => client.commit(),
 * });
 *
 * // Handle events
 * client.onTranscription((result) => {
 *   console.log(`You said: ${result.text}`);
 * });
 *
 * client.onActionResult((result) => {
 *   console.log(`Response: ${result.responseText}`);
 * });
 *
 * client.onTtsChunk((chunk) => player.queueChunk(chunk));
 * client.onTtsEnd(() => player.finalize());
 *
 * // Start capture
 * const capture = new AudioCapture({
 *   sampleRate: 16000,
 *   onChunk: (data) => {
 *     vad.process(data);
 *     if (vad.isSpeaking) {
 *       client.sendAudio(data);
 *     }
 *   },
 * });
 *
 * // Connect and start
 * await client.connect();
 * await capture.start();
 * ```
 *
 * @packageDocumentation
 */

// Re-export client
export { VoiceAssistantClient, VoiceAssistantConfig } from './client';

// Re-export audio utilities
export {
  AudioCapture,
  AudioCaptureOptions,
  AudioChunkCallback,
  AudioPlayer,
  AudioPlayerOptions,
  VoiceActivityDetector,
} from './audio';

// Re-export types
export {
  // Enums
  WSMessageType,
  VoiceAssistantState,
  VoiceActionType,
  AudioFormat,

  // Result types
  TranscriptionResult,
  IntentResult,
  ActionResult,
  WorkflowProgress,
  WorkflowComplete,
  TTSChunk,
  VoiceError,

  // Callback types
  TranscriptionCallback,
  IntentCallback,
  ActionResultCallback,
  TTSChunkCallback,
  TTSEndCallback,
  StateChangeCallback,
  ErrorCallback,
  WorkflowProgressCallback,
  WorkflowCompleteCallback,
  ConnectedCallback,
  DisconnectedCallback,

  // Message types (for advanced use)
  ClientMessage,
  ServerMessage,
  WSAuthMessage,
  WSConfigMessage,
  WSAudioMessage,
  WSCommitMessage,
  WSCancelMessage,
  WSTextMessage,
  WSWorkflowSubscribeMessage,
  WSWorkflowCancelMessage,
  WSAuthOKMessage,
  WSAuthErrorMessage,
  WSConfigAckMessage,
  WSTranscriptionMessage,
  WSIntentMessage,
  WSActionStartMessage,
  WSActionResultMessage,
  WSTTSChunkMessage,
  WSTTSEndMessage,
  WSErrorMessage,
  WSStateChangeMessage,
  WSWorkflowProgressMessage,
  WSWorkflowCompleteMessage,
} from './types';
