from __future__ import annotations

from tldw_Server_API.app.core.Evaluations.benchmark_utils import NextTokenCapture


def test_parse_logprobs_completions_style():
    capture = NextTokenCapture(top_k=2)
    response = {
        "choices": [
            {
                "text": "x",
                "logprobs": {
                    "tokens": ["x"],
                    "top_logprobs": [
                        {"x": -0.1, "y": -1.0}
                    ],
                },
            }
        ]
    }

    parsed = capture.parse_logprobs(response)
    assert parsed["generated_token"] == "x"
    tokens = [t["token"] for t in parsed["top_tokens"]]
    assert tokens[:2] == ["x", "y"]


def test_parse_logprobs_chat_style():
    capture = NextTokenCapture(top_k=2)
    response = {
        "choices": [
            {
                "message": {"role": "assistant", "content": "x"},
                "logprobs": {
                    "content": [
                        {
                            "token": "x",
                            "logprob": -0.1,
                            "top_logprobs": [
                                {"token": "x", "logprob": -0.1},
                                {"token": "y", "logprob": -1.0},
                            ],
                        }
                    ]
                },
            }
        ]
    }

    parsed = capture.parse_logprobs(response)
    assert parsed["generated_token"] == "x"
    tokens = [t["token"] for t in parsed["top_tokens"]]
    assert tokens[:2] == ["x", "y"]
