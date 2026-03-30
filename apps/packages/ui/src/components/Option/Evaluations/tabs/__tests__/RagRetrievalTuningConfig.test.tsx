// @vitest-environment jsdom

import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import React from "react"
import type { DatasetSample } from "@/services/evaluations"
import { RagRetrievalTuningConfig } from "../recipe-configs/RagRetrievalTuningConfig"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      _key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return _key
    }
  })
}))

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("RagRetrievalTuningConfig", () => {
  it("serializes labeled targets from guided dataset fields", () => {
    let datasetState: DatasetSample[] = []

    const Harness = () => {
      const [dataset, setDataset] = React.useState<DatasetSample[]>([
        {
          sample_id: "sample-1",
          query: ""
        } as DatasetSample
      ])
      const [runConfig, setRunConfig] = React.useState<Record<string, any>>({
        candidate_creation_mode: "auto_sweep",
        corpus_scope: { sources: ["media_db"] },
        weak_supervision_budget: {
          review_sample_fraction: 0.2,
          max_review_samples: 25,
          min_review_samples: 3,
          synthetic_query_limit: 20
        }
      })

      React.useEffect(() => {
        datasetState = dataset
      }, [dataset])

      return (
        <RagRetrievalTuningConfig
          datasetSource="inline"
          dataset={dataset}
          runConfig={runConfig}
          onDatasetChange={setDataset}
          onRunConfigChange={setRunConfig}
        />
      )
    }

    render(<Harness />)

    fireEvent.change(screen.getByLabelText("Query text 1"), {
      target: { value: "find the architecture summary" }
    })
    fireEvent.change(screen.getByLabelText("Relevant media targets 1 (optional)"), {
      target: { value: "10:3\n12:1" }
    })
    fireEvent.change(screen.getByLabelText("Relevant note targets 1 (optional)"), {
      target: { value: "note-7:2" }
    })
    fireEvent.change(screen.getByLabelText("Relevant spans 1 (optional)"), {
      target: { value: "media_db,10,0,42,3" }
    })

    expect(datasetState).toEqual([
      {
        sample_id: "sample-1",
        query: "find the architecture summary",
        targets: {
          relevant_media_ids: [
            { id: "10", grade: 3 },
            { id: "12", grade: 1 }
          ],
          relevant_note_ids: [{ id: "note-7", grade: 2 }],
          relevant_spans: [
            {
              source: "media_db",
              record_id: "10",
              start: 0,
              end: 42,
              grade: 3
            }
          ]
        }
      }
    ])
  })

  it("switches to manual candidates and builds candidate rows", () => {
    let runConfigState: Record<string, any> = {}

    const Harness = () => {
      const [dataset, setDataset] = React.useState<DatasetSample[]>([])
      const [runConfig, setRunConfig] = React.useState<Record<string, any>>({
        candidate_creation_mode: "auto_sweep",
        corpus_scope: { sources: ["media_db", "notes"] },
        weak_supervision_budget: {
          review_sample_fraction: 0.2,
          max_review_samples: 25,
          min_review_samples: 3,
          synthetic_query_limit: 20
        }
      })

      React.useEffect(() => {
        runConfigState = runConfig
      }, [runConfig])

      return (
        <RagRetrievalTuningConfig
          datasetSource="saved"
          dataset={dataset}
          runConfig={runConfig}
          onDatasetChange={setDataset}
          onRunConfigChange={setRunConfig}
        />
      )
    }

    render(<Harness />)

    fireEvent.change(screen.getByLabelText("Candidate creation mode"), {
      target: { value: "manual" }
    })
    fireEvent.change(screen.getByLabelText("Candidate ID 1"), {
      target: { value: "manual-a" }
    })
    fireEvent.change(screen.getByLabelText("Search mode 1"), {
      target: { value: "vector" }
    })
    fireEvent.change(screen.getByLabelText("Top K 1"), {
      target: { value: "8" }
    })
    fireEvent.change(screen.getByLabelText("Chunking preset 1"), {
      target: { value: "fixed_index" }
    })

    expect(runConfigState).toMatchObject({
      candidate_creation_mode: "manual",
      candidates: [
        {
          candidate_id: "manual-a",
          retrieval_config: expect.objectContaining({
            search_mode: "vector",
            top_k: 8
          }),
          indexing_config: expect.objectContaining({
            chunking_preset: "fixed_index"
          })
        }
      ]
    })
  })
})
