// API Response Types

export interface MediaListItem {
  id: number;
  title: string;
  url: string;
  type: string;
  keywords?: string[];
}

export type MediaItem = MediaListItem;

export interface MediaPagination {
  page: number;
  results_per_page: number;
  total_pages: number;
  total_items: number;
}

export interface MediaListResponse {
  items: MediaListItem[];
  pagination: MediaPagination;
  results?: MediaListItem[];
}

export interface MediaSourceDetail {
  url?: string;
  title: string;
  duration?: number | string;
  type: string;
}

export interface MediaProcessingDetail {
  prompt?: string;
  analysis?: string;
  safe_metadata?: Record<string, unknown>;
  model?: string;
  timestamp_option?: boolean;
}

export interface MediaContentDetail {
  metadata: Record<string, unknown>;
  text: string;
  word_count: number;
}

export interface MediaDetailResponse {
  media_id: number;
  source: MediaSourceDetail;
  processing: MediaProcessingDetail;
  content: MediaContentDetail;
  keywords: string[];
  timestamps: string[];
  versions?: Array<Record<string, unknown>>;
}

export interface SearchResult {
  media_id: number;
  title: string;
  content_snippet: string;
  relevance_score: number;
  metadata?: Record<string, unknown>;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
  search_type: 'title' | 'content' | 'both';
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
}

export interface ChatRequest {
  messages: ChatMessage[];
  model?: string;
  temperature?: number;
  max_tokens?: number;
  stream?: boolean;
}

export interface ChatResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: Array<{
    index: number;
    message: ChatMessage;
    finish_reason: string;
  }>;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

export interface Note {
  id: number;
  title: string;
  content: string;
  tags?: string[];
  created_at: string;
  updated_at: string;
}

export interface Prompt {
  id: number;
  name: string;
  content: string;
  description?: string;
  category?: string;
  tags?: string[];
  created_at: string;
  updated_at: string;
}

export interface TranscriptionRequest {
  file?: File;
  url?: string;
  language?: string;
  model?: string;
}

export interface TranscriptionResponse {
  text: string;
  language?: string;
  duration?: number;
  segments?: Array<{
    start: number;
    end: number;
    text: string;
  }>;
}

export interface ErrorResponse {
  detail: string;
  status_code?: number;
  type?: string;
}

// Pagination params
export interface PaginationParams {
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

// Filter params
export interface FilterParams {
  type?: string;
  tags?: string[];
  date_from?: string;
  date_to?: string;
  author?: string;
}
