import uuid

import pytest


@pytest.mark.e2e
def test_evaluations_dataset_and_evaluation_crud(configured_page):
    page = configured_page
    dataset_suffix = uuid.uuid4().hex[:8]
    dataset_name = f"e2e_dataset_{dataset_suffix}"
    eval_name = f"e2e_eval_{dataset_suffix}"

    page.goto("/evaluations")
    page.get_by_role("heading", name="Evaluations").wait_for()

    page.get_by_role("tab", name="Datasets").click()
    page.get_by_role("button", name="New dataset").click()

    dataset_modal = page.get_by_role("dialog", name="New dataset")
    dataset_modal.get_by_label("Name").fill(dataset_name)
    dataset_modal.get_by_label("Description").fill("E2E dataset description")
    dataset_modal.get_by_label("Sample input").fill("What is tldw?")
    dataset_modal.get_by_label("Expected output (optional)").fill("An AI assistant.")
    dataset_modal.get_by_role("button", name="Create").click()

    page.get_by_text(dataset_name).wait_for(timeout=60_000)
    dataset_card = page.locator(".ant-card").filter(
        has=page.get_by_text(dataset_name)
    ).first
    dataset_card.get_by_role("button", name="View").click()
    page.get_by_role("dialog", name="Dataset details").get_by_text("Samples preview").wait_for()
    page.get_by_role("button", name="Close").click()

    page.get_by_role("tab", name="Evaluations").click()
    page.get_by_role("button", name="New evaluation").click()

    eval_modal = page.get_by_role("dialog", name="New evaluation")
    eval_modal.get_by_label("Name").fill(eval_name)
    eval_modal.get_by_role("button", name="Next").click()
    eval_modal.get_by_role("button", name="Next").click()

    dataset_select = eval_modal.get_by_placeholder("Select dataset")
    dataset_select.click()
    page.locator(".ant-select-dropdown").get_by_text(dataset_name).click()
    eval_modal.get_by_role("button", name="Create").click()

    page.get_by_text(eval_name).wait_for(timeout=60_000)
    page.get_by_text(eval_name).click()
    page.get_by_role("button", name="Delete").click()
    delete_dialog = page.get_by_role("dialog", name="Delete this evaluation?")
    delete_dialog.get_by_role("button", name="Delete").click()

    page.get_by_role("tab", name="Datasets").click()
    dataset_card = page.locator(".ant-card").filter(
        has=page.get_by_text(dataset_name)
    ).first
    dataset_card.get_by_role("button", name="Delete").click()
    delete_dataset_dialog = page.get_by_role("dialog", name="Delete this dataset?")
    delete_dataset_dialog.get_by_role("button", name="Delete").click()
