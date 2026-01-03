import type { ChatMessage } from '@/components/ui/ChatMessageList';

export type Role = 'user' | 'assistant' | 'system' | 'tool';

const VALID_ROLES: Role[] = ['user', 'assistant', 'system', 'tool'];

export type UiMessage = {
  messageId?: string;
  role: Role;
  text?: string;
  name?: string;
  tool?: { name?: string; id?: string; content?: string };
  provider?: string;
  model?: string;
  error?: boolean;
};

type ApiHistoryMessage = {
  role?: string;
  content?: string;
  name?: string;
  tool_call_id?: string;
  message_id?: string;
  id?: string;
};

type ApiPayloadMessage = {
  role: Role;
  content?: string;
  tool_call_id?: string;
  name?: string;
};

export const mapHistoryMessagesToUi = (messages: ApiHistoryMessage[]): UiMessage[] =>
  messages.map((m) => {
    const rawRole = m.role || 'assistant';
    const isValidRole = VALID_ROLES.includes(rawRole as Role);
    const role = (isValidRole ? rawRole : 'assistant') as Role;
    if (!isValidRole && process.env.NODE_ENV === 'development') {
      console.warn(`Unknown message role: ${rawRole}, defaulting to assistant`);
    }
    const messageId = m.message_id || m.id;
    const name = typeof m.name === 'string' ? m.name : undefined;
    if (role === 'tool') {
      return { role, messageId, tool: { id: m.tool_call_id, name: m.name, content: m.content } };
    }
    return { role, messageId, text: m.content, name };
  });

export const buildChatPayloadMessages = (messages: UiMessage[]): ApiPayloadMessage[] =>
  messages
    .filter((m) => m.role !== 'system' && !m.error)
    .map((m) => {
      const content = m.tool?.content ?? m.text ?? '';
      const out: ApiPayloadMessage = { role: m.role, content };
      const toolCallId = m.tool?.id;
      if (toolCallId) out.tool_call_id = toolCallId;
      const senderName = m.name || m.tool?.name;
      if (senderName) out.name = senderName;
      return out;
    });

export const normalizeHistoryMessages = (messages: UiMessage[], offset: number): UiMessage[] => {
  if (offset > 0) {
    return messages.filter((m) => !(m.role === 'system' && !m.messageId));
  }
  return messages;
};

export const ensureSystemMessage = (messages: UiMessage[], systemText: string): UiMessage[] => {
  const hasSystem = messages.some((m) => m.role === 'system');
  if (hasSystem) return messages;
  return [{ role: 'system', text: systemText }, ...messages];
};

export const toChatMessages = (messages: UiMessage[], avatarUrl?: string): ChatMessage[] =>
  messages.map((m) => {
    if (m.role === 'tool' && m.tool) {
      return {
        type: 'tool',
        position: 'left',
        content: { name: m.tool.name || 'tool', text: m.tool.content || '' },
        user: { name: 'Tool' },
        role: 'tool',
        messageId: m.messageId,
      };
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
    };
  });
