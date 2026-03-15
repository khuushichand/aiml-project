import React from "react"
import { useTranslation } from "react-i18next"

import {
  type PersonaExemplar,
  tldwClient
} from "@/services/tldw/TldwApiClient"

type ExemplarImportPanelProps = {
  selectedPersonaId: string
  selectedPersonaName: string
  candidates: PersonaExemplar[]
  onCandidatesImported?: (candidates: PersonaExemplar[]) => void
  onCandidateReviewed?: (candidate: PersonaExemplar) => void
}

export const ExemplarImportPanel: React.FC<ExemplarImportPanelProps> = ({
  selectedPersonaId,
  selectedPersonaName,
  candidates,
  onCandidatesImported,
  onCandidateReviewed
}) => {
  const { t } = useTranslation(["sidepanel", "common"])
  const [transcript, setTranscript] = React.useState("")
  const [error, setError] = React.useState<string | null>(null)
  const [submitting, setSubmitting] = React.useState(false)
  const [reviewingId, setReviewingId] = React.useState<string | null>(null)

  const pendingCandidates = React.useMemo(
    () =>
      candidates.filter(
        (candidate) =>
          candidate.source_type === "generated_candidate" && candidate.enabled === false
      ),
    [candidates]
  )

  const handleImport = async () => {
    if (!selectedPersonaId) {
      return
    }
    if (!transcript.trim()) {
      setError(
        t("sidepanel:personaGarden.voiceExamples.import.validationTranscript", {
          defaultValue: "Transcript is required"
        })
      )
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      const imported = await tldwClient.importPersonaExemplars(selectedPersonaId, {
        transcript: transcript.trim()
      })
      onCandidatesImported?.(imported)
      setTranscript("")
    } catch (importError) {
      setError(
        importError instanceof Error
          ? importError.message
          : t("sidepanel:personaGarden.voiceExamples.import.loadError", {
              defaultValue: "Failed to import transcript candidates."
            })
      )
    } finally {
      setSubmitting(false)
    }
  }

  const handleReview = async (candidateId: string, action: "approve" | "reject") => {
    if (!selectedPersonaId) {
      return
    }
    setReviewingId(candidateId)
    setError(null)
    try {
      const reviewed = await tldwClient.reviewPersonaExemplar(
        selectedPersonaId,
        candidateId,
        { action }
      )
      onCandidateReviewed?.(reviewed)
    } catch (reviewError) {
      setError(
        reviewError instanceof Error
          ? reviewError.message
          : t("sidepanel:personaGarden.voiceExamples.import.reviewError", {
              defaultValue: "Failed to review transcript candidate."
            })
      )
    } finally {
      setReviewingId(null)
    }
  }

  return (
    <div className="rounded-md border border-border bg-bg p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-text-subtle">
        {t("sidepanel:personaGarden.voiceExamples.import.heading", {
          defaultValue: "Transcript Import"
        })}
      </div>
      <p className="mt-2 text-xs text-text-muted">
        {t("sidepanel:personaGarden.voiceExamples.import.description", {
          defaultValue:
            "Create review-gated candidates for {{personaName}} from transcript text.",
          personaName:
            selectedPersonaName ||
            selectedPersonaId ||
            t("sidepanel:personaGarden.voiceExamples.currentPersona", {
              defaultValue: "this persona"
            })
        })}
      </p>

      <label className="mt-3 block text-xs text-text-muted">
        {t("sidepanel:personaGarden.voiceExamples.import.transcriptLabel", {
          defaultValue: "Transcript"
        })}
        <textarea
          data-testid="exemplar-import-transcript-input"
          className="mt-1 min-h-28 w-full rounded-md border border-border bg-surface px-2 py-2 text-sm text-text"
          value={transcript}
          onChange={(event) => setTranscript(event.target.value)}
          placeholder={t(
            "sidepanel:personaGarden.voiceExamples.import.transcriptPlaceholder",
            {
              defaultValue: "Paste transcript text here."
            }
          )}
        />
      </label>

      {error ? <div className="mt-2 text-xs text-red-600">{error}</div> : null}

      <div className="mt-3 flex justify-end">
        <button
          type="button"
          data-testid="exemplar-import-submit"
          className="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface2 disabled:cursor-not-allowed disabled:opacity-60"
          onClick={() => void handleImport()}
          disabled={submitting || !selectedPersonaId}
        >
          {submitting
            ? t("sidepanel:personaGarden.voiceExamples.import.submitting", {
                defaultValue: "Importing..."
              })
            : t("sidepanel:personaGarden.voiceExamples.import.submit", {
                defaultValue: "Create Candidates"
              })}
        </button>
      </div>

      <div className="mt-4 space-y-2">
        <div className="text-xs font-semibold uppercase tracking-wide text-text-subtle">
          {t("sidepanel:personaGarden.voiceExamples.import.queueHeading", {
            defaultValue: "Candidate Review Queue"
          })}
        </div>
        {pendingCandidates.length > 0 ? (
          pendingCandidates.map((candidate) => (
            <div
              key={candidate.id}
              className="rounded-md border border-border bg-surface p-2"
            >
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-text-muted">
                <span>{candidate.kind}</span>
                {candidate.tone ? <span>{candidate.tone}</span> : null}
              </div>
              <div className="mt-1 text-sm text-text">{candidate.content}</div>
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  data-testid={`exemplar-import-approve-${candidate.id}`}
                  className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-2 py-1 text-xs text-emerald-700 hover:bg-emerald-500/15 disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={() => void handleReview(candidate.id, "approve")}
                  disabled={reviewingId === candidate.id}
                >
                  {t("common:approve", { defaultValue: "Approve" })}
                </button>
                <button
                  type="button"
                  data-testid={`exemplar-import-reject-${candidate.id}`}
                  className="rounded-md border border-amber-500/40 bg-amber-500/10 px-2 py-1 text-xs text-amber-700 hover:bg-amber-500/15 disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={() => void handleReview(candidate.id, "reject")}
                  disabled={reviewingId === candidate.id}
                >
                  {t("common:reject", { defaultValue: "Reject" })}
                </button>
              </div>
            </div>
          ))
        ) : (
          <div className="text-xs text-text-muted">
            {t("sidepanel:personaGarden.voiceExamples.import.emptyQueue", {
              defaultValue: "No transcript candidates are waiting for review."
            })}
          </div>
        )}
      </div>
    </div>
  )
}
