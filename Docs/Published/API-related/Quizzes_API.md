# Quizzes API

Quizzes provide structured assessments with questions, attempts, and optional AI generation from media.

Base path: `/api/v1/quizzes`

## Endpoints

- `GET /` - list quizzes
- `POST /` - create a quiz
- `GET /{quiz_id}` - quiz detail
- `PATCH /{quiz_id}` - update quiz metadata
- `DELETE /{quiz_id}` - delete quiz (soft by default)
- `GET /{quiz_id}/questions` - list questions
- `POST /{quiz_id}/questions` - add a question
- `PATCH /{quiz_id}/questions/{question_id}` - update a question
- `DELETE /{quiz_id}/questions/{question_id}` - delete a question
- `POST /{quiz_id}/attempts` - start an attempt
- `PUT /attempts/{attempt_id}` - submit answers
- `GET /attempts` - list attempts
- `GET /attempts/{attempt_id}` - attempt detail
- `POST /generate` - generate a quiz from media

## Core Objects

### QuizResponse

```
{
  "id": 12,
  "name": "RAG Basics",
  "description": "Intro quiz",
  "workspace_tag": "workspace:research",
  "media_id": 1024,
  "total_questions": 10,
  "time_limit_seconds": 600,
  "passing_score": 70,
  "deleted": false,
  "client_id": "user_123",
  "version": 2,
  "created_at": "2026-01-29T10:00:00Z",
  "last_modified": "2026-01-29T10:05:00Z"
}
```

### Question (admin view)

```
{
  "id": 44,
  "quiz_id": 12,
  "question_type": "multiple_choice",
  "question_text": "What is BM25?",
  "options": ["Vector search", "Keyword ranking", "Summarizer"],
  "correct_answer": 1,
  "explanation": "BM25 is a keyword-based ranking function.",
  "points": 1,
  "order_index": 0,
  "tags": ["search"],
  "deleted": false,
  "client_id": "user_123",
  "version": 1,
  "created_at": "2026-01-29T10:00:00Z",
  "last_modified": "2026-01-29T10:00:00Z"
}
```

### AttemptResponse

```
{
  "id": 90,
  "quiz_id": 12,
  "started_at": "2026-01-29T10:10:00Z",
  "completed_at": "2026-01-29T10:12:00Z",
  "score": 8,
  "total_possible": 10,
  "time_spent_seconds": 120,
  "answers": [
    {
      "question_id": 44,
      "user_answer": 1,
      "is_correct": true,
      "correct_answer": 1,
      "points_awarded": 1
    }
  ]
}
```

## Create Quiz

`POST /api/v1/quizzes`

Request:
```
{
  "name": "RAG Basics",
  "description": "Intro quiz",
  "workspace_tag": "workspace:research",
  "media_id": 1024,
  "time_limit_seconds": 600,
  "passing_score": 70
}
```

## Update Quiz

`PATCH /api/v1/quizzes/{quiz_id}`

Request fields match `QuizUpdate`. Use `expected_version` for optimistic locking when supported by the DB layer.

## Delete Quiz

`DELETE /api/v1/quizzes/{quiz_id}?expected_version=2&hard=false`

## Questions

- List: `GET /api/v1/quizzes/{quiz_id}/questions?include_answers=true`
- Create: `POST /api/v1/quizzes/{quiz_id}/questions`
- Update: `PATCH /api/v1/quizzes/{quiz_id}/questions/{question_id}`
- Delete: `DELETE /api/v1/quizzes/{quiz_id}/questions/{question_id}?expected_version=1&hard=false`

Create question request:
```
{
  "question_type": "multiple_choice",
  "question_text": "What is BM25?",
  "options": ["Vector search", "Keyword ranking", "Summarizer"],
  "correct_answer": 1,
  "explanation": "BM25 is a keyword-based ranking function.",
  "points": 1,
  "order_index": 0,
  "tags": ["search"]
}
```

## Attempts

Start attempt:
`POST /api/v1/quizzes/{quiz_id}/attempts`

Submit answers:
`PUT /api/v1/quizzes/attempts/{attempt_id}`

Request:
```
{
  "answers": [
    {"question_id": 44, "user_answer": 1, "time_spent_ms": 3000}
  ]
}
```

List attempts:
`GET /api/v1/quizzes/attempts?quiz_id=12`

## Generate Quiz

`POST /api/v1/quizzes/generate`

Request:
```
{
  "media_id": 1024,
  "num_questions": 10,
  "question_types": ["multiple_choice", "true_false"],
  "difficulty": "mixed",
  "focus_topics": ["retrieval", "reranking"],
  "model": "gpt-4o-mini",
  "workspace_tag": "workspace:research"
}
```

Response:
```
{
  "quiz": {"id": 12, "name": "RAG Basics", "total_questions": 10, "version": 1, "deleted": false, "client_id": "user_123"},
  "questions": [
    {"id": 44, "quiz_id": 12, "question_type": "multiple_choice", "question_text": "...", "options": ["A", "B"], "correct_answer": 0, "points": 1, "order_index": 0, "deleted": false, "client_id": "user_123", "version": 1}
  ]
}
```
