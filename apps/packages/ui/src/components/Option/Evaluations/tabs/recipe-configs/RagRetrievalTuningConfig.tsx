import React from "react"
import { Alert, Button, Card, Checkbox, Input, Typography } from "antd"
import type { DatasetSample } from "@/services/evaluations"

const { Text } = Typography
const { TextArea } = Input

type TargetItem = {
  id: string
  grade: number
}

type SpanItem = {
  source: "media_db" | "notes"
  record_id: string
  start: number
  end: number
  grade: number
}

type Props = {
  datasetSource: "inline" | "saved"
  dataset: DatasetSample[]
  runConfig: Record<string, any>
  onDatasetChange: (next: DatasetSample[]) => void
  onRunConfigChange: (next: Record<string, any>) => void
}

const DEFAULT_WEAK_SUPERVISION_BUDGET = {
  review_sample_fraction: 0.2,
  max_review_samples: 25,
  min_review_samples: 3,
  synthetic_query_limit: 20
}

const DEFAULT_RETRIEVAL_CONFIG = {
  search_mode: "hybrid",
  top_k: 10,
  hybrid_alpha: 0.7,
  enable_reranking: true,
  reranking_strategy: "flashrank",
  rerank_top_k: 10
}

const DEFAULT_INDEXING_CONFIG = {
  chunking_preset: "baseline"
}

const splitCsv = (value: string): string[] =>
  value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean)

const joinCsv = (items: unknown): string =>
  Array.isArray(items)
    ? items
        .map((item) => String(item || "").trim())
        .filter(Boolean)
        .join(", ")
    : ""

const splitLines = (value: string): string[] =>
  value
    .split(/\r?\n/)
    .map((entry) => entry.trim())
    .filter(Boolean)

const parseNumeric = (value: unknown, fallback: number): number => {
  const next = Number(value)
  return Number.isFinite(next) ? next : fallback
}

const parseInteger = (value: unknown, fallback: number): number => {
  const next = Number.parseInt(String(value), 10)
  return Number.isFinite(next) ? next : fallback
}

const normalizeSources = (sources: unknown): Array<"media_db" | "notes"> => {
  const normalized = Array.isArray(sources)
    ? sources
        .map((source) => String(source).trim())
        .filter((source): source is "media_db" | "notes" =>
          source === "media_db" || source === "notes"
        )
    : []
  return normalized.length > 0 ? Array.from(new Set(normalized)) : ["media_db", "notes"]
}

const parseTargetText = (value: string): TargetItem[] =>
  splitLines(value).map((entry) => {
    const [rawId, rawGrade] = entry.split(":").map((part) => part.trim())
    return {
      id: rawId,
      grade: Math.max(0, Math.min(3, parseInteger(rawGrade, 1)))
    }
  })

const formatTargetText = (items: unknown): string =>
  Array.isArray(items)
    ? items
        .map((item) => {
          if (!item || typeof item !== "object") return ""
          const record = item as Record<string, any>
          const id = String(record.id ?? record.record_id ?? "").trim()
          if (!id) return ""
          const grade = Math.max(0, Math.min(3, parseInteger(record.grade, 1)))
          return `${id}:${grade}`
        })
        .filter(Boolean)
        .join("\n")
    : ""

const parseSpanText = (value: string): SpanItem[] =>
  splitLines(value)
    .map((entry) => {
      const [rawSource, rawRecordId, rawStart, rawEnd, rawGrade] = entry
        .split(",")
        .map((part) => part.trim())
      if (
        (rawSource !== "media_db" && rawSource !== "notes") ||
        !rawRecordId ||
        rawStart === undefined ||
        rawEnd === undefined
      ) {
        return null
      }
      return {
        source: rawSource,
        record_id: rawRecordId,
        start: parseInteger(rawStart, 0),
        end: parseInteger(rawEnd, 0),
        grade: Math.max(0, Math.min(3, parseInteger(rawGrade, 1)))
      } satisfies SpanItem
    })
    .filter((item): item is SpanItem => item !== null)

const formatSpanText = (items: unknown): string =>
  Array.isArray(items)
    ? items
        .map((item) => {
          if (!item || typeof item !== "object") return ""
          const span = item as Record<string, any>
          const source = String(span.source || "").trim()
          const recordId = String(span.record_id || "").trim()
          if (
            (source !== "media_db" && source !== "notes") ||
            !recordId ||
            span.start == null ||
            span.end == null
          ) {
            return ""
          }
          const grade = Math.max(0, Math.min(3, parseInteger(span.grade, 1)))
          return `${source},${recordId},${parseInteger(span.start, 0)},${parseInteger(span.end, 0)},${grade}`
        })
        .filter(Boolean)
        .join("\n")
    : ""

const normalizeDataset = (dataset: DatasetSample[]): DatasetSample[] => {
  const baseSamples = Array.isArray(dataset) && dataset.length > 0 ? dataset : [{}]
  return baseSamples.map((sample, index) => {
    const sampleRecord = sample && typeof sample === "object" ? sample : {}
    const sampleId =
      String(
        (sampleRecord as Record<string, any>).sample_id ??
          (sampleRecord as Record<string, any>).query_id ??
          `sample-${index + 1}`
      ).trim() || `sample-${index + 1}`
    const query =
      String(
        (sampleRecord as Record<string, any>).query ??
          (sampleRecord as Record<string, any>).input ??
          ""
      ) || ""
    const targets =
      sampleRecord &&
      typeof (sampleRecord as Record<string, any>).targets === "object" &&
      !Array.isArray((sampleRecord as Record<string, any>).targets)
        ? { ...((sampleRecord as Record<string, any>).targets as Record<string, any>) }
        : undefined

    const normalized: Record<string, any> = {
      sample_id: sampleId,
      query
    }
    if (targets && Object.keys(targets).length > 0) {
      normalized.targets = targets
    }
    return normalized as DatasetSample
  })
}

const normalizeRunConfig = (runConfig: Record<string, any>) => {
  const candidateCreationMode =
    String(runConfig.candidate_creation_mode || "auto_sweep") === "manual"
      ? "manual"
      : "auto_sweep"
  const rawScope =
    runConfig.corpus_scope && typeof runConfig.corpus_scope === "object"
      ? runConfig.corpus_scope
      : {}
  const rawBudget =
    runConfig.weak_supervision_budget && typeof runConfig.weak_supervision_budget === "object"
      ? runConfig.weak_supervision_budget
      : {}
  const rawRetrievalConfig =
    runConfig.retrieval_config && typeof runConfig.retrieval_config === "object"
      ? runConfig.retrieval_config
      : {}
  const rawIndexingConfig =
    runConfig.indexing_config && typeof runConfig.indexing_config === "object"
      ? runConfig.indexing_config
      : {}

  return {
    ...runConfig,
    candidate_creation_mode: candidateCreationMode,
    corpus_scope: {
      sources: normalizeSources(rawScope.sources),
      media_ids: Array.isArray(rawScope.media_ids)
        ? rawScope.media_ids.map((value: unknown) => parseInteger(value, 0)).filter((value: number) => value > 0)
        : [],
      note_ids: Array.isArray(rawScope.note_ids)
        ? rawScope.note_ids.map((value: unknown) => String(value).trim()).filter(Boolean)
        : [],
      indexing_fixed: Boolean(rawScope.indexing_fixed)
    },
    weak_supervision_budget: {
      ...DEFAULT_WEAK_SUPERVISION_BUDGET,
      ...rawBudget
    },
    retrieval_config: {
      ...DEFAULT_RETRIEVAL_CONFIG,
      ...rawRetrievalConfig
    },
    indexing_config: {
      ...DEFAULT_INDEXING_CONFIG,
      ...rawIndexingConfig
    },
    candidates:
      candidateCreationMode === "manual" && Array.isArray(runConfig.candidates) && runConfig.candidates.length > 0
        ? runConfig.candidates
        : candidateCreationMode === "manual"
          ? [
              {
                candidate_id: "manual-1",
                retrieval_config: { ...DEFAULT_RETRIEVAL_CONFIG },
                indexing_config: { ...DEFAULT_INDEXING_CONFIG }
              }
            ]
          : []
  }
}

const updateSampleTargets = (
  dataset: DatasetSample[],
  sampleIndex: number,
  targetKey: string,
  nextValue: unknown
): DatasetSample[] =>
  dataset.map((sample, index) => {
    if (index !== sampleIndex) return sample
    const record = { ...(sample as Record<string, any>) }
    const nextTargets =
      record.targets && typeof record.targets === "object" && !Array.isArray(record.targets)
        ? { ...(record.targets as Record<string, any>) }
        : {}
    const shouldDelete =
      nextValue == null || (Array.isArray(nextValue) && nextValue.length === 0)
    if (shouldDelete) {
      delete nextTargets[targetKey]
    } else {
      nextTargets[targetKey] = nextValue
    }
    if (Object.keys(nextTargets).length === 0) {
      delete record.targets
    } else {
      record.targets = nextTargets
    }
    return record as DatasetSample
  })

export const RagRetrievalTuningConfig: React.FC<Props> = ({
  datasetSource,
  dataset,
  runConfig,
  onDatasetChange,
  onRunConfigChange
}) => {
  const normalizedDataset = React.useMemo(() => normalizeDataset(dataset), [dataset])
  const normalizedRunConfig = React.useMemo(() => normalizeRunConfig(runConfig), [runConfig])
  const corpusScope = normalizedRunConfig.corpus_scope
  const weakBudget = normalizedRunConfig.weak_supervision_budget
  const isManualMode = normalizedRunConfig.candidate_creation_mode === "manual"

  const applyRunConfig = (updater: (current: Record<string, any>) => Record<string, any>) => {
    onRunConfigChange(updater(normalizeRunConfig(runConfig)))
  }

  const applyDataset = (updater: (current: DatasetSample[]) => DatasetSample[]) => {
    onDatasetChange(updater(normalizeDataset(dataset)))
  }

  const toggleSource = (source: "media_db" | "notes", checked: boolean) => {
    applyRunConfig((current) => {
      const currentSources = normalizeSources(current.corpus_scope?.sources)
      const nextSources = checked
        ? Array.from(new Set([...currentSources, source]))
        : currentSources.filter((item) => item !== source)
      return {
        ...current,
        corpus_scope: {
          ...current.corpus_scope,
          sources: nextSources.length > 0 ? nextSources : currentSources
        }
      }
    })
  }

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        <Text strong>Corpus sources</Text>
        <div className="grid gap-3 md:grid-cols-2">
          <Checkbox
            aria-label="Use media_db source"
            checked={corpusScope.sources.includes("media_db")}
            onChange={(event) => toggleSource("media_db", event.target.checked)}
          >
            media_db
          </Checkbox>
          <Checkbox
            aria-label="Use notes source"
            checked={corpusScope.sources.includes("notes")}
            onChange={(event) => toggleSource("notes", event.target.checked)}
          >
            notes
          </Checkbox>
          <div>
            <Text strong>Media IDs</Text>
            <Input
              aria-label="Media IDs"
              className="mt-2"
              value={joinCsv(corpusScope.media_ids)}
              onChange={(event) =>
                applyRunConfig((current) => ({
                  ...current,
                  corpus_scope: {
                    ...current.corpus_scope,
                    media_ids: splitCsv(event.target.value)
                      .map((value) => parseInteger(value, 0))
                      .filter((value) => value > 0)
                  }
                }))
              }
            />
          </div>
          <div>
            <Text strong>Note IDs</Text>
            <Input
              aria-label="Note IDs"
              className="mt-2"
              value={joinCsv(corpusScope.note_ids)}
              onChange={(event) =>
                applyRunConfig((current) => ({
                  ...current,
                  corpus_scope: {
                    ...current.corpus_scope,
                    note_ids: splitCsv(event.target.value)
                  }
                }))
              }
            />
          </div>
        </div>
        <Checkbox
          aria-label="Indexing fixed"
          checked={Boolean(corpusScope.indexing_fixed)}
          onChange={(event) =>
            applyRunConfig((current) => ({
              ...current,
              corpus_scope: {
                ...current.corpus_scope,
                indexing_fixed: event.target.checked
              }
            }))
          }
        >
          Indexing fixed
        </Checkbox>
        <div className="text-xs text-text-muted">
          Mark indexing as fixed when you want chunk-level labels to stay valid across candidates.
        </div>
      </div>

      {datasetSource === "inline" && (
        <div className="space-y-3">
          <Text strong>Dataset samples</Text>
          {normalizedDataset.map((sample, index) => {
            const targets = ((sample as Record<string, any>).targets as Record<string, any> | undefined) || {}
            return (
              <Card
                key={`rag-query-${index}`}
                size="small"
                title={`Query ${index + 1}`}
                extra={
                  <Button
                    size="small"
                    onClick={() =>
                      applyDataset((current) =>
                        current.filter((_, datasetIndex) => datasetIndex !== index)
                      )
                    }
                    disabled={normalizedDataset.length <= 1}
                  >
                    Remove
                  </Button>
                }
              >
                <div className="grid gap-3 md:grid-cols-2">
                  <div>
                    <Text strong>{`Sample ID ${index + 1}`}</Text>
                    <Input
                      aria-label={`Sample ID ${index + 1}`}
                      className="mt-2"
                      value={String((sample as Record<string, any>).sample_id || "")}
                      onChange={(event) =>
                        applyDataset((current) =>
                          current.map((item, datasetIndex) =>
                            datasetIndex === index
                              ? ({ ...(item as Record<string, any>), sample_id: event.target.value } as DatasetSample)
                              : item
                          )
                        )
                      }
                    />
                  </div>
                  <div className="md:col-span-2">
                    <Text strong>{`Query text ${index + 1}`}</Text>
                    <TextArea
                      aria-label={`Query text ${index + 1}`}
                      rows={3}
                      className="mt-2"
                      value={String((sample as Record<string, any>).query || "")}
                      onChange={(event) =>
                        applyDataset((current) =>
                          current.map((item, datasetIndex) =>
                            datasetIndex === index
                              ? ({ ...(item as Record<string, any>), query: event.target.value } as DatasetSample)
                              : item
                          )
                        )
                      }
                    />
                  </div>
                  <div>
                    <Text strong>{`Relevant media targets ${index + 1} (optional)`}</Text>
                    <TextArea
                      aria-label={`Relevant media targets ${index + 1} (optional)`}
                      rows={3}
                      className="mt-2"
                      value={formatTargetText(targets.relevant_media_ids)}
                      onChange={(event) =>
                        applyDataset((current) =>
                          updateSampleTargets(
                            current,
                            index,
                            "relevant_media_ids",
                            parseTargetText(event.target.value)
                          )
                        )
                      }
                    />
                  </div>
                  <div>
                    <Text strong>{`Relevant note targets ${index + 1} (optional)`}</Text>
                    <TextArea
                      aria-label={`Relevant note targets ${index + 1} (optional)`}
                      rows={3}
                      className="mt-2"
                      value={formatTargetText(targets.relevant_note_ids)}
                      onChange={(event) =>
                        applyDataset((current) =>
                          updateSampleTargets(
                            current,
                            index,
                            "relevant_note_ids",
                            parseTargetText(event.target.value)
                          )
                        )
                      }
                    />
                  </div>
                  <div>
                    <Text strong>{`Relevant chunk targets ${index + 1} (optional)`}</Text>
                    <TextArea
                      aria-label={`Relevant chunk targets ${index + 1} (optional)`}
                      rows={3}
                      className="mt-2"
                      disabled={!Boolean(corpusScope.indexing_fixed)}
                      value={formatTargetText(targets.relevant_chunk_ids)}
                      onChange={(event) =>
                        applyDataset((current) =>
                          updateSampleTargets(
                            current,
                            index,
                            "relevant_chunk_ids",
                            parseTargetText(event.target.value)
                          )
                        )
                      }
                    />
                  </div>
                  <div className="md:col-span-2">
                    <Text strong>{`Relevant spans ${index + 1} (optional)`}</Text>
                    <TextArea
                      aria-label={`Relevant spans ${index + 1} (optional)`}
                      rows={3}
                      className="mt-2"
                      value={formatSpanText(targets.relevant_spans)}
                      onChange={(event) =>
                        applyDataset((current) =>
                          updateSampleTargets(
                            current,
                            index,
                            "relevant_spans",
                            parseSpanText(event.target.value)
                          )
                        )
                      }
                    />
                  </div>
                </div>
              </Card>
            )
          })}
          <Button
            onClick={() =>
              applyDataset((current) => [
                ...current,
                {
                  sample_id: `sample-${current.length + 1}`,
                  query: ""
                } as DatasetSample
              ])
            }
          >
            Add query sample
          </Button>
        </div>
      )}

      <div className="space-y-3">
        <Text strong>Candidate planning</Text>
        <div>
          <Text strong>Candidate creation mode</Text>
          <select
            aria-label="Candidate creation mode"
            className="mt-2 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={normalizedRunConfig.candidate_creation_mode}
            onChange={(event) =>
              applyRunConfig((current) => {
                const nextMode = event.target.value === "manual" ? "manual" : "auto_sweep"
                const nextConfig: Record<string, any> = {
                  ...current,
                  candidate_creation_mode: nextMode
                }
                if (nextMode === "manual") {
                  nextConfig.candidates =
                    Array.isArray(current.candidates) && current.candidates.length > 0
                      ? current.candidates
                      : [
                          {
                            candidate_id: "manual-1",
                            retrieval_config: { ...DEFAULT_RETRIEVAL_CONFIG },
                            indexing_config: { ...DEFAULT_INDEXING_CONFIG }
                          }
                        ]
                } else {
                  delete nextConfig.candidates
                }
                return nextConfig
              })
            }
          >
            <option value="auto_sweep">auto_sweep</option>
            <option value="manual">manual</option>
          </select>
        </div>

        {isManualMode ? (
          <div className="space-y-3">
            {normalizedRunConfig.candidates.map((candidate: Record<string, any>, index: number) => {
              const retrievalConfig = {
                ...DEFAULT_RETRIEVAL_CONFIG,
                ...(candidate.retrieval_config || {})
              }
              const indexingConfig = {
                ...DEFAULT_INDEXING_CONFIG,
                ...(candidate.indexing_config || {})
              }
              return (
                <Card
                  key={`rag-candidate-${index}`}
                  size="small"
                  title={`Candidate ${index + 1}`}
                  extra={
                    <Button
                      size="small"
                      onClick={() =>
                        applyRunConfig((current) => ({
                          ...current,
                          candidates: (Array.isArray(current.candidates) ? current.candidates : []).filter(
                            (_: unknown, candidateIndex: number) => candidateIndex !== index
                          )
                        }))
                      }
                      disabled={normalizedRunConfig.candidates.length <= 1}
                    >
                      Remove
                    </Button>
                  }
                >
                  <div className="grid gap-3 md:grid-cols-2">
                    <div>
                      <Text strong>{`Candidate ID ${index + 1}`}</Text>
                      <Input
                        aria-label={`Candidate ID ${index + 1}`}
                        className="mt-2"
                        value={String(candidate.candidate_id || "")}
                        onChange={(event) =>
                          applyRunConfig((current) => ({
                            ...current,
                            candidates: (Array.isArray(current.candidates) ? current.candidates : []).map(
                              (item: Record<string, any>, candidateIndex: number) =>
                                candidateIndex === index
                                  ? { ...item, candidate_id: event.target.value }
                                  : item
                            )
                          }))
                        }
                      />
                    </div>
                    <div>
                      <Text strong>{`Search mode ${index + 1}`}</Text>
                      <select
                        aria-label={`Search mode ${index + 1}`}
                        className="mt-2 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                        value={String(retrievalConfig.search_mode)}
                        onChange={(event) =>
                          applyRunConfig((current) => ({
                            ...current,
                            candidates: (Array.isArray(current.candidates) ? current.candidates : []).map(
                              (item: Record<string, any>, candidateIndex: number) =>
                                candidateIndex === index
                                  ? {
                                      ...item,
                                      retrieval_config: {
                                        ...DEFAULT_RETRIEVAL_CONFIG,
                                        ...(item.retrieval_config || {}),
                                        search_mode: event.target.value
                                      }
                                    }
                                  : item
                            )
                          }))
                        }
                      >
                        <option value="fts">fts</option>
                        <option value="vector">vector</option>
                        <option value="hybrid">hybrid</option>
                      </select>
                    </div>
                    <div>
                      <Text strong>{`Top K ${index + 1}`}</Text>
                      <Input
                        aria-label={`Top K ${index + 1}`}
                        className="mt-2"
                        value={String(retrievalConfig.top_k)}
                        onChange={(event) =>
                          applyRunConfig((current) => ({
                            ...current,
                            candidates: (Array.isArray(current.candidates) ? current.candidates : []).map(
                              (item: Record<string, any>, candidateIndex: number) =>
                                candidateIndex === index
                                  ? {
                                      ...item,
                                      retrieval_config: {
                                        ...DEFAULT_RETRIEVAL_CONFIG,
                                        ...(item.retrieval_config || {}),
                                        top_k: parseInteger(event.target.value, DEFAULT_RETRIEVAL_CONFIG.top_k)
                                      }
                                    }
                                  : item
                            )
                          }))
                        }
                      />
                    </div>
                    <div>
                      <Text strong>{`Hybrid alpha ${index + 1}`}</Text>
                      <Input
                        aria-label={`Hybrid alpha ${index + 1}`}
                        className="mt-2"
                        value={String(retrievalConfig.hybrid_alpha)}
                        onChange={(event) =>
                          applyRunConfig((current) => ({
                            ...current,
                            candidates: (Array.isArray(current.candidates) ? current.candidates : []).map(
                              (item: Record<string, any>, candidateIndex: number) =>
                                candidateIndex === index
                                  ? {
                                      ...item,
                                      retrieval_config: {
                                        ...DEFAULT_RETRIEVAL_CONFIG,
                                        ...(item.retrieval_config || {}),
                                        hybrid_alpha: parseNumeric(
                                          event.target.value,
                                          DEFAULT_RETRIEVAL_CONFIG.hybrid_alpha
                                        )
                                      }
                                    }
                                  : item
                            )
                          }))
                        }
                      />
                    </div>
                    <div>
                      <Text strong>{`Reranking strategy ${index + 1}`}</Text>
                      <select
                        aria-label={`Reranking strategy ${index + 1}`}
                        className="mt-2 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                        value={String(retrievalConfig.reranking_strategy)}
                        onChange={(event) =>
                          applyRunConfig((current) => ({
                            ...current,
                            candidates: (Array.isArray(current.candidates) ? current.candidates : []).map(
                              (item: Record<string, any>, candidateIndex: number) =>
                                candidateIndex === index
                                  ? {
                                      ...item,
                                      retrieval_config: {
                                        ...DEFAULT_RETRIEVAL_CONFIG,
                                        ...(item.retrieval_config || {}),
                                        reranking_strategy: event.target.value
                                      }
                                    }
                                  : item
                            )
                          }))
                        }
                      >
                        <option value="flashrank">flashrank</option>
                        <option value="cross_encoder">cross_encoder</option>
                        <option value="hybrid">hybrid</option>
                        <option value="none">none</option>
                      </select>
                    </div>
                    <div>
                      <Text strong>{`Chunking preset ${index + 1}`}</Text>
                      <select
                        aria-label={`Chunking preset ${index + 1}`}
                        className="mt-2 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                        value={String(indexingConfig.chunking_preset)}
                        onChange={(event) =>
                          applyRunConfig((current) => ({
                            ...current,
                            candidates: (Array.isArray(current.candidates) ? current.candidates : []).map(
                              (item: Record<string, any>, candidateIndex: number) =>
                                candidateIndex === index
                                  ? {
                                      ...item,
                                      indexing_config: {
                                        ...DEFAULT_INDEXING_CONFIG,
                                        ...(item.indexing_config || {}),
                                        chunking_preset: event.target.value
                                      }
                                    }
                                  : item
                            )
                          }))
                        }
                      >
                        <option value="baseline">baseline</option>
                        <option value="compact">compact</option>
                        <option value="fixed_index">fixed_index</option>
                      </select>
                    </div>
                  </div>
                </Card>
              )
            })}
            <Button
              onClick={() =>
                applyRunConfig((current) => ({
                  ...current,
                  candidates: [
                    ...(Array.isArray(current.candidates) ? current.candidates : []),
                    {
                      candidate_id: `manual-${(Array.isArray(current.candidates) ? current.candidates.length : 0) + 1}`,
                      retrieval_config: { ...DEFAULT_RETRIEVAL_CONFIG },
                      indexing_config: { ...DEFAULT_INDEXING_CONFIG }
                    }
                  ]
                }))
              }
            >
              Add candidate
            </Button>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <Text strong>Search mode</Text>
              <select
                aria-label="Search mode"
                className="mt-2 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={String(normalizedRunConfig.retrieval_config.search_mode)}
                onChange={(event) =>
                  applyRunConfig((current) => ({
                    ...current,
                    retrieval_config: {
                      ...DEFAULT_RETRIEVAL_CONFIG,
                      ...(current.retrieval_config || {}),
                      search_mode: event.target.value
                    }
                  }))
                }
              >
                <option value="fts">fts</option>
                <option value="vector">vector</option>
                <option value="hybrid">hybrid</option>
              </select>
            </div>
            <div>
              <Text strong>Top K</Text>
              <Input
                aria-label="Top K"
                className="mt-2"
                value={String(normalizedRunConfig.retrieval_config.top_k)}
                onChange={(event) =>
                  applyRunConfig((current) => ({
                    ...current,
                    retrieval_config: {
                      ...DEFAULT_RETRIEVAL_CONFIG,
                      ...(current.retrieval_config || {}),
                      top_k: parseInteger(event.target.value, DEFAULT_RETRIEVAL_CONFIG.top_k)
                    }
                  }))
                }
              />
            </div>
            <div>
              <Text strong>Hybrid alpha</Text>
              <Input
                aria-label="Hybrid alpha"
                className="mt-2"
                value={String(normalizedRunConfig.retrieval_config.hybrid_alpha)}
                onChange={(event) =>
                  applyRunConfig((current) => ({
                    ...current,
                    retrieval_config: {
                      ...DEFAULT_RETRIEVAL_CONFIG,
                      ...(current.retrieval_config || {}),
                      hybrid_alpha: parseNumeric(
                        event.target.value,
                        DEFAULT_RETRIEVAL_CONFIG.hybrid_alpha
                      )
                    }
                  }))
                }
              />
            </div>
            <div>
              <Text strong>Reranking strategy</Text>
              <select
                aria-label="Reranking strategy"
                className="mt-2 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={String(normalizedRunConfig.retrieval_config.reranking_strategy)}
                onChange={(event) =>
                  applyRunConfig((current) => ({
                    ...current,
                    retrieval_config: {
                      ...DEFAULT_RETRIEVAL_CONFIG,
                      ...(current.retrieval_config || {}),
                      reranking_strategy: event.target.value
                    }
                  }))
                }
              >
                <option value="flashrank">flashrank</option>
                <option value="cross_encoder">cross_encoder</option>
                <option value="hybrid">hybrid</option>
                <option value="none">none</option>
              </select>
            </div>
            <div>
              <Text strong>Chunking preset</Text>
              <select
                aria-label="Chunking preset"
                className="mt-2 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={String(normalizedRunConfig.indexing_config.chunking_preset)}
                onChange={(event) =>
                  applyRunConfig((current) => ({
                    ...current,
                    indexing_config: {
                      ...DEFAULT_INDEXING_CONFIG,
                      ...(current.indexing_config || {}),
                      chunking_preset: event.target.value
                    }
                  }))
                }
              >
                <option value="baseline">baseline</option>
                <option value="compact">compact</option>
                <option value="fixed_index">fixed_index</option>
              </select>
            </div>
          </div>
        )}
      </div>

      <div className="space-y-3">
        <Text strong>Weak supervision budget</Text>
        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <Text strong>Review sample fraction</Text>
            <Input
              aria-label="Review sample fraction"
              className="mt-2"
              value={String(weakBudget.review_sample_fraction)}
              onChange={(event) =>
                applyRunConfig((current) => ({
                  ...current,
                  weak_supervision_budget: {
                    ...DEFAULT_WEAK_SUPERVISION_BUDGET,
                    ...(current.weak_supervision_budget || {}),
                    review_sample_fraction: parseNumeric(
                      event.target.value,
                      DEFAULT_WEAK_SUPERVISION_BUDGET.review_sample_fraction
                    )
                  }
                }))
              }
            />
          </div>
          <div>
            <Text strong>Max review samples</Text>
            <Input
              aria-label="Max review samples"
              className="mt-2"
              value={String(weakBudget.max_review_samples)}
              onChange={(event) =>
                applyRunConfig((current) => ({
                  ...current,
                  weak_supervision_budget: {
                    ...DEFAULT_WEAK_SUPERVISION_BUDGET,
                    ...(current.weak_supervision_budget || {}),
                    max_review_samples: parseInteger(
                      event.target.value,
                      DEFAULT_WEAK_SUPERVISION_BUDGET.max_review_samples
                    )
                  }
                }))
              }
            />
          </div>
          <div>
            <Text strong>Min review samples</Text>
            <Input
              aria-label="Min review samples"
              className="mt-2"
              value={String(weakBudget.min_review_samples)}
              onChange={(event) =>
                applyRunConfig((current) => ({
                  ...current,
                  weak_supervision_budget: {
                    ...DEFAULT_WEAK_SUPERVISION_BUDGET,
                    ...(current.weak_supervision_budget || {}),
                    min_review_samples: parseInteger(
                      event.target.value,
                      DEFAULT_WEAK_SUPERVISION_BUDGET.min_review_samples
                    )
                  }
                }))
              }
            />
          </div>
          <div>
            <Text strong>Synthetic query limit</Text>
            <Input
              aria-label="Synthetic query limit"
              className="mt-2"
              value={String(weakBudget.synthetic_query_limit)}
              onChange={(event) =>
                applyRunConfig((current) => ({
                  ...current,
                  weak_supervision_budget: {
                    ...DEFAULT_WEAK_SUPERVISION_BUDGET,
                    ...(current.weak_supervision_budget || {}),
                    synthetic_query_limit: parseInteger(
                      event.target.value,
                      DEFAULT_WEAK_SUPERVISION_BUDGET.synthetic_query_limit
                    )
                  }
                }))
              }
            />
          </div>
        </div>
        <Alert
          type="info"
          showIcon
          title="Approved synthetic queries should be reviewed before they count toward recommendations."
        />
      </div>
    </div>
  )
}
