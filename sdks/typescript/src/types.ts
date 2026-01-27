/**
 * Type definitions for tldw Voice Assistant SDK.
 */

/**
 * WebSocket message types for client-server communication.
 */
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

/**
 * Voice assistant session states.
 */
export enum VoiceAssistantState {
  IDLE = 'idle',
  LISTENING = 'listening',
  PROCESSING = 'processing',
  SPEAKING = 'speaking',
  AWAITING_CONFIRMATION = 'awaiting_confirmation',
  ERROR = 'error',
}

/**
 * Types of voice command actions.
 */
export enum VoiceActionType {
  MCP_TOOL = 'mcp_tool',
  WORKFLOW = 'workflow',
  CUSTOM = 'custom',
  LLM_CHAT = 'llm_chat',
}

/**
 * Audio format options for TTS output.
 */
export type AudioFormat = 'mp3' | 'opus' | 'wav' | 'pcm';

/**
 * Result from speech-to-text transcription.
 */
export interface TranscriptionResult {
  text: string;
  isFinal: boolean;
  confidence?: number;
}

/**
 * Parsed intent from voice command.
 */
export interface IntentResult {
  actionType: VoiceActionType;
  commandName?: string;
  entities: Record<string, unknown>;
  confidence: number;
  requiresConfirmation: boolean;
}

/**
 * Result from executing a voice command action.
 */
export interface ActionResult {
  success: boolean;
  actionType: VoiceActionType;
  responseText: string;
  resultData?: Record<string, unknown>;
  executionTimeMs: number;
}

/**
 * Progress update from a running workflow.
 */
export interface WorkflowProgress {
  runId: string;
  eventType: string;
  message?: string;
  data: Record<string, unknown>;
  timestamp: number;
}

/**
 * Completion notification for a workflow.
 */
export interface WorkflowComplete {
  runId: string;
  status: string;
  responseText: string;
  outputs?: Record<string, unknown>;
  error?: string;
  durationMs?: number;
}

/**
 * Audio chunk from TTS response.
 */
export interface TTSChunk {
  data: ArrayBuffer;
  sequence: number;
  format: AudioFormat;
}

/**
 * Error from voice assistant.
 */
export interface VoiceError {
  error: string;
  code?: string;
  recoverable: boolean;
}

// Client -> Server message interfaces

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
  tts_format?: AudioFormat;
  session_id?: string;
  sample_rate?: number;
}

export interface WSAudioMessage {
  type: WSMessageType.AUDIO;
  data: string; // Base64-encoded PCM data
  sequence: number;
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

// Server -> Client message interfaces

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
  format: AudioFormat;
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

// Union types for messages
export type ClientMessage =
  | WSAuthMessage
  | WSConfigMessage
  | WSAudioMessage
  | WSCommitMessage
  | WSCancelMessage
  | WSTextMessage
  | WSWorkflowSubscribeMessage
  | WSWorkflowCancelMessage;

export type ServerMessage =
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

// Callback types
export type TranscriptionCallback = (result: TranscriptionResult) => void;
export type IntentCallback = (result: IntentResult) => void;
export type ActionResultCallback = (result: ActionResult) => void;
export type TTSChunkCallback = (chunk: TTSChunk) => void;
export type TTSEndCallback = () => void;
export type StateChangeCallback = (
  state: VoiceAssistantState,
  previousState?: VoiceAssistantState
) => void;
export type ErrorCallback = (error: VoiceError) => void;
export type WorkflowProgressCallback = (progress: WorkflowProgress) => void;
export type WorkflowCompleteCallback = (complete: WorkflowComplete) => void;
export type ConnectedCallback = () => void;
export type DisconnectedCallback = (reason: string) => void;
