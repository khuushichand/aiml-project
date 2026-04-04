import { useCallback, useEffect, useRef, useState } from "react"
import { useStorage } from "@plasmohq/storage/hook"

export type Mood = "tense" | "romantic" | "melancholic" | "action" | "calm" | "mysterious" | "humorous" | null

export type EchoReaction = {
  persona: string
  emoji: string
  message: string
  timestamp: number
}

const MOOD_PROMPT = `Classify the emotional mood of this text. Respond with ONLY one word from: tense, romantic, melancholic, action, calm, mysterious, humorous\n\nText: `

const ECHO_PERSONAS = [
  { name: "Alex", emoji: "🧐", role: "The Analyst", prompt: "You are Alex, a sharp literary analyst. In 1-2 sentences, comment on the structure, foreshadowing, or plot mechanics. Be concise." },
  { name: "Sam", emoji: "😍", role: "The Shipper", prompt: "You are Sam, obsessed with character relationships. In 1-2 sentences, react to relationship dynamics or romantic tension." },
  { name: "Max", emoji: "🤨", role: "The Skeptic", prompt: "You are Max, a skeptical reader. In 1-2 sentences, point out anything contrived or unmotivated." },
  { name: "Riley", emoji: "🎉", role: "The Hype", prompt: "You are Riley, an enthusiastic reader. In 1-2 sentences, react with energy to the most exciting element." },
  { name: "Jordan", emoji: "📚", role: "The Lore Keeper", prompt: "You are Jordan, a world-building enthusiast. In 1-2 sentences, comment on world-building details or consistency." },
] as const

const VALID_MOODS = new Set(["tense", "romantic", "melancholic", "action", "calm", "mysterious", "humorous"])
const MOOD_DEBOUNCE_MS = 10_000
const ECHO_DEBOUNCE_MS = 30_000
const ECHO_CHAR_THRESHOLD = 500

type UseWritingFeedbackProps = {
  editorText: string
  isOnline: boolean
  isGenerating: boolean
  selectedModel?: string
}

export type UseWritingFeedbackReturn = {
  moodEnabled: boolean
  setMoodEnabled: (v: boolean) => void
  currentMood: Mood
  moodAnalyzing: boolean
  echoEnabled: boolean
  setEchoEnabled: (v: boolean) => void
  echoReactions: EchoReaction[]
  echoAnalyzing: boolean
  charsSinceLastEcho: number
}

async function callChat(systemPrompt: string, userText: string, model?: string): Promise<string> {
  try {
    const resp = await fetch("/api/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: model || "default",
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userText },
        ],
        temperature: 0.7,
        max_tokens: 100,
      }),
    })
    if (!resp.ok) return ""
    const data = await resp.json()
    return data?.choices?.[0]?.message?.content?.trim() || ""
  } catch {
    return ""
  }
}

export function useWritingFeedback({
  editorText,
  isOnline,
  isGenerating,
  selectedModel,
}: UseWritingFeedbackProps): UseWritingFeedbackReturn {
  const [moodEnabled, setMoodEnabled] = useStorage<boolean>("writing:mood-enabled", false)
  const [echoEnabled, setEchoEnabled] = useStorage<boolean>("writing:echo-enabled", false)
  const [currentMood, setCurrentMood] = useState<Mood>(null)
  const [moodAnalyzing, setMoodAnalyzing] = useState(false)
  const [echoReactions, setEchoReactions] = useState<EchoReaction[]>([])
  const [echoAnalyzing, setEchoAnalyzing] = useState(false)
  const [charsSinceLastEcho, setCharsSinceLastEcho] = useState(0)

  const lastMoodCallRef = useRef(0)
  const lastEchoCallRef = useRef(0)
  const echoIndexRef = useRef(0)
  const prevTextLenRef = useRef(editorText.length)
  const moodTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Track chars typed since last echo
  useEffect(() => {
    const delta = editorText.length - prevTextLenRef.current
    prevTextLenRef.current = editorText.length
    if (delta > 0) {
      setCharsSinceLastEcho((prev) => prev + delta)
    }
  }, [editorText])

  // Mood detection (debounced)
  useEffect(() => {
    if (!moodEnabled || !isOnline || isGenerating || !editorText.trim()) return

    if (moodTimerRef.current) clearTimeout(moodTimerRef.current)

    moodTimerRef.current = setTimeout(async () => {
      const now = Date.now()
      if (now - lastMoodCallRef.current < MOOD_DEBOUNCE_MS) return
      lastMoodCallRef.current = now

      setMoodAnalyzing(true)
      const textSlice = editorText.slice(-500)
      const result = await callChat(
        "You are a mood classifier. Respond with exactly one word.",
        MOOD_PROMPT + textSlice,
        selectedModel,
      )
      const word = result.toLowerCase().trim().replace(/[^a-z]/g, "")
      if (VALID_MOODS.has(word)) {
        setCurrentMood(word as Mood)
      }
      setMoodAnalyzing(false)
    }, MOOD_DEBOUNCE_MS)

    return () => {
      if (moodTimerRef.current) clearTimeout(moodTimerRef.current)
    }
  }, [editorText, moodEnabled, isOnline, isGenerating, selectedModel])

  // Echo Chamber
  useEffect(() => {
    if (!echoEnabled || !isOnline || isGenerating || charsSinceLastEcho < ECHO_CHAR_THRESHOLD) return

    const now = Date.now()
    if (now - lastEchoCallRef.current < ECHO_DEBOUNCE_MS) return

    lastEchoCallRef.current = now
    setCharsSinceLastEcho(0)

    const persona = ECHO_PERSONAS[echoIndexRef.current % ECHO_PERSONAS.length]
    echoIndexRef.current += 1

    setEchoAnalyzing(true)
    const textSlice = editorText.slice(-1000)

    callChat(persona.prompt, `React to this passage:\n\n${textSlice}`, selectedModel).then(
      (message) => {
        if (message) {
          setEchoReactions((prev) => [
            { persona: persona.name, emoji: persona.emoji, message, timestamp: Date.now() },
            ...prev,
          ].slice(0, 20)) // Keep last 20 reactions
        }
        setEchoAnalyzing(false)
      },
    )
  }, [charsSinceLastEcho, echoEnabled, isOnline, isGenerating, editorText, selectedModel])

  return {
    moodEnabled: moodEnabled ?? false,
    setMoodEnabled,
    currentMood,
    moodAnalyzing,
    echoEnabled: echoEnabled ?? false,
    setEchoEnabled,
    echoReactions,
    echoAnalyzing,
    charsSinceLastEcho,
  }
}
