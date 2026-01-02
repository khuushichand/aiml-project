import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Button } from '@/components/ui/Button';
import { apiClient, getApiBaseUrl, buildAuthHeaders } from '@/lib/api';
import { cn } from '@/lib/utils';
import { streamSSE } from '@/lib/sse';
import { useToast } from '@/components/ui/ToastProvider';
import JsonEditor from '@/components/ui/JsonEditor';
import HotkeysOverlay from '@/components/ui/HotkeysOverlay';
import { ChatComposer } from '@/components/ui/ChatComposer';
import { ChatMessageList, type ChatMessage } from '@/components/ui/ChatMessageList';

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

type Role = 'user'|'assistant'|'system'|'tool';
type UiMessage = {
  messageId?: string;
  role: Role;
  text?: string;
  name?: string;
  tool?: { name?: string; id?: string; content?: string };
  provider?: string;
  model?: string;
  // Flag messages that are UI-only errors; excluded from API payloads
  error?: boolean;
};

type SessionItem = { id: string; title: string; model: string; created_at: string };

export default function ChatPage() {
  const { show } = useToast();
  const [uiMessages, setUiMessages] = useState<UiMessage[]>([
    { role: 'system', text: 'System prompt text' },
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
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const lastSessionIdRef = useRef<string | null>(null);
  const [preset, setPreset] = useState<'creative'|'balanced'|'precise'|'json'>('balanced');
  const [advanced, setAdvanced] = useState<string>('{}');
  const [recentModels, setRecentModels] = useState<string[]>([]);
  const pageSize = 50;
  const [pageOffset, setPageOffset] = useState(0);
  const [hasMoreHistory, setHasMoreHistory] = useState(false);
  const [currentProvider, setCurrentProvider] = useState<string | undefined>(undefined);
  const [currentModelOnly, setCurrentModelOnly] = useState<string | undefined>(undefined);
  const [scrollLock, setScrollLock] = useState(false);
  const [showJump, setShowJump] = useState(false);
  const [feedbackById, setFeedbackById] = useState<Record<string, { value?: 'up' | 'down'; pending?: boolean }>>({});
  const chatSessionIdRef = useRef<string | null>(null);
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false);
  const [feedbackModalMessage, setFeedbackModalMessage] = useState<ChatMessage | null>(null);
  const [feedbackModalHelpful, setFeedbackModalHelpful] = useState<boolean | null>(null);
  const [feedbackModalRating, setFeedbackModalRating] = useState(0);
  const [feedbackModalIssues, setFeedbackModalIssues] = useState<string[]>([]);
  const [feedbackModalNotes, setFeedbackModalNotes] = useState('');
  const [feedbackModalSubmitting, setFeedbackModalSubmitting] = useState(false);
  const dwellTimerRef = useRef<number | null>(null);
  const dwellSentRef = useRef<Set<string>>(new Set());
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

  const issueOptions = useMemo(() => ([
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
        session_id: chatSessionIdRef.current || undefined,
        conversation_id: conversationId || undefined,
        ...payload,
      });
    } catch {
      // best-effort
    }
  }, [conversationId, getLatestUserQuery]);

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

  const persistSessions = (list: SessionItem[]) => {
    try { localStorage.setItem('tldw-chat-sessions', JSON.stringify(list)); } catch {}
  };
  const loadSessions = () => {
    try { const s = localStorage.getItem('tldw-chat-sessions'); if (s) setSessions(JSON.parse(s)); } catch {}
  };
  useEffect(() => { loadSessions(); }, []);
  useEffect(() => {
    try {
      const key = 'tldw-chat-session-id';
      const existing = localStorage.getItem(key);
      if (existing) {
        chatSessionIdRef.current = existing;
        return;
      }
      const hasCrypto = typeof crypto !== 'undefined';
      const generated = (hasCrypto && 'randomUUID' in crypto)
        ? crypto.randomUUID()
        : (hasCrypto && 'getRandomValues' in crypto)
          ? (() => {
              const bytes = new Uint8Array(16);
              crypto.getRandomValues(bytes);
              // Convert bytes to a hex string, keep existing "sess_" prefix
              return 'sess_' + Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('');
            })()
          : `sess_${Date.now()}`;
      localStorage.setItem(key, generated);
      chatSessionIdRef.current = generated;
    } catch {
      const hasCrypto = typeof crypto !== 'undefined' && 'getRandomValues' in crypto;
      if (hasCrypto) {
        const bytes = new Uint8Array(16);
        crypto.getRandomValues(bytes);
        chatSessionIdRef.current = 'sess_' + Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('');
      } else {
        chatSessionIdRef.current = `sess_${Date.now()}`;
      }
    }
  }, []);

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
    setUiMessages([{ role: 'system', text: 'System prompt text' }]);
    setPageOffset(0);
    setHasMoreHistory(false);
    setFeedbackById({});
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
    // Map to UiMessage[]
    const mapped: UiMessage[] = msgs.map((m) => {
      const role: Role = (m.role || 'assistant') as Role;
      const messageId = m.message_id || m.id;
      const name = typeof m.name === 'string' ? m.name : undefined;
      if (role === 'tool') {
        return { role, messageId, tool: { id: m.tool_call_id, name: m.name, content: m.content } };
      }
      return { role, messageId, text: m.content, name };
    });
    const normalized = offset > 0
      ? mapped.filter((m) => !(m.role === 'system' && !m.messageId))
      : mapped;
    setUiMessages((prev) => {
      if (offset > 0) {
        return [...normalized, ...prev];
      }
      const hasSystem = normalized.some((m) => m.role === 'system');
      if (!hasSystem) {
        return [{ role: 'system', text: 'System prompt text' }, ...normalized];
      }
      return normalized;
    });
    setHasMoreHistory(msgs.length === pageSize);
  }, [pageSize]);

  // Migrate session id from temporary local-* to server conversation id when assigned
  useEffect(() => {
    const oldId = lastSessionIdRef.current;
    if (!oldId) return;
    if (!conversationId) return;
    if (oldId.startsWith('local-') && oldId !== conversationId) {
      const changed = sessions.some((s) => s.id === oldId);
      if (changed) {
        const updated = sessions.map((s) => s.id === oldId ? { ...s, id: conversationId } : s);
        setSessions(updated);
        persistSessions(updated);
        lastSessionIdRef.current = conversationId;
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

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
        messages: newUi
          .filter((m) => m.role !== 'system' && !m.error)
          .map((m) => {
            const content = m.tool?.content ?? m.text ?? '';
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const out: any = { role: m.role, content };
            const toolCallId = m.tool?.id;
            if (toolCallId) out.tool_call_id = toolCallId;
            const senderName = m.name || m.tool?.name;
            if (senderName) out.name = senderName;
            return out;
          }),
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
          const id = conversationId || 'local-' + Date.now();
          lastSessionIdRef.current = id;
          if (!sessions.find((s) => s.id === id)) {
            const next = [{ id, title, model, created_at: new Date().toISOString() }, ...sessions].slice(0, 50);
            setSessions(next); persistSessions(next);
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
        const id = res?.tldw_conversation_id || conversationId || 'local-' + Date.now();
        lastSessionIdRef.current = String(id);
        if (!sessions.find((s) => s.id === id)) {
          const next = [{ id: String(id), title, model, created_at: new Date().toISOString() }, ...sessions].slice(0, 50);
          setSessions(next); persistSessions(next);
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
    let previousValue: 'up' | 'down' | undefined;
    let shouldSend = false;
    setFeedbackById((prev) => {
      const current = prev[messageId];
      if (current?.pending) return prev;
      if (current?.value === nextValue) return prev;
      previousValue = current?.value;
      shouldSend = true;
      return {
        ...prev,
        [messageId]: { value: nextValue, pending: true },
      };
    });
    if (!shouldSend) return;

    try {
      await apiClient.post('/feedback/explicit', {
        conversation_id: conversationId || undefined,
        message_id: messageId,
        feedback_type: 'helpful',
        helpful,
        session_id: chatSessionIdRef.current || undefined,
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
  }, [conversationId, show]);

  const handleDetailedFeedbackSubmit = useCallback(async () => {
    const messageId = feedbackModalMessage?.messageId;
    if (!messageId) return;
    const trimmedNotes = feedbackModalNotes.trim();
    const hasRating = feedbackModalRating > 0;
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
        relevance_score: hasRating ? feedbackModalRating : undefined,
        issues: hasIssues ? feedbackModalIssues : undefined,
        user_notes: hasNotes ? trimmedNotes : undefined,
        session_id: chatSessionIdRef.current || undefined,
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
            { role: 'system', text: 'System prompt text' },
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
        if (mapped.length) {
          setSessions((prev) => {
            const ids = new Set(prev.map((p) => p.id));
            const merged = [...prev, ...mapped.filter((m) => !ids.has(m.id))];
            persistSessions(merged);
            return merged;
          });
        }
      } catch {}
    };
    fetchSessions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // When conversationId changes, reset view and load first page
  useEffect(() => {
    if (!conversationId) return;
    setUiMessages([{ role: 'system', text: 'System prompt text' }]);
    setPageOffset(0);
    setFeedbackById({});
    (async () => {
      await loadConversationPage(conversationId, 0);
      setPageOffset((p) => p + pageSize);
    })();
  }, [conversationId, loadConversationPage, pageSize]);

  const handleLoadOlder = async () => {
    if (!conversationId) return;
    suppressAutoScrollRef.current = true;
    await loadConversationPage(conversationId, pageOffset);
    setPageOffset((p) => p + pageSize);
    // Re-enable auto-scroll after render tick
    setTimeout(() => { suppressAutoScrollRef.current = false; }, 0);
  };

  const chatuiMessages: ChatMessage[] = useMemo(() => {
    const providerFromModel = (() => {
      try { return (model || '').split('/')[0] || undefined; } catch { return undefined; }
    })();
    const avatarProvider = currentProvider || providerFromModel;
    const avatarUrl = providerIconUrl(avatarProvider);
    return uiMessages
      .map((m) => {
        if (m.role === 'tool' && m.tool) {
          return {
            type: 'tool',
            position: 'left',
            content: { name: m.tool.name || 'tool', text: m.tool.content || '' },
            user: { name: 'Tool' },
            role: 'tool',
            messageId: m.messageId,
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
          } as any;
        }
        const isUser = m.role === 'user';
        const isSystem = m.role === 'system';
        const assistantName = m.name || 'Assistant';
        return {
          type: 'text',
          position: isSystem ? 'center' : (isUser ? 'right' : 'left'),
          content: { text: m.text || '' },
          user: isUser
            ? { name: 'You' }
            : isSystem
              ? undefined
              : (avatarUrl ? { name: assistantName, avatar: avatarUrl } : { name: assistantName }),
          role: m.role,
          messageId: m.messageId,
        } as ChatMessage;
      });
  }, [uiMessages, model, currentProvider, providerIconUrl]);

  const renderFeedbackFooter = useCallback((msg: ChatMessage) => {
    if (!msg.messageId) return null;
    if (!msg.role || msg.role === 'user') return null;
    const state = feedbackById[msg.messageId] || {};
    const pending = state.pending;
    const upSelected = state.value === 'up';
    const downSelected = state.value === 'down';

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
      <div className="flex items-center gap-2 text-[11px] text-gray-500">
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
      </div>
    );
  }, [feedbackById, handleFeedback, openFeedbackModal]);

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
        dwell_ms: 3000,
        message_id: lastAssistant.messageId,
      });
    }, 3000);

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
    const el = chatListRef.current;
    if (!el) return;
    if (!scrollLock && !suppressAutoScrollRef.current) {
      el.scrollTop = el.scrollHeight;
      setShowJump(false);
    } else {
      setShowJump(!atBottom(el));
    }
  }, [uiMessages, scrollLock]);

  const onScrollContainer = () => {
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
          <h2 className="text-lg font-semibold text-gray-800">Conversations</h2>
          <div className="rounded-md border bg-white p-3 h-[72vh] overflow-y-auto">
            <div className="mb-2 flex items-center justify-between text-xs text-gray-600">
              <div>Count: {sessions.length}</div>
              <Button variant="secondary" onClick={startNewChat}>New Chat</Button>
            </div>
            <ul className="text-sm divide-y">
              {sessions.map((s) => (
                <li key={s.id} className="py-2">
                  <button className="text-left" onClick={() => setConversationId(s.id)}>
                    <div className="font-medium truncate">{s.title || 'Chat'}</div>
                    <div className="text-xs text-gray-500 truncate">{s.model} • {new Date(s.created_at).toLocaleString()}</div>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="md:col-span-3 rounded-md border bg-white p-4 flex flex-col h-[80vh]">
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
                {hasMoreHistory && <Button variant="secondary" onClick={handleLoadOlder}>Load older</Button>}
              </div>
              <div className="font-mono">{currentProvider ? `${currentProvider}${currentModelOnly ? '/' + currentModelOnly : ''}` : ''}</div>
            </div>
            <div ref={chatListRef} onScroll={onScrollContainer} className="relative flex-1 min-h-0 rounded border p-2 overflow-y-auto">
              {showJump && (
                <button onClick={jumpToLatest} className="absolute right-3 bottom-3 z-10 rounded bg-blue-600 px-3 py-1 text-white text-xs shadow">
                  Jump to latest
                </button>
              )}
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
                          if (target.open && msg.messageId) {
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
                          <span>System prompt text</span>
                        </summary>
                        <div className="mt-2 whitespace-pre-wrap text-xs text-amber-900">
                          {text || 'System prompt text'}
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
        </div>
      </div>
      {feedbackModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={closeFeedbackModal}>
          <div
            className="w-full max-w-lg rounded-lg bg-white p-4 shadow-xl"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Feedback</h3>
              <button
                type="button"
                className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-600 hover:bg-gray-100"
                onClick={closeFeedbackModal}
                aria-label="Close feedback dialog"
              >
                Close
              </button>
            </div>

            <div className="mb-4">
              <div className="text-sm font-medium text-gray-800">How would you rate this response?</div>
              <div className="mt-2 flex items-center gap-2">
                {Array.from({ length: 5 }).map((_, idx) => {
                  const ratingValue = idx + 1;
                  const active = ratingValue <= feedbackModalRating;
                  return (
                    <button
                      key={`rating-${ratingValue}`}
                      type="button"
                      className={cn(
                        'h-8 w-8 rounded-full border text-sm font-semibold transition',
                        active ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-gray-300 text-gray-500 hover:bg-gray-100'
                      )}
                      onClick={() => setFeedbackModalRating(ratingValue)}
                      aria-label={`Rate ${ratingValue} out of 5`}
                    >
                      {ratingValue}
                    </button>
                  );
                })}
                {feedbackModalRating > 0 && (
                  <span className="text-xs text-gray-500">{feedbackModalRating}/5</span>
                )}
              </div>
            </div>

            <div className="mb-4">
              <div className="text-sm font-medium text-gray-800">What was the issue? (select all that apply)</div>
              <div className="mt-2 grid grid-cols-1 gap-2 text-sm text-gray-700 sm:grid-cols-2">
                {issueOptions.map((issue) => (
                  <label key={issue.id} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={feedbackModalIssues.includes(issue.id)}
                      onChange={() => {
                        setFeedbackModalIssues((prev) => (
                          prev.includes(issue.id)
                            ? prev.filter((item) => item !== issue.id)
                            : [...prev, issue.id]
                        ));
                      }}
                    />
                    <span>{issue.label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="mb-4">
              <label className="text-sm font-medium text-gray-800" htmlFor="feedback-notes">
                Additional comments (optional)
              </label>
              <textarea
                id="feedback-notes"
                className="mt-2 w-full rounded border border-gray-300 p-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                rows={4}
                value={feedbackModalNotes}
                onChange={(event) => setFeedbackModalNotes(event.target.value)}
                placeholder="Share extra context to help improve responses..."
              />
            </div>

            <div className="flex items-center justify-end gap-2">
              <Button variant="secondary" onClick={closeFeedbackModal} disabled={feedbackModalSubmitting}>
                Cancel
              </Button>
              <Button onClick={handleDetailedFeedbackSubmit} loading={feedbackModalSubmitting}>
                Submit Feedback
              </Button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
