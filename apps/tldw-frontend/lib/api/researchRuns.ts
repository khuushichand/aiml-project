import { apiClient, buildAuthHeaders, getApiBaseUrl } from '@web/lib/api';
import { streamStructuredSSE } from '@web/lib/sse';

export interface ResearchRunCreateRequest {
  query: string;
  source_policy?: string;
  autonomy_mode?: string;
  limits_json?: Record<string, unknown> | null;
  provider_overrides?: Record<string, unknown> | null;
}

export interface ResearchRun {
  id: string;
  status: string;
  phase: string;
  control_state: string;
  progress_percent?: number | null;
  progress_message?: string | null;
  active_job_id?: string | null;
  latest_checkpoint_id?: string | null;
  completed_at?: string | null;
}

export interface ResearchRunListItem extends ResearchRun {
  query: string;
  created_at: string;
  updated_at: string;
}

export interface ResearchCheckpointSummary {
  checkpoint_id: string;
  checkpoint_type: string;
  status: string;
  proposed_payload: Record<string, unknown>;
  resolution?: string | null;
}

export interface ResearchArtifactManifestEntry {
  artifact_name: string;
  artifact_version: number;
  content_type: string;
  phase: string;
  job_id?: string | null;
}

export interface ResearchRunSnapshot {
  run: ResearchRun;
  latest_event_id: number;
  checkpoint?: ResearchCheckpointSummary | null;
  artifacts: ResearchArtifactManifestEntry[];
}

export interface ResearchArtifactResponse {
  artifact_name: string;
  content_type: string;
  content: unknown;
}

export interface ResearchRunStreamEvent {
  event: string;
  id?: number;
  payload?: unknown;
}

export interface SubscribeResearchRunEventsOptions {
  sessionId: string;
  afterId?: number;
  reconnectDelayMs?: number;
  onEvent: (event: ResearchRunStreamEvent) => void;
  onError?: (error: unknown) => void;
}

const DEFAULT_RECONNECT_DELAY_MS = 1200;

function toQuery(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null) {
      return;
    }
    search.set(key, String(value));
  });
  const encoded = search.toString();
  return encoded ? `?${encoded}` : '';
}

function runStreamUrl(sessionId: string, afterId: number): string {
  const baseUrl = getApiBaseUrl().replace(/\/$/, '');
  return `${baseUrl}/research/runs/${encodeURIComponent(sessionId)}/events/stream${toQuery({ after_id: afterId })}`;
}

async function readResearchRunStream(
  signal: AbortSignal,
  sessionId: string,
  afterId: number,
  onEvent: (event: ResearchRunStreamEvent) => void
): Promise<{ cursor: number; terminalSeen: boolean }> {
  const headers = buildAuthHeaders('GET');
  if (afterId > 0) {
    headers['Last-Event-ID'] = String(afterId);
  }

  let cursor = afterId;
  let terminalSeen = false;

  await streamStructuredSSE(
    runStreamUrl(sessionId, afterId),
    {
      method: 'GET',
      headers,
      credentials: 'include',
      signal,
    },
    (event) => {
      if (typeof event.id === 'number' && Number.isFinite(event.id) && event.id > cursor) {
        cursor = event.id;
      }
      if (event.event === 'terminal') {
        terminalSeen = true;
      }
      onEvent({
        event: event.event,
        id: event.id,
        payload: event.payload,
      });
    }
  );

  return { cursor, terminalSeen };
}

export function listResearchRuns(limit?: number): Promise<ResearchRunListItem[]> {
  const query = typeof limit === 'number' ? toQuery({ limit }) : '';
  return apiClient.get<ResearchRunListItem[]>(`/research/runs${query}`);
}

export function createResearchRun(payload: ResearchRunCreateRequest): Promise<ResearchRun> {
  return apiClient.post<ResearchRun>('/research/runs', payload);
}

export function getResearchRun(sessionId: string): Promise<ResearchRun> {
  return apiClient.get<ResearchRun>(`/research/runs/${sessionId}`);
}

export function pauseResearchRun(sessionId: string): Promise<ResearchRun> {
  return apiClient.post<ResearchRun>(`/research/runs/${sessionId}/pause`);
}

export function resumeResearchRun(sessionId: string): Promise<ResearchRun> {
  return apiClient.post<ResearchRun>(`/research/runs/${sessionId}/resume`);
}

export function cancelResearchRun(sessionId: string): Promise<ResearchRun> {
  return apiClient.post<ResearchRun>(`/research/runs/${sessionId}/cancel`);
}

export function approveResearchCheckpoint(
  sessionId: string,
  checkpointId: string,
  patchPayload?: Record<string, unknown>
): Promise<ResearchRun> {
  const body = patchPayload === undefined ? {} : { patch_payload: patchPayload };
  return apiClient.post<ResearchRun>(
    `/research/runs/${sessionId}/checkpoints/${checkpointId}/patch-and-approve`,
    body
  );
}

export function getResearchArtifact(
  sessionId: string,
  artifactName: string
): Promise<ResearchArtifactResponse> {
  return apiClient.get<ResearchArtifactResponse>(
    `/research/runs/${sessionId}/artifacts/${artifactName}`
  );
}

export function getResearchBundle<T = Record<string, unknown>>(sessionId: string): Promise<T> {
  return apiClient.get<T>(`/research/runs/${sessionId}/bundle`);
}

export function subscribeResearchRunEvents(
  options: SubscribeResearchRunEventsOptions
): () => void {
  const controller = new AbortController();
  const reconnectDelayMs = Math.max(250, options.reconnectDelayMs ?? DEFAULT_RECONNECT_DELAY_MS);
  let cursor = Math.max(0, options.afterId ?? 0);

  const run = async () => {
    while (!controller.signal.aborted) {
      try {
        const next = await readResearchRunStream(
          controller.signal,
          options.sessionId,
          cursor,
          options.onEvent
        );
        cursor = next.cursor;
        if (next.terminalSeen) {
          break;
        }
      } catch (error) {
        if (controller.signal.aborted) {
          break;
        }
        options.onError?.(error);
        await new Promise((resolve) => setTimeout(resolve, reconnectDelayMs));
      }
    }
  };

  void run();
  return () => controller.abort();
}
