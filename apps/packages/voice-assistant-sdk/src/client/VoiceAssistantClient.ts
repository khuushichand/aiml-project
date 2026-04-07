/**
 * VoiceAssistantClient
 *
 * WebSocket client for the tldw Voice Assistant API.
 * Handles authentication, audio streaming, and message handling.
 */

import { EventEmitter } from 'eventemitter3';
import type {
  VoiceAssistantConfig,
  VoiceAssistantEvents,
  VoiceAssistantState,
  WSMessageType,
  WSClientMessage,
  WSServerMessage,
  WSAuthOKMessage,
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
} from '../types';

export class VoiceAssistantClient extends EventEmitter<VoiceAssistantEvents> {
  private config: Required<VoiceAssistantConfig>;
  private ws: WebSocket | null = null;
  private state: VoiceAssistantState = 'idle' as VoiceAssistantState;
  private sessionId: string | null = null;
  private userId: number | null = null;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private isConnecting = false;
  private audioSequence = 0;

  constructor(config: VoiceAssistantConfig) {
    super();

    // Apply defaults
    this.config = {
      wsUrl: config.wsUrl,
      token: config.token,
      sttModel: config.sttModel ?? 'parakeet',
      sttLanguage: config.sttLanguage ?? '',
      ttsProvider: config.ttsProvider ?? 'kitten_tts',
      ttsVoice: config.ttsVoice ?? 'Bella',
      ttsFormat: config.ttsFormat ?? 'mp3',
      sampleRate: config.sampleRate ?? 16000,
      sessionId: config.sessionId ?? '',
      autoReconnect: config.autoReconnect ?? true,
      maxReconnectAttempts: config.maxReconnectAttempts ?? 5,
      reconnectDelay: config.reconnectDelay ?? 1000,
      debug: config.debug ?? false,
    };
  }

  /**
   * Connect to the voice assistant WebSocket endpoint.
   */
  async connect(): Promise<void> {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.log('Already connected');
      return;
    }

    if (this.isConnecting) {
      this.log('Connection in progress');
      return;
    }

    this.isConnecting = true;

    try {
      await this.createConnection();
      await this.authenticate();
      await this.configure();
      this.isConnecting = false;
      this.reconnectAttempts = 0;
    } catch (error) {
      this.isConnecting = false;
      throw error;
    }
  }

  /**
   * Disconnect from the voice assistant.
   */
  disconnect(): void {
    this.cancelReconnect();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.state = 'idle' as VoiceAssistantState;
    this.sessionId = null;
    this.userId = null;
  }

  /**
   * Send audio data to the server.
   *
   * @param audioData - Float32Array of audio samples or base64-encoded string
   */
  sendAudio(audioData: Float32Array | string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.log('WebSocket not connected');
      return;
    }

    let base64Data: string;

    if (typeof audioData === 'string') {
      base64Data = audioData;
    } else {
      // Convert Float32Array to base64
      const buffer = new ArrayBuffer(audioData.length * 4);
      const view = new DataView(buffer);
      for (let i = 0; i < audioData.length; i++) {
        view.setFloat32(i * 4, audioData[i], true);
      }
      base64Data = this.arrayBufferToBase64(buffer);
    }

    this.send({
      type: 'audio' as WSMessageType.AUDIO,
      data: base64Data,
      sequence: this.audioSequence++,
    });
  }

  /**
   * Commit the current audio buffer for processing.
   * Call this after the user has finished speaking.
   */
  commit(): void {
    this.audioSequence = 0;
    this.send({ type: 'commit' as WSMessageType.COMMIT });
  }

  /**
   * Cancel the current operation.
   */
  cancel(): void {
    this.audioSequence = 0;
    this.send({ type: 'cancel' as WSMessageType.CANCEL });
  }

  /**
   * Send a text command (bypasses STT).
   *
   * @param text - Text command to process
   */
  sendText(text: string): void {
    this.send({
      type: 'text' as WSMessageType.TEXT,
      text,
    });
  }

  /**
   * Subscribe to workflow progress updates.
   *
   * @param runId - Workflow run ID
   */
  subscribeToWorkflow(runId: string): void {
    this.send({
      type: 'workflow_subscribe' as WSMessageType.WORKFLOW_SUBSCRIBE,
      run_id: runId,
    });
  }

  /**
   * Cancel a running workflow.
   *
   * @param runId - Workflow run ID
   */
  cancelWorkflow(runId: string): void {
    this.send({
      type: 'workflow_cancel' as WSMessageType.WORKFLOW_CANCEL,
      run_id: runId,
    });
  }

  /**
   * Get the current session ID.
   */
  getSessionId(): string | null {
    return this.sessionId;
  }

  /**
   * Get the current user ID.
   */
  getUserId(): number | null {
    return this.userId;
  }

  /**
   * Get the current state.
   */
  getState(): VoiceAssistantState {
    return this.state;
  }

  /**
   * Check if the client is connected.
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  // Private methods

  private createConnection(): Promise<void> {
    return new Promise((resolve, reject) => {
      const url = new URL(this.config.wsUrl);
      url.searchParams.set('token', this.config.token);

      this.log(`Connecting to ${url.origin}${url.pathname}`);

      this.ws = new WebSocket(url.toString());

      this.ws.onopen = () => {
        this.log('WebSocket connected');
        this.emit('connected');
        resolve();
      };

      this.ws.onerror = (event) => {
        this.log('WebSocket error', event);
        reject(new Error('WebSocket connection failed'));
      };

      this.ws.onclose = (event) => {
        this.log(`WebSocket closed: ${event.code} ${event.reason}`);
        this.emit('disconnected', event.reason || 'Connection closed');
        this.handleDisconnect();
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(event.data);
      };
    });
  }

  private authenticate(): Promise<WSAuthOKMessage> {
    return new Promise((resolve, reject) => {
      const authTimeout = setTimeout(() => {
        reject(new Error('Authentication timeout'));
      }, 10000);

      const handleAuth = (data: WSAuthOKMessage) => {
        clearTimeout(authTimeout);
        this.off('authenticated', handleAuth);
        resolve(data);
      };

      const handleError = (error: string) => {
        clearTimeout(authTimeout);
        this.off('authError', handleError);
        reject(new Error(error));
      };

      this.once('authenticated', handleAuth);
      this.once('authError', handleError);

      this.send({
        type: 'auth' as WSMessageType.AUTH,
        token: this.config.token,
      });
    });
  }

  private configure(): Promise<WSConfigAckMessage> {
    return new Promise((resolve, reject) => {
      const configTimeout = setTimeout(() => {
        reject(new Error('Configuration timeout'));
      }, 10000);

      const handleConfig = (data: WSConfigAckMessage) => {
        clearTimeout(configTimeout);
        this.off('configured', handleConfig);
        resolve(data);
      };

      this.once('configured', handleConfig);

      this.send({
        type: 'config' as WSMessageType.CONFIG,
        stt_model: this.config.sttModel,
        stt_language: this.config.sttLanguage || undefined,
        tts_provider: this.config.ttsProvider,
        tts_voice: this.config.ttsVoice,
        tts_format: this.config.ttsFormat,
        sample_rate: this.config.sampleRate,
        session_id: this.config.sessionId || undefined,
      });
    });
  }

  private handleMessage(data: string): void {
    try {
      const message = JSON.parse(data) as WSServerMessage;
      this.log('Received message:', message.type);

      switch (message.type) {
        case 'auth_ok':
          this.userId = (message as WSAuthOKMessage).user_id;
          this.sessionId = (message as WSAuthOKMessage).session_id;
          this.emit('authenticated', message as WSAuthOKMessage);
          break;

        case 'auth_error':
          this.emit('authError', (message as { error: string }).error);
          break;

        case 'config_ack':
          this.sessionId = (message as WSConfigAckMessage).session_id;
          this.emit('configured', message as WSConfigAckMessage);
          break;

        case 'state_change':
          const stateMsg = message as WSStateChangeMessage;
          const previousState = this.state;
          this.state = stateMsg.state;
          this.emit('stateChange', stateMsg.state, previousState);
          break;

        case 'transcription':
          this.emit('transcription', message as WSTranscriptionMessage);
          break;

        case 'intent':
          this.emit('intent', message as WSIntentMessage);
          break;

        case 'action_start':
          this.emit('actionStart', message as WSActionStartMessage);
          break;

        case 'action_result':
          this.emit('actionResult', message as WSActionResultMessage);
          break;

        case 'tts_chunk':
          this.emit('ttsChunk', message as WSTTSChunkMessage);
          break;

        case 'tts_end':
          this.emit('ttsEnd', message as WSTTSEndMessage);
          break;

        case 'workflow_progress':
          this.emit('workflowProgress', message as WSWorkflowProgressMessage);
          break;

        case 'workflow_complete':
          this.emit('workflowComplete', message as WSWorkflowCompleteMessage);
          break;

        case 'error':
          this.emit('error', message as WSErrorMessage);
          break;

        default:
          this.log('Unknown message type:', (message as { type: string }).type);
      }
    } catch (error) {
      this.log('Failed to parse message:', error);
    }
  }

  private handleDisconnect(): void {
    this.ws = null;

    if (this.config.autoReconnect && this.reconnectAttempts < this.config.maxReconnectAttempts) {
      const delay = this.config.reconnectDelay * Math.pow(2, this.reconnectAttempts);
      this.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1}/${this.config.maxReconnectAttempts})`);

      this.reconnectTimer = setTimeout(() => {
        this.reconnectAttempts++;
        this.connect().catch((error) => {
          this.log('Reconnection failed:', error);
        });
      }, delay);
    }
  }

  private cancelReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.reconnectAttempts = 0;
  }

  private send(message: WSClientMessage): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.log('Cannot send: WebSocket not connected');
      return;
    }

    this.ws.send(JSON.stringify(message));
  }

  private arrayBufferToBase64(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  private log(...args: unknown[]): void {
    if (this.config.debug) {
      console.log('[VoiceAssistant]', ...args);
    }
  }
}
