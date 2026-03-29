export type WebhookItem = {
  id: string;
  url: string;
  events: string[];
  enabled: boolean;
  created_at?: string | null;
  updated_at?: string | null;
};

export type WebhookCreateResponse = WebhookItem & {
  secret: string;
};

export type WebhookListResponse = {
  items: WebhookItem[];
  total: number;
};
