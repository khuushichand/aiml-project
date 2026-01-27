/**
 * @tldw/voice-assistant-sdk
 *
 * Voice Assistant SDK for tldw_server
 *
 * Provides a complete voice assistant experience including:
 * - WebSocket client for real-time communication
 * - Audio capture and playback
 * - React hooks for easy integration
 *
 * @example
 * ```typescript
 * import { VoiceAssistantClient } from '@tldw/voice-assistant-sdk';
 *
 * const client = new VoiceAssistantClient({
 *   wsUrl: 'ws://localhost:8000/api/v1/voice/assistant',
 *   token: 'your-api-key',
 * });
 *
 * await client.connect();
 * client.sendText('search for machine learning');
 * ```
 *
 * @example React
 * ```tsx
 * import { useVoiceAssistant } from '@tldw/voice-assistant-sdk/hooks';
 *
 * function VoiceButton() {
 *   const { startListening, stopListening, isListening, transcription } = useVoiceAssistant({
 *     wsUrl: 'ws://localhost:8000/api/v1/voice/assistant',
 *     token: 'your-api-key',
 *   });
 *
 *   return (
 *     <button onClick={isListening ? stopListening : startListening}>
 *       {isListening ? 'Stop' : 'Start'}
 *     </button>
 *   );
 * }
 * ```
 */

// Client
export { VoiceAssistantClient } from './src/client';

// Audio
export { AudioCapture, AudioPlayer } from './src/audio';
export type { AudioCaptureEvents, AudioPlayerEvents } from './src/audio';

// Hooks
export { useVoiceAssistant } from './src/hooks';
export type { UseVoiceAssistantOptions, UseVoiceAssistantReturn } from './src/hooks';

// Types
export * from './src/types';

// Utils
export * from './src/utils';
