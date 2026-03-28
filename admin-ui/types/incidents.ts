export type IncidentEvent = {
  id: string;
  message: string;
  created_at: string;
  actor?: string | null;
};

export type IncidentActionItem = {
  id: string;
  text: string;
  done: boolean;
};

export type IncidentItem = {
  id: string;
  title: string;
  status: 'open' | 'investigating' | 'mitigating' | 'resolved';
  severity: 'low' | 'medium' | 'high' | 'critical';
  summary?: string | null;
  tags?: string[];
  created_at: string;
  updated_at: string;
  acknowledged_at?: string | null;
  resolved_at?: string | null;
  mtta_minutes?: number | null;
  mttr_minutes?: number | null;
  created_by?: string | null;
  updated_by?: string | null;
  timeline?: IncidentEvent[];
  assigned_to_user_id?: number | null;
  assigned_to_label?: string | null;
  root_cause?: string | null;
  impact?: string | null;
  action_items?: IncidentActionItem[];
};

export type IncidentsResponse = {
  items: IncidentItem[];
  total: number;
  limit: number;
  offset: number;
};
