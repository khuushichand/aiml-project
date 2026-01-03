import type { JsonSchema } from '@/lib/schema';

const MAX_MESSAGE_LENGTH = 10000;
const MAX_TOTAL_MESSAGE_LENGTH = 50000;

export type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
export type ApiPath = `/${string}`;
export type QuickFormValue = string | number | boolean | Record<string, unknown> | Array<unknown> | null | undefined;
export type QuickFormState = Record<string, QuickFormValue>;
export type QuickFormBody = Record<string, QuickFormValue>;

export interface QuickFormPreset<TState extends QuickFormState = QuickFormState> {
  id: string;
  title: string;
  method: Method;
  path: ApiPath; // relative to /api/{version}
  defaults: TState;
  toBody: (state: TState) => QuickFormBody | undefined;
  validate?: (body: QuickFormBody) => string[]; // return list of errors; empty = valid
  describe?: string;
  schema?: JsonSchema; // optional JSON schema for request body
}

/**
 * Returns the value if it's an array, otherwise returns an empty array.
 * Used for validation: non-arrays are treated as invalid/empty.
 */
export const asArray = (value: unknown): QuickFormValue[] => (Array.isArray(value) ? value : []);

export const QUICK_FORMS: QuickFormPreset[] = [
  {
    id: 'llm/providers',
    title: 'LLM Providers (List)',
    method: 'GET',
    path: '/llm/providers',
    defaults: {},
    toBody: () => undefined,
    describe: 'Lists configured LLM providers and models.',
  },
  {
    id: 'evaluations/list',
    title: 'Evaluations: List',
    method: 'GET',
    path: '/evaluations',
    defaults: {},
    toBody: () => undefined,
    describe: 'List recent evaluations metadata.',
  },
  {
    id: 'evaluations/metrics',
    title: 'Evaluations: Metrics',
    method: 'GET',
    path: '/evaluations/metrics',
    defaults: {},
    toBody: () => undefined,
    describe: 'Global evaluation metrics.',
  },
  {
    id: 'evaluations/health',
    title: 'Evaluations: Health',
    method: 'GET',
    path: '/evaluations/health',
    defaults: {},
    toBody: () => undefined,
    describe: 'Evaluations service health.',
  },
  {
    id: 'evaluations/rag',
    title: 'Evaluations: RAG Batch',
    method: 'POST',
    path: '/evaluations/rag',
    defaults: { queries: ['What is the topic?'], config: { search_mode: 'hybrid', top_k: 5 } },
    toBody: (s) => ({ queries: s.queries || [], config: s.config || {} }),
    validate: (b) => {
      const errs: string[] = [];
      const queries = asArray(b?.queries);
      if (queries.length === 0) errs.push('queries must be non-empty array');
      return errs;
    },
    schema: {
      type: 'object',
      required: ['queries'],
      properties: {
        queries: { type: 'array', items: { type: 'string' } },
        config: { type: 'object' },
      },
    },
    describe: 'Runs RAG evaluations over multiple queries (payload shape matches backend).',
  },
  {
    id: 'audio/speech',
    title: 'Audio TTS (Speech)',
    method: 'POST',
    path: '/audio/speech',
    defaults: { model: 'tts-1', voice: 'alloy', input: 'Hello from TLDW Server' },
    toBody: (s) => ({ model: s.model || 'tts-1', voice: s.voice || 'alloy', input: s.input || 'Hello' }),
    validate: (b) => {
      const errs: string[] = [];
      if (!String(b?.input || '').trim()) errs.push('input is required');
      return errs;
    },
    schema: {
      type: 'object',
      required: ['model', 'input'],
      properties: {
        model: { type: 'string' },
        voice: { type: 'string' },
        input: { type: 'string' },
      },
    },
    describe: 'Text-to-speech (OpenAI-compatible). Response may be binary in non-stream mode.',
  },
  {
    id: 'audio/transcriptions',
    title: 'Audio STT (Transcriptions)',
    method: 'POST',
    path: '/audio/transcriptions',
    defaults: { model: 'whisper-1', audio_url: 'https://example.com/audio.wav', language: 'en' },
    toBody: (s) => ({ model: s.model || 'whisper-1', audio_url: s.audio_url || '', language: s.language || 'en' }),
    validate: (b) => {
      const errs: string[] = [];
      if (!String(b?.audio_url || '').trim()) errs.push('audio_url is required (server must fetch remotely)');
      return errs;
    },
    schema: {
      type: 'object',
      required: ['audio_url'],
      properties: {
        model: { type: 'string' },
        audio_url: { type: 'string' },
        language: { type: 'string' },
      },
    },
    describe: 'File-based STT is usually multipart; this template uses a remote audio_url for convenience.',
  },
  {
    id: 'evaluations/ocr',
    title: 'Evaluations: OCR (JSON)',
    method: 'POST',
    path: '/evaluations/ocr',
    defaults: { images: [{ url: 'https://example.com/page1.png' }], engine: 'auto' },
    toBody: (s) => ({ images: s.images || [], engine: s.engine || 'auto' }),
    validate: (b) => {
      const errs: string[] = [];
      const images = asArray(b?.images);
      if (images.length === 0) errs.push('images must be a non-empty array');
      return errs;
    },
    schema: {
      type: 'object',
      required: ['images'],
      properties: {
        engine: { type: 'string' },
        images: { type: 'array', items: { type: 'object', properties: { url: { type: 'string' }, b64: { type: 'string' } } } },
      },
    },
    describe: 'OCR evaluation on remote image URLs (or base64). Upload/PDF flow lives elsewhere.',
  },
  {
    id: 'evaluations/geval',
    title: 'Evaluations: G-Eval',
    method: 'POST',
    path: '/evaluations/geval/run',
    defaults: { name: 'response-quality', inputs: [{ id: '1', prompt: 'Say hello', reference: 'Hello' }], model: '' },
    toBody: (s) => ({ name: s.name || 'response-quality', inputs: s.inputs || [], model: s.model || undefined }),
    validate: (b) => {
      const errs: string[] = [];
      const inputs = asArray(b?.inputs);
      if (inputs.length === 0) errs.push('inputs must be a non-empty array');
      return errs;
    },
    schema: {
      type: 'object',
      required: ['name', 'inputs'],
      properties: {
        name: { type: 'string' },
        model: { type: 'string' },
        inputs: { type: 'array', items: { type: 'object' } },
      },
    },
    describe: 'Runs a generic evaluation with a minimal payload (adjust to your backend schema).',
  },
  {
    id: 'users/me',
    title: 'Current User',
    method: 'GET',
    path: '/users/me',
    defaults: {},
    toBody: () => undefined,
    describe: 'Returns information about the current user/session.',
  },
  {
    id: 'rag/capabilities',
    title: 'RAG Capabilities',
    method: 'GET',
    path: '/rag/capabilities',
    defaults: {},
    toBody: () => undefined,
    describe: 'Returns RAG service capabilities and feature flags.',
  },
  {
    id: 'mcp/status',
    title: 'MCP Status',
    method: 'GET',
    path: '/mcp/status',
    defaults: {},
    toBody: () => undefined,
    describe: 'Model Context Protocol server status.',
  },
  {
    id: 'rag/presets',
    title: 'RAG Presets (List)',
    method: 'GET',
    path: '/evaluations/rag/pipeline/presets',
    defaults: {},
    toBody: () => undefined,
    describe: 'Lists available RAG pipeline presets.',
  },
  {
    id: 'chat/completions',
    title: 'Chat Completion',
    method: 'POST',
    path: '/chat/completions',
    defaults: {
      model: 'auto',
      prompt: 'What is the main topic?',
      system: 'You are a helpful assistant.',
      stream: true,
      save_to_db: false,
    },
    toBody: (s) => ({
      model: s.model || 'auto',
      stream: !!s.stream,
      save_to_db: !!s.save_to_db,
      messages: [
        { role: 'system', content: String(s.system || 'You are a helpful assistant.') },
        { role: 'user', content: String(s.prompt || '') },
      ],
    }),
    validate: (b) => {
      const errs: string[] = [];
      if (!b || typeof b !== 'object') errs.push('Body must be an object');
      const messages = asArray(b?.messages);
      if (messages.length === 0) errs.push('messages must be a non-empty array');
      for (let i = 0; i < messages.length; i++) {
        const msg = messages[i];
        if (!msg || typeof msg !== 'object' || Array.isArray(msg)) {
          errs.push(`Message ${i + 1} must be an object`);
          continue;
        }
        const msgObj = msg as QuickFormBody;
        if (!msgObj.role || typeof msgObj.role !== 'string') {
          errs.push(`Message ${i + 1} missing valid role`);
        }
        if (msgObj.content === undefined || msgObj.content === null) {
          errs.push(`Message ${i + 1} missing content`);
        }
      }
      if (errs.length > 0) return errs;
      const last = (messages[messages.length - 1] ?? {}) as QuickFormBody;
      if (last.role !== 'user' || !String(last.content || '').trim()) errs.push('Last message must be a non-empty user message');
      const totalLength = messages.reduce((sum: number, msg: { content?: QuickFormValue }) => sum + String(msg?.content || '').length, 0);
      if (totalLength > MAX_TOTAL_MESSAGE_LENGTH) {
        errs.push(`Total message content exceeds maximum length (${MAX_TOTAL_MESSAGE_LENGTH} characters)`);
      }
      const oversizeIndex = messages.findIndex(
        (msg: { content?: QuickFormValue }) => String(msg?.content || '').length > MAX_MESSAGE_LENGTH
      );
      if (oversizeIndex >= 0) {
        errs.push(`Message ${oversizeIndex + 1} exceeds maximum length (${MAX_MESSAGE_LENGTH} characters)`);
      }
      return errs;
    },
    describe: 'OpenAI-compatible chat endpoint with optional streaming and DB persistence.',
    schema: {
      type: 'object',
      required: ['model', 'messages'],
      properties: {
        model: { type: 'string', description: 'Provider/model identifier' },
        stream: { type: 'boolean', description: 'Enable Server-Sent Events streaming' },
        save_to_db: { type: 'boolean', description: 'Persist conversation to database' },
        system: { type: 'string', description: 'System prompt for the assistant' },
        messages: {
          type: 'array',
          items: {
            type: 'object',
            required: ['role', 'content'],
            properties: {
              role: { type: 'string' },
              content: { type: 'string' },
            },
          },
        },
        conversation_id: { type: 'string' },
      },
    },
  },
  {
    id: 'rag/search',
    title: 'Unified RAG Search',
    method: 'POST',
    path: '/rag/search',
    defaults: { query: 'What is the main topic?', top_k: 10, generation: false },
    toBody: (s) => ({
      query: String(s.query || ''),
      top_k: Number(s.top_k || 10),
      enable_generation: !!s.generation,
      // Simple subset of options; advanced UI on search page
      search_mode: 'hybrid',
      hybrid_alpha: 0.7,
      enable_reranking: true,
    }),
    validate: (b) => {
      const errs: string[] = [];
      if (!String(b?.query || '').trim()) errs.push('query is required');
      const tk = Number(b?.top_k || 0);
      if (!Number.isFinite(tk) || tk <= 0 || tk > 100) errs.push('top_k must be between 1 and 100');
      return errs;
    },
    describe: 'Search across your content with a minimal config. Use the Search page for full options.',
    schema: {
      type: 'object',
      required: ['query'],
      properties: {
        query: { type: 'string' },
        top_k: { type: 'integer', minimum: 1, maximum: 100 },
        search_mode: { type: 'string', enum: ['hybrid', 'vector', 'fts'] },
        hybrid_alpha: { type: 'number', minimum: 0, maximum: 1 },
        enable_generation: { type: 'boolean' },
        enable_reranking: { type: 'boolean' },
      },
    },
  },
  {
    id: 'embeddings',
    title: 'Embeddings',
    method: 'POST',
    path: '/embeddings',
    defaults: { model: 'text-embedding-3-small', input: 'hello world' },
    toBody: (s) => ({ model: s.model || 'text-embedding-3-small', input: s.input }),
    validate: (b) => {
      const errs: string[] = [];
      if (!b?.input || (typeof b.input !== 'string' && !Array.isArray(b.input))) errs.push('input must be a string or array');
      return errs;
    },
    describe: 'OpenAI-compatible embeddings endpoint.',
    schema: {
      type: 'object',
      required: ['model', 'input'],
      properties: {
        model: { type: 'string' },
        input: { type: 'string' },
      },
    },
  },
  {
    id: 'media/search',
    title: 'Media Search (POST)',
    method: 'POST',
    path: '/media/search',
    defaults: { query: 'example search', page: 1, per_page: 20 },
    toBody: (s) => ({ query: String(s.query || ''), page: Number(s.page || 1), per_page: Number(s.per_page || 20) }),
    validate: (b) => {
      const errs: string[] = [];
      if (!String(b?.query || '').trim()) errs.push('query is required');
      return errs;
    },
    describe: 'Search ingested media with pagination.',
    schema: {
      type: 'object',
      required: ['query'],
      properties: {
        query: { type: 'string' },
        page: { type: 'integer', minimum: 1 },
        per_page: { type: 'integer', minimum: 1, maximum: 100 },
      },
    },
  },
  {
    id: 'evaluations/response-quality',
    title: 'Evaluations: Response Quality',
    method: 'POST',
    path: '/evaluations/response-quality',
    defaults: { predicted: 'Hello, world!', reference: 'Hello world', criteria: ['fluency','adequacy'] },
    toBody: (s) => ({ predicted: s.predicted, reference: s.reference, criteria: s.criteria || ['fluency','adequacy'] }),
    validate: (b) => {
      const errs: string[] = [];
      if (!String(b?.predicted || '').trim()) errs.push('predicted is required');
      if (!String(b?.reference || '').trim()) errs.push('reference is required');
      return errs;
    },
    schema: {
      type: 'object',
      required: ['predicted','reference'],
      properties: {
        predicted: { type: 'string' },
        reference: { type: 'string' },
        criteria: { type: 'array', items: { type: 'string' } },
      },
    },
    describe: 'Evaluates a prediction against a reference over specified criteria.',
  },
  {
    id: 'evaluations/batch/run',
    title: 'Evaluations: Batch Run',
    method: 'POST',
    path: '/evaluations/batch/run',
    defaults: { tasks: [{ name: 'response-quality', input: { predicted: 'Hello', reference: 'Hello' } }] },
    toBody: (s) => ({ tasks: s.tasks || [] }),
    validate: (b) => {
      const errs: string[] = [];
      const tasks = asArray(b?.tasks);
      if (tasks.length === 0) errs.push('tasks must be non-empty array');
      return errs;
    },
    schema: {
      type: 'object',
      required: ['tasks'],
      properties: {
        tasks: { type: 'array', items: { type: 'object' } },
      },
    },
    describe: 'Runs a batch of evaluation tasks.',
  },
];
