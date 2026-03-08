import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { renderWithProviders } from '@web/__tests__/testUtils/renderWithProviders';

const mocks = vi.hoisted(() => ({
  listResearchRuns: vi.fn(),
  createResearchRun: vi.fn(),
  getResearchRun: vi.fn(),
  pauseResearchRun: vi.fn(),
  resumeResearchRun: vi.fn(),
  cancelResearchRun: vi.fn(),
  approveResearchCheckpoint: vi.fn(),
  getResearchArtifact: vi.fn(),
  getResearchBundle: vi.fn(),
  subscribeResearchRunEvents: vi.fn(),
}));

vi.mock('@web/lib/api/researchRuns', () => ({
  listResearchRuns: (...args: unknown[]) => mocks.listResearchRuns(...args),
  createResearchRun: (...args: unknown[]) => mocks.createResearchRun(...args),
  getResearchRun: (...args: unknown[]) => mocks.getResearchRun(...args),
  pauseResearchRun: (...args: unknown[]) => mocks.pauseResearchRun(...args),
  resumeResearchRun: (...args: unknown[]) => mocks.resumeResearchRun(...args),
  cancelResearchRun: (...args: unknown[]) => mocks.cancelResearchRun(...args),
  approveResearchCheckpoint: (...args: unknown[]) => mocks.approveResearchCheckpoint(...args),
  getResearchArtifact: (...args: unknown[]) => mocks.getResearchArtifact(...args),
  getResearchBundle: (...args: unknown[]) => mocks.getResearchBundle(...args),
  subscribeResearchRunEvents: (...args: unknown[]) => mocks.subscribeResearchRunEvents(...args),
}));

import ResearchRunsPage from '@web/pages/research';

function makeRun(overrides: Record<string, unknown> = {}) {
  return {
    id: 'rs_1',
    query: 'Investigate local evidence',
    status: 'running',
    phase: 'collecting',
    control_state: 'running',
    progress_percent: 35,
    progress_message: 'Planning research',
    active_job_id: '11',
    latest_checkpoint_id: 'chk_1',
    created_at: '2026-03-07T10:00:00Z',
    updated_at: '2026-03-07T10:05:00Z',
    completed_at: null,
    ...overrides,
  };
}

function makeSnapshot(overrides: Record<string, unknown> = {}) {
  return {
    run: makeRun(),
    latest_event_id: 5,
    checkpoint: {
      checkpoint_id: 'chk_1',
      checkpoint_type: 'plan_review',
      status: 'pending',
      proposed_payload: {
        query: 'Investigate local evidence',
        focus_areas: ['background', 'counterevidence'],
        constraints: ['Use cited sources'],
        open_questions: ['What changed most recently?'],
        stop_criteria: {
          min_cited_sections: 1,
          min_sources: 2,
        },
      },
      resolution: null,
    },
    artifacts: [
      {
        artifact_name: 'plan.json',
        artifact_version: 1,
        content_type: 'application/json',
        phase: 'drafting_plan',
        job_id: '11',
      },
    ],
    ...overrides,
  };
}

describe('ResearchRunsPage', () => {
  let currentSnapshot: ReturnType<typeof makeSnapshot>;

  beforeEach(() => {
    vi.clearAllMocks();
    currentSnapshot = makeSnapshot();

    mocks.listResearchRuns.mockResolvedValue([
      makeRun(),
      makeRun({
        id: 'rs_0',
        query: 'Older run',
        latest_checkpoint_id: null,
        created_at: '2026-03-07T09:00:00Z',
        updated_at: '2026-03-07T09:05:00Z',
      }),
    ]);
    mocks.getResearchRun.mockImplementation(async (sessionId: string) => {
      if (sessionId === 'rs_new') {
        return makeRun({
          id: 'rs_new',
          query: 'Newly created run',
          latest_checkpoint_id: null,
        });
      }
      return makeRun({ id: sessionId });
    });
    mocks.createResearchRun.mockResolvedValue(
      makeRun({
        id: 'rs_new',
        query: 'Newly created run',
        latest_checkpoint_id: null,
      })
    );
    mocks.pauseResearchRun.mockResolvedValue(makeRun({ control_state: 'pause_requested' }));
    mocks.resumeResearchRun.mockResolvedValue(makeRun({ control_state: 'running' }));
    mocks.cancelResearchRun.mockResolvedValue(makeRun({ control_state: 'cancel_requested' }));
    mocks.approveResearchCheckpoint.mockResolvedValue(
      makeRun({
        phase: 'collecting',
        latest_checkpoint_id: null,
      })
    );
    mocks.getResearchArtifact.mockResolvedValue({
      artifact_name: 'plan.json',
      content_type: 'application/json',
      content: { artifact_summary: 'Loaded artifact body' },
    });
    mocks.getResearchBundle.mockResolvedValue({
      concise_answer: 'Final synthesized answer',
      report: '# Final report',
    });
    mocks.subscribeResearchRunEvents.mockImplementation((options: {
      sessionId: string;
      onEvent: (event: { event: string; id?: number; payload?: unknown }) => void;
    }) => {
      if (options.sessionId === 'rs_1') {
        options.onEvent({
          event: 'snapshot',
          id: 5,
          payload: currentSnapshot,
        });
        options.onEvent({
          event: 'progress',
          id: 6,
          payload: {
            id: 'rs_1',
            progress_percent: 55,
            progress_message: 'Collecting sources',
          },
        });
      }
      if (options.sessionId === 'rs_new') {
        options.onEvent({
          event: 'snapshot',
          id: 7,
          payload: makeSnapshot({
            run: makeRun({
              id: 'rs_new',
              query: 'Newly created run',
              latest_checkpoint_id: null,
            }),
            checkpoint: null,
            artifacts: [],
          }),
        });
      }
      return () => {};
    });
  });

  it('renders run history and applies live snapshot updates for the selected run', async () => {
    renderWithProviders(<ResearchRunsPage />);

    expect(await screen.findByText('Investigate local evidence')).toBeInTheDocument();
    expect(await screen.findByText('Collecting sources')).toBeInTheDocument();
    expect(screen.getByText('plan_review')).toBeInTheDocument();
    expect(mocks.subscribeResearchRunEvents).toHaveBeenCalledWith(
      expect.objectContaining({
        sessionId: 'rs_1',
        afterId: 0,
      })
    );
  });

  it('creates a run and selects the new session', async () => {
    const user = userEvent.setup();

    renderWithProviders(<ResearchRunsPage />);

    await screen.findByText('Investigate local evidence');
    await user.type(screen.getByLabelText('Research question'), 'Newly created run');
    await user.click(screen.getByRole('button', { name: 'Start run' }));

    await waitFor(() => {
      expect(mocks.createResearchRun).toHaveBeenCalledWith({
        query: 'Newly created run',
        source_policy: 'balanced',
        autonomy_mode: 'checkpointed',
      });
    });
    expect(await screen.findByText('Selected run: Newly created run')).toBeInTheDocument();
  });

  it('submits an edited plan_review checkpoint patch', async () => {
    const user = userEvent.setup();

    renderWithProviders(<ResearchRunsPage />);

    await screen.findByText('Investigate local evidence');
    await user.clear(screen.getByLabelText('Focus areas'));
    await user.type(screen.getByLabelText('Focus areas'), 'background{enter}counterevidence{enter}primary sources');
    await user.clear(screen.getByLabelText('Minimum sources'));
    await user.type(screen.getByLabelText('Minimum sources'), '3');
    await user.click(screen.getByRole('button', { name: 'Approve checkpoint' }));

    await waitFor(() => {
      expect(mocks.approveResearchCheckpoint).toHaveBeenCalledWith('rs_1', 'chk_1', {
        focus_areas: ['background', 'counterevidence', 'primary sources'],
        constraints: ['Use cited sources'],
        open_questions: ['What changed most recently?'],
        stop_criteria: {
          min_cited_sections: 1,
          min_sources: 3,
        },
      });
    });
  });

  it('submits a sources_review patch with curation and recollection directives', async () => {
    const user = userEvent.setup();
    currentSnapshot = makeSnapshot({
      checkpoint: {
        checkpoint_id: 'chk_sources',
        checkpoint_type: 'sources_review',
        status: 'pending',
        proposed_payload: {
          query: 'Investigate local evidence',
          focus_areas: ['background'],
          source_inventory: [
            { source_id: 'src_1', title: 'Primary memo', provider: 'local_corpus', focus_area: 'background' },
            { source_id: 'src_2', title: 'Counter note', provider: 'kagi', focus_area: 'background' },
          ],
          collection_summary: { source_count: 2 },
        },
        resolution: null,
      },
    });
    mocks.approveResearchCheckpoint.mockResolvedValue(
      makeRun({
        phase: 'collecting',
        latest_checkpoint_id: null,
      })
    );

    renderWithProviders(<ResearchRunsPage />);

    await screen.findByText('Investigate local evidence');
    await user.click(screen.getByRole('button', { name: 'Pin Primary memo' }));
    await user.click(screen.getByRole('button', { name: 'Drop Counter note' }));
    await user.click(screen.getByRole('button', { name: 'Prioritize Primary memo' }));
    await user.click(screen.getByLabelText('Recollect sources'));
    await user.click(screen.getByLabelText('Need more primary sources'));
    await user.click(screen.getByLabelText('Need more contradictions'));
    await user.type(screen.getByLabelText('Recollection guidance'), 'Look for newer contradictory primary sources.');
    await user.click(screen.getByRole('button', { name: 'Approve checkpoint' }));

    await waitFor(() => {
      expect(mocks.approveResearchCheckpoint).toHaveBeenCalledWith('rs_1', 'chk_sources', {
        pinned_source_ids: ['src_1'],
        dropped_source_ids: ['src_2'],
        prioritized_source_ids: ['src_1'],
        recollect: {
          enabled: true,
          need_primary_sources: true,
          need_contradictions: true,
          guidance: 'Look for newer contradictory primary sources.',
        },
      });
    });
  });

  it('blocks invalid sources_review edits and submits an edited outline_review patch', async () => {
    const user = userEvent.setup();
    currentSnapshot = makeSnapshot({
      checkpoint: {
        checkpoint_id: 'chk_outline',
        checkpoint_type: 'outline_review',
        status: 'pending',
        proposed_payload: {
          outline: {
            sections: [
              { title: 'Background', focus_area: 'background' },
              { title: 'Counterevidence', focus_area: 'counterevidence' },
            ],
          },
          focus_areas: ['background', 'counterevidence'],
        },
        resolution: null,
      },
    });

    renderWithProviders(<ResearchRunsPage />);

    await screen.findByText('Investigate local evidence');
    await user.clear(screen.getByLabelText('Section title 1'));
    await user.click(screen.getByRole('button', { name: 'Approve checkpoint' }));

    expect(screen.getByText('Every outline section needs a title and focus area.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Approve checkpoint' })).toBeDisabled();

    await user.type(screen.getByLabelText('Section title 1'), 'Background context');
    await user.click(screen.getByRole('button', { name: 'Move section down: background' }));
    await user.click(screen.getByRole('button', { name: 'Approve checkpoint' }));

    await waitFor(() => {
      expect(mocks.approveResearchCheckpoint).toHaveBeenCalledWith('rs_1', 'chk_outline', {
        sections: [
          { title: 'Counterevidence', focus_area: 'counterevidence' },
          { title: 'Background context', focus_area: 'background' },
        ],
      });
    });
  });

  it('lazy-loads artifacts and completed bundles', async () => {
    const user = userEvent.setup();

    renderWithProviders(<ResearchRunsPage />);

    await screen.findByText('Investigate local evidence');
    await user.click(screen.getByRole('button', { name: 'Load plan.json' }));
    await waitFor(() => {
      expect(mocks.getResearchArtifact).toHaveBeenCalledWith('rs_1', 'plan.json');
    });
    expect(await screen.findByText(/Loaded artifact body/)).toBeInTheDocument();

    mocks.getResearchRun.mockResolvedValueOnce(
      makeRun({
        id: 'rs_1',
        status: 'completed',
        phase: 'completed',
        progress_message: 'Completed',
        latest_checkpoint_id: null,
        completed_at: '2026-03-07T10:10:00Z',
      })
    );

    await user.click(screen.getByRole('button', { name: 'Refresh selected run' }));
    await user.click(screen.getByRole('button', { name: 'Load bundle' }));
    await waitFor(() => {
      expect(mocks.getResearchBundle).toHaveBeenCalledWith('rs_1');
    });
    expect(await screen.findByText(/Final synthesized answer/)).toBeInTheDocument();
  });
});
