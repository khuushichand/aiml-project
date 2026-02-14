# Effective Character Roleplay and You

A practical guide for individuals who want better, more immersive roleplay with character chat.

## Why this guide exists

Most weak roleplay is not caused by a "bad model." It is usually caused by weak scene setup, unclear intent, or turns that give the model nothing concrete to react to.

This document is the core onboarding guide for improving roleplay quality in tldw character chat.

## Who this is for

- New users who want to learn roleplay basics quickly
- Intermediate users who get inconsistent or bland responses
- Individual users building personal characters, worlds, and long-running scenes

## Quick-start in 60 seconds

1. Define your character clearly: personality, scenario, first message, and examples.
2. Write each turn with the PEAS pattern: Persona, Environment, Action, Sensory.
3. End with an open loop (action or question) so the model has a clear next move.
4. Keep continuity in world books and dictionaries, not just in memory.
5. If quality drops, simplify, shorten, and re-anchor the scene.

---

## The PEAS framework

Use this on every important turn. It gives the model a compact "snapshot" of the current scene.

### P - Persona (internal state)

State your internal mindset, intention, or emotional pressure.

Good:
- "I keep my voice calm, but my pulse is racing and I am seconds from losing my temper."

Weak:
- "I am here."

### E - Environment (the stage)

Ground the scene with a few concrete details.

Good:
- "Rain taps against the window, neon reflections flicker across the wet floor, and the room smells like burnt coffee."

Weak:
- "We are in a room."

### A - Action (momentum)

Use decisive verbs. Do the thing now.

Good:
- "I slide the file across the desk, lock eyes with you, and wait."

Weak:
- "I begin to maybe say something."

### S - Sensory (the hook)

Add one or two non-visual signals (sound, texture, smell, temperature).

Good:
- "The metal handle bites cold into my palm and distant sirens pulse through the wall."

Weak:
- "It feels normal."

### PEAS turn template (copy/paste)

```text
[P] Internal state: ...
[E] Scene detail: ...
[A] Action taken now: ...
[S] Sensory cue: ...
Open loop: (question or action that demands response)
```

---

## Build a stronger character card

In tldw, your core roleplay quality starts with these fields:

- `name`: clear, stable identity
- `description`: what this character is
- `personality`: behavior style, values, social tone
- `scenario`: default context and relationship frame
- `first_message`: sets opening energy and voice
- `message_example`: teaches format, rhythm, and reply style
- `system_prompt` (advanced): hard boundaries and style contract
- `post_history_instructions` (advanced): reinforcement after long context

### Character-writing rules

- Use specific behavioral cues, not generic labels.
- Add contradictions carefully (for realism), but define priorities.
- Write examples in the exact style you want returned.
- Keep it stable: frequent personality rewrites reduce consistency.

### Example personality block

```text
Observant and dry-humored. Speaks in concise sentences under pressure.
Avoids melodrama. Protective of allies, skeptical of authority.
When angry: voice gets quieter, not louder.
```

---

## Turn design that gets strong responses

### Show, do not label

Instead of emotion labels alone, describe physical and behavioral evidence.

- Better: "My jaw locks and I fold the map twice before answering."
- Worse: "I am angry."

### End with an open loop

If your turn ends passively, the model often summarizes instead of interacting.

Use endings like:
- "I stop inches away. 'Your move.'"
- "I hold up the key. 'Which door first?'"

### Control pacing

Alternate:
- long descriptive turns (scene weight)
- short sharp turns (momentum)

If every turn is long prose, response quality tends to flatten.

### Protect agency

Do not write the other character's full response for them.
Give pressure, offer openings, and let them act.

---

## Scene continuity for individuals

### Use world books (lorebooks) for persistent context

Store durable facts there, not in every message:
- places
- factions
- relationship history
- recurring rules of the setting

### Use chat dictionaries for consistent language

Great for:
- terms and acronyms
- custom lore shorthand
- recurring setting phrases

This keeps vocabulary stable without inflating every prompt turn.

---

## Quality debugging workflow

When responses degrade, use this order:

1. Re-anchor with PEAS in one clean turn.
2. Shorten your turn by 30-50%.
3. Re-state intent and scene objective in one sentence.
4. Add one concrete action and one sensory cue.
5. End with a forced open loop.

If still weak:
- tighten character `personality` and `message_example`
- reduce conflicting instructions
- remove overly abstract wording

---

## Common failure modes and fixes

| Problem | Likely Cause | Fix |
|---|---|---|
| Replies feel generic | Weak scene anchors | Add PEAS details and explicit stakes |
| Model rambles | No open loop | End with direct question or decisive action |
| Character feels out of voice | Thin personality/example fields | Rewrite `personality` and `message_example` with concrete style patterns |
| Scene loses continuity | Important facts only in chat memory | Move stable facts to world books |
| Replies become repetitive | Same cadence every turn | Alternate long and short pacing |
| Roleplay becomes flat summary | Action verbs missing | Use immediate verbs and present-moment interaction |

---

## Individual improvement drills

Do these in short sessions.

### Drill 1: PEAS compression

Write a full turn in 5 lines or less using all PEAS parts.

### Drill 2: Open-loop endings

Rewrite 10 old turns so each ends with a response-forcing hook.

### Drill 3: Voice lock

Write 5 `message_example` snippets for your character:
- calm
- stressed
- confrontational
- playful
- reflective

### Drill 4: Sensory discipline

For one scene, every turn must include one non-visual sensory detail.

### Drill 5: Pacing alternation

Run 8 turns where odd turns are descriptive and even turns are concise dialogue/action.

---

## Roleplay ethics and boundaries

- Keep clear boundaries for themes you do not want.
- Use system instructions for hard constraints.
- Do not confuse "in-character conflict" with "out-of-character discomfort."
- If needed, pause and reset scene expectations in plain language.

---

## Final send checklist

Before hitting send, ask:

- Did I provide internal state (P)?
- Did I ground the environment (E)?
- Did I perform a concrete action (A)?
- Did I include at least one sensory hook (S)?
- Did I end with an open loop?
- Is this in my character's voice?

If yes, your turn is likely to produce a stronger response.

---

## One-page starter template

```text
Character intent: [what I want right now]
Emotion pressure: [what I am holding back or pushing through]
Scene anchor: [where we are + 2 concrete details]
Immediate action: [what I do right now]
Sensory detail: [sound/smell/texture/temp]
Open loop: [question, challenge, or move that demands response]
```

Use this until it becomes automatic.
