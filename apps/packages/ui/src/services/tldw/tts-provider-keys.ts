export const normalizeTtsProviderKey = (value?: string | null): string => {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "")
}

export const toServerTtsProviderKey = (value?: string | null): string => {
  const normalized = normalizeTtsProviderKey(value)
  switch (normalized) {
    case "pockettts":
      return "pocket_tts"
    case "vibevoicerealtime":
      return "vibevoice_realtime"
    case "indextts2":
      return "index_tts2"
    case "indextts":
      return "index_tts"
    case "qwen3tts":
      return "qwen3_tts"
    case "luxtts":
      return "lux_tts"
    case "echotts":
      return "echo_tts"
    case "supertonic2":
      return "supertonic2"
    case "supertonic":
      return "supertonic"
    default:
      return String(value || "").trim().toLowerCase()
  }
}
