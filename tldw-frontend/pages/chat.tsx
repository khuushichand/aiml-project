import { Layout } from '@/components/layout/Layout';

export default function ChatPage() {
  return (
    <Layout>
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-gray-900">Chat</h1>
        <p className="text-gray-600">Coming soon: OpenAI-compatible chat UI for /api/v1/chat/completions.</p>
      </div>
    </Layout>
  );
}

