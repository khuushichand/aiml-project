import { describe, expect, it } from 'vitest';
import {
  addIncidentActionItem,
  buildPostmortemTimelineMessage,
  ensureIncidentWorkflowState,
  upsertIncidentWorkflowState,
  updateIncidentActionItem,
} from './incident-workflow';

describe('incident workflow state helpers', () => {
  it('creates default incident workflow state when missing', () => {
    const state = ensureIncidentWorkflowState({}, 'inc-1');
    expect(state.assignedTo).toBeUndefined();
    expect(state.rootCause).toBe('');
    expect(state.impact).toBe('');
    expect(state.actionItems).toEqual([]);
  });

  it('supports action item add and update operations', () => {
    let map = upsertIncidentWorkflowState({}, 'inc-1', {
      rootCause: 'Database lock contention',
      impact: 'Elevated latency for writes',
    });
    map = addIncidentActionItem(map, 'inc-1');
    const added = map['inc-1'].actionItems[0];
    map = updateIncidentActionItem(map, 'inc-1', added.id, {
      text: 'Add lock wait observability dashboard',
      done: true,
    });
    expect(map['inc-1'].actionItems[0].text).toBe('Add lock wait observability dashboard');
    expect(map['inc-1'].actionItems[0].done).toBe(true);
  });

  it('builds a post-mortem timeline summary message', () => {
    const message = buildPostmortemTimelineMessage({
      assignedTo: '2',
      rootCause: 'API pool exhausted',
      impact: 'Requests failed for 4 minutes',
      actionItems: [
        { id: 'a1', text: 'Raise pool limits', done: false },
        { id: 'a2', text: 'Add saturation alert', done: false },
      ],
    });
    expect(message).toContain('Post-mortem updated');
    expect(message).toContain('2 action items');
  });
});
