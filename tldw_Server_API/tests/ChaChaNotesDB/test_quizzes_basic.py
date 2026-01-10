import os
import tempfile

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


def test_quizzes_basic_flow():


    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "ChaChaNotes.db")
        db = CharactersRAGDB(db_path, client_id="test")

        quiz_id = db.create_quiz(name="Quiz One", description="desc", media_id=None)
        assert isinstance(quiz_id, int)

        question_id = db.create_question(
            quiz_id=quiz_id,
            question_type="multiple_choice",
            question_text="What is 2+2?",
            options=["1", "2", "4", "5"],
            correct_answer=2,
            explanation="2+2=4",
            points=1,
            order_index=0,
        )
        assert isinstance(question_id, int)

        quiz = db.get_quiz(quiz_id)
        assert quiz is not None
        assert quiz["total_questions"] == 1

        public_payload = db.list_questions(quiz_id, include_answers=False, limit=10, offset=0)
        public_questions = public_payload["items"]
        assert public_questions
        assert "correct_answer" not in public_questions[0]

        admin_payload = db.list_questions(quiz_id, include_answers=True, limit=10, offset=0)
        admin_questions = admin_payload["items"]
        assert admin_questions[0]["correct_answer"] == 2

        attempt = db.start_attempt(quiz_id)
        assert attempt["total_possible"] == 1
        assert attempt["questions"]
        assert "correct_answer" not in attempt["questions"][0]

        result = db.submit_attempt(
            attempt["id"],
            [{"question_id": question_id, "user_answer": 2, "time_spent_ms": 250}],
        )
        assert result["score"] == 1
        assert result["total_possible"] == 1
        assert result["answers"][0]["is_correct"] is True

        attempts = db.list_attempts(quiz_id=quiz_id, limit=10, offset=0)
        assert attempts["count"] == 1
