/**
 * Voice Assistant SDK Types
 *
 * Type definitions for the WebSocket protocol and client API.
 */

// WebSocket Message Types
export enum WSMessageType {
  // Client -> Server
  AUTH = 'auth',
  CONFIG = 'config',
  AUDIO = 'audio',
  COMMIT = 'commit',
  CANCEL = 'cancel',
  TEXT = 'text',
  WORKFLOW_SUBSCRIBE = 'workflow_subscribe',
  WORKFLOW_CANCEL = 'workflow_cancel',

  // Server -> Client
  AUTH_OK = 'auth_ok',
  AUTH_ERROR = 'auth_error',
  CONFIG_ACK = 'config_ack',
  TRANSCRIPTION = 'transcription',
  INTENT = 'intent',
  ACTION_START = 'action_start',
  ACTION_RESULT = 'action_result',
  TTS_CHUNK = 'tts_chunk',
  TTS_END = 'tts_end',
  ERROR = 'error',
  STATE_CHANGE = 'state_change',
  WORKFLOW_PROGRESS = 'workflow_progress',
  WORKFLOW_COMPLETE = 'workflow_complete',
}

// Voice Assistant States
export enum VoiceAssistantState {
  IDLE = 'idle',
  LISTENING = 'listening',
  PROCESSING = 'processing',
  SPEAKING = 'speaking',
  AWAITING_CONFIRMATION = 'awaiting_confirmation',
  ERROR = 'error',
}

// Action Types
export enum VoiceActionType {
  MCP_TOOL = 'mcp_tool',
  WORKFLOW = 'workflow',
  CUSTOM = 'custom',
  LLM_CHAT = 'llm_chat',
}

// Client -> Server Messages
export interface WSAuthMessage {
  type: WSMessageType.AUTH;
  token: string;
}

export interface WSConfigMessage {
  type: WSMessageType.CONFIG;
  stt_model?: string;
  stt_language?: string;
  tts_provider?: string;
  tts_voice?: string;
  tts_format?: 'mp3' | 'opus' | 'wav' | 'pcm';
  session_id?: string;
  sample_rate?: number;
}

export interface WSAudioMessage {
  type: WSMessageType.AUDIO;
  data: string; // Base64-encoded audio
  sequence?: number;
}

export interface WSCommitMessage {
  type: WSMessageType.COMMIT;
}

export interface WSCancelMessage {
  type: WSMessageType.CANCEL;
}

export interface WSTextMessage {
  type: WSMessageType.TEXT;
  text: string;
}

export interface WSWorkflowSubscribeMessage {
  type: WSMessageType.WORKFLOW_SUBSCRIBE;
  run_id: string;
}

export interface WSWorkflowCancelMessage {
  type: WSMessageType.WORKFLOW_CANCEL;
  run_id: string;
}

// Server -> Client Messages
export interface WSAuthOKMessage {
  type: WSMessageType.AUTH_OK;
  user_id: number;
  session_id: string;
}

export interface WSAuthErrorMessage {
  type: WSMessageType.AUTH_ERROR;
  error: string;
}

export interface WSConfigAckMessage {
  type: WSMessageType.CONFIG_ACK;
  session_id: string;
  stt_model: string;
  tts_provider: string;
}

export interface WSTranscriptionMessage {
  type: WSMessageType.TRANSCRIPTION;
  text: string;
  is_final: boolean;
  confidence?: number;
}

export interface WSIntentMessage {
  type: WSMessageType.INTENT;
  action_type: VoiceActionType;
  command_name?: string;
  entities: Record<string, unknown>;
  confidence: number;
  requires_confirmation: boolean;
}

export interface WSActionStartMessage {
  type: WSMessageType.ACTION_START;
  action_type: VoiceActionType;
  action_name?: string;
}

export interface WSActionResultMessage {
  type: WSMessageType.ACTION_RESULT;
  success: boolean;
  action_type: VoiceActionType;
  result_data?: Record<string, unknown>;
  response_text: string;
  execution_time_ms: number;
}

export interface WSTTSChunkMessage {
  type: WSMessageType.TTS_CHUNK;
  data: string; // Base64-encoded audio
  sequence: number;
  format: string;
}

export interface WSTTSEndMessage {
  type: WSMessageType.TTS_END;
  total_chunks: number;
  total_bytes: number;
  duration_ms?: number;
}

export interface WSErrorMessage {
  type: WSMessageType.ERROR;
  error: string;
  code?: string;
  recoverable: boolean;
}

export interface WSStateChangeMessage {
  type: WSMessageType.STATE_CHANGE;
  state: VoiceAssistantState;
  previous_state?: VoiceAssistantState;
}

export interface WSWorkflowProgressMessage {
  type: WSMessageType.WORKFLOW_PROGRESS;
  run_id: string;
  event_type: string;
  message?: string;
  data: Record<string, unknown>;
  timestamp: number;
}

export interface WSWorkflowCompleteMessage {
  type: WSMessageType.WORKFLOW_COMPLETE;
  run_id: string;
  status: string;
  outputs?: Record<string, unknown>;
  error?: string;
  duration_ms?: number;
  response_text: string;
}

// Union types for message handling
export type WSClientMessage =
  | WSAuthMessage
  | WSConfigMessage
  | WSAudioMessage
  | WSCommitMessage
  | WSCancelMessage
  | WSTextMessage
  | WSWorkflowSubscribeMessage
  | WSWorkflowCancelMessage;

export type WSServerMessage =
  | WSAuthOKMessage
  | WSAuthErrorMessage
  | WSConfigAckMessage
  | WSTranscriptionMessage
  | WSIntentMessage
  | WSActionStartMessage
  | WSActionResultMessage
  | WSTTSChunkMessage
  | WSTTSEndMessage
  | WSErrorMessage
  | WSStateChangeMessage
  | WSWorkflowProgressMessage
  | WSWorkflowCompleteMessage;

// Client Configuration
export interface VoiceAssistantConfig {
  /** WebSocket URL for the voice assistant endpoint */
  wsUrl: string;
  /** Authentication token (JWT or API key) */
  token: string;
  /** STT model to use (default: 'parakeet') */
  sttModel?: string;
  /** Language code for STT (default: auto-detect) */
  sttLanguage?: string;
  /** TTS provider (default: 'kokoro') */
  ttsProvider?: string;
  /** TTS voice (default: 'af_heart') */
  ttsVoice?: string;
  /** TTS audio format (default: 'mp3') */
  ttsFormat?: 'mp3' | 'opus' | 'wav' | 'pcm';
  /** Audio sample rate in Hz (default: 16000) */
  sampleRate?: number;
  /** Resume existing session ID */
  sessionId?: string;
  /** Auto-reconnect on disconnect (default: true) */
  autoReconnect?: boolean;
  /** Max reconnection attempts (default: 5) */
  maxReconnectAttempts?: number;
  /** Reconnection delay in ms (default: 1000) */
  reconnectDelay?: number;
  /** Enable debug logging (default: false) */
  debug?: boolean;
}

// Event types for client event emitter
export interface VoiceAssistantEvents {
  connected: () => void;
  disconnected: (reason: string) => void;
  authenticated: (data: WSAuthOKMessage) => void;
  authError: (error: string) => void;
  configured: (data: WSConfigAckMessage) => void;
  stateChange: (state: VoiceAssistantState, previousState?: VoiceAssistantState) => void;
  transcription: (data: WSTranscriptionMessage) => void;
  intent: (data: WSIntentMessage) => void;
  actionStart: (data: WSActionStartMessage) => void;
  actionResult: (data: WSActionResultMessage) => void;
  ttsChunk: (data: WSTTSChunkMessage) => void;
  ttsEnd: (data: WSTTSEndMessage) => void;
  workflowProgress: (data: WSWorkflowProgressMessage) => void;
  workflowComplete: (data: WSWorkflowCompleteMessage) => void;
  error: (error: WSErrorMessage) => void;
  audioLevel: (level: number) => void;
}

// Audio configuration
export interface AudioConfig {
  sampleRate: number;
  channelCount: number;
  echoCancellation: boolean;
  noiseSuppression: boolean;
  autoGainControl: boolean;
}

// Wake word configuration
export interface WakeWordConfig {
  /** Wake word engine to use */
  engine: 'porcupine' | 'openwakeword' | 'custom';
  /** Wake word keyword (e.g., 'hey tldw') */
  keyword: string;
  /** Sensitivity (0.0 - 1.0) */
  sensitivity?: number;
  /** Path to custom model file (for custom engine) */
  modelPath?: string;
  /** Porcupine access key (for porcupine engine) */
  accessKey?: string;
}
