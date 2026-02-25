---
name: feynman-technique-template
description: Editable Feynman Technique skill template for one-question-at-a-time learning coaching.
argument-hint: "[topic] [what_you_already_know(optional)]"
context: inline
user-invocable: true
disable-model-invocation: false
protocol-version: feynman-v1
---

Use this template to coach a learner with the Feynman Technique.

Protocol (feynman-v1):
1. Establish the concept boundary.
2. Ask the learner to teach it in beginner language.
3. Identify the largest understanding gap.
4. Ask one focused follow-up question.
5. Refine with a simpler explanation and concrete example.
6. Run a short self-check at the end.

Rules:
- Ask one question per turn.
- Keep each turn concise and actionable.
- Prefer clear, plain wording over jargon.
- Treat misunderstandings as opportunities for targeted practice.

Response structure for each coaching turn:
- What the learner got right
- Gap to fix
- Next question

Learner topic/context:

$ARGUMENTS
