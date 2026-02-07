# Refined Brainstorming Prompts: Watchlist Briefing Workflows

## Context

Two prompts for brainstorming end-to-end user experiences and test plans for:

1. **Newsletter Briefing** - Watchlist setup through formatted newsletter delivery
2. **Spoken-Word TTS Briefing** - Extends (1) with audio narration via TTS

Both prompts are grounded in the real API surface and data models of the tldw platform so the brainstorming output will be actionable rather than hypothetical.

---

## Prompt 1: Newsletter Briefing Workflow

> **Goal:** Brainstorm the complete end-to-end user experience and test plan for a user who discovers the application, sets up a watchlist of RSS feeds and websites, and then consumes curated content through a formatted newsletter-style briefing.
>
> ### System Capabilities to Build On
>
> The platform already provides:
> - **Source management** (`POST /api/v1/watchlists/sources`) supporting `rss`, `site`, and `forum` source types, with bulk creation and OPML import/export
> - **Groups & tags** for organizing sources into logical collections (e.g. "Tech News", "Finance", "Research")
> - **Jobs** (`POST /api/v1/watchlists/jobs`) with cron scheduling (`schedule_expr`), timezone support, scoped source selection (by source IDs, groups, or tags), and configurable filters (keyword, regex, author, date_range) with include/exclude/flag actions and priority ordering
> - **A fetch pipeline** that normalizes RSS items and scraped web articles into a unified `{title, url, summary, content, author, published}` structure, with SHA256-based deduplication and conditional-GET (ETag/Last-Modified) for efficiency
> - **Filter evaluation** with `require_include` gating and per-run filter tallies
> - **Output generation** (`POST /api/v1/watchlists/outputs`) with Jinja2 template rendering, supporting `briefing_markdown`, `newsletter_markdown`, `newsletter_html`, and `mece_markdown` template types
> - **Delivery channels**: email (SMTP with recipient list, subject, body format) and chatbook export (conversation integration)
> - **LLM-powered summarization** via `recursive_summarize_chunks()` and a document generator with a dedicated `BRIEFING` type (temperature 0.4, 2500 max tokens, "executive briefing with actionable insights" system prompt)
> - **RAG hybrid search** (FTS5 + vector + reranking) for semantically retrieving the most relevant ingested articles
> - **A simplified Collections Feeds API** (`POST /api/v1/collections/feeds`) that auto-creates the underlying watchlist source + job in one call
>
> ### What I Need You to Brainstorm
>
> **A. User Journey (step-by-step)**
> 1. **Onboarding & first source** - How does a new user discover watchlists? What's the minimal "time to first value" flow? Should we guide them through adding their first RSS feed vs. importing an OPML file vs. using the simplified Collections Feeds API?
> 2. **Source organization** - When and how should the user create groups and tags? Should the UI suggest default groupings (by topic, by update frequency, by priority)?
> 3. **Filter configuration** - How do we make filter rules approachable for non-technical users while preserving power for advanced users? Consider: preset filter bundles (e.g. "skip paywalled content", "only English", "flag breaking news"), a visual filter builder vs. raw config, and the `require_include` toggle.
> 4. **Schedule setup** - What are sensible default schedules? (e.g. hourly for news, daily for blogs, weekly for research). How do we present cron expressions in a human-friendly way?
> 5. **First run & preview** - The system has `POST /jobs/{job_id}/preview` for dry-run testing. How should we use this to build user confidence before committing to a schedule?
> 6. **Briefing generation** - After a run completes: Should briefings auto-generate or require explicit trigger? What LLM provider/model should default? How do we let users customize the briefing prompt and template? Should we offer multiple briefing "styles" (executive summary, deep dive, bullet points, narrative)?
> 7. **Briefing consumption** - Where and how does the user read the briefing? In-app reading view, email delivery, chatbook thread, downloadable PDF/Markdown? Should briefings be conversational (user can ask follow-up questions about articles)?
> 8. **Iteration & refinement** - How does the user tune their watchlist over time? Consider: "too noisy / too quiet" feedback loops, filter suggestions based on what they mark as reviewed vs. skipped, source health monitoring (dead feeds, error rates).
>
> **B. Data Flow Architecture**
> - Map the exact API call sequence from source creation -> job creation -> scheduled run -> item filtering -> output generation -> delivery
> - Identify where LLM calls happen (summarization of individual articles vs. composition of the full briefing) and how to minimize token usage
> - Consider caching: should we cache per-article summaries so repeat appearances across runs don't re-summarize?
>
> **C. Test Plan**
> - **Unit tests**: Filter evaluation with edge cases (overlapping include/exclude, empty filter sets, priority conflicts), template rendering with missing variables, dedup with near-identical URLs
> - **Integration tests**: Full pipeline from RSS fetch -> filter -> output render using `TEST_MODE` (which returns static items), OPML round-trip (import -> export -> import), job preview accuracy (preview matches actual run results)
> - **E2E tests**: Create source -> create job -> trigger run -> verify scraped items -> generate output -> verify rendered content. Test with real RSS feeds (use stable feeds like BBC, Hacker News) and verify email delivery via a test SMTP server
> - **Edge cases**: Empty runs (all items filtered), sources that return errors, extremely long articles, feeds with non-UTF8 encoding, concurrent job runs for same sources
> - **UX testing scenarios**: First-time user with zero sources, power user importing 100+ feeds via OPML, user with highly restrictive filters getting empty briefings (what's the empty state?)

---

## Prompt 2: Spoken-Word TTS News Briefing (extends Prompt 1)

> **Goal:** Extend the newsletter briefing workflow above to also produce a spoken-word audio news briefing using TTS, suitable for listening during a commute or workout.
>
> ### Additional System Capabilities
>
> The platform's TTS stack provides:
> - **18+ TTS providers** including local (Kokoro ONNX, VibeVoice PyTorch, Dia, Higgs, Chatterbox) and cloud (OpenAI tts-1/tts-1-hd, ElevenLabs 30+ voices)
> - **OpenAI-compatible endpoint** (`POST /api/v1/speech`) with streaming support, voice selection, speed control (0.25x-4.0x), and format options (MP3, WAV, OPUS, FLAC, AAC)
> - **Long-form async jobs** (`POST /api/v1/speech/jobs`) for content exceeding ~5 minutes
> - **Voice cloning** (VibeVoice, Higgs, Qwen3-TTS, ElevenLabs) using uploaded reference audio
> - **Workflow TTS adapter** (`adapter: "tts"`) that chains with other workflow steps, supports Jinja2 input templating (`{{ prev.summary }}`), post-processing (EBU R128 loudness normalization), and custom output filenames
> - **Audio normalization** (target LUFS, true peak limiting) for consistent listening levels
> - **Circuit breaker pattern** with automatic fallback between providers
> - **Output template type** `tts_audio` already defined in the template system
> - **Voice catalog endpoint** (`GET /api/v1/audio/voices/catalog`) listing all available voices across providers
> - **TTS history tracking** with favorites, soft delete, and artifact linking
>
> ### What I Need You to Brainstorm
>
> **A. Audio Briefing User Journey**
> 1. **Opt-in flow** - How does the user enable audio briefings alongside (or instead of) written ones? Per-job toggle? Global preference? Should audio generation be automatic on every run or on-demand?
> 2. **Voice & provider selection** - How do we help the user pick a voice? Consider: audio preview samples, a "match my preference" wizard (formal vs. casual, male vs. female, accent), default to Kokoro (fast, local, free) with upgrade path to ElevenLabs/OpenAI for higher quality.
> 3. **Content adaptation for audio** - Written briefings don't translate directly to good spoken content. How should we transform the text? Consider: removing markdown formatting, expanding abbreviations, adding natural transitions ("Moving on to technology news..."), pronunciation hints for technical terms, inserting pauses between sections via SSML or text cues.
> 4. **Length management** - A 2000-word written briefing might be 15+ minutes of audio. Should we offer length presets (5-min quick brief, 15-min standard, 30-min deep dive)? Should the summarization prompt adapt based on target audio duration?
> 5. **Multi-voice / multi-section** - For a richer listening experience, should different sections use different voices (e.g. a "host" voice for transitions and a "reporter" voice for article summaries)? VibeVoice supports 4 simultaneous speakers. Chatterbox supports multi-speaker dialogue.
> 6. **Delivery & playback** - Where does the user listen? In-app audio player, email attachment (MP3), podcast-compatible RSS feed, download link? Should we generate chapter markers for longer briefings?
> 7. **Progressive generation** - For streaming: should we send audio chunks as they're generated (first section plays while remaining sections still synthesize)?
>
> **B. Audio Pipeline Architecture**
> - Define the exact chain: `run items -> LLM summarize (audio-adapted prompt) -> text post-processing (strip markdown, add transitions) -> TTS generation -> audio normalization -> storage -> delivery`
> - Should we use the Workflow TTS adapter for the chain, or direct API calls?
> - How do we handle TTS failures gracefully? (fallback provider, retry, deliver text-only with apology?)
> - Storage: where do audio artifacts live? Expiry policy? Quota implications?
>
> **C. Additional Test Plan (Audio-Specific)**
> - **Unit tests**: Text-to-audio adaptation (markdown stripping, abbreviation expansion, transition insertion), audio format validation, voice selection logic, duration estimation from text length
> - **Integration tests**: Full pipeline from briefing text -> TTS generation -> audio file validation (correct format, non-zero duration, acceptable file size), provider fallback when primary provider fails (circuit breaker engagement)
> - **E2E tests**: Complete flow from watchlist run -> briefing generation -> TTS synthesis -> audio delivery. Test with Kokoro (local, no API key needed) as baseline. Verify audio plays correctly in common players
> - **Performance tests**: Generation time for 5-min vs. 15-min vs. 30-min briefings, memory usage for local providers (VibeVoice needs 8-16GB GPU RAM), concurrent audio generation limits
> - **Quality tests**: Subjective listening tests for naturalness, correct pronunciation of domain-specific terms, appropriate pacing, volume consistency across sections (LUFS normalization verification)
> - **Edge cases**: Empty briefing (no items passed filters -> should we generate "no news today" audio or skip?), extremely long briefings exceeding provider limits, special characters / emoji in source content, non-English content handling

---

## Appendix A: Concrete Workflow YAML Examples

Reference implementations to ground the brainstorming in real workflow syntax.

### Workflow A: Newsletter Briefing (Text Only)

```yaml
name: "Daily Newsletter Briefing"
version: 1
description: "Fetch watchlist items, summarize, compose briefing, deliver via email"
tags: ["watchlist", "newsletter", "briefing"]
inputs:
  watchlist_job_id: "int - the watchlist job to pull items from"
  briefing_style: "executive|deep_dive|bullets"
  llm_provider: "openai"
  llm_model: "gpt-4o"
  email_recipients: "comma-separated emails"
metadata:
  author: "system"
  category: "news-briefing"

steps:
  # Step 1: Fetch latest watchlist run items via RAG search
  - id: "fetch_items"
    name: "Retrieve watchlist content"
    type: "rag_search"
    config:
      query: "latest news and updates"
      collection: "watchlist_{{ inputs.watchlist_job_id }}"
      top_k: 25
      search_type: "hybrid"
      rerank: true
    timeout_seconds: 60

  # Step 2: Summarize each article into a concise blurb
  - id: "summarize_articles"
    name: "Summarize individual articles"
    type: "map"
    config:
      items: "{{ prev.results }}"
      step:
        type: "summarize"
        config:
          text: "{{ item.content }}"
          max_length: 150
          style: "bullet_points"
          provider: "{{ inputs.llm_provider }}"
          model: "{{ inputs.llm_model }}"
    timeout_seconds: 300

  # Step 3: Compose the full briefing document from summaries
  - id: "compose_briefing"
    name: "Compose newsletter briefing"
    type: "llm"
    config:
      provider: "{{ inputs.llm_provider }}"
      model: "{{ inputs.llm_model }}"
      temperature: 0.4
      max_tokens: 3000
      system_prompt: |
        You are an expert newsletter editor. Create a well-structured
        briefing document from the article summaries provided. Group
        related items by topic. Use clear section headers. For each
        item include the title, a 2-3 sentence summary, and the
        source URL. End with a "Key Takeaways" section with 3-5
        actionable insights.
      prompt: |
        Create a {{ inputs.briefing_style }} newsletter briefing
        from these {{ prev.results | length }} article summaries:

        {% for item in prev.results %}
        ---
        Title: {{ item.title }}
        Source: {{ item.url }}
        Summary: {{ item.summary }}
        {% endfor %}
    timeout_seconds: 120

  # Step 4: Render into newsletter template
  - id: "render_template"
    name: "Render newsletter HTML"
    type: "template_render"
    config:
      template: "newsletter_html"
      variables:
        briefing_body: "{{ prev.text }}"
        date: "{{ now() }}"
        item_count: "{{ fetch_items.results | length }}"
    timeout_seconds: 30

  # Step 5: Deliver via email
  - id: "send_email"
    name: "Email the briefing"
    type: "email_send"
    config:
      to: "{{ inputs.email_recipients }}"
      subject: "Your Daily Briefing - {{ now().strftime('%B %d') }}"
      body: "{{ prev.rendered }}"
      body_format: "html"
    timeout_seconds: 60
    retry: 2
    on_failure: "log_failure"

  # Error handler
  - id: "log_failure"
    name: "Log delivery failure"
    type: "log"
    config:
      level: "error"
      message: "Newsletter delivery failed: {{ last.error }}"
```

### Workflow B: Newsletter + Spoken-Word TTS Audio Briefing

```yaml
name: "Daily News Briefing with Audio"
version: 1
description: "Fetch, summarize, compose briefing, generate audio narration, deliver both"
tags: ["watchlist", "newsletter", "briefing", "tts", "audio"]
inputs:
  watchlist_job_id: "int"
  briefing_style: "executive"
  llm_provider: "openai"
  llm_model: "gpt-4o"
  tts_provider: "kokoro"
  tts_voice: "af_heart"
  tts_speed: 1.0
  target_audio_minutes: 10
  email_recipients: "comma-separated emails"

steps:
  # Step 1: Retrieve curated watchlist items
  - id: "fetch_items"
    name: "Retrieve watchlist content"
    type: "rag_search"
    config:
      query: "latest news and updates"
      collection: "watchlist_{{ inputs.watchlist_job_id }}"
      top_k: 20
      search_type: "hybrid"
      rerank: true
    timeout_seconds: 60

  # Step 2: Summarize each article
  - id: "summarize_articles"
    name: "Summarize articles"
    type: "map"
    config:
      items: "{{ prev.results }}"
      step:
        type: "summarize"
        config:
          text: "{{ item.content }}"
          max_length: 150
          style: "bullet_points"
          provider: "{{ inputs.llm_provider }}"
          model: "{{ inputs.llm_model }}"
    timeout_seconds: 300

  # Step 3: Compose written briefing (for email/reading)
  - id: "compose_written"
    name: "Compose written briefing"
    type: "llm"
    config:
      provider: "{{ inputs.llm_provider }}"
      model: "{{ inputs.llm_model }}"
      temperature: 0.4
      max_tokens: 3000
      system_prompt: |
        You are an expert newsletter editor. Create a well-structured
        briefing from the article summaries. Group by topic, use clear
        headers, include source URLs. End with Key Takeaways.
      prompt: |
        Create a {{ inputs.briefing_style }} briefing from these
        {{ prev.results | length }} summaries:

        {% for item in prev.results %}
        ---
        Title: {{ item.title }}
        Source: {{ item.url }}
        Summary: {{ item.summary }}
        {% endfor %}
    timeout_seconds: 120

  # Step 4: Compose audio-adapted script (parallel with Step 5)
  - id: "compose_audio_script"
    name: "Compose audio-friendly script"
    type: "llm"
    config:
      provider: "{{ inputs.llm_provider }}"
      model: "{{ inputs.llm_model }}"
      temperature: 0.5
      max_tokens: 2500
      system_prompt: |
        You are a professional news anchor writing a script for a
        spoken-word audio briefing. Rules:
        - NO markdown, bullet points, headers, or URLs
        - Use natural spoken transitions between topics
          ("Turning to technology...", "In financial news today...")
        - Expand all abbreviations (AI -> Artificial Intelligence,
          CEO -> Chief Executive Officer) on first use
        - Use short, clear sentences suited for listening
        - Open with a brief greeting and date context
        - Close with a concise wrap-up
        - Target approximately {{ inputs.target_audio_minutes }}
          minutes of speaking time (~150 words per minute)
        - Insert "[pause]" between major sections for natural pacing
      prompt: |
        Convert these {{ summarize_articles.results | length }}
        article summaries into an audio news briefing script:

        {% for item in summarize_articles.results %}
        Topic: {{ item.title }}
        Details: {{ item.summary }}
        {% endfor %}
    timeout_seconds: 120

  # Step 5: Render written briefing as HTML (parallel with Step 4)
  - id: "render_html"
    name: "Render newsletter HTML"
    type: "template_render"
    config:
      template: "newsletter_html"
      variables:
        briefing_body: "{{ compose_written.text }}"
        date: "{{ now() }}"
    timeout_seconds: 30

  # Step 6: Clean the audio script
  - id: "clean_script"
    name: "Post-process audio script"
    type: "text_clean"
    config:
      text: "{{ compose_audio_script.text }}"
      operations:
        - strip_markdown
        - normalize_whitespace
        - normalize_unicode
    timeout_seconds: 10

  # Step 7: Generate TTS audio from the script
  - id: "generate_audio"
    name: "Synthesize audio briefing"
    type: "tts"
    config:
      input: "{{ prev.text }}"
      model: "{{ inputs.tts_provider }}"
      voice: "{{ inputs.tts_voice }}"
      response_format: "mp3"
      speed: "{{ inputs.tts_speed }}"
      post_process:
        normalize: true
        target_lufs: -16.0
        true_peak_dbfs: -1.5
      output_filename_template: "briefing_{{ now().strftime('%Y%m%d') }}.mp3"
    timeout_seconds: 600
    retry: 1
    on_failure: "tts_fallback"

  # Step 7b: TTS fallback - try OpenAI if primary fails
  - id: "tts_fallback"
    name: "TTS fallback provider"
    type: "tts"
    config:
      input: "{{ clean_script.text }}"
      model: "tts-1"
      voice: "nova"
      response_format: "mp3"
      speed: "{{ inputs.tts_speed }}"
      provider: "openai"
      output_filename_template: "briefing_{{ now().strftime('%Y%m%d') }}_fallback.mp3"
    timeout_seconds: 600
    retry: 1
    on_failure: "deliver_text_only"

  # Step 8: Send email with both text and audio
  - id: "send_email"
    name: "Deliver briefing + audio"
    type: "email_send"
    config:
      to: "{{ inputs.email_recipients }}"
      subject: "Your Daily Briefing - {{ now().strftime('%B %d') }}"
      body: "{{ render_html.rendered }}"
      body_format: "html"
      attachments:
        - "{{ generate_audio.audio_uri }}"
    timeout_seconds: 60
    retry: 2
    on_failure: "log_failure"

  # Fallback: deliver text-only if all TTS fails
  - id: "deliver_text_only"
    name: "Deliver text-only (TTS failed)"
    type: "email_send"
    config:
      to: "{{ inputs.email_recipients }}"
      subject: "Your Daily Briefing (text only) - {{ now().strftime('%B %d') }}"
      body: |
        {{ render_html.rendered }}
        <hr>
        <p><em>Audio briefing unavailable today due to a
        generation error. We'll try again tomorrow.</em></p>
      body_format: "html"
    timeout_seconds: 60

  - id: "log_failure"
    name: "Log delivery failure"
    type: "log"
    config:
      level: "error"
      message: "Briefing delivery failed: {{ last.error }}"
```

### Appendix B: Scheduling Either Workflow

```yaml
# Schedule via POST /api/v1/scheduler/workflows
{
  "workflow_id": 42,
  "name": "Weekday Morning Briefing",
  "cron": "0 7 * * 1-5",
  "timezone": "America/New_York",
  "inputs": {
    "watchlist_job_id": 1,
    "briefing_style": "executive",
    "llm_provider": "openai",
    "llm_model": "gpt-4o",
    "tts_provider": "kokoro",
    "tts_voice": "af_heart",
    "tts_speed": 1.1,
    "target_audio_minutes": 10,
    "email_recipients": "user@example.com"
  },
  "enabled": true,
  "concurrency_mode": "skip"
}
```

---

## How to Use These Prompts

Feed either prompt (or both sequentially) to an LLM. The prompts are self-contained with enough system context to produce actionable designs rather than generic hand-waving. The brainstorming output should give you:

1. A concrete user journey you can wireframe
2. An API call sequence you can implement as a workflow
3. A test matrix you can convert directly into pytest fixtures

You can also use them with your team for design review sessions - the "What I Need You to Brainstorm" sections work as structured discussion agendas.
