import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Button } from '@/components/ui/Button';
import { apiClient, getApiBaseUrl, buildAuthHeaders } from '@/lib/api';
import { getOrCreateSessionId } from '@/lib/session';
import { cn } from '@/lib/utils';
import { streamSSE } from '@/lib/sse';
import { useToast } from '@/components/ui/ToastProvider';
import JsonEditor from '@/components/ui/JsonEditor';
import HotkeysOverlay from '@/components/ui/HotkeysOverlay';
import { ChatComposer } from '@/components/ui/ChatComposer';
import { ChatMessageList, type ChatMessage } from '@/components/ui/ChatMessageList';
import { FeedbackModal, type FeedbackIssueOption } from '@/components/chat/FeedbackModal';
import { useChatSessions, type SessionItem } from '@/hooks/useChatSessions';
import {
  buildChatPayloadMessages,
  ensureSystemMessage,
  mapHistoryMessagesToUi,
  normalizeHistoryMessages,
  toChatMessages,
  type UiMessage,
} from '@/lib/chatTransforms';

interface LLMProvider {
  name: string;
  display_name?: string;
  type?: string;
  models?: string[];
  is_configured?: boolean;
  default_model?: string;
}

interface ProvidersResponse {
  providers?: LLMProvider[];
  default_provider?: string;
  total_configured?: number;
}

interface ConversationListItem {
  id: string;
  character_id?: number;
  title?: string;
  state: string;
  topic_label?: string;
  bm25_norm?: number | null;
  last_modified: string;
  created_at: string;
  message_count: number;
  keywords: string[];
  cluster_id?: string | null;
  source?: string | null;
  external_ref?: string | null;
  version: number;
}

interface ConversationListPagination {
  limit: number;
  offset: number;
  total: number;
  has_more: boolean;
}

interface ConversationListResponse {
  items: ConversationListItem[];
  pagination: ConversationListPagination;
}

interface ConversationTreeNode {
  id: string;
  role: string;
  content: string;
  created_at: string;
  children: ConversationTreeNode[];
  truncated: boolean;
}

interface ConversationTreeResponse {
  conversation: {
    id: string;
    title?: string | null;
    state: string;
    topic_label?: string | null;
    last_modified: string;
  };
  root_threads: ConversationTreeNode[];
  pagination: {
    limit: number;
    offset: number;
    total_root_threads: number;
    has_more: boolean;
  };
  depth_cap: number;
}

interface ChatAnalyticsBucket {
  bucket_start: string;
  topic_label?: string | null;
  state: string;
  count: number;
}

interface ChatAnalyticsResponse {
  buckets: ChatAnalyticsBucket[];
  pagination: {
    limit: number;
    offset: number;
    total: number;
    has_more: boolean;
  };
  bucket_granularity: 'day' | 'week';
}

const DEFAULT_SYSTEM_PROMPT = 'System prompt text';
const DWELL_TIME_THRESHOLD_MS = 3000;
const CONVERSATION_PAGE_LIMIT = 30;
const ANALYTICS_DEFAULT_RANGE_DAYS = 14;

export default function ChatPage() {
  const { show } = useToast();
  const [uiMessages, setUiMessages] = useState<UiMessage[]>([
    { role: 'system', text: DEFAULT_SYSTEM_PROMPT },
  ]);
  const [composerText, setComposerText] = useState('');
  const [model, setModel] = useState('gpt-3.5-turbo');
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [stream, setStream] = useState(true);
  const [sending, setSending] = useState(false);
  const [saveToDb, setSaveToDb] = useState<boolean>(false);
  const abortRef = useRef<AbortController | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [mainTab, setMainTab] = useState<'chat' | 'analytics'>('chat');
  const [conversationItems, setConversationItems] = useState<ConversationListItem[]>([]);
  const [conversationPagination, setConversationPagination] = useState<ConversationListPagination>({
    limit: CONVERSATION_PAGE_LIMIT,
    offset: 0,
    total: 0,
    has_more: false,
  });
  const [conversationLoading, setConversationLoading] = useState(false);
  const [conversationError, setConversationError] = useState<string | null>(null);
  const [conversationQuery, setConversationQuery] = useState('');
  const [conversationState, setConversationState] = useState('all');
  const [conversationTopic, setConversationTopic] = useState('');
  const [conversationKeywords, setConversationKeywords] = useState('');
  const [conversationOrderBy, setConversationOrderBy] = useState<'bm25' | 'recency' | 'hybrid' | 'topic'>('recency');
  const [conversationOffset, setConversationOffset] = useState(0);
  const [treeViewEnabled, setTreeViewEnabled] = useState(false);
  const [treeData, setTreeData] = useState<ConversationTreeResponse | null>(null);
  const [treeLoading, setTreeLoading] = useState(false);
  const [treeError, setTreeError] = useState<string | null>(null);
  const [treeOffset, setTreeOffset] = useState(0);
  const [treeMaxDepth, setTreeMaxDepth] = useState(4);
  const [analyticsBuckets, setAnalyticsBuckets] = useState<ChatAnalyticsBucket[]>([]);
  const [analyticsPagination, setAnalyticsPagination] = useState({
    limit: 100,
    offset: 0,
    total: 0,
    has_more: false,
  });
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);
  const [analyticsGranularity, setAnalyticsGranularity] = useState<'day' | 'week'>('day');
  const [analyticsStartDate, setAnalyticsStartDate] = useState(() => {
    const start = new Date();
    start.setUTCDate(start.getUTCDate() - ANALYTICS_DEFAULT_RANGE_DAYS);
    return start.toISOString().slice(0, 10);
  });
  const [analyticsEndDate, setAnalyticsEndDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [knowledgeSaveById, setKnowledgeSaveById] = useState<Record<string, { status?: string; pending?: boolean }>>({});
  const { addSession, mergeSessions, migrateSessionId, lastSessionIdRef } = useChatSessions();
  const [preset, setPreset] = useState<'creative'|'balanced'|'precise'|'json'>('balanced');
  const [advanced, setAdvanced] = useState<string>('{}');
  const [recentModels, setRecentModels] = useState<string[]>([]);
  const pageSize = 50;
  const treePageLimit = 6;
  const [pageOffset, setPageOffset] = useState(0);
  const [hasMoreHistory, setHasMoreHistory] = useState(false);
  const [currentProvider, setCurrentProvider] = useState<string | undefined>(undefined);
  const [currentModelOnly, setCurrentModelOnly] = useState<string | undefined>(undefined);
  const [scrollLock, setScrollLock] = useState(false);
  const [showJump, setShowJump] = useState(false);
  const [feedbackById, setFeedbackById] = useState<Record<string, { value?: 'up' | 'down'; pending?: boolean }>>({});
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false);
  const [feedbackModalMessage, setFeedbackModalMessage] = useState<ChatMessage | null>(null);
  const [feedbackModalHelpful, setFeedbackModalHelpful] = useState<boolean | null>(null);
  const [feedbackModalRating, setFeedbackModalRating] = useState(0);
  const [feedbackModalIssues, setFeedbackModalIssues] = useState<string[]>([]);
  const [feedbackModalNotes, setFeedbackModalNotes] = useState('');
  const [feedbackModalSubmitting, setFeedbackModalSubmitting] = useState(false);
  const dwellTimerRef = useRef<number | null>(null);
  const dwellSentRef = useRef<Set<string>>(new Set());
  const expandSentRef = useRef<Set<string>>(new Set());
  const [slashMode, setSlashMode] = useState<'system'|'preface'|'replace'>(() => {
    try {
      const s = localStorage.getItem('tldw-slash-mode');
      const v = (s || '').toLowerCase();
      return (v === 'preface' || v === 'replace') ? v : 'system';
    } catch {
      return 'system';
    }
  });
  const chatListRef = useRef<HTMLDivElement | null>(null);
  const suppressAutoScrollRef = useRef(false);
  const onStopStream = useCallback(() => {
    try { abortRef.current?.abort(); } catch {}
  }, []);
  const attachMessageIdToLastAssistant = useCallback((messageId: string) => {
    if (!messageId) return;
    setUiMessages((prev) => {
      const updated = [...prev];
      for (let i = updated.length - 1; i >= 0; i--) {
        const msg = updated[i];
        if (msg?.role === 'assistant' && !msg.messageId) {
          updated[i] = { ...msg, messageId };
          break;
        }
      }
      return updated;
    });
  }, []);
  const attachMessageIdToSystem = useCallback((messageId: string) => {
    if (!messageId) return;
    setUiMessages((prev) => {
      const updated = [...prev];
      for (let i = 0; i < updated.length; i++) {
        const msg = updated[i];
        if (msg?.role === 'system' && !msg.messageId) {
          updated[i] = { ...msg, messageId };
          break;
        }
      }
      return updated;
    });
  }, []);

  const issueOptions: FeedbackIssueOption[] = useMemo(() => ([
    { id: 'incorrect_information', label: 'Incorrect information' },
    { id: 'not_relevant', label: 'Not relevant to my question' },
    { id: 'missing_details', label: 'Missing important details' },
    { id: 'sources_unhelpful', label: 'Sources were unhelpful' },
    { id: 'too_verbose', label: 'Too verbose' },
    { id: 'too_brief', label: 'Too brief' },
    { id: 'other', label: 'Other' },
  ]), []);

  const getLatestUserQuery = useCallback(() => {
    for (let i = uiMessages.length - 1; i >= 0; i--) {
      if (uiMessages[i]?.role === 'user' && uiMessages[i]?.text) {
        return uiMessages[i]?.text || '';
      }
    }
    return '';
  }, [uiMessages]);

  const sendImplicitFeedback = useCallback(async (payload: Record<string, unknown>) => {
    try {
      const query = getLatestUserQuery();
      await apiClient.post('/rag/feedback/implicit', {
        query: query || undefined,
        session_id: getOrCreateSessionId() || undefined,
        conversation_id: conversationId || undefined,
        ...payload,
      });
    } catch {
      // best-effort
    }
  }, [conversationId, getLatestUserQuery]);

  const normalizeText = (value: unknown): string => {
    if (value === null || value === undefined) return '';
    return String(value).trim();
  };

  const buildDocIdFromPayload = (doc: Record<string, any>): string => {
    return (
      normalizeText(doc.id) ||
      normalizeText(doc.doc_id) ||
      normalizeText(doc.document_id) ||
      normalizeText(doc.metadata?.doc_id) ||
      normalizeText(doc.metadata?.document_id) ||
      ''
    );
  };

  const buildChunkIdsFromPayload = (doc: Record<string, any>): string[] => {
    const list = doc.chunk_ids || doc.chunkIds || doc.metadata?.chunk_ids || doc.metadata?.chunkIds;
    const single = doc.chunk_id || doc.chunkId || doc.metadata?.chunk_id || doc.metadata?.chunkId;
    if (Array.isArray(list)) {
      return list.map((id: unknown) => normalizeText(id)).filter(Boolean);
    }
    if (single) {
      return [normalizeText(single)].filter(Boolean);
    }
    return [];
  };

  const buildCorpusFromPayload = (doc: Record<string, any>): string => {
    return (
      normalizeText(doc.corpus) ||
      normalizeText(doc.source) ||
      normalizeText(doc.metadata?.corpus) ||
      normalizeText(doc.metadata?.source) ||
      normalizeText(doc.metadata?.source_name) ||
      ''
    );
  };

  const extractCitationTargets = (payload: unknown) => {
    const docIds = new Set<string>();
    const chunkIds = new Set<string>();
    const corpora = new Set<string>();

    const addDoc = (doc: Record<string, any>) => {
      const docId = buildDocIdFromPayload(doc);
      if (docId) docIds.add(docId);
      buildChunkIdsFromPayload(doc).forEach((id) => chunkIds.add(id));
      const corpus = buildCorpusFromPayload(doc);
      if (corpus) corpora.add(corpus);
    };

    const addCitation = (citation: Record<string, any>) => {
      const docId = normalizeText(citation.doc_id || citation.document_id);
      if (docId) docIds.add(docId);
      const chunkId = normalizeText(citation.chunk_id);
      if (chunkId) chunkIds.add(chunkId);
      const chunkList = citation.chunk_ids;
      if (Array.isArray(chunkList)) {
        chunkList.map((id: unknown) => normalizeText(id)).filter(Boolean).forEach((id: string) => chunkIds.add(id));
      }
    };

    const collectFromContainer = (container: Record<string, any>) => {
      const docs = container.documents || container.results || container.items;
      if (Array.isArray(docs)) {
        docs.filter(Boolean).forEach((doc: Record<string, any>) => addDoc(doc));
      }
      const citations = container.citations;
      if (Array.isArray(citations)) {
        citations.filter(Boolean).forEach((c: Record<string, any>) => addCitation(c));
      }
      const chunkCitations = container.chunk_citations || container.chunkCitations;
      if (Array.isArray(chunkCitations)) {
        chunkCitations.filter(Boolean).forEach((c: Record<string, any>) => addCitation(c));
      }
    };

    if (payload && typeof payload === 'object') {
      collectFromContainer(payload as Record<string, any>);
      const nested = (payload as Record<string, any>).data;
      if (nested && typeof nested === 'object') {
        collectFromContainer(nested);
      }
    }

    return {
      docIds: Array.from(docIds),
      chunkIds: Array.from(chunkIds),
      corpora: Array.from(corpora),
    };
  };

  const collectCitationTargetsForMessage = useCallback((messageId?: string) => {
    if (!messageId) return { docIds: [] as string[], chunkIds: [] as string[], corpus: undefined as string | undefined };
    const idx = uiMessages.findIndex((m) => m.messageId === messageId);
    if (idx < 0) return { docIds: [], chunkIds: [], corpus: undefined };

    let start = -1;
    for (let i = idx - 1; i >= 0; i--) {
      if (uiMessages[i]?.role === 'user') {
        start = i;
        break;
      }
    }
    let end = uiMessages.length;
    for (let i = idx + 1; i < uiMessages.length; i++) {
      if (uiMessages[i]?.role === 'user') {
        end = i;
        break;
      }
    }

    const docIds = new Set<string>();
    const chunkIds = new Set<string>();
    const corpora = new Set<string>();

    for (let i = start + 1; i < end; i++) {
      if (i === idx) continue;
      const msg = uiMessages[i];
      if (msg?.role !== 'tool') continue;
      const raw = msg.tool?.content ?? msg.text ?? '';
      if (!raw) continue;
      try {
        const parsed = JSON.parse(raw);
        const targets = extractCitationTargets(parsed);
        targets.docIds.forEach((id) => docIds.add(id));
        targets.chunkIds.forEach((id) => chunkIds.add(id));
        targets.corpora.forEach((c) => corpora.add(c));
      } catch {
        continue;
      }
    }

    const corpus = corpora.size === 1 ? Array.from(corpora)[0] : undefined;
    return { docIds: Array.from(docIds), chunkIds: Array.from(chunkIds), corpus };
  }, [uiMessages]);

  const getMessageText = useCallback((msg: ChatMessage): string => {
    if (typeof msg.content === 'string') return msg.content;
    return msg.content?.text || '';
  }, []);

  const parseConversationKeywords = useCallback(() => {
    return conversationKeywords
      .split(',')
      .map((kw) => kw.trim())
      .filter(Boolean);
  }, [conversationKeywords]);

  const fetchConversations = useCallback(async (nextOffset: number, append: boolean = false) => {
    setConversationLoading(true);
    setConversationError(null);
    try {
      const params = new URLSearchParams({
        limit: String(CONVERSATION_PAGE_LIMIT),
        offset: String(nextOffset),
        order_by: conversationOrderBy,
      });
      if (conversationQuery.trim()) params.set('query', conversationQuery.trim());
      if (conversationState !== 'all') params.set('state', conversationState);
      if (conversationTopic.trim()) params.set('topic_label', conversationTopic.trim());
      const keywords = parseConversationKeywords();
      keywords.forEach((kw) => params.append('keywords', kw));

      const data = await apiClient.get<ConversationListResponse>(`/chat/conversations?${params.toString()}`);
      setConversationItems((prev) => (append ? [...prev, ...(data?.items || [])] : (data?.items || [])));
      setConversationPagination(data?.pagination || {
        limit: CONVERSATION_PAGE_LIMIT,
        offset: nextOffset,
        total: data?.items?.length || 0,
        has_more: false,
      });
      setConversationOffset(nextOffset);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load conversations';
      setConversationError(message);
    } finally {
      setConversationLoading(false);
    }
  }, [conversationOrderBy, conversationQuery, conversationState, conversationTopic, parseConversationKeywords]);

  const fetchConversationTree = useCallback(async (nextOffset: number) => {
    if (!conversationId) return;
    setTreeLoading(true);
    setTreeError(null);
    try {
      const params = new URLSearchParams({
        limit: String(treePageLimit),
        offset: String(nextOffset),
        max_depth: String(treeMaxDepth),
      });
      const data = await apiClient.get<ConversationTreeResponse>(
        `/chat/conversations/${conversationId}/tree?${params.toString()}`
      );
      setTreeData(data);
      setTreeOffset(nextOffset);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load tree';
      setTreeError(message);
    } finally {
      setTreeLoading(false);
    }
  }, [conversationId, treeMaxDepth, treePageLimit]);

  const fetchAnalytics = useCallback(async (nextOffset: number) => {
    setAnalyticsLoading(true);
    setAnalyticsError(null);
    try {
      const params = new URLSearchParams({
        start_date: analyticsStartDate,
        end_date: analyticsEndDate,
        bucket_granularity: analyticsGranularity,
        limit: String(analyticsPagination.limit),
        offset: String(nextOffset),
      });
      const data = await apiClient.get<ChatAnalyticsResponse>(`/chat/analytics?${params.toString()}`);
      setAnalyticsBuckets(data?.buckets || []);
      setAnalyticsPagination(data?.pagination || {
        limit: analyticsPagination.limit,
        offset: nextOffset,
        total: data?.buckets?.length || 0,
        has_more: false,
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load analytics';
      setAnalyticsError(message);
    } finally {
      setAnalyticsLoading(false);
    }
  }, [analyticsEndDate, analyticsGranularity, analyticsPagination.limit, analyticsStartDate]);

  const handleKnowledgeSave = useCallback(async (msg: ChatMessage) => {
    if (!conversationId || !msg.messageId) {
      show({ title: 'Save unavailable', description: 'Missing conversation or message ID.', variant: 'warning' });
      return;
    }
    const snippet = getMessageText(msg).trim();
    if (!snippet) {
      show({ title: 'Save skipped', description: 'No message content found.', variant: 'warning' });
      return;
    }
    setKnowledgeSaveById((prev) => ({
      ...prev,
      [msg.messageId as string]: { status: prev[msg.messageId as string]?.status, pending: true },
    }));
    try {
      const res = await apiClient.post<any>('/chat/knowledge/save', {
        conversation_id: conversationId,
        message_id: msg.messageId,
        snippet,
        export_to: 'none',
      });
      const status = res?.export_status || 'not_requested';
      setKnowledgeSaveById((prev) => ({
        ...prev,
        [msg.messageId as string]: { status, pending: false },
      }));
      show({ title: 'Saved snippet', description: `Export status: ${status}`, variant: 'success' });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Save failed';
      setKnowledgeSaveById((prev) => ({
        ...prev,
        [msg.messageId as string]: { status: prev[msg.messageId as string]?.status, pending: false },
      }));
      show({ title: 'Save failed', description: message, variant: 'danger' });
    }
  }, [conversationId, getMessageText, show]);

  const handleCopyWithCitations = useCallback(async (msg: ChatMessage) => {
    const messageText = getMessageText(msg);
    if (!messageText) return;
    try {
      await navigator.clipboard.writeText(messageText);
      show({ title: 'Answer with citations copied', variant: 'success' });
      const targets = collectCitationTargetsForMessage(msg.messageId);
      void sendImplicitFeedback({
        event_type: 'citation_used',
        message_id: msg.messageId || undefined,
        doc_id: targets.docIds.length === 1 ? targets.docIds[0] : undefined,
        chunk_ids: targets.chunkIds.length ? targets.chunkIds : undefined,
        impression_list: targets.docIds.length ? targets.docIds : undefined,
        corpus: targets.corpus,
      });
    } catch {
      show({ title: 'Copy failed', variant: 'danger' });
    }
  }, [collectCitationTargetsForMessage, getMessageText, sendImplicitFeedback, show]);

  const openFeedbackModal = useCallback((msg: ChatMessage, helpful: boolean | null) => {
    setFeedbackModalMessage(msg);
    setFeedbackModalHelpful(helpful);
    setFeedbackModalRating(0);
    setFeedbackModalIssues([]);
    setFeedbackModalNotes('');
    setFeedbackModalOpen(true);
  }, []);

  const closeFeedbackModal = useCallback(() => {
    setFeedbackModalOpen(false);
  }, []);

  const webAssetBase = useMemo(() => {
    // Prefer explicit env override for flexibility across environments
    const envBase = (process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || '').toString().trim();
    if (envBase) {
      return envBase.replace(/\/$/, '');
    }
    // Derive from API base URL if available (strip trailing /api/vN)
    try {
      const apiBase = getApiBaseUrl();
      if (apiBase && typeof apiBase === 'string') {
        const host = apiBase.replace(/\/(api|API)\/v\d+$/, '');
        if (host) return host;
      }
    } catch {}
    // Fallback to browser origin when running client-side
    try {
      if (typeof window !== 'undefined' && window.location?.origin) {
        return window.location.origin;
      }
    } catch {}
    // Final fallback for local development
    return 'http://127.0.0.1:8000';
  }, []);
  const providerIconUrl = useCallback((prov?: string) => {
    if (!prov) return '';
    const p = String(prov).toLowerCase();
    const known = new Set(['openai','anthropic','google','groq','mistral','huggingface','ollama']);
    if (!known.has(p)) return '';
    return `${webAssetBase}/webui/img/providers/${p}.svg`;
  }, [webAssetBase]);

  // Recent models helpers
  const loadRecentModels = () => {
    try { const s = localStorage.getItem('tldw-recent-models'); if (s) setRecentModels(JSON.parse(s)); } catch {}
  };
  const pushRecentModel = (m: string) => {
    try {
      const key = 'tldw-recent-models';
      const cur: string[] = JSON.parse(localStorage.getItem(key) || '[]');
      const next = [m, ...cur.filter((x) => x !== m)].slice(0, 8);
      localStorage.setItem(key, JSON.stringify(next));
      setRecentModels(next);
    } catch {}
  };
  useEffect(() => { loadRecentModels(); }, []);
  useEffect(() => {
    try { localStorage.setItem('tldw-slash-mode', slashMode); } catch {}
  }, [slashMode]);

  const startNewChat = () => {
    setConversationId(null);
    setUiMessages([{ role: 'system', text: DEFAULT_SYSTEM_PROMPT }]);
    setPageOffset(0);
    setHasMoreHistory(false);
    setFeedbackById({});
    setTreeViewEnabled(false);
    setTreeData(null);
  };

  // Load saved messages when switching to a known conversation
  // Load messages for a conversation (paged, include tools)
  const loadConversationPage = useCallback(async (cid: string, offset: number) => {
    const qs = new URLSearchParams({
      limit: String(pageSize),
      offset: String(offset),
      format_for_completions: 'true',
      include_character_context: 'true',
      include_message_ids: 'true',
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const data = await apiClient.get<any>(`/chats/${cid}/messages?${qs.toString()}`);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const msgs: any[] = Array.isArray(data?.messages) ? data.messages : [];
    const mapped = mapHistoryMessagesToUi(msgs);
    const normalized = normalizeHistoryMessages(mapped, offset);
    setUiMessages((prev) => {
      if (offset > 0) {
        return [...normalized, ...prev];
      }
      return ensureSystemMessage(normalized, DEFAULT_SYSTEM_PROMPT);
    });
    setHasMoreHistory(msgs.length === pageSize);
  }, [pageSize]);

  // Migrate session id from temporary local-* to server conversation id when assigned
  useEffect(() => {
    const oldId = lastSessionIdRef.current;
    if (!oldId) return;
    if (!conversationId) return;
    if (oldId.startsWith('local-') && oldId !== conversationId) {
      migrateSessionId(oldId, conversationId);
    }
  }, [conversationId, migrateSessionId, lastSessionIdRef]);

  const sendMessage = async (messageText?: string) => {
    const text = messageText ?? composerText;
        if (!text.trim() || sending) return;
        show({ title: 'Sending message…', variant: 'info' });
    const lastAssistantName = (() => {
      for (let i = uiMessages.length - 1; i >= 0; i--) {
        if (uiMessages[i]?.role === 'assistant' && uiMessages[i]?.name) {
          return uiMessages[i]?.name;
        }
      }
      return undefined;
    })();
    const newUi = [
      ...uiMessages,
      { role: 'user', text: text.trim() } as UiMessage,
      { role: 'assistant', text: '', name: lastAssistantName } as UiMessage,
    ];
        setUiMessages(newUi);
        setComposerText('');
        setSending(true);

    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let payload: any = {
        model,
        stream,
        save_to_db: saveToDb,
        messages: buildChatPayloadMessages(newUi),
      };
      try { const extra = JSON.parse(advanced || '{}'); if (extra && typeof extra === 'object') payload = { ...payload, ...extra }; } catch {}
      payload.slash_command_injection_mode = slashMode;
      if (conversationId) payload.conversation_id = conversationId;
      const body = JSON.stringify(payload);

      if (stream) {
        const url = `${getApiBaseUrl()}/chat/completions`;
        const headers = { ...buildAuthHeaders('POST', 'application/json'), Accept: 'text/event-stream' };
        const controller = new AbortController();
        abortRef.current = controller;

        let acc = '';
        await streamSSE(url, { method: 'POST', headers, body, signal: controller.signal }, (delta) => {
          acc += delta;
          setUiMessages((prev) => {
            const updated = [...prev];
            // Find the most recent assistant message from the end
            let idx = -1;
            for (let i = updated.length - 1; i >= 0; i--) {
              if (updated[i]?.role === 'assistant') { idx = i; break; }
            }
            if (idx >= 0) {
              updated[idx] = { ...(updated[idx] as UiMessage), text: acc } as UiMessage;
            } else {
              updated.push({ role: 'assistant', text: acc } as UiMessage);
            }
            return updated;
          });
        }, (json) => {
          // Capture metadata conversation_id and provider/model
          const metaConv = json?.conversation_id || json?.tldw_metadata?.conversation_id;
          if (metaConv && !conversationId) setConversationId(String(metaConv));
          const prov = json?.provider || json?.tldw_provider || json?.tldw_metadata?.provider;
          const mdl = json?.model || json?.tldw_model || json?.tldw_metadata?.model;
          if (prov) setCurrentProvider(String(prov));
          if (mdl) setCurrentModelOnly(String(mdl));
          const streamMessageId = json?.tldw_message_id;
          if (streamMessageId) attachMessageIdToLastAssistant(String(streamMessageId));
          const streamSystemMessageId = json?.tldw_system_message_id;
          if (streamSystemMessageId) attachMessageIdToSystem(String(streamSystemMessageId));
          // Streamed tool calls / results
          const dTools = json?.choices?.[0]?.delta?.tool_calls;
          if (Array.isArray(dTools) && dTools.length) {
            // Reflect tool call names inline as a small card
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const tcNames = dTools.map((tc: any) => tc?.function?.name).filter(Boolean);
            if (tcNames.length) {
              setUiMessages((prev) => [...prev, { role: 'tool', tool: { name: tcNames.join(', '), content: '' } }]);
            }
          }
          const dResults = json?.tool_results || json?.tldw_tool_results;
          if (Array.isArray(dResults) && dResults.length) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            dResults.forEach((r: any) => {
              const name = r?.name || r?.tool || 'tool';
              const content = typeof r?.content === 'string' ? r.content : JSON.stringify(r?.content ?? r);
              const toolCallId = r?.tool_call_id || r?.id;
              setUiMessages((prev) => [
                ...prev,
                { role: 'tool', tool: { id: toolCallId, name, content } },
              ]);
            });
          }
        }, () => {
          // On done, optionally store session reference
          const firstUser = newUi.find((m) => m.role === 'user');
          const title = (firstUser?.text || '').slice(0, 60) || 'Chat';
          const id = conversationId || getOrCreateSessionId();
          if (id) {
            addSession({ id, title, model, created_at: new Date().toISOString() });
          }
          if (saveToDb) {
            refreshConversations();
          }
        });
        show({ title: 'Response complete', variant: 'success' });
      } else {
        // Non-streaming
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const res = await apiClient.post<any>('/chat/completions', JSON.parse(body));
        const text = res?.choices?.[0]?.message?.content || '';
        if (res?.tldw_conversation_id && !conversationId) {
          setConversationId(String(res.tldw_conversation_id));
        }
        if (res?.tldw_message_id) {
          attachMessageIdToLastAssistant(String(res.tldw_message_id));
        }
        if (res?.tldw_system_message_id) {
          attachMessageIdToSystem(String(res.tldw_system_message_id));
        }
        setUiMessages((prev) => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
            updated[lastIdx] = { ...updated[lastIdx], text } as UiMessage;
          }
          return updated;
        });
        const firstUser = newUi.find((m) => m.role === 'user');
        const title = (firstUser?.text || '').slice(0, 60) || 'Chat';
        const id = res?.tldw_conversation_id || conversationId || getOrCreateSessionId();
        if (id) {
          addSession({ id: String(id), title, model, created_at: new Date().toISOString() });
        }
        if (saveToDb) {
          refreshConversations();
        }
        show({ title: 'Response ready', variant: 'success' });
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      setUiMessages((prev) => [
        ...prev,
        { role: 'assistant', text: `Error: ${message}`, error: true } as UiMessage,
      ]);
      show({ title: 'Chat error', description: message, variant: 'danger' });
    } finally {
      setSending(false);
      abortRef.current = null;
    }
  };

  const handleFeedback = useCallback(async (messageId: string, helpful: boolean) => {
    if (!messageId) return;
    const nextValue = helpful ? 'up' : 'down';
    const current = feedbackById[messageId];
    if (current?.pending || current?.value === nextValue) return;
    const previousValue = current?.value;

    setFeedbackById((prev) => ({
      ...prev,
      [messageId]: { value: nextValue, pending: true },
    }));

    try {
      await apiClient.post('/feedback/explicit', {
        conversation_id: conversationId || undefined,
        message_id: messageId,
        feedback_type: 'helpful',
        helpful,
        session_id: getOrCreateSessionId() || undefined,
      });
      setFeedbackById((prev) => ({
        ...prev,
        [messageId]: { value: nextValue, pending: false },
      }));
      show({ title: 'Feedback sent', variant: 'success' });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Could not submit feedback';
      setFeedbackById((prev) => ({
        ...prev,
        [messageId]: { value: previousValue, pending: false },
      }));
      show({ title: 'Feedback failed', description: message, variant: 'danger' });
    }
  }, [conversationId, feedbackById, show]);

  const handleDetailedFeedbackSubmit = useCallback(async () => {
    const messageId = feedbackModalMessage?.messageId;
    if (!messageId) return;
    const trimmedNotes = feedbackModalNotes.trim();
    const hasRating = feedbackModalRating > 0;
    const clampedRating = Math.min(5, Math.max(1, feedbackModalRating));
    const hasIssues = feedbackModalIssues.length > 0;
    const hasNotes = trimmedNotes.length > 0;
    const helpful = feedbackModalHelpful;
    if (!hasRating && !hasIssues && !hasNotes && helpful === null) {
      show({ title: 'Add a rating or note', variant: 'warning' });
      return;
    }

    let feedbackType: 'helpful' | 'relevance' | 'report' = 'helpful';
    if (hasRating) {
      feedbackType = 'relevance';
    } else if (hasIssues || hasNotes) {
      feedbackType = 'report';
    }

    setFeedbackModalSubmitting(true);
    try {
      await apiClient.post('/feedback/explicit', {
        conversation_id: conversationId || undefined,
        message_id: messageId,
        feedback_type: feedbackType,
        helpful: helpful ?? undefined,
        relevance_score: hasRating ? clampedRating : undefined,
        issues: hasIssues ? feedbackModalIssues : undefined,
        user_notes: hasNotes ? trimmedNotes : undefined,
        session_id: getOrCreateSessionId() || undefined,
      });
      if (helpful !== null) {
        setFeedbackById((prev) => ({
          ...prev,
          [messageId]: { value: helpful ? 'up' : 'down', pending: false },
        }));
      }
      show({ title: 'Feedback sent', variant: 'success' });
      closeFeedbackModal();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Could not submit feedback';
      show({ title: 'Feedback failed', description: message, variant: 'danger' });
    } finally {
      setFeedbackModalSubmitting(false);
    }
  }, [
    conversationId,
    feedbackModalHelpful,
    feedbackModalIssues,
    feedbackModalMessage,
    feedbackModalNotes,
    feedbackModalRating,
    closeFeedbackModal,
    show,
  ]);

  useEffect(() => {
    const loadProviders = async () => {
      setLoadingProviders(true);
      try {
        const resp = await apiClient.get<ProvidersResponse>('/llm/providers');
        const list = resp?.providers || [];
        setProviders(list);
        // Pick default provider/model if exposed
        const defProvName = resp?.default_provider;
        const defProv = list.find((p) => p.name === defProvName && p.is_configured !== false) || list.find((p) => p.is_configured !== false);
        if (defProv && defProv.models && defProv.models.length > 0) {
          const defModel = defProv.default_model || defProv.models[0];
          const full = `${defProv.name}/${defModel}`;
          setModel(full);
          pushRecentModel(full);
        }
      } catch {
        // keep current model
      } finally {
        setLoadingProviders(false);
      }
    };
    loadProviders();
  }, []);

  const applyPreset = (p: typeof preset) => {
    setPreset(p);
    if (p === 'creative') setAdvanced(JSON.stringify({ temperature: 1.0, top_p: 1.0, presence_penalty: 0.2 }, null, 2));
    else if (p === 'precise') setAdvanced(JSON.stringify({ temperature: 0.2, top_p: 0.9 }, null, 2));
    else if (p === 'json') setAdvanced(JSON.stringify({ response_format: { type: 'json_object' } }, null, 2));
    else setAdvanced(JSON.stringify({ temperature: 0.7, top_p: 1.0 }, null, 2));
  };

  // Chat hotkeys: Cmd/Ctrl+Enter send, Esc abort stream, Cmd/Ctrl+Shift+J copy last assistant message
  useEffect(() => {
    const onKey = async (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        await sendMessage();
      }
      if (e.key === 'Escape') {
        abortRef.current?.abort();
        show({ title: 'Streaming aborted', variant: 'info' });
      }
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === 'j') {
        try {
          const last = [...uiMessages].reverse().find((m) => m.role === 'assistant');
          if (last?.text) {
            await navigator.clipboard.writeText(last.text);
            show({ title: 'Assistant reply copied', variant: 'success' });
            void sendImplicitFeedback({
              event_type: 'copy',
              message_id: last.messageId || undefined,
            });
          }
        } catch {}
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uiMessages, sendMessage, sendImplicitFeedback, show]);

  // Persist current chat model for use across pages (e.g., Media Analyze)
  useEffect(() => {
    try { localStorage.setItem('tldw-current-chat-model', model); } catch {}
    pushRecentModel(model);
  }, [model]);

  // Prefill message from Media page
  useEffect(() => {
    try {
      const raw = localStorage.getItem('tldw-chat-prefill');
      if (raw) {
        const data = JSON.parse(raw);
        // Only prefill if starting fresh
        const userCount = uiMessages.filter((m) => m.role === 'user').length;
        if (userCount === 0 && !conversationId && data?.message) {
          setUiMessages([
            { role: 'system', text: DEFAULT_SYSTEM_PROMPT },
            { role: 'user', text: String(data.message) }
          ] as UiMessage[]);
        }
      }
      localStorage.removeItem('tldw-chat-prefill');
    } catch {
      // ignore
    }
    // run once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchConversations(0, false);
  }, [fetchConversations]);

  // Load sessions from server (first page)
  useEffect(() => {
    const fetchSessions = async () => {
      try {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const data = await apiClient.get<any>('/chats?limit=30&offset=0');
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const list: any[] = Array.isArray(data?.chats) ? data.chats : [];
        const mapped: SessionItem[] = list.map((c) => ({
          id: c.id,
          title: c.title || 'Chat',
          model: c.model || model,
          created_at: c.created_at || new Date().toISOString(),
        }));
        mergeSessions(mapped);
      } catch {}
    };
    fetchSessions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // When conversationId changes, reset view and load first page
  useEffect(() => {
    if (!conversationId) return;
    setUiMessages([{ role: 'system', text: DEFAULT_SYSTEM_PROMPT }]);
    setPageOffset(0);
    setFeedbackById({});
    setTreeData(null);
    setTreeOffset(0);
    (async () => {
      await loadConversationPage(conversationId, 0);
      setPageOffset((p) => p + pageSize);
    })();
  }, [conversationId, loadConversationPage, pageSize]);

  useEffect(() => {
    if (conversationId) return;
    if (treeViewEnabled) setTreeViewEnabled(false);
  }, [conversationId, treeViewEnabled]);

  useEffect(() => {
    if (!treeViewEnabled || !conversationId) return;
    fetchConversationTree(0);
  }, [conversationId, fetchConversationTree, treeViewEnabled]);

  useEffect(() => {
    if (mainTab !== 'analytics') return;
    fetchAnalytics(0);
  }, [analyticsEndDate, analyticsGranularity, analyticsStartDate, fetchAnalytics, mainTab]);

  const handleLoadOlder = async () => {
    if (!conversationId) return;
    suppressAutoScrollRef.current = true;
    await loadConversationPage(conversationId, pageOffset);
    setPageOffset((p) => p + pageSize);
    // Re-enable auto-scroll after render tick
    setTimeout(() => { suppressAutoScrollRef.current = false; }, 0);
  };

  const loadMoreConversations = () => {
    if (conversationLoading || !conversationPagination.has_more) return;
    fetchConversations(conversationOffset + CONVERSATION_PAGE_LIMIT, true);
  };

  const refreshConversations = () => {
    fetchConversations(0, false);
  };

  const loadNextTreePage = () => {
    if (!treeData?.pagination?.has_more || treeLoading) return;
    fetchConversationTree(treeOffset + treePageLimit);
  };

  const loadPrevTreePage = () => {
    if (treeOffset <= 0 || treeLoading) return;
    fetchConversationTree(Math.max(treeOffset - treePageLimit, 0));
  };

  const loadNextAnalyticsPage = () => {
    if (!analyticsPagination.has_more || analyticsLoading) return;
    fetchAnalytics(analyticsPagination.offset + analyticsPagination.limit);
  };

  const loadPrevAnalyticsPage = () => {
    if (analyticsPagination.offset <= 0 || analyticsLoading) return;
    fetchAnalytics(Math.max(analyticsPagination.offset - analyticsPagination.limit, 0));
  };

  const chatuiMessages: ChatMessage[] = useMemo(() => {
    const providerFromModel = (() => {
      try { return (model || '').split('/')[0] || undefined; } catch { return undefined; }
    })();
    const avatarProvider = currentProvider || providerFromModel;
    const avatarUrl = providerIconUrl(avatarProvider);
    return toChatMessages(uiMessages, avatarUrl);
  }, [uiMessages, model, currentProvider, providerIconUrl]);

  const maxAnalyticsCount = useMemo(() => {
    const counts = analyticsBuckets.map((b) => b.count);
    return Math.max(1, ...counts);
  }, [analyticsBuckets]);

  const renderTreeNode = useCallback((node: ConversationTreeNode, depth: number) => {
    const indent = Math.min(depth, 8) * 12;
    return (
      <div key={node.id} style={{ marginLeft: indent }} className="mb-2">
        <div className="rounded border border-gray-200 bg-gray-50 px-2 py-1 text-xs">
          <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-gray-500">
            <span>{node.role}</span>
            <span>{new Date(node.created_at).toLocaleString()}</span>
          </div>
          <div className="mt-1 whitespace-pre-wrap text-gray-700">{node.content || '(empty message)'}</div>
          {node.truncated && (
            <div className="mt-1 text-[10px] text-amber-600">Truncated (depth or message cap)</div>
          )}
        </div>
        {node.children?.map((child) => renderTreeNode(child, depth + 1))}
      </div>
    );
  }, []);

  const renderFeedbackFooter = useCallback((msg: ChatMessage) => {
    if (!msg.messageId) return null;
    if (!msg.role || msg.role === 'user') return null;
    const messageText = getMessageText(msg);
    const hasCitations = /(^|\n)\s*(Sources|Citations|References)\b/i.test(messageText);
    const state = feedbackById[msg.messageId] || {};
    const pending = state.pending;
    const upSelected = state.value === 'up';
    const downSelected = state.value === 'down';
    const saveState = knowledgeSaveById[msg.messageId] || {};
    const savePending = saveState.pending;
    const saveStatus = saveState.status;

    const baseButton = 'rounded border px-2 py-0.5 text-[11px] transition';
    const upClasses = cn(
      baseButton,
      upSelected ? 'border-blue-400 bg-blue-50 text-blue-700' : 'border-gray-300 text-gray-600 hover:bg-gray-100',
      pending && 'opacity-60 cursor-not-allowed'
    );
    const downClasses = cn(
      baseButton,
      downSelected ? 'border-red-400 bg-red-50 text-red-700' : 'border-gray-300 text-gray-600 hover:bg-gray-100',
      pending && 'opacity-60 cursor-not-allowed'
    );

    return (
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-gray-500">
        <span>Was this helpful?</span>
        <button
          type="button"
          className={upClasses}
          onClick={() => handleFeedback(msg.messageId as string, true)}
          disabled={pending}
          aria-label="Send helpful feedback"
        >
          Yes
        </button>
        <button
          type="button"
          className={downClasses}
          onClick={() => handleFeedback(msg.messageId as string, false)}
          disabled={pending}
          aria-label="Send not helpful feedback"
        >
          No
        </button>
        <button
          type="button"
          className="rounded border border-gray-300 px-2 py-0.5 text-[11px] text-gray-600 hover:bg-gray-100"
          onClick={() => openFeedbackModal(msg, null)}
          aria-label="Open feedback details"
        >
          Details
        </button>
        <button
          type="button"
          className={cn(
            baseButton,
            savePending
              ? 'border-gray-200 bg-gray-50 text-gray-400'
              : 'border-emerald-300 text-emerald-700 hover:bg-emerald-50'
          )}
          onClick={() => handleKnowledgeSave(msg)}
          disabled={pending || savePending || !conversationId}
          aria-label="Save snippet to notes"
          title={conversationId ? 'Save snippet to Notes' : 'Save requires a saved conversation'}
        >
          Save snippet
        </button>
        {saveStatus && (
          <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] text-emerald-700">
            Export: {saveStatus}
          </span>
        )}
        {hasCitations && (
          <button
            type="button"
            className="rounded border border-gray-300 px-2 py-0.5 text-[11px] text-gray-600 hover:bg-gray-100"
            onClick={() => handleCopyWithCitations(msg)}
            aria-label="Copy with citations"
          >
            Copy with citations
          </button>
        )}
      </div>
    );
  }, [
    conversationId,
    feedbackById,
    getMessageText,
    handleCopyWithCitations,
    handleFeedback,
    handleKnowledgeSave,
    knowledgeSaveById,
    openFeedbackModal,
  ]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const lastAssistant = [...uiMessages].reverse().find((m) => m.role === 'assistant' && m.messageId && m.text);
    if (!lastAssistant?.messageId || !lastAssistant.text) return;
    if (dwellSentRef.current.has(lastAssistant.messageId)) return;

    if (dwellTimerRef.current) {
      window.clearTimeout(dwellTimerRef.current);
    }

    dwellTimerRef.current = window.setTimeout(() => {
      if (!lastAssistant.messageId || dwellSentRef.current.has(lastAssistant.messageId)) return;
      dwellSentRef.current.add(lastAssistant.messageId);
      void sendImplicitFeedback({
        event_type: 'dwell_time',
        dwell_ms: DWELL_TIME_THRESHOLD_MS,
        message_id: lastAssistant.messageId,
      });
    }, DWELL_TIME_THRESHOLD_MS);

    return () => {
      if (dwellTimerRef.current) {
        window.clearTimeout(dwellTimerRef.current);
        dwellTimerRef.current = null;
      }
    };
  }, [sendImplicitFeedback, uiMessages]);

  const atBottom = (el: HTMLElement | null): boolean => {
    if (!el) return true;
    const epsilon = 4;
    return (el.scrollHeight - el.scrollTop - el.clientHeight) <= epsilon;
  };

  useEffect(() => {
    if (treeViewEnabled) return;
    const el = chatListRef.current;
    if (!el) return;
    if (!scrollLock && !suppressAutoScrollRef.current) {
      el.scrollTop = el.scrollHeight;
      setShowJump(false);
    } else {
      setShowJump(!atBottom(el));
    }
  }, [scrollLock, treeViewEnabled, uiMessages]);

  const onScrollContainer = () => {
    if (treeViewEnabled) return;
    const el = chatListRef.current;
    if (!el) return;
    setShowJump(!atBottom(el));
  };

  const jumpToLatest = () => {
    const el = chatListRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    setShowJump(false);
  };

  const onComposerSend = async (_type: string, content: string) => {
    if (!content) return;
    setComposerText('');
    await sendMessage(content);
  };

  return (
    <Layout>
      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-4 md:grid-cols-4 transition-all duration-150">
        <HotkeysOverlay
          entries={[
            { keys: 'Cmd/Ctrl+Enter', description: 'Send message' },
            { keys: 'Esc', description: 'Abort streaming' },
            { keys: 'Cmd/Ctrl+Shift+J', description: 'Copy last assistant reply' },
            { keys: 'Cmd/Ctrl+Shift+C', description: 'Copy cURL (on pages that have it)' },
            { keys: '?', description: 'Toggle this help' },
          ]}
        />
        <div className="md:col-span-1 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-800">Conversations</h2>
            <Button variant="secondary" onClick={startNewChat}>New Chat</Button>
          </div>
          <div className="rounded-md border bg-white p-3 h-[72vh] overflow-y-auto">
            <div className="mb-3 space-y-2 text-xs text-gray-600">
              <div className="flex items-center gap-2">
                <input
                  className="w-full rounded border border-gray-300 px-2 py-1 text-xs"
                  placeholder="Search titles"
                  value={conversationQuery}
                  onChange={(e) => setConversationQuery(e.target.value)}
                />
                <Button variant="secondary" onClick={refreshConversations}>Refresh</Button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <select
                  className="w-full rounded border border-gray-300 px-2 py-1 text-xs"
                  value={conversationState}
                  onChange={(e) => setConversationState(e.target.value)}
                >
                  <option value="all">All states</option>
                  <option value="in-progress">In-progress</option>
                  <option value="resolved">Resolved</option>
                  <option value="backlog">Backlog</option>
                  <option value="non-viable">Non-viable</option>
                </select>
                <input
                  className="w-full rounded border border-gray-300 px-2 py-1 text-xs"
                  placeholder="Topic label"
                  value={conversationTopic}
                  onChange={(e) => setConversationTopic(e.target.value)}
                />
              </div>
              <input
                className="w-full rounded border border-gray-300 px-2 py-1 text-xs"
                placeholder="Keywords (comma-separated)"
                value={conversationKeywords}
                onChange={(e) => setConversationKeywords(e.target.value)}
              />
              <div className="flex flex-wrap gap-2">
                {(['recency', 'bm25', 'hybrid', 'topic'] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    className={cn(
                      'rounded-full border px-2 py-0.5 text-[11px] uppercase tracking-wide',
                      conversationOrderBy === mode
                        ? 'border-blue-400 bg-blue-50 text-blue-700'
                        : 'border-gray-300 text-gray-600 hover:bg-gray-100'
                    )}
                    onClick={() => setConversationOrderBy(mode)}
                  >
                    {mode}
                  </button>
                ))}
              </div>
              <div className="flex items-center justify-between text-[11px] text-gray-500">
                <span>Showing {conversationItems.length} of {conversationPagination.total}</span>
                {conversationLoading && <span>Loading…</span>}
              </div>
            </div>
            {conversationError && (
              <div className="mb-2 text-xs text-red-600">{conversationError}</div>
            )}
            <ul className="text-sm divide-y">
              {conversationItems.map((item) => (
                <li key={item.id} className={cn('py-2', conversationId === item.id && 'bg-blue-50/40')}>
                  <button className="w-full text-left" onClick={() => setConversationId(item.id)}>
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-medium truncate">{item.title || 'Chat'}</div>
                      {typeof item.bm25_norm === 'number' && (
                        <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] text-blue-700">
                          {Math.round(item.bm25_norm * 100)}%
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1 text-[11px]">
                      <span className="rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 uppercase tracking-wide text-gray-600">
                        {item.state || 'in-progress'}
                      </span>
                      {item.topic_label && (
                        <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-emerald-700">
                          {item.topic_label}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-xs text-gray-500 truncate">
                      {item.message_count} msgs • {new Date(item.last_modified).toLocaleString()}
                    </div>
                  </button>
                </li>
              ))}
              {!conversationItems.length && !conversationLoading && (
                <li className="py-4 text-center text-xs text-gray-500">No conversations found.</li>
              )}
            </ul>
            <div className="mt-3 flex items-center justify-between text-xs text-gray-600">
              <span>Offset: {conversationPagination.offset}</span>
              <Button variant="secondary" onClick={loadMoreConversations} disabled={!conversationPagination.has_more || conversationLoading}>
                Load more
              </Button>
            </div>
          </div>
        </div>

        <div className="md:col-span-3 rounded-md border bg-white p-4 flex flex-col h-[80vh]">
          <div className="mb-3 flex items-center justify-between">
            <div className="inline-flex rounded border border-gray-200 bg-gray-50 p-1 text-xs">
              <button
                type="button"
                className={cn(
                  'rounded px-3 py-1',
                  mainTab === 'chat' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-800'
                )}
                onClick={() => setMainTab('chat')}
              >
                Chat
              </button>
              <button
                type="button"
                className={cn(
                  'rounded px-3 py-1',
                  mainTab === 'analytics' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-800'
                )}
                onClick={() => setMainTab('analytics')}
              >
                Analytics
              </button>
            </div>
            {mainTab === 'chat' && (
              <div className="flex items-center gap-3 text-xs text-gray-600">
                <label className="inline-flex items-center space-x-2">
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={treeViewEnabled}
                    onChange={(e) => setTreeViewEnabled(e.target.checked)}
                    disabled={!conversationId}
                  />
                  <span>Tree view</span>
                </label>
                {treeViewEnabled && (
                  <div className="flex items-center gap-2">
                    <span>Depth</span>
                    <select
                      className="rounded border border-gray-300 px-2 py-1 text-xs"
                      value={treeMaxDepth}
                      onChange={(e) => setTreeMaxDepth(Number(e.target.value))}
                    >
                      {[2, 3, 4, 5, 6].map((depth) => (
                        <option key={depth} value={depth}>{depth}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            )}
          </div>
          {mainTab === 'analytics' ? (
            <div className="flex min-h-0 flex-1 flex-col">
              <div className="mb-3 grid grid-cols-2 gap-3 text-xs text-gray-600 md:grid-cols-4">
                <div>
                  <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-gray-500">Start</label>
                  <input
                    type="date"
                    className="w-full rounded border border-gray-300 px-2 py-1 text-xs"
                    value={analyticsStartDate}
                    onChange={(e) => setAnalyticsStartDate(e.target.value)}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-gray-500">End</label>
                  <input
                    type="date"
                    className="w-full rounded border border-gray-300 px-2 py-1 text-xs"
                    value={analyticsEndDate}
                    onChange={(e) => setAnalyticsEndDate(e.target.value)}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-gray-500">Granularity</label>
                  <select
                    className="w-full rounded border border-gray-300 px-2 py-1 text-xs"
                    value={analyticsGranularity}
                    onChange={(e) => setAnalyticsGranularity(e.target.value as 'day' | 'week')}
                  >
                    <option value="day">Day</option>
                    <option value="week">Week</option>
                  </select>
                </div>
                <div className="flex items-end justify-end">
                  <Button variant="secondary" onClick={() => fetchAnalytics(0)}>Refresh</Button>
                </div>
              </div>
              {analyticsError && (
                <div className="mb-2 text-xs text-red-600">{analyticsError}</div>
              )}
              <div className="flex-1 overflow-y-auto rounded border p-3">
                {analyticsLoading && <div className="text-xs text-gray-500">Loading analytics…</div>}
                {!analyticsLoading && analyticsBuckets.length === 0 && (
                  <div className="text-xs text-gray-500">No analytics buckets found for this range.</div>
                )}
                <div className="space-y-2">
                  {analyticsBuckets.map((bucket) => (
                    <div key={`${bucket.bucket_start}-${bucket.state}-${bucket.topic_label || 'none'}`} className="space-y-1">
                      <div className="flex items-center justify-between text-[11px] text-gray-600">
                        <span>{new Date(bucket.bucket_start).toLocaleDateString()}</span>
                        <span className="uppercase tracking-wide">{bucket.state}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="h-2 flex-1 rounded-full bg-gray-100">
                          <div
                            className="h-2 rounded-full bg-blue-500"
                            style={{ width: `${(bucket.count / maxAnalyticsCount) * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-700">{bucket.count}</span>
                        <span className="text-[11px] text-emerald-700">
                          {bucket.topic_label || 'No topic'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="mt-3 flex items-center justify-between text-xs text-gray-600">
                <Button variant="secondary" onClick={loadPrevAnalyticsPage} disabled={analyticsPagination.offset <= 0 || analyticsLoading}>
                  Prev
                </Button>
                <span>
                  Offset {analyticsPagination.offset} • Total {analyticsPagination.total}
                </span>
                <Button variant="secondary" onClick={loadNextAnalyticsPage} disabled={!analyticsPagination.has_more || analyticsLoading}>
                  Next
                </Button>
              </div>
            </div>
          ) : (
            <>
          <div className="mb-3 grid grid-cols-1 gap-3 md:grid-cols-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Model</label>
              <select
                className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                value={model}
                onChange={(e) => setModel(e.target.value)}
              >
                {recentModels.length > 0 && (
                  <optgroup label="Recently Used">
                    {recentModels.map((m) => (
                      <option key={`recent-${m}`} value={m}>{m}</option>
                    ))}
                  </optgroup>
                )}
                {providers.length > 0 ? (
                  providers.map((p) => (
                    <optgroup key={p.name} label={`${p.display_name || p.name}${p.is_configured === false ? ' (Not Configured)' : ''}`}>
                      {(p.models || []).map((m) => (
                        <option key={`${p.name}/${m}`} value={`${p.name}/${m}`} disabled={p.is_configured === false}>
                          {m}
                        </option>
                      ))}
                    </optgroup>
                  ))
                ) : (
                  <option value={model}>{loadingProviders ? 'Loading models…' : model}</option>
                )}
              </select>
            </div>
            <div className="flex items-end justify-end md:col-span-3">
              <div className="flex items-center gap-4 text-sm text-gray-700">
                <label className="inline-flex items-center space-x-2">
                  <input type="checkbox" className="h-4 w-4" checked={stream} onChange={(e) => setStream(e.target.checked)} />
                  <span>Stream</span>
                </label>
                <label className="inline-flex items-center space-x-2">
                  <input type="checkbox" className="h-4 w-4" checked={saveToDb} onChange={(e) => setSaveToDb(e.target.checked)} />
                  <span>Save to DB</span>
                </label>
                {/* Stop moved into Composer right actions */}
              </div>
            </div>
          </div>

          <details className="mb-3 rounded border p-3">
            <summary className="cursor-pointer text-sm font-medium">Advanced Parameters</summary>
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Preset</label>
                <select className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={preset} onChange={(e)=>applyPreset(e.target.value as typeof preset)}>
                  <option value="creative">Creative</option>
                  <option value="balanced">Balanced</option>
                  <option value="precise">Precise</option>
                  <option value="json">JSON Mode</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Slash Command Injection</label>
                <select
                  className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  value={slashMode}
                  onChange={(e) => setSlashMode(e.target.value as typeof slashMode)}
                >
                  <option value="system">System (separate)</option>
                  <option value="preface">Preface user</option>
                  <option value="replace">Replace user</option>
                </select>
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block text-sm font-medium text-gray-700">Params (JSON)</label>
                <JsonEditor value={advanced} onChange={setAdvanced} height={140} />
              </div>
            </div>
          </details>

          <div className="mb-2 flex items-center justify-between text-xs text-gray-600">
            <div>Conversation ID: <span className="font-mono">{conversationId || '(new)'}</span></div>
            <div className="space-x-2">
              <Button variant="secondary" onClick={startNewChat}>New Chat</Button>
            </div>
          </div>
          <div className="flex-1 min-h-0 flex flex-col">
            <div className="flex items-center justify-between mb-1 text-xs text-gray-600">
              <div className="space-x-2">
                {treeViewEnabled ? (
                  <>
                    <Button variant="secondary" onClick={loadPrevTreePage} disabled={treeOffset <= 0 || treeLoading}>
                      Prev threads
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={loadNextTreePage}
                      disabled={!treeData?.pagination?.has_more || treeLoading}
                    >
                      Next threads
                    </Button>
                    {treeData && (
                      <span className="text-[11px] text-gray-500">
                        {treeOffset + 1}–{Math.min(treeOffset + treePageLimit, treeData.pagination.total_root_threads)} of {treeData.pagination.total_root_threads}
                      </span>
                    )}
                  </>
                ) : (
                  hasMoreHistory && <Button variant="secondary" onClick={handleLoadOlder}>Load older</Button>
                )}
              </div>
              <div className="font-mono">{currentProvider ? `${currentProvider}${currentModelOnly ? '/' + currentModelOnly : ''}` : ''}</div>
            </div>
            <div ref={chatListRef} onScroll={onScrollContainer} className="relative flex-1 min-h-0 rounded border p-2 overflow-y-auto">
              {!treeViewEnabled && showJump && (
                <button onClick={jumpToLatest} className="absolute right-3 bottom-3 z-10 rounded bg-blue-600 px-3 py-1 text-white text-xs shadow">
                  Jump to latest
                </button>
              )}
              {treeViewEnabled ? (
                <div className="space-y-3">
                  {treeLoading && <div className="text-xs text-gray-500">Loading tree…</div>}
                  {treeError && <div className="text-xs text-red-600">{treeError}</div>}
                  {!treeLoading && treeData?.root_threads?.length === 0 && (
                    <div className="text-xs text-gray-500">No root threads found.</div>
                  )}
                  {treeData?.root_threads?.map((node) => renderTreeNode(node, 0))}
                </div>
              ) : (
                <ChatMessageList
                  messages={chatuiMessages}
                  renderMessageFooter={renderFeedbackFooter}
                  renderMessageContent={(msg: ChatMessage) => {
                    if (msg.role === 'system') {
                      const text = typeof msg.content === 'string'
                        ? msg.content
                        : msg.content?.text || '';
                      return (
                        <details
                          onToggle={(event) => {
                            const target = event.currentTarget as HTMLDetailsElement;
                            if (target.open && msg.messageId && !expandSentRef.current.has(msg.messageId)) {
                              expandSentRef.current.add(msg.messageId);
                              void sendImplicitFeedback({
                                event_type: 'expand',
                                message_id: msg.messageId,
                              });
                            }
                          }}
                        >
                          <summary className="cursor-pointer text-xs text-amber-700">
                            <span className="mr-2 inline-flex rounded-full bg-amber-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-900">
                              System
                            </span>
                            <span>View system prompt</span>
                          </summary>
                          <div className="mt-2 whitespace-pre-wrap text-xs text-amber-900">
                            {text || DEFAULT_SYSTEM_PROMPT}
                          </div>
                        </details>
                      );
                    }
                    if (msg.type === 'tool') {
                      const contentObj = typeof msg.content === 'object' ? msg.content : null;
                      const name = contentObj?.name || 'tool';
                      const text = contentObj?.text || '';
                      return (
                        <div className="rounded border bg-gray-50 p-2 text-xs">
                          <div className="mb-1 font-semibold text-gray-700">Tool: {name}</div>
                          <pre className="whitespace-pre-wrap text-gray-700 max-h-56 overflow-auto">{text}</pre>
                          <div className="mt-2 text-right">
                            <button
                              className="inline-flex items-center rounded border border-gray-300 bg-white px-2 py-1 text-[11px] text-gray-700 hover:bg-gray-100"
                              aria-label="Mention tool in chat"
                              title="Mention tool in chat"
                              onClick={() => setComposerText((prev: string) => {
                                const mention = `[tool:${name}]`;
                                const base = typeof prev === 'string' ? prev : '';
                                return base && base.trim().length ? `${base} ${mention}` : mention;
                              })}
                            >
                              Mention in chat
                            </button>
                          </div>
                        </div>
                      );
                    }
                    // Use default renderer for non-tool messages
                    return undefined;
                  }}
                />
              )}
            </div>
            <div className="mt-2">
              <div className="mb-2 flex items-center justify-between text-xs text-gray-600">
                <label className="inline-flex items-center space-x-2">
                  <input type="checkbox" className="h-4 w-4" checked={scrollLock} onChange={(e) => setScrollLock(e.target.checked)} />
                  <span>Scroll lock</span>
                </label>
                {/* Stop moved into Composer right actions */}
              </div>
              <ChatComposer
                placeholder="Type your message…"
                onSend={onComposerSend}
                text={composerText}
                onChange={(val: string) => setComposerText(val)}
                rows={2}
                disabled={sending}
                rightActions={
                  sending && stream
                    ? [
                        <Button key="stop" variant="secondary" onClick={onStopStream}>
                          Stop
                        </Button>,
                      ]
                    : [
                        <Button key="send" onClick={() => onComposerSend('text', composerText)} disabled={sending}>
                          Send
                        </Button>,
                      ]
                }
              />
            </div>
          </div>
          </>
          )}
        </div>
      </div>
      <FeedbackModal
        open={feedbackModalOpen}
        rating={feedbackModalRating}
        issues={feedbackModalIssues}
        notes={feedbackModalNotes}
        submitting={feedbackModalSubmitting}
        issueOptions={issueOptions}
        onClose={closeFeedbackModal}
        onSubmit={handleDetailedFeedbackSubmit}
        onRatingChange={setFeedbackModalRating}
        onIssuesChange={setFeedbackModalIssues}
        onNotesChange={setFeedbackModalNotes}
      />
    </Layout>
  );
}
