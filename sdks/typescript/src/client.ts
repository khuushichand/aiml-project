/**
 * Voice Assistant WebSocket Client.
 *
 * Provides async interface for connecting to tldw voice assistant.
 */

import {
  ActionResult,
  ActionResultCallback,
  AudioFormat,
  ConnectedCallback,
  DisconnectedCallback,
  ErrorCallback,
  IntentCallback,
  IntentResult,
  StateChangeCallback,
  TranscriptionCallback,
  TranscriptionResult,
  TTSChunk,
  TTSChunkCallback,
  TTSEndCallback,
  VoiceActionType,
  VoiceAssistantState,
  VoiceError,
  WorkflowComplete,
  WorkflowCompleteCallback,
  WorkflowProgress,
  WorkflowProgressCallback,
  WSMessageType,
} from './types';

/**
 * Configuration for VoiceAssistantClient.
 */
export interface VoiceAssistantConfig {
  /** WebSocket URL for the voice assistant endpoint. */
  wsUrl: string;
  /** Authentication token (JWT or API key). */
  token: string;
  /** STT model to use. */
  sttModel?: string;
  /** Language code for STT. */
  sttLanguage?: string;
  /** TTS provider. */
  ttsProvider?: string;
  /** TTS voice. */
  ttsVoice?: string;
  /** TTS audio format. */
  ttsFormat?: AudioFormat;
  /** Audio sample rate in Hz. */
  sampleRate?: number;
  /** Resume existing session ID. */
  sessionId?: string;
  /** Auto-reconnect on disconnect. */
  autoReconnect?: boolean;
  /** Maximum reconnection attempts. */
  maxReconnectAttempts?: number;
  /** Initial reconnection delay in seconds. */
  reconnectDelay?: number;
  /** Enable debug logging. */
  debug?: boolean;
}

const DEFAULT_CONFIG: Required<Omit<VoiceAssistantConfig, 'wsUrl' | 'token'>> = {
  sttModel: 'parakeet',
  sttLanguage: '',
  ttsProvider: 'kokoro',
  ttsVoice: 'af_heart',
  ttsFormat: 'mp3',
  sampleRate: 16000,
  sessionId: '',
  autoReconnect: true,
  maxReconnectAttempts: 5,
  reconnectDelay: 1.0,
  debug: false,
};

/**
 * WebSocket client for tldw Voice Assistant.
 *
 * @example
 * ```typescript
 * const client = new VoiceAssistantClient({
 *   wsUrl: 'ws://localhost:8000/api/v1/voice/assistant',
 *   token: 'your-api-key',
 * });
 *
 * client.onTranscription((result) => {
 *   console.log(`Transcription: ${result.text}`);
 * });
 *
 * client.onActionResult((result) => {
 *   console.log(`Response: ${result.responseText}`);
 * });
 *
 * await client.connect();
 * await client.sendText('search for machine learning');
 * ```
 */
export class VoiceAssistantClient {
  private config: Required<VoiceAssistantConfig>;
  private ws: WebSocket | null = null;
  private _state: VoiceAssistantState = VoiceAssistantState.IDLE;
  private _sessionId: string | null = null;
  private _userId: number | null = null;
  private reconnectAttempts = 0;
  private audioSequence = 0;
  private running = false;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

  // Event callbacks
  private onConnectedCallbacks: ConnectedCallback[] = [];
  private onDisconnectedCallbacks: DisconnectedCallback[] = [];
  private onTranscriptionCallbacks: TranscriptionCallback[] = [];
  private onIntentCallbacks: IntentCallback[] = [];
  private onActionResultCallbacks: ActionResultCallback[] = [];
  private onTtsChunkCallbacks: TTSChunkCallback[] = [];
  private onTtsEndCallbacks: TTSEndCallback[] = [];
  private onStateChangeCallbacks: StateChangeCallback[] = [];
  private onErrorCallbacks: ErrorCallback[] = [];
  private onWorkflowProgressCallbacks: WorkflowProgressCallback[] = [];
  private onWorkflowCompleteCallbacks: WorkflowCompleteCallback[] = [];

  // Promise resolvers for auth/config handshake
  private authResolver: ((msg: Record<string, unknown>) => void) | null = null;
  private configResolver: ((msg: Record<string, unknown>) => void) | null = null;

  constructor(config: VoiceAssistantConfig) {
    this.config = {
      ...DEFAULT_CONFIG,
      ...config,
    } as Required<VoiceAssistantConfig>;

    if (this.config.debug) {
      console.debug('[VoiceAssistant] Initialized with config:', {
        wsUrl: this.config.wsUrl,
        sttModel: this.config.sttModel,
        ttsProvider: this.config.ttsProvider,
      });
    }
  }

  // Properties

  /** Check if connected to the server. */
  get isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  /** Get current state. */
  get state(): VoiceAssistantState {
    return this._state;
  }

  /** Get current session ID. */
  get sessionId(): string | null {
    return this._sessionId;
  }

  /** Get current user ID. */
  get userId(): number | null {
    return this._userId;
  }

  // Event registration methods

  /** Register callback for connection event. */
  onConnected(callback: ConnectedCallback): this {
    this.onConnectedCallbacks.push(callback);
    return this;
  }

  /** Register callback for disconnection event. */
  onDisconnected(callback: DisconnectedCallback): this {
    this.onDisconnectedCallbacks.push(callback);
    return this;
  }

  /** Register callback for transcription events. */
  onTranscription(callback: TranscriptionCallback): this {
    this.onTranscriptionCallbacks.push(callback);
    return this;
  }

  /** Register callback for intent events. */
  onIntent(callback: IntentCallback): this {
    this.onIntentCallbacks.push(callback);
    return this;
  }

  /** Register callback for action result events. */
  onActionResult(callback: ActionResultCallback): this {
    this.onActionResultCallbacks.push(callback);
    return this;
  }

  /** Register callback for TTS chunk events. */
  onTtsChunk(callback: TTSChunkCallback): this {
    this.onTtsChunkCallbacks.push(callback);
    return this;
  }

  /** Register callback for TTS end events. */
  onTtsEnd(callback: TTSEndCallback): this {
    this.onTtsEndCallbacks.push(callback);
    return this;
  }

  /** Register callback for state change events. */
  onStateChange(callback: StateChangeCallback): this {
    this.onStateChangeCallbacks.push(callback);
    return this;
  }

  /** Register callback for error events. */
  onError(callback: ErrorCallback): this {
    this.onErrorCallbacks.push(callback);
    return this;
  }

  /** Register callback for workflow progress events. */
  onWorkflowProgress(callback: WorkflowProgressCallback): this {
    this.onWorkflowProgressCallbacks.push(callback);
    return this;
  }

  /** Register callback for workflow complete events. */
  onWorkflowComplete(callback: WorkflowCompleteCallback): this {
    this.onWorkflowCompleteCallbacks.push(callback);
    return this;
  }

  // Connection methods

  /** Connect to the voice assistant server. */
  async connect(): Promise<void> {
    if (this.isConnected) {
      this.log('Already connected');
      return;
    }

    try {
      // Build URL with token
      const url = `${this.config.wsUrl}?token=${encodeURIComponent(this.config.token)}`;
      this.log(`Connecting to ${this.config.wsUrl}`);

      // Create WebSocket - works in both browser and Node.js (with ws package)
      this.ws = new WebSocket(url);

      // Wait for connection
      await new Promise<void>((resolve, reject) => {
        const onOpen = () => {
          this.ws?.removeEventListener('open', onOpen);
          this.ws?.removeEventListener('error', onError);
          resolve();
        };
        const onError = (event: Event) => {
          this.ws?.removeEventListener('open', onOpen);
          this.ws?.removeEventListener('error', onError);
          reject(new Error('WebSocket connection failed'));
        };
        this.ws!.addEventListener('open', onOpen);
        this.ws!.addEventListener('error', onError);
      });

      // Set up message handler
      this.ws.addEventListener('message', this.handleMessage.bind(this));
      this.ws.addEventListener('close', this.handleClose.bind(this));
      this.ws.addEventListener('error', this.handleError.bind(this));

      // Authenticate
      await this.authenticate();

      // Configure
      await this.configure();

      this.running = true;
      this.reconnectAttempts = 0;

      for (const callback of this.onConnectedCallbacks) {
        callback();
      }

      this.log('Connected to voice assistant');
    } catch (error) {
      console.error('[VoiceAssistant] Connection failed:', error);
      throw error;
    }
  }

  /** Disconnect from the server. */
  async disconnect(): Promise<void> {
    this.running = false;

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this._state = VoiceAssistantState.IDLE;
    this._sessionId = null;
    this._userId = null;

    for (const callback of this.onDisconnectedCallbacks) {
      callback('Client disconnect');
    }

    this.log('Disconnected from voice assistant');
  }

  // Audio methods

  /**
   * Send audio data to the server.
   * @param audioData - Raw PCM bytes as ArrayBuffer, Uint8Array, or Float32Array
   */
  async sendAudio(audioData: ArrayBuffer | Uint8Array | Float32Array): Promise<void> {
    if (!this.isConnected) {
      throw new Error('Not connected');
    }

    // Convert to Uint8Array if needed
    let bytes: Uint8Array;
    if (audioData instanceof Float32Array) {
      bytes = new Uint8Array(audioData.buffer);
    } else if (audioData instanceof ArrayBuffer) {
      bytes = new Uint8Array(audioData);
    } else {
      bytes = audioData;
    }

    // Encode as base64
    const b64Data = this.arrayBufferToBase64(bytes);

    await this.send({
      type: WSMessageType.AUDIO,
      data: b64Data,
      sequence: this.audioSequence,
    });
    this.audioSequence++;
  }

  /** Signal end of utterance. */
  async commit(): Promise<void> {
    if (!this.isConnected) {
      throw new Error('Not connected');
    }

    this.audioSequence = 0;
    await this.send({ type: WSMessageType.COMMIT });
  }

  /** Cancel current operation. */
  async cancel(): Promise<void> {
    if (!this.isConnected) {
      throw new Error('Not connected');
    }

    this.audioSequence = 0;
    await this.send({ type: WSMessageType.CANCEL });
  }

  /**
   * Send a text command (bypasses STT).
   * @param text - Text command to process
   */
  async sendText(text: string): Promise<void> {
    if (!this.isConnected) {
      throw new Error('Not connected');
    }

    await this.send({ type: WSMessageType.TEXT, text });
  }

  // Workflow methods

  /**
   * Subscribe to workflow progress updates.
   * @param runId - Workflow run ID
   */
  async subscribeToWorkflow(runId: string): Promise<void> {
    if (!this.isConnected) {
      throw new Error('Not connected');
    }

    await this.send({ type: WSMessageType.WORKFLOW_SUBSCRIBE, run_id: runId });
  }

  /**
   * Cancel a running workflow.
   * @param runId - Workflow run ID
   */
  async cancelWorkflow(runId: string): Promise<void> {
    if (!this.isConnected) {
      throw new Error('Not connected');
    }

    await this.send({ type: WSMessageType.WORKFLOW_CANCEL, run_id: runId });
  }

  // Private methods

  private async authenticate(): Promise<void> {
    await this.send({ type: WSMessageType.AUTH, token: this.config.token });

    // Wait for auth response
    const response = await this.receiveOne();
    if (response.type === WSMessageType.AUTH_OK) {
      this._userId = response.user_id as number;
      this._sessionId = response.session_id as string;
      this.log(`Authenticated: user=${this._userId}, session=${this._sessionId}`);
    } else if (response.type === WSMessageType.AUTH_ERROR) {
      throw new Error(`Authentication failed: ${response.error}`);
    } else {
      throw new Error(`Unexpected response: ${JSON.stringify(response)}`);
    }
  }

  private async configure(): Promise<void> {
    const configMsg: Record<string, unknown> = {
      type: WSMessageType.CONFIG,
      stt_model: this.config.sttModel,
      tts_provider: this.config.ttsProvider,
      tts_voice: this.config.ttsVoice,
      tts_format: this.config.ttsFormat,
      sample_rate: this.config.sampleRate,
    };

    if (this.config.sttLanguage) {
      configMsg.stt_language = this.config.sttLanguage;
    }
    if (this.config.sessionId) {
      configMsg.session_id = this.config.sessionId;
    }

    await this.send(configMsg);

    // Wait for config ack
    const response = await this.receiveOne();
    if (response.type === WSMessageType.CONFIG_ACK) {
      this._sessionId = (response.session_id as string) || this._sessionId;
      this.log(`Configured: session=${this._sessionId}`);
    } else {
      this.log(`Unexpected config response: ${JSON.stringify(response)}`);
    }
  }

  private async send(message: Record<string, unknown>): Promise<void> {
    if (!this.ws) {
      throw new Error('Not connected');
    }

    this.ws.send(JSON.stringify(message));
  }

  private receiveOne(): Promise<Record<string, unknown>> {
    return new Promise((resolve) => {
      if (this.authResolver) {
        // Already waiting for a response
        this.configResolver = resolve;
      } else {
        this.authResolver = resolve;
      }
    });
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message = JSON.parse(event.data as string) as Record<string, unknown>;
      const msgType = message.type as string;
      this.log(`Received: ${msgType}`);

      // Handle handshake messages
      if (
        this.authResolver &&
        (msgType === WSMessageType.AUTH_OK || msgType === WSMessageType.AUTH_ERROR)
      ) {
        const resolver = this.authResolver;
        this.authResolver = null;
        resolver(message);
        return;
      }

      if (this.configResolver && msgType === WSMessageType.CONFIG_ACK) {
        const resolver = this.configResolver;
        this.configResolver = null;
        resolver(message);
        return;
      }

      // Handle normal messages
      this.dispatchMessage(message);
    } catch (error) {
      console.error('[VoiceAssistant] Error parsing message:', error);
    }
  }

  private dispatchMessage(message: Record<string, unknown>): void {
    const msgType = message.type as string;

    switch (msgType) {
      case WSMessageType.STATE_CHANGE: {
        const previous = this._state;
        this._state = (message.state as VoiceAssistantState) || VoiceAssistantState.IDLE;
        for (const callback of this.onStateChangeCallbacks) {
          callback(this._state, previous);
        }
        break;
      }

      case WSMessageType.TRANSCRIPTION: {
        const result: TranscriptionResult = {
          text: (message.text as string) || '',
          isFinal: (message.is_final as boolean) || false,
          confidence: message.confidence as number | undefined,
        };
        for (const callback of this.onTranscriptionCallbacks) {
          callback(result);
        }
        break;
      }

      case WSMessageType.INTENT: {
        const result: IntentResult = {
          actionType: (message.action_type as VoiceActionType) || VoiceActionType.CUSTOM,
          commandName: message.command_name as string | undefined,
          entities: (message.entities as Record<string, unknown>) || {},
          confidence: (message.confidence as number) || 0,
          requiresConfirmation: (message.requires_confirmation as boolean) || false,
        };
        for (const callback of this.onIntentCallbacks) {
          callback(result);
        }
        break;
      }

      case WSMessageType.ACTION_RESULT: {
        const result: ActionResult = {
          success: (message.success as boolean) || false,
          actionType: (message.action_type as VoiceActionType) || VoiceActionType.CUSTOM,
          responseText: (message.response_text as string) || '',
          resultData: message.result_data as Record<string, unknown> | undefined,
          executionTimeMs: (message.execution_time_ms as number) || 0,
        };
        for (const callback of this.onActionResultCallbacks) {
          callback(result);
        }
        break;
      }

      case WSMessageType.TTS_CHUNK: {
        const b64Data = (message.data as string) || '';
        const chunk: TTSChunk = {
          data: this.base64ToArrayBuffer(b64Data),
          sequence: (message.sequence as number) || 0,
          format: (message.format as AudioFormat) || 'mp3',
        };
        for (const callback of this.onTtsChunkCallbacks) {
          callback(chunk);
        }
        break;
      }

      case WSMessageType.TTS_END: {
        for (const callback of this.onTtsEndCallbacks) {
          callback();
        }
        break;
      }

      case WSMessageType.WORKFLOW_PROGRESS: {
        const progress: WorkflowProgress = {
          runId: (message.run_id as string) || '',
          eventType: (message.event_type as string) || '',
          message: message.message as string | undefined,
          data: (message.data as Record<string, unknown>) || {},
          timestamp: (message.timestamp as number) || 0,
        };
        for (const callback of this.onWorkflowProgressCallbacks) {
          callback(progress);
        }
        break;
      }

      case WSMessageType.WORKFLOW_COMPLETE: {
        const complete: WorkflowComplete = {
          runId: (message.run_id as string) || '',
          status: (message.status as string) || '',
          responseText: (message.response_text as string) || '',
          outputs: message.outputs as Record<string, unknown> | undefined,
          error: message.error as string | undefined,
          durationMs: message.duration_ms as number | undefined,
        };
        for (const callback of this.onWorkflowCompleteCallbacks) {
          callback(complete);
        }
        break;
      }

      case WSMessageType.ERROR: {
        const error: VoiceError = {
          error: (message.error as string) || 'Unknown error',
          code: message.code as string | undefined,
          recoverable: (message.recoverable as boolean) ?? true,
        };
        for (const callback of this.onErrorCallbacks) {
          callback(error);
        }
        break;
      }
    }
  }

  private handleClose(event: CloseEvent): void {
    this.log(`Connection closed: ${event.code} ${event.reason}`);
    this.handleDisconnect(`${event.code}: ${event.reason || 'Connection closed'}`);
  }

  private handleError(event: Event): void {
    console.error('[VoiceAssistant] WebSocket error:', event);
  }

  private handleDisconnect(reason: string): void {
    this.ws = null;
    this._state = VoiceAssistantState.IDLE;

    for (const callback of this.onDisconnectedCallbacks) {
      callback(reason);
    }

    // Auto-reconnect if enabled
    if (
      this.config.autoReconnect &&
      this.running &&
      this.reconnectAttempts < this.config.maxReconnectAttempts
    ) {
      const delay = this.config.reconnectDelay * Math.pow(2, this.reconnectAttempts) * 1000;
      this.log(
        `Reconnecting in ${delay / 1000}s (attempt ${this.reconnectAttempts + 1}/${this.config.maxReconnectAttempts})`
      );

      this.reconnectTimeout = setTimeout(async () => {
        this.reconnectAttempts++;
        try {
          await this.connect();
        } catch (error) {
          console.error('[VoiceAssistant] Reconnection failed:', error);
        }
      }, delay);
    }
  }

  private log(message: string): void {
    if (this.config.debug) {
      console.debug(`[VoiceAssistant] ${message}`);
    }
  }

  private arrayBufferToBase64(buffer: Uint8Array): string {
    // Works in both browser and Node.js
    if (typeof Buffer !== 'undefined') {
      // Node.js
      return Buffer.from(buffer).toString('base64');
    } else {
      // Browser
      let binary = '';
      const len = buffer.byteLength;
      for (let i = 0; i < len; i++) {
        binary += String.fromCharCode(buffer[i]);
      }
      return btoa(binary);
    }
  }

  private base64ToArrayBuffer(base64: string): ArrayBuffer {
    // Works in both browser and Node.js
    if (typeof Buffer !== 'undefined') {
      // Node.js
      const buf = Buffer.from(base64, 'base64');
      return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
    } else {
      // Browser
      const binary = atob(base64);
      const len = binary.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binary.charCodeAt(i);
      }
      return bytes.buffer;
    }
  }
}
