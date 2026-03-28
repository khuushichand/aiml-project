import type {
  IncidentActionItem,
  IncidentItem,
} from '@/types/incidents';

export interface IncidentWorkflowState {
  assignedTo?: string;
  assignedToLabel?: string;
  rootCause: string;
  impact: string;
  runbookUrl?: string;
  actionItems: IncidentActionItem[];
}

export type IncidentWorkflowMap = Record<string, IncidentWorkflowState>;

const emptyIncidentWorkflowState = (): IncidentWorkflowState => ({
  assignedTo: undefined,
  assignedToLabel: undefined,
  rootCause: '',
  impact: '',
  runbookUrl: '',
  actionItems: [],
});

const cloneActionItems = (items: IncidentActionItem[] | undefined | null): IncidentActionItem[] =>
  Array.isArray(items)
    ? items.map((item) => ({
        id: item.id,
        text: item.text,
        done: Boolean(item.done),
      }))
    : [];

export const incidentWorkflowStateFromIncident = (
  incident: IncidentItem
): IncidentWorkflowState => ({
  assignedTo:
    incident.assigned_to_user_id !== undefined && incident.assigned_to_user_id !== null
      ? String(incident.assigned_to_user_id)
      : undefined,
  assignedToLabel: incident.assigned_to_label ?? undefined,
  rootCause: incident.root_cause ?? '',
  impact: incident.impact ?? '',
  runbookUrl: incident.runbook_url ?? '',
  actionItems: cloneActionItems(incident.action_items),
});

export const ensureIncidentWorkflowState = (
  map: IncidentWorkflowMap,
  incident: IncidentItem
): IncidentWorkflowState => map[incident.id] ?? incidentWorkflowStateFromIncident(incident);

export const replaceIncidentWorkflowState = (
  map: IncidentWorkflowMap,
  incident: IncidentItem
): IncidentWorkflowMap => ({
  ...map,
  [incident.id]: incidentWorkflowStateFromIncident(incident),
});

export const incidentAssignmentWorkflowStateFromIncident = (
  incident: IncidentItem
): Pick<IncidentWorkflowState, 'assignedTo' | 'assignedToLabel'> => ({
  assignedTo:
    incident.assigned_to_user_id !== undefined && incident.assigned_to_user_id !== null
      ? String(incident.assigned_to_user_id)
      : undefined,
  assignedToLabel: incident.assigned_to_label ?? undefined,
});

export const upsertIncidentWorkflowState = (
  map: IncidentWorkflowMap,
  incidentId: string,
  nextState: Partial<IncidentWorkflowState>
): IncidentWorkflowMap => {
  const current = map[incidentId] ?? emptyIncidentWorkflowState();
  return {
    ...map,
    [incidentId]: {
      ...current,
      ...nextState,
      actionItems: nextState.actionItems ?? cloneActionItems(current.actionItems),
    },
  };
};

export const addIncidentActionItem = (
  map: IncidentWorkflowMap,
  incidentId: string
): IncidentWorkflowMap => {
  const current = map[incidentId] ?? emptyIncidentWorkflowState();
  return upsertIncidentWorkflowState(map, incidentId, {
    actionItems: [
      ...cloneActionItems(current.actionItems),
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
  const actionItems = cloneActionItems(map[incidentId]?.actionItems).map((item) =>
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
  const actionItems = cloneActionItems(map[incidentId]?.actionItems).filter(
    (item) => item.id !== actionItemId
  );
  return upsertIncidentWorkflowState(map, incidentId, { actionItems });
};

export const mergeIncidentWorkflowWithIncidents = (
  incidents: IncidentItem[],
  map: IncidentWorkflowMap
): IncidentWorkflowMap =>
  incidents.reduce<IncidentWorkflowMap>((next, incident) => {
    next[incident.id] = map[incident.id] ?? incidentWorkflowStateFromIncident(incident);
    return next;
  }, {});

export const buildPostmortemTimelineMessage = (state: IncidentWorkflowState): string => {
  const actionItemCount = state.actionItems.filter((item) => item.text.trim()).length;
  const root = state.rootCause.trim() ? 'root cause set' : 'root cause pending';
  const impact = state.impact.trim() ? 'impact set' : 'impact pending';
  return `Post-mortem updated (${root}, ${impact}, ${actionItemCount} action item${actionItemCount === 1 ? '' : 's'})`;
};
