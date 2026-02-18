# Advanced Character Roleplay Guide

A companion guide for users who already know the basics and want higher consistency, stronger immersion, and better long-session control.

Prerequisite: complete `Docs/User_Guides/Character_Roleplay_Quickstart.md` first.

## Advanced goals

This guide focuses on:
- maintaining voice under long context
- balancing style and momentum
- controlling scene state transitions
- recovering quality when responses flatten

## 1) Voice locking with example sets

Single `message_example` blocks are useful, but advanced consistency improves when you design a small response matrix.

Create one short example for each pressure state:
- baseline neutral
- time pressure
- emotional pressure
- confrontation
- reflective cooldown

Rules for each example:
- keep the same sentence rhythm you want in outputs
- include one signature phrase pattern
- avoid conflicting behavior cues

### Mini matrix template

```text
State: Time pressure
Cadence: Short, clipped sentences.
Signature: One tactical question near the end.
Sample: "We have three minutes. Map first, arguments later. Where is the nearest service tunnel?"
```

## 2) Prompt contract hierarchy

Treat your character setup as a contract with descending priority:
1. hard constraints in `system_prompt`
2. role definition in `description` and `personality`
3. default interaction frame in `scenario`
4. stylistic shape in `message_example`
5. reinforcement in `post_history_instructions`

When outputs conflict, resolve from top to bottom. Do not patch lower layers if the conflict starts in higher-layer instructions.

## 3) Scene-state management

Long roleplay sessions fail when scene state becomes implicit and ambiguous.

Track these state buckets explicitly:
- objective state: what each participant wants now
- relationship state: trust, tension, leverage
- environment state: location hazards, timing, constraints
- evidence state: what facts are known, uncertain, or false

### State snapshot pattern

Every 4-8 turns, post a compact in-character snapshot:

```text
Current objective: get the ledger before sunrise.
Constraint: patrol route resets every seven minutes.
Relationship pressure: uneasy alliance, low trust.
Immediate move: test whether your story is consistent.
```

This reduces drift and prevents random tone pivots.

## 4) Pacing architecture

Advanced pacing is intentional alternation, not random verbosity.

Use a repeating cycle:
- setup turn: anchor scene and stakes
- pressure turn: apply conflict or urgency
- action turn: concrete movement/decision
- consequence turn: reveal cost/result

Then repeat with changed stakes.

### Practical cadence targets

- setup/consequence turns: longer descriptive density
- pressure/action turns: shorter, sharper phrasing

If every turn has equal length, scenes often feel flat.

## 5) Sensory layering without purple prose

Sensory detail should sharpen decisions, not decorate every sentence.

Use the 1-1-1 rule per turn:
- one dominant sense
- one physical cue
- one tactical implication

Example:

```text
The room smells like ozone and hot plastic.
My fingertips tingle on the cracked control panel.
If we trigger this now, the backup lights will expose us.
```

## 6) Open-loop engineering

Advanced open loops are specific and constrained.

Prefer bounded choices:
- "Window or stairwell? Pick one now."

Avoid vague prompts:
- "What do you think we should do?"

Use escalation ladders:
1. soft query
2. narrowed choice
3. forced decision under cost

This prevents meandering and keeps replies interactive.

## 7) Drift recovery protocol (when quality drops)

If outputs become generic, repetitive, or out-of-character, run this protocol in order:

1. Reset objective and constraint in one sentence.
2. Re-anchor setting with two concrete details.
3. Add one decisive action.
4. End with a bounded open loop.
5. If still weak, tighten `message_example` and `post_history_instructions`.

### Recovery turn template

```text
Objective reset: We are here to identify the leak before dawn.
Scene re-anchor: Generator hum, wet concrete, one exit stairwell.
Action: I seal the door and place the recorder on the table.
Bounded loop: "You talk first, or I play the tape. Which is it?"
```

## 8) Continuity systems for long campaigns

For multi-session roleplay, split memory across durable channels:
- world books: setting canon, factions, timeline anchors
- chat dictionaries: recurring terms and custom lexicon
- character fields: stable behavior rules, speaking style, and taboos

Guideline:
- session facts that may change stay in chat
- canonical facts that should persist go into world books/dictionaries

## 9) Quality audits (weekly)

Review one saved conversation and score 1-5:
- voice consistency
- scene clarity
- action momentum
- sensory effectiveness
- ending strength (open loop)

Any category below 3 gets a targeted update:
- voice low: revise `message_example`
- clarity low: improve environment anchors
- momentum low: enforce action verbs
- sensory low: apply 1-1-1 rule
- endings low: switch to bounded choice loops

## 10) Anti-patterns to remove

- overloading every turn with backstory
- writing the other character's full response
- replacing action with abstract emotion labels
- conflicting character instructions across fields
- passive turn endings that invite summarization

## Advanced practice block

Run this 12-turn drill:
1. Turns 1-3: setup + stakes
2. Turns 4-6: rising pressure + bounded choices
3. Turns 7-9: decisive actions + consequence reveals
4. Turns 10-12: resolution attempt with one twist

Constraints:
- every turn includes one sensory cue
- every turn ends with an open loop
- at turn 8, post a scene-state snapshot

## Character recovery workflow

When managing characters in the Characters page:
- delete is reversible for 10 seconds via the undo toast
- bulk delete follows the same soft-delete + undo behavior
- after the toast expires, use the `Recently deleted` scope and click `Restore`

If restore fails because the record changed in another tab/session, refresh the list and retry restore.

## Companion docs

- Core onboarding: `Docs/User_Guides/Effective_Character_Roleplay_and_You.md`
- Fast start: `Docs/User_Guides/Character_Roleplay_Quickstart.md`
