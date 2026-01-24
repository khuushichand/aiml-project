// Reading List API types.
// Mirrors Docs/API-related/Reading_List_API.md.

export type ReadingStatus = 'saved' | 'reading' | 'read' | 'archived';
export type ReadingProcessingStatus = 'processing' | 'ready';

export interface ReadingItem {
  id: number;
  media_id?: number | null;
  media_uuid?: string | null;
  title: string;
  url?: string | null;
  canonical_url?: string | null;
  domain?: string | null;
  summary?: string | null;
  notes?: string | null;
  published_at?: string | null;
  status?: ReadingStatus | null;
  processing_status?: ReadingProcessingStatus | null;
  favorite: boolean;
  tags: string[];
  created_at?: string | null;
  updated_at?: string | null;
  read_at?: string | null;
}

export interface ReadingItemDetail extends ReadingItem {
  text?: string | null;
  clean_html?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface ReadingItemsListResponse {
  items: ReadingItem[];
  total: number;
  page: number;
  size: number;
  offset?: number | null;
  limit?: number | null;
}

export interface ReadingSaveRequest {
  url: string;
  title?: string;
  tags?: string[];
  status?: ReadingStatus;
  favorite?: boolean;
  summary?: string;
  notes?: string;
  content?: string;
}

export interface ReadingUpdateRequest {
  status?: ReadingStatus;
  favorite?: boolean;
  tags?: string[];
  notes?: string;
  title?: string;
}

export interface ReadingDeleteResponse {
  status: string;
  item_id: number;
  hard: boolean;
}

export interface ReadingImportResponse {
  source: string;
  imported: number;
  updated: number;
  skipped: number;
  errors: string[];
}

export interface ReadingSummarizeRequest {
  provider?: string;
  model?: string;
  prompt?: string;
  system_prompt?: string;
  temperature?: number;
  recursive?: boolean;
  chunked?: boolean;
}

export interface ReadingCitation {
  item_id: number;
  url?: string | null;
  canonical_url?: string | null;
  title?: string | null;
  source: string;
}

export interface ReadingSummaryResponse {
  item_id: number;
  summary: string;
  provider: string;
  model?: string | null;
  citations: ReadingCitation[];
  generated_at?: string | null;
}

export type ReadingTTSFormat = 'mp3' | 'opus' | 'aac' | 'flac' | 'wav' | 'pcm';
export type ReadingTTSTextSource = 'text' | 'summary' | 'notes';

export interface ReadingTTSRequest {
  model: string;
  voice: string;
  response_format: ReadingTTSFormat;
  stream: boolean;
  speed?: number;
  max_chars?: number;
  text_source?: ReadingTTSTextSource;
}
