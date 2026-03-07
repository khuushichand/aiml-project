import React, { useEffect, useReducer, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import { useToast } from '@web/components/ui/ToastProvider';
import {
  approveResearchCheckpoint,
  cancelResearchRun,
  createResearchRun,
  getResearchArtifact,
  getResearchBundle,
  getResearchRun,
  listResearchRuns,
  pauseResearchRun,
  resumeResearchRun,
  subscribeResearchRunEvents,
  type ResearchArtifactManifestEntry,
  type ResearchCheckpointSummary,
  type ResearchRun,
  type ResearchRunListItem,
  type ResearchRunSnapshot,
  type ResearchRunStreamEvent,
} from '@web/lib/api/researchRuns';

type ConsoleState = {
  snapshot: ResearchRunSnapshot | null;
  artifactContents: Record<string, unknown>;
  bundle: unknown | null;
};

type ConsoleAction =
  | { type: 'clear' }
  | { type: 'replace-run'; run: ResearchRun }
  | { type: 'replace-snapshot'; snapshot: ResearchRunSnapshot }
  | { type: 'apply-event'; event: ResearchRunStreamEvent }
  | { type: 'store-artifact'; artifactName: string; content: unknown }
  | { type: 'store-bundle'; bundle: unknown };

const INITIAL_STATE: ConsoleState = {
  snapshot: null,
  artifactContents: {},
  bundle: null,
};

function makeSnapshotFromRun(run: ResearchRun): ResearchRunSnapshot {
  return {
    run,
    latest_event_id: 0,
    checkpoint: null,
    artifacts: [],
  };
}

function mergeArtifactEntry(
  artifacts: ResearchArtifactManifestEntry[],
  nextArtifact: ResearchArtifactManifestEntry
): ResearchArtifactManifestEntry[] {
  const remaining = artifacts.filter((artifact) => artifact.artifact_name !== nextArtifact.artifact_name);
  return [...remaining, nextArtifact].sort((left, right) =>
    left.artifact_name.localeCompare(right.artifact_name)
  );
}

function updateLatestEventId(snapshot: ResearchRunSnapshot, eventId?: number): ResearchRunSnapshot {
  if (typeof eventId !== 'number' || !Number.isFinite(eventId) || eventId <= snapshot.latest_event_id) {
    return snapshot;
  }
  return {
    ...snapshot,
    latest_event_id: eventId,
  };
}

function isSnapshotPayload(payload: unknown): payload is ResearchRunSnapshot {
  if (!payload || typeof payload !== 'object') {
    return false;
  }
  const data = payload as Record<string, unknown>;
  return typeof data.latest_event_id === 'number' && typeof data.run === 'object' && data.run !== null;
}

function reducer(state: ConsoleState, action: ConsoleAction): ConsoleState {
  switch (action.type) {
    case 'clear':
      return INITIAL_STATE;
    case 'replace-run':
      if (state.snapshot) {
        const preserveLiveProgress =
          state.snapshot.run.status === action.run.status &&
          state.snapshot.run.phase === action.run.phase;

        return {
          ...state,
          snapshot: {
            ...state.snapshot,
            run: {
              ...state.snapshot.run,
              ...action.run,
              progress_percent: preserveLiveProgress
                ? state.snapshot.run.progress_percent
                : action.run.progress_percent,
              progress_message: preserveLiveProgress
                ? state.snapshot.run.progress_message
                : action.run.progress_message,
            },
          },
        };
      }
      return {
        ...state,
        snapshot: makeSnapshotFromRun(action.run),
      };
    case 'replace-snapshot':
      return {
        ...state,
        snapshot: action.snapshot,
      };
    case 'apply-event': {
      if (action.event.event === 'snapshot' && isSnapshotPayload(action.event.payload)) {
        return {
          ...state,
          snapshot: action.event.payload,
        };
      }
      const current = state.snapshot;
      if (!current) {
        return state;
      }
      if (!action.event.payload || typeof action.event.payload !== 'object') {
        return {
          ...state,
          snapshot: updateLatestEventId(current, action.event.id),
        };
      }

      const payload = action.event.payload as Record<string, unknown>;
      let nextSnapshot = current;

      if (action.event.event === 'status' || action.event.event === 'terminal') {
        nextSnapshot = {
          ...nextSnapshot,
          run: {
            ...nextSnapshot.run,
            ...payload,
          },
        };
      } else if (action.event.event === 'progress') {
        nextSnapshot = {
          ...nextSnapshot,
          run: {
            ...nextSnapshot.run,
            progress_percent:
              typeof payload.progress_percent === 'number'
                ? payload.progress_percent
                : nextSnapshot.run.progress_percent,
            progress_message:
              typeof payload.progress_message === 'string'
                ? payload.progress_message
                : nextSnapshot.run.progress_message,
          },
        };
      } else if (action.event.event === 'checkpoint') {
        if (payload.checkpoint_id === null) {
          nextSnapshot = {
            ...nextSnapshot,
            checkpoint: null,
            run: {
              ...nextSnapshot.run,
              latest_checkpoint_id: null,
            },
          };
        } else {
          const checkpoint = payload as unknown as ResearchCheckpointSummary;
          nextSnapshot = {
            ...nextSnapshot,
            checkpoint,
            run: {
              ...nextSnapshot.run,
              latest_checkpoint_id: checkpoint.checkpoint_id,
            },
          };
        }
      } else if (action.event.event === 'artifact') {
        const artifact = payload as unknown as ResearchArtifactManifestEntry;
        nextSnapshot = {
          ...nextSnapshot,
          artifacts: mergeArtifactEntry(nextSnapshot.artifacts, artifact),
        };
      }

      return {
        ...state,
        snapshot: updateLatestEventId(nextSnapshot, action.event.id),
      };
    }
    case 'store-artifact':
      return {
        ...state,
        artifactContents: {
          ...state.artifactContents,
          [action.artifactName]: action.content,
        },
      };
    case 'store-bundle':
      return {
        ...state,
        bundle: action.bundle,
      };
    default:
      return state;
  }
}

function upsertListItem(
  items: ResearchRunListItem[] | undefined,
  run: ResearchRun,
  query: string
): ResearchRunListItem[] {
  const nextItem: ResearchRunListItem = {
    ...run,
    query,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  const remaining = (items ?? []).filter((item) => item.id !== run.id);
  return [nextItem, ...remaining];
}

function formatArtifactContent(content: unknown): string {
  if (typeof content === 'string') {
    return content;
  }
  return JSON.stringify(content, null, 2);
}

export default function ResearchRunsPage() {
  const queryClient = useQueryClient();
  const { show } = useToast();
  const [question, setQuestion] = useState('');
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);

  const runsQuery = useQuery({
    queryKey: ['research-runs'],
    queryFn: () => listResearchRuns(),
    refetchInterval: 5000,
  });

  const effectiveSelectedRunId = selectedRunId ?? runsQuery.data?.[0]?.id ?? null;
  const selectedListItem =
    runsQuery.data?.find((run) => run.id === effectiveSelectedRunId) ?? runsQuery.data?.[0] ?? null;

  useEffect(() => {
    if (!selectedRunId && runsQuery.data && runsQuery.data.length > 0) {
      setSelectedRunId(runsQuery.data[0].id);
    }
  }, [runsQuery.data, selectedRunId]);

  useEffect(() => {
    dispatch({ type: 'clear' });
  }, [effectiveSelectedRunId]);

  const selectedRunQuery = useQuery({
    queryKey: ['research-run', effectiveSelectedRunId],
    queryFn: () => getResearchRun(effectiveSelectedRunId!),
    enabled: Boolean(effectiveSelectedRunId),
  });

  useEffect(() => {
    if (selectedRunQuery.data) {
      dispatch({ type: 'replace-run', run: selectedRunQuery.data });
    }
  }, [selectedRunQuery.data]);

  useEffect(() => {
    if (!effectiveSelectedRunId) {
      return;
    }
    return subscribeResearchRunEvents({
      sessionId: effectiveSelectedRunId,
      afterId: 0,
      onEvent: (event) => {
        dispatch({ type: 'apply-event', event });
      },
      onError: (error) => {
        const message = error instanceof Error ? error.message : 'Research stream disconnected';
        show({
          title: 'Research stream warning',
          description: message,
          variant: 'warning',
        });
      },
    });
  }, [effectiveSelectedRunId, show]);

  const selectedSnapshot = state.snapshot;
  const selectedRun = selectedSnapshot?.run ?? selectedRunQuery.data ?? selectedListItem;
  const selectedRunTitle =
    selectedListItem?.query ||
    (selectedSnapshot?.run as ResearchRun & { query?: string } | undefined)?.query ||
    selectedRun?.id ||
    'No run selected';

  async function handleCreateRun(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) {
      return;
    }
    try {
      const createdRun = await createResearchRun({
        query: trimmed,
        source_policy: 'balanced',
        autonomy_mode: 'checkpointed',
      });
      queryClient.setQueryData<ResearchRunListItem[]>(['research-runs'], (current) =>
        upsertListItem(current, createdRun, trimmed)
      );
      setSelectedRunId(createdRun.id);
      dispatch({ type: 'replace-run', run: createdRun });
      setQuestion('');
    } catch (error) {
      show({
        title: 'Run creation failed',
        description: error instanceof Error ? error.message : 'Unable to start research run',
        variant: 'danger',
      });
    }
  }

  async function handleRefreshSelectedRun() {
    if (!effectiveSelectedRunId) {
      return;
    }
    const refreshed = await selectedRunQuery.refetch();
    if (refreshed.data) {
      dispatch({ type: 'replace-run', run: refreshed.data });
    }
  }

  async function handlePauseRun() {
    if (!effectiveSelectedRunId) {
      return;
    }
    const updated = await pauseResearchRun(effectiveSelectedRunId);
    dispatch({ type: 'replace-run', run: updated });
  }

  async function handleResumeRun() {
    if (!effectiveSelectedRunId) {
      return;
    }
    const updated = await resumeResearchRun(effectiveSelectedRunId);
    dispatch({ type: 'replace-run', run: updated });
  }

  async function handleCancelRun() {
    if (!effectiveSelectedRunId) {
      return;
    }
    const updated = await cancelResearchRun(effectiveSelectedRunId);
    dispatch({ type: 'replace-run', run: updated });
  }

  async function handleApproveCheckpoint() {
    if (!effectiveSelectedRunId || !selectedSnapshot?.checkpoint) {
      return;
    }
    const updated = await approveResearchCheckpoint(
      effectiveSelectedRunId,
      selectedSnapshot.checkpoint.checkpoint_id,
      {}
    );
    dispatch({ type: 'replace-run', run: updated });
  }

  async function handleLoadArtifact(artifactName: string) {
    if (!effectiveSelectedRunId) {
      return;
    }
    const artifact = await getResearchArtifact(effectiveSelectedRunId, artifactName);
    dispatch({
      type: 'store-artifact',
      artifactName,
      content: artifact.content,
    });
  }

  async function handleLoadBundle() {
    if (!effectiveSelectedRunId) {
      return;
    }
    const bundle = await getResearchBundle(effectiveSelectedRunId);
    dispatch({
      type: 'store-bundle',
      bundle,
    });
  }

  const canPause = selectedRun && selectedRun.control_state === 'running' && selectedRun.status !== 'completed';
  const canResume = selectedRun?.control_state === 'paused';
  const canCancel = selectedRun && !['completed', 'failed', 'cancelled'].includes(selectedRun.status);
  const canLoadBundle = selectedRun?.status === 'completed';

  return (
    <div className="min-h-screen bg-bg text-foreground">
      <main className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 lg:flex-row lg:px-8">
        <section className="w-full rounded-2xl border border-border bg-card/95 p-5 shadow-sm lg:max-w-md">
          <div className="space-y-1">
            <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Deep Research</p>
            <h1 className="text-2xl font-semibold">Run console</h1>
            <p className="text-sm text-muted-foreground">
              Create long-running research runs and inspect them live.
            </p>
          </div>

          <form className="mt-5 space-y-3" onSubmit={handleCreateRun}>
            <label className="block text-sm font-medium" htmlFor="research-question">
              Research question
            </label>
            <textarea
              id="research-question"
              className="min-h-28 w-full rounded-xl border border-border bg-bg px-3 py-2 text-sm outline-none transition focus:border-primary"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
            />
            <button
              type="submit"
              className="inline-flex rounded-full bg-primary px-4 py-2 text-sm font-medium text-white transition hover:opacity-90"
            >
              Start run
            </button>
          </form>

          <div className="mt-6 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                Newly created runs
              </h2>
              {runsQuery.isFetching && <span className="text-xs text-muted-foreground">Refreshing…</span>}
            </div>
            <div className="space-y-2">
              {runsQuery.data?.map((run) => {
                const selected = run.id === effectiveSelectedRunId;
                return (
                  <button
                    key={run.id}
                    type="button"
                    className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                      selected
                        ? 'border-primary bg-primary/5 shadow-sm'
                        : 'border-border bg-bg/70 hover:border-primary/40'
                    }`}
                    onClick={() => setSelectedRunId(run.id)}
                  >
                    <div className="text-sm font-medium">{run.query}</div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {run.status} · {run.phase} · {run.control_state}
                    </div>
                    {run.progress_message && (
                      <div className="mt-2 text-sm text-muted-foreground">{run.progress_message}</div>
                    )}
                  </button>
                );
              })}
              {!runsQuery.isLoading && (!runsQuery.data || runsQuery.data.length === 0) && (
                <div className="rounded-2xl border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                  No research runs yet.
                </div>
              )}
            </div>
          </div>
        </section>

        <section className="flex-1 rounded-2xl border border-border bg-card p-5 shadow-sm">
          <div className="flex flex-col gap-3 border-b border-border pb-4 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Selected run</p>
              <h2 className="mt-1 text-2xl font-semibold">Selected run: {selectedRunTitle}</h2>
              {selectedRun && (
                <p className="mt-2 text-sm text-muted-foreground">
                  {selectedRun.status} · {selectedRun.phase} · {selectedRun.control_state}
                </p>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="rounded-full border border-border px-3 py-2 text-sm hover:bg-muted"
                onClick={handleRefreshSelectedRun}
              >
                Refresh selected run
              </button>
              <button
                type="button"
                className="rounded-full border border-border px-3 py-2 text-sm hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                onClick={handlePauseRun}
                disabled={!canPause}
              >
                Pause
              </button>
              <button
                type="button"
                className="rounded-full border border-border px-3 py-2 text-sm hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                onClick={handleResumeRun}
                disabled={!canResume}
              >
                Resume
              </button>
              <button
                type="button"
                className="rounded-full border border-danger/30 px-3 py-2 text-sm text-danger hover:bg-danger/10 disabled:cursor-not-allowed disabled:opacity-50"
                onClick={handleCancelRun}
                disabled={!canCancel}
              >
                Cancel
              </button>
            </div>
          </div>

          {!selectedRun && (
            <div className="py-10 text-sm text-muted-foreground">Select a research run to inspect it.</div>
          )}

          {selectedRun && (
            <div className="space-y-6 py-5">
              <section className="rounded-2xl border border-border bg-bg/70 p-4">
                <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  Live status
                </h3>
                <div className="mt-3 grid gap-3 md:grid-cols-3">
                  <div className="rounded-xl border border-border bg-card px-3 py-3">
                    <div className="text-xs text-muted-foreground">Phase</div>
                    <div className="mt-1 text-sm font-medium">{selectedRun.phase}</div>
                  </div>
                  <div className="rounded-xl border border-border bg-card px-3 py-3">
                    <div className="text-xs text-muted-foreground">Progress</div>
                    <div className="mt-1 text-sm font-medium">
                      {selectedRun.progress_percent ?? 0}%
                    </div>
                  </div>
                  <div className="rounded-xl border border-border bg-card px-3 py-3">
                    <div className="text-xs text-muted-foreground">Message</div>
                    <div className="mt-1 text-sm font-medium">
                      {selectedRun.progress_message || 'Waiting for updates'}
                    </div>
                  </div>
                </div>
              </section>

              <section className="rounded-2xl border border-border bg-bg/70 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                      Checkpoint
                    </h3>
                    {selectedSnapshot?.checkpoint ? (
                      <p className="mt-2 text-sm font-medium">
                        {selectedSnapshot.checkpoint.checkpoint_type}
                      </p>
                    ) : (
                      <p className="mt-2 text-sm text-muted-foreground">No checkpoint awaiting review.</p>
                    )}
                  </div>
                  <button
                    type="button"
                    className="rounded-full bg-primary px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                    onClick={handleApproveCheckpoint}
                    disabled={!selectedSnapshot?.checkpoint}
                  >
                    Approve checkpoint
                  </button>
                </div>
                {selectedSnapshot?.checkpoint && (
                  <pre className="mt-4 overflow-x-auto rounded-xl border border-border bg-card p-3 text-xs text-muted-foreground">
                    {JSON.stringify(selectedSnapshot.checkpoint.proposed_payload, null, 2)}
                  </pre>
                )}
              </section>

              <section className="rounded-2xl border border-border bg-bg/70 p-4">
                <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  Artifacts
                </h3>
                <div className="mt-3 space-y-3">
                  {selectedSnapshot?.artifacts.length ? (
                    selectedSnapshot.artifacts.map((artifact) => (
                      <div
                        key={artifact.artifact_name}
                        className="rounded-xl border border-border bg-card px-3 py-3"
                      >
                        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                          <div>
                            <div className="text-sm font-medium">{artifact.artifact_name}</div>
                            <div className="mt-1 text-xs text-muted-foreground">
                              v{artifact.artifact_version} · {artifact.phase}
                            </div>
                          </div>
                          <button
                            type="button"
                            className="rounded-full border border-border px-3 py-2 text-sm hover:bg-muted"
                            onClick={() => handleLoadArtifact(artifact.artifact_name)}
                          >
                            Load {artifact.artifact_name}
                          </button>
                        </div>
                        {state.artifactContents[artifact.artifact_name] !== undefined && (
                          <pre className="mt-3 overflow-x-auto rounded-xl border border-border bg-bg p-3 text-xs text-muted-foreground">
                            {formatArtifactContent(state.artifactContents[artifact.artifact_name])}
                          </pre>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="rounded-xl border border-dashed border-border px-3 py-4 text-sm text-muted-foreground">
                      No artifact metadata yet.
                    </div>
                  )}
                </div>
              </section>

              <section className="rounded-2xl border border-border bg-bg/70 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                      Bundle
                    </h3>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Load the final package once the run is completed.
                    </p>
                  </div>
                  <button
                    type="button"
                    className="rounded-full border border-border px-3 py-2 text-sm hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                    onClick={handleLoadBundle}
                    disabled={!canLoadBundle}
                  >
                    Load bundle
                  </button>
                </div>
                {state.bundle && (
                  <pre className="mt-4 overflow-x-auto rounded-xl border border-border bg-card p-3 text-xs text-muted-foreground">
                    {formatArtifactContent(state.bundle)}
                  </pre>
                )}
              </section>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
