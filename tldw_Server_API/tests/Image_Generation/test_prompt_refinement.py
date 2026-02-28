from tldw_Server_API.app.core.Image_Generation.prompt_refinement import (
    DEFAULT_QUALITY_SUFFIX,
    normalize_prompt_refinement_mode,
    refine_image_prompt,
)


def test_normalize_prompt_refinement_mode_maps_booleans():
    assert normalize_prompt_refinement_mode(True) == "basic"
    assert normalize_prompt_refinement_mode(False) == "off"


def test_normalize_prompt_refinement_mode_falls_back_to_default():
    assert normalize_prompt_refinement_mode("not-a-mode", default="auto") == "auto"
    assert normalize_prompt_refinement_mode(None, default="off") == "off"


def test_refine_image_prompt_off_mode_keeps_prompt():
    prompt = "  cat portrait  "
    assert refine_image_prompt(prompt, mode="off") == "cat portrait"


def test_refine_image_prompt_auto_mode_enriches_sparse_prompt():
    refined = refine_image_prompt("cat portrait", mode="auto")
    assert refined.startswith("cat portrait,")
    assert DEFAULT_QUALITY_SUFFIX in refined


def test_refine_image_prompt_auto_mode_keeps_detailed_prompt():
    prompt = "highly detailed portrait of a cat with cinematic lighting and sharp focus"
    assert refine_image_prompt(prompt, mode="auto") == prompt


def test_refine_image_prompt_respects_max_length():
    prompt = "cat portrait"
    assert refine_image_prompt(prompt, mode="basic", max_length=len(prompt)) == prompt

