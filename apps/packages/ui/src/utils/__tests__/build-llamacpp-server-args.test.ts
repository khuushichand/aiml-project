import { describe, expect, it } from "vitest"
import { buildLlamacppServerArgs } from "../build-llamacpp-server-args"

describe("buildLlamacppServerArgs", () => {
  it("maps structured options into llama-server args", () => {
    const args = buildLlamacppServerArgs({
      contextSize: 8192,
      gpuLayers: 40,
      threads: 12,
      threadsBatch: 8,
      batchSize: 1024,
      ubatchSize: 512,
      mlock: true,
      noMmap: true,
      noKvOffload: true,
      splitMode: "layer",
      rowSplit: true,
      tensorSplit: "38,62",
      cacheType: "f16",
      ropeFreqBase: 1_000_000,
      compressPosEmb: 2,
      cpuMoe: true,
      nCpuMoe: 27,
      streamingLlm: true,
      flashAttn: "on",
      mmprojAuto: false,
      mmprojOffload: false,
      host: "127.0.0.1",
      port: 8080
    })

    expect(args.ctx_size).toBe(8192)
    expect(args.n_gpu_layers).toBe(40)
    expect(args.threads).toBe(12)
    expect(args.threads_batch).toBe(8)
    expect(args.batch_size).toBe(1024)
    expect(args.ubatch_size).toBe(512)
    expect(args.mlock).toBe(true)
    expect(args.no_mmap).toBe(true)
    expect(args.no_kv_offload).toBe(true)
    expect(args.split_mode).toBe("row")
    expect(args.tensor_split).toEqual([38, 62])
    expect(args.cache_type_k).toBe("f16")
    expect(args.cache_type_v).toBe("f16")
    expect(args.rope_freq_base).toBe(1_000_000)
    expect(args.rope_freq_scale).toBe(0.5)
    expect(args.cpu_moe).toBe(true)
    expect(args.n_cpu_moe).toBe(27)
    expect(args.streaming_llm).toBe(true)
    expect(args.flash_attn).toBe("on")
    expect(args.no_mmproj).toBe(true)
    expect(args.no_mmproj_offload).toBe(true)
    expect(args.host).toBe("127.0.0.1")
    expect(args.port).toBe(8080)
  })

  it("parses extra flags and normalizes custom arg keys", () => {
    const args = buildLlamacppServerArgs({
      contextSize: 4096,
      gpuLayers: 0,
      extraFlags: "n-cpu-moe=4, no-mmap, foo=1.25",
      customArgs: {
        "cache-type-k": "bf16",
        "--my-flag": "x"
      }
    })

    expect(args.n_cpu_moe).toBe(4)
    expect(args.no_mmap).toBe(true)
    expect(args.foo).toBe(1.25)
    expect(args.cache_type_k).toBe("bf16")
    expect(args.my_flag).toBe("x")
  })
})
