// tldw_server Admin Types

export interface User {
  id: number;
  uuid: string;
  username: string;
  email: string;
  role: string;
  roles?: string[];
  is_active: boolean;
  is_verified: boolean;
  storage_quota_mb: number;
  storage_used_mb: number;
  created_at: string;
  updated_at: string;
  last_login?: string;
}

export interface UserWithKeyCount extends User {
  api_key_count?: number;
}

export interface Organization {
  id: number;
  name: string;
  slug: string;
  description?: string;
  owner_user_id: number;
  created_at: string;
  updated_at: string;
}

export interface Team {
  id: number;
  org_id: number;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface RegistrationCode {
  id: number;
  code: string;
  max_uses: number;
  times_used: number;
  expires_at: string;
  created_at: string;
  role_to_grant: string;
  is_valid?: boolean;
}

export interface RegistrationSettings {
  enable_registration: boolean;
  require_registration_code: boolean;
  auth_mode?: string;
  profile?: string;
  self_registration_allowed?: boolean;
}

export interface WatchlistSettings {
  watchlists_enabled?: boolean;
  default_threshold?: number;
  notification_email?: string;
  alert_on_breach?: boolean;
}

export interface OrgMember {
  org_id: number;
  user_id: number;
  role: string;
  joined_at: string;
  user?: User;
}

export interface TeamMember {
  team_id: number;
  user_id: number;
  role: string;
  joined_at: string;
  user?: User;
}

export interface ApiKey {
  id: string;
  user_id: number;
  name?: string;
  key_prefix: string;
  scope: string;
  created_at: string;
  expires_at?: string;
  revoked_at?: string;
  last_used_at?: string;
}

export interface Role {
  id: number;
  name: string;
  description?: string;
  is_system: boolean;
}

export interface Permission {
  id: number;
  name: string;
  description?: string;
}

export interface AuditLog {
  id: string;
  timestamp: string;
  user_id: number;
  action: string;
  resource: string;
  details?: Record<string, unknown>;
  ip_address?: string;
  username?: string;
  raw?: Record<string, unknown>;
}

export interface BackupItem {
  id: string;
  dataset: string;
  user_id?: number | null;
  status: string;
  size_bytes: number;
  created_at: string;
}

export interface BackupsResponse {
  items: BackupItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface RetentionPolicy {
  key: string;
  days?: number | null;
  description?: string | null;
}

export interface RetentionPoliciesResponse {
  policies: RetentionPolicy[];
}

export interface ProviderSecret {
  provider: string;
  created_at: string;
  updated_at: string;
}

export interface LLMProviderOverride {
  provider: string;
  is_enabled?: boolean;
  allowed_models?: string[];
  config?: Record<string, unknown>;
  credential_fields?: Record<string, unknown>;
  has_api_key?: boolean;
  api_key_hint?: string;
  created_at?: string;
  updated_at?: string;
}

export interface LLMProvider {
  name: string;
  enabled: boolean;
  models?: string[];
  default_model?: string;
  override?: LLMProviderOverride;
}

export interface DashboardStats {
  users: number;
  organizations: number;
  teams: number;
  apiKeys: number;
  providers: number;
  storageUsedMb: number;
}

export type SecurityHealthData = {
  risk_score?: number;
  recent_security_events?: number;
  failed_logins_24h?: number;
  suspicious_activity?: number;
  mfa_adoption_rate?: number;
  active_sessions?: number;
  api_keys_active?: number;
  last_security_scan?: string;
};

export interface AuthContextType {
  user: User | null;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  isAuthenticated: boolean;
}

// Voice Commands
export type VoiceActionType = 'mcp_tool' | 'workflow' | 'custom' | 'llm_chat';

export interface VoiceCommand {
  id: string;
  user_id: number;
  name: string;
  phrases: string[];
  action_type: VoiceActionType;
  action_config: Record<string, unknown>;
  priority: number;
  enabled: boolean;
  requires_confirmation: boolean;
  description?: string;
  created_at?: string;
  updated_at?: string;
}

export interface VoiceSession {
  session_id: string;
  user_id: number;
  state: string;
  created_at: string;
  last_activity: string;
  turn_count: number;
}

export interface VoiceCommandUsage {
  command_id: string;
  command_name: string;
  total_invocations: number;
  success_count: number;
  error_count: number;
  avg_response_time_ms: number;
  last_used?: string;
}

export interface VoiceAnalytics {
  date: string;
  total_commands: number;
  unique_users: number;
  success_rate: number;
  avg_response_time_ms: number;
  top_commands: Array<{
    command_id: string;
    command_name: string;
    count: number;
  }>;
}

export interface VoiceAnalyticsSummary {
  total_commands_processed: number;
  active_sessions: number;
  total_voice_commands: number;
  enabled_commands: number;
  success_rate: number;
  avg_response_time_ms: number;
  top_commands: VoiceCommandUsage[];
  usage_by_day: VoiceAnalytics[];
}

export type { IncidentEvent, IncidentItem, IncidentsResponse } from './incidents';

// ============================================
// Billing & Subscription Types
// ============================================

export type PlanTier = 'free' | 'pro' | 'enterprise';
export type SubscriptionStatus = 'active' | 'past_due' | 'canceled' | 'trialing' | 'incomplete';

export interface Plan {
  id: string;
  name: string;
  tier: PlanTier;
  stripe_product_id: string;
  stripe_price_id: string;
  monthly_price_cents: number;
  included_token_credits: number;
  overage_rate_per_1k_tokens_cents: number;
  features: string[];
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface Subscription {
  id: string;
  org_id: number;
  plan_id: string;
  plan?: Plan;
  stripe_subscription_id: string;
  status: SubscriptionStatus;
  current_period_start: string;
  current_period_end: string;
  trial_end?: string;
  cancel_at?: string;
  created_at: string;
  updated_at: string;
}

export interface OrgUsageSummary {
  org_id: number;
  period_start: string;
  period_end: string;
  tokens_used: number;
  tokens_included: number;
  tokens_overage: number;
  overage_cost_cents: number;
  breakdown_by_provider: Record<string, number>;
}

export interface Invoice {
  id: string;
  stripe_invoice_id: string;
  amount_cents: number;
  currency: string;
  status: 'paid' | 'open' | 'void' | 'draft' | 'uncollectible';
  invoice_pdf?: string;
  period_start: string;
  period_end: string;
  created_at: string;
}

export interface FeatureRegistryEntry {
  feature_key: string;
  display_name: string;
  description: string;
  plans: string[];
  category: string;
}
