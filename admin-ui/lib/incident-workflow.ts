import type { IncidentItem } from '@/types/incidents';

export interface IncidentActionItem {
  id: string;
  text: string;
  done: boolean;
}

export interface IncidentWorkflowState {
  assignedTo?: string;
  rootCause?: string;
  impact?: string;
  actionItems: IncidentActionItem[];
}

export type IncidentWorkflowMap = Record<string, IncidentWorkflowState>;

const INCIDENT_WORKFLOW_STORAGE_KEY = 'admin.incidents.workflow.v1';

const toObject = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object'
    ? (value as Record<string, unknown>)
    : null;

const toStringValue = (value: unknown): string | undefined =>
  typeof value === 'string' && value.trim()
    ? value.trim()
    : undefined;

const toActionItems = (value: unknown): IncidentActionItem[] => {
  if (!Array.isArray(value)) return [];
  return value
    .map((entry): IncidentActionItem | null => {
      const obj = toObject(entry);
      if (!obj) return null;
      const id = toStringValue(obj.id) ?? `ai_${Math.random().toString(36).slice(2, 10)}`;
      const text = toStringValue(obj.text) ?? '';
      return {
        id,
        text,
        done: Boolean(obj.done),
      };
    })
    .filter((entry): entry is IncidentActionItem => entry !== null);
};

const getStorage = (): Storage | null =>
  typeof window === 'undefined' ? null : window.localStorage;

export const readIncidentWorkflowMap = (storage?: Storage | null): IncidentWorkflowMap => {
  const resolvedStorage = storage ?? getStorage();
  if (!resolvedStorage) return {};
  try {
    const raw = resolvedStorage.getItem(INCIDENT_WORKFLOW_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    const root = toObject(parsed);
    if (!root) return {};
    const normalized: IncidentWorkflowMap = {};
    Object.entries(root).forEach(([incidentId, value]) => {
      const entry = toObject(value);
      if (!entry) return;
      normalized[incidentId] = {
        assignedTo: toStringValue(entry.assignedTo),
        rootCause: toStringValue(entry.rootCause),
        impact: toStringValue(entry.impact),
        actionItems: toActionItems(entry.actionItems),
      };
    });
    return normalized;
  } catch {
    return {};
  }
};

export const writeIncidentWorkflowMap = (
  state: IncidentWorkflowMap,
  storage?: Storage | null
): void => {
  const resolvedStorage = storage ?? getStorage();
  if (!resolvedStorage) return;
  try {
    resolvedStorage.setItem(INCIDENT_WORKFLOW_STORAGE_KEY, JSON.stringify(state));
  } catch {
    // no-op if storage is unavailable
  }
};

const createDefaultState = (): IncidentWorkflowState => ({
  assignedTo: undefined,
  rootCause: '',
  impact: '',
  actionItems: [],
});

export const ensureIncidentWorkflowState = (
  map: IncidentWorkflowMap,
  incidentId: string
): IncidentWorkflowState => map[incidentId] ?? createDefaultState();

export const upsertIncidentWorkflowState = (
  map: IncidentWorkflowMap,
  incidentId: string,
  nextState: Partial<IncidentWorkflowState>
): IncidentWorkflowMap => ({
  ...map,
  [incidentId]: {
    ...ensureIncidentWorkflowState(map, incidentId),
    ...nextState,
    actionItems: nextState.actionItems ?? ensureIncidentWorkflowState(map, incidentId).actionItems,
  },
});

export const addIncidentActionItem = (
  map: IncidentWorkflowMap,
  incidentId: string
): IncidentWorkflowMap => {
  const current = ensureIncidentWorkflowState(map, incidentId);
  return upsertIncidentWorkflowState(map, incidentId, {
    actionItems: [
      ...current.actionItems,
      {
        id: `ai_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        text: '',
        done: false,
      },
    ],
  });
};

export const updateIncidentActionItem = (
  map: IncidentWorkflowMap,
  incidentId: string,
  actionItemId: string,
  next: Partial<IncidentActionItem>
): IncidentWorkflowMap => {
  const current = ensureIncidentWorkflowState(map, incidentId);
  const actionItems = current.actionItems.map((item) =>
    item.id === actionItemId
      ? { ...item, ...next }
      : item
  );
  return upsertIncidentWorkflowState(map, incidentId, { actionItems });
};

export const removeIncidentActionItem = (
  map: IncidentWorkflowMap,
  incidentId: string,
  actionItemId: string
): IncidentWorkflowMap => {
  const current = ensureIncidentWorkflowState(map, incidentId);
  const actionItems = current.actionItems.filter((item) => item.id !== actionItemId);
  return upsertIncidentWorkflowState(map, incidentId, { actionItems });
};

export const mergeIncidentWorkflowWithIncidents = (
  incidents: IncidentItem[],
  map: IncidentWorkflowMap
): IncidentWorkflowMap => {
  let next = { ...map };
  incidents.forEach((incident) => {
    if (!next[incident.id]) {
      next = upsertIncidentWorkflowState(next, incident.id, {});
    }
  });
  return next;
};

export const buildPostmortemTimelineMessage = (state: IncidentWorkflowState): string => {
  const actionItemCount = state.actionItems.filter((item) => item.text.trim()).length;
  const root = state.rootCause?.trim() ? 'root cause set' : 'root cause pending';
  const impact = state.impact?.trim() ? 'impact set' : 'impact pending';
  return `Post-mortem updated (${root}, ${impact}, ${actionItemCount} action item${actionItemCount === 1 ? '' : 's'})`;
};
