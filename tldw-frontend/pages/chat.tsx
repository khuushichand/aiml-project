import { useEffect, useState, useRef } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { apiClient, getApiBaseUrl, buildAuthHeaders } from '@/lib/api';
import { streamSSE } from '@/lib/sse';
import { useToast } from '@/components/ui/ToastProvider';
import type { ChatMessage } from '@/types/api';
import JsonEditor from '@/components/ui/JsonEditor';
import { Tabs } from '@/components/ui/Tabs';
import HotkeysOverlay from '@/components/ui/HotkeysOverlay';

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

export default function ChatPage() {
  const { show } = useToast();
  const [messages, setMessages] = useState<ChatMessage[]>([{
    role: 'system',
    content: 'You are a helpful assistant.',
  }]);
  const [input, setInput] = useState('');
  const [model, setModel] = useState('gpt-3.5-turbo');
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [stream, setStream] = useState(true);
  const [sending, setSending] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [saveToDb, setSaveToDb] = useState<boolean>(false);
  const [sessions, setSessions] = useState<Array<{ id: string; title: string; model: string; created_at: string }>>([]);
  const lastSessionIdRef = useRef<string | null>(null);
  const [preset, setPreset] = useState<'creative'|'balanced'|'precise'|'json'>('balanced');
  const [advanced, setAdvanced] = useState<string>('{}');

  const persistSessions = (list: any[]) => {
    try { localStorage.setItem('tldw-chat-sessions', JSON.stringify(list)); } catch {}
  };
  const loadSessions = () => {
    try { const s = localStorage.getItem('tldw-chat-sessions'); if (s) setSessions(JSON.parse(s)); } catch {}
  };
  useEffect(() => { loadSessions(); }, []);

  const startNewChat = () => {
    setConversationId(null);
    setMessages([{ role: 'system', content: 'You are a helpful assistant.' }]);
  };

  // Load saved messages when switching to a known conversation
  useEffect(() => {
    if (conversationId) {
      try {
        const raw = localStorage.getItem(`tldw-chat-messages-${conversationId}`);
        if (raw) {
          const parsed = JSON.parse(raw);
          if (Array.isArray(parsed)) setMessages(parsed);
        }
      } catch {}
    }
  }, [conversationId]);

  // Persist messages to localStorage per conversation (when available)
  useEffect(() => {
    if (conversationId) {
      try { localStorage.setItem(`tldw-chat-messages-${conversationId}`, JSON.stringify(messages)); } catch {}
    }
  }, [messages, conversationId]);

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
    if (!input.trim() || sending) return;
    show({ title: 'Sending message…', variant: 'info' });
    const newMessages = [...messages, { role: 'user', content: input.trim() } as ChatMessage, { role: 'assistant', content: '' } as ChatMessage];
    setMessages(newMessages);
    setInput('');
    setSending(true);

    try {
      let payload: any = {
        model,
        stream,
        save_to_db: !!saveToDb,
        messages: newMessages.filter((m) => m.role !== 'system' || m.content.trim() !== '').map((m) => ({ role: m.role, content: m.content })),
      };
      try { const extra = JSON.parse(advanced || '{}'); if (extra && typeof extra === 'object') payload = { ...payload, ...extra }; } catch {}
      if (conversationId) payload.conversation_id = conversationId;
      const body = JSON.stringify(payload);

      if (stream) {
        const url = `${getApiBaseUrl()}/chat/completions`;
        const headers = { ...buildAuthHeaders('POST', 'application/json'), Accept: 'text/event-stream' };
        const controller = new AbortController();
        abortRef.current = controller;

        let acc = '';
        await streamSSE(url, { method: 'POST', headers, body }, (delta) => {
          acc += delta;
          setMessages((prev) => {
            const updated = [...prev];
            // Append to last assistant message
            const lastIdx = updated.length - 1;
            if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
              updated[lastIdx] = { ...updated[lastIdx], content: acc } as ChatMessage;
            }
            return updated;
          });
        }, (json) => {
          // Capture metadata conversation_id from stream_start or provider frames
          const metaConv = json?.conversation_id || json?.tldw_metadata?.conversation_id;
          if (metaConv && !conversationId) {
            setConversationId(String(metaConv));
          }
        }, () => {
          // On done, optionally store session reference
          const firstUser = newMessages.find((m) => m.role === 'user');
          const title = (firstUser?.content || '').slice(0, 60) || 'Chat';
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
        setMessages((prev) => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
            updated[lastIdx] = { ...updated[lastIdx], content: text } as ChatMessage;
          }
          return updated;
        });
        const firstUser = newMessages.find((m) => m.role === 'user');
        const title = (firstUser?.content || '').slice(0, 60) || 'Chat';
        const id = res?.tldw_conversation_id || conversationId || 'local-' + Date.now();
        lastSessionIdRef.current = String(id);
        if (!sessions.find((s) => s.id === id)) {
          const next = [{ id: String(id), title, model, created_at: new Date().toISOString() }, ...sessions].slice(0, 50);
          setSessions(next); persistSessions(next);
        }
        show({ title: 'Response ready', variant: 'success' });
      }
    } catch (e: any) {
      setMessages((prev) => [...prev, { role: 'system', content: `Error: ${e.message || e}` } as ChatMessage]);
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
          setModel(`${defProv.name}/${defModel}`);
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
          const last = [...messages].reverse().find((m) => m.role === 'assistant');
          if (last?.content) {
            await navigator.clipboard.writeText(last.content);
            show({ title: 'Assistant reply copied', variant: 'success' });
          }
        } catch {}
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [messages, sendMessage]);

  // Persist current chat model for use across pages (e.g., Media Analyze)
  useEffect(() => {
    try { localStorage.setItem('tldw-current-chat-model', model); } catch {}
  }, [model]);

  // Prefill message from Media page
  useEffect(() => {
    try {
      const raw = localStorage.getItem('tldw-chat-prefill');
      if (raw) {
        const data = JSON.parse(raw);
        // Only prefill if starting fresh
        const userCount = messages.filter((m) => m.role === 'user').length;
        if (userCount === 0 && !conversationId && data?.message) {
          setMessages([
            { role: 'system', content: 'You are a helpful assistant.' },
            { role: 'user', content: String(data.message) }
          ] as ChatMessage[]);
        }
      }
      localStorage.removeItem('tldw-chat-prefill');
    } catch {
      // ignore
    }
    // run once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Layout>
      <div className="mx-auto max-w-3xl space-y-4 transition-all duration-150">
        <HotkeysOverlay
          entries={[
            { keys: 'Cmd/Ctrl+Enter', description: 'Send message' },
            { keys: 'Esc', description: 'Abort streaming' },
            { keys: 'Cmd/Ctrl+Shift+J', description: 'Copy last assistant reply' },
            { keys: 'Cmd/Ctrl+Shift+C', description: 'Copy cURL (on pages that have it)' },
            { keys: '?', description: 'Toggle this help' },
          ]}
        />
        <h1 className="text-2xl font-bold text-gray-900">Chat</h1>

        <div className="rounded-md border bg-white p-4">
          <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Model</label>
              <select
                className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                value={model}
                onChange={(e) => setModel(e.target.value)}
              >
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
            <div className="flex items-end">
              <label className="inline-flex items-center space-x-2 text-sm text-gray-700">
                <input type="checkbox" className="h-4 w-4" checked={stream} onChange={(e) => setStream(e.target.checked)} />
                <span>Stream</span>
              </label>
            </div>
            <div className="flex items-end">
              <label className="inline-flex items-center space-x-2 text-sm text-gray-700">
                <input type="checkbox" className="h-4 w-4" checked={saveToDb} onChange={(e) => setSaveToDb(e.target.checked)} />
                <span>Save to DB</span>
              </label>
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

          <div className="mb-4 h-80 overflow-y-auto rounded border p-3 text-sm">
            {messages.filter(m => m.role !== 'system').map((m, idx) => (
              <div key={idx} className="mb-3">
                <div className="font-semibold text-gray-800">{m.role === 'user' ? 'You' : 'Assistant'}</div>
                <div className="whitespace-pre-wrap text-gray-700">{m.content}</div>
              </div>
            ))}
          </div>

          <div className="flex items-end space-x-3">
            <div className="flex-1">
              <label className="mb-1 block text-sm font-medium text-gray-700">Message</label>
              <textarea
                className="h-24 w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type your message..."
              />
            </div>
            <div className="pb-1">
              <Button onClick={sendMessage} loading={sending} disabled={sending}>Send</Button>
            </div>
          </div>
        </div>

        {/* Sessions list */}
        {sessions.length > 0 && (
          <div className="mt-6 rounded-md border bg-white p-3">
            <div className="mb-2 text-sm font-medium text-gray-800">Recent Chats</div>
            <ul className="text-sm">
              {sessions.map((s) => (
                <li key={s.id} className="flex items-center justify-between border-b py-1 last:border-b-0">
                  <div>
                    <div className="font-medium">{s.title}</div>
                    <div className="text-xs text-gray-500">{s.model} • {new Date(s.created_at).toLocaleString()}</div>
                  </div>
                  <div className="space-x-2">
                    <Button variant="secondary" onClick={() => setConversationId(s.id)}>Continue</Button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Layout>
  );
}
