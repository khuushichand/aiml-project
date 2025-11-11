import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Button } from '@/components/ui/Button';
import { apiClient, getApiBaseUrl, buildAuthHeaders } from '@/lib/api';
import { streamSSE } from '@/lib/sse';
import { useToast } from '@/components/ui/ToastProvider';
import JsonEditor from '@/components/ui/JsonEditor';
import HotkeysOverlay from '@/components/ui/HotkeysOverlay';
import '@chatui/core/dist/index.css';
import { Composer, Message, MessageList, type MessageProps } from '@chatui/core';

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
  id?: string;
  role: Role;
  text?: string;
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
    { role: 'system', text: 'You are a helpful assistant.' },
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
  const [slashMode, setSlashMode] = useState<'system'|'preface'|'replace'>(() => {
    try {
      const s = localStorage.getItem('tldw-slash-mode');
      const v = (s || '').toLowerCase();
      return (v === 'preface' || v === 'replace') ? (v as any) : 'system';
    } catch {
      return 'system';
    }
  });
  const chatListRef = useRef<HTMLDivElement | null>(null);
  const suppressAutoScrollRef = useRef(false);
  const onStopStream = useCallback(() => {
    try { abortRef.current?.abort(); } catch {}
  }, []);

  const webAssetBase = useMemo(() => {
    try { return getApiBaseUrl().replace(/\/(api|API)\/v\d+$/,''); } catch { return 'http://127.0.0.1:8000'; }
  }, []);
  const providerIconUrl = useCallback((prov?: string) => {
    if (!prov) return '';
    const p = String(prov).toLowerCase();
    const known = new Set(['openai','anthropic','google','groq','mistral','huggingface','ollama']);
    if (!known.has(p)) return '';
    return `${webAssetBase}/webui/img/providers/${p}.svg`;
  }, [webAssetBase]);

  const persistSessions = (list: any[]) => {
    try { localStorage.setItem('tldw-chat-sessions', JSON.stringify(list)); } catch {}
  };
  const loadSessions = () => {
    try { const s = localStorage.getItem('tldw-chat-sessions'); if (s) setSessions(JSON.parse(s)); } catch {}
  };
  useEffect(() => { loadSessions(); }, []);

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
    setUiMessages([{ role: 'system', text: 'You are a helpful assistant.' }]);
    setPageOffset(0);
    setHasMoreHistory(false);
  };

  // Load saved messages when switching to a known conversation
  // Load messages for a conversation (paged, include tools)
  const loadConversationPage = useCallback(async (cid: string, offset: number) => {
    const qs = new URLSearchParams({
      limit: String(pageSize),
      offset: String(offset),
      format_for_completions: 'true',
      include_character_context: 'true',
    });
    const data = await apiClient.get<any>(`/chats/${cid}/messages?${qs.toString()}`);
    const msgs: any[] = Array.isArray(data?.messages) ? data.messages : [];
    // Map to UiMessage[]
    const mapped: UiMessage[] = msgs.map((m) => {
      const role: Role = (m.role || 'assistant') as Role;
      if (role === 'tool') {
        return { role, tool: { id: m.tool_call_id, name: m.name, content: m.content } };
      }
      return { role, text: m.content };
    });
    // If offset > 0, prepend older messages
    setUiMessages((prev) => {
      const withoutSystem = prev.filter((x) => x.role !== 'system');
      const system = prev.find((x) => x.role === 'system');
      const combined = [...(system ? [system] : []), ...mapped, ...withoutSystem];
      return combined;
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

  const sendMessage = async () => {
    if (!composerText.trim() || sending) return;
    show({ title: 'Sending message…', variant: 'info' });
    const newUi = [...uiMessages, { role: 'user', text: composerText.trim() } as UiMessage, { role: 'assistant', text: '' } as UiMessage];
    setUiMessages(newUi);
    setComposerText('');
    setSending(true);

    try {
      let payload: any = {
        model,
        stream,
        save_to_db: !!saveToDb,
        messages: newUi
          .filter((m) => m.role !== 'system' && !m.error)
          .map((m) => ({ role: m.role, content: m.text || '' })),
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
          // Streamed tool calls / results
          const dTools = json?.choices?.[0]?.delta?.tool_calls;
          if (Array.isArray(dTools) && dTools.length) {
            // Reflect tool call names inline as a small card
            const tcNames = dTools.map((tc: any) => tc?.function?.name).filter(Boolean);
            if (tcNames.length) {
              setUiMessages((prev) => [...prev, { role: 'tool', tool: { name: tcNames.join(', '), content: '' } }]);
            }
          }
          const dResults = json?.tool_results || json?.tldw_tool_results;
          if (Array.isArray(dResults) && dResults.length) {
            dResults.forEach((r: any) => {
              const name = r?.name || r?.tool || 'tool';
              const content = typeof r?.content === 'string' ? r.content : JSON.stringify(r?.content ?? r);
              setUiMessages((prev) => [...prev, { role: 'tool', tool: { name, content } }]);
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
        const res = await apiClient.post<any>('/chat/completions', JSON.parse(body));
        const text = res?.choices?.[0]?.message?.content || '';
        if (res?.tldw_conversation_id && !conversationId) {
          setConversationId(String(res.tldw_conversation_id));
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
    } catch (e: any) {
      setUiMessages((prev) => [
        ...prev,
        { role: 'assistant', text: `Error: ${e.message || e}`, error: true } as UiMessage,
      ]);
      show({ title: 'Chat error', description: e?.message || 'Failed', variant: 'danger' });
    } finally {
      setSending(false);
      abortRef.current = null;
    }
  };

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
      } catch (e) {
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
          }
        } catch {}
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [uiMessages, sendMessage]);

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
            { role: 'system', text: 'You are a helpful assistant.' },
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
        const data = await apiClient.get<any>('/chats?limit=30&offset=0');
        const list: any[] = Array.isArray(data?.chats) ? data.chats : [];
        const mapped: SessionItem[] = list.map((c) => ({ id: c.id, title: c.title || 'Chat', model: model, created_at: c.created_at || new Date().toISOString() }));
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
    setUiMessages([{ role: 'system', text: 'You are a helpful assistant.' }]);
    setPageOffset(0);
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

  const chatuiMessages: MessageProps[] = useMemo(() => {
    const providerFromModel = (() => {
      try { return (model || '').split('/')[0] || undefined; } catch { return undefined; }
    })();
    const avatarProvider = currentProvider || providerFromModel;
    const avatarUrl = providerIconUrl(avatarProvider);
    return uiMessages
      .filter((m) => m.role !== 'system')
      .map((m) => {
        if (m.role === 'tool' && m.tool) {
          return {
            type: 'tool',
            position: 'left',
            content: { name: m.tool.name || 'tool', text: m.tool.content || '' },
            user: { name: 'Tool' },
          } as any;
        }
        const isUser = m.role === 'user';
        return {
          type: 'text',
          position: isUser ? 'right' : 'left',
          content: { text: m.text || '' },
          user: isUser ? { name: 'You' } : (avatarUrl ? { name: 'Assistant', avatar: avatarUrl } : { name: 'Assistant' }),
        } as MessageProps;
      });
  }, [uiMessages, model, currentProvider, providerIconUrl]);

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

  const onComposerSend = async (data: { text: string }) => {
    if (!data?.text) return;
    setComposerText(data.text);
    await sendMessage();
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
                <select className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={preset} onChange={(e)=>applyPreset(e.target.value as any)}>
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
                  onChange={(e) => setSlashMode(e.target.value as any)}
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
              <MessageList
                messages={chatuiMessages}
                renderMessageContent={(msg: any) => {
                  if (msg.type === 'tool') {
                    const name = msg.content?.name || 'tool';
                    const text = msg.content?.text || '';
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
                  return undefined as any;
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
              <Composer
                placeholder="Type your message…"
                onSend={onComposerSend}
                text={composerText}
                onChange={(val: any) => setComposerText(typeof val === 'string' ? val : (val?.text ?? ''))}
                rows={2}
                showSend={false}
                disabled={sending}
                rightActions={
                  sending && stream
                    ? [
                        <Button key="stop" variant="secondary" onClick={onStopStream}>
                          Stop
                        </Button>,
                      ]
                    : [
                        <Button key="send" onClick={() => onComposerSend({ text: composerText })} disabled={sending}>
                          Send
                        </Button>,
                      ]
                }
              />
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
