export type IncidentEvent = {
  id: string;
  message: string;
  created_at: string;
  actor?: string | null;
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
  resolved_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
  timeline?: IncidentEvent[];
};

export type IncidentsResponse = {
  items: IncidentItem[];
  total: number;
  limit: number;
  offset: number;
};
