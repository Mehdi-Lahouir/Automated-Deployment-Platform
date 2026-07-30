from uuid import uuid4

from playwright.sync_api import Page, expect

from e2e_tests.conftest import API_KEY


def test_unlock_and_task_lifecycle_with_filters(page: Page, app_url: str) -> None:
    task_title = f"Browser smoke task {uuid4().hex[:8]}"

    page.goto(app_url)
    expect(page.get_by_role("heading", name="Unlock TaskFlow")).to_be_visible()

    page.get_by_label("API key").fill("invalid-api-key-with-24-characters")
    page.get_by_role("button", name="Unlock workspace").click()
    expect(page.get_by_role("alert")).to_contain_text("not accepted")

    page.get_by_label("API key").fill(API_KEY)
    page.get_by_role("button", name="Unlock workspace").click()
    expect(page.locator("#auth-overlay")).to_be_hidden()
    expect(page.get_by_role("button", name="Lock")).to_be_visible()

    page.get_by_label("New task title").fill(task_title)
    page.get_by_role("button", name="Add task").click()
    task = page.locator(".task-item", has_text=task_title)
    expect(task).to_be_visible()
    expect(page.locator("#total-count")).to_have_text("1")
    expect(page.locator("#pending-count")).to_have_text("1")

    page.get_by_label("Search tasks").fill("no task has this title")
    expect(task).to_be_hidden()
    expect(page.get_by_text("No matching tasks")).to_be_visible()

    page.get_by_label("Search tasks").fill(task_title)
    expect(task).to_be_visible()
    task.get_by_role("button", name=f"Mark {task_title} as completed").click()
    expect(page.locator("#completed-count")).to_have_text("1")

    page.get_by_label("Filter by status").select_option("pending")
    expect(task).to_be_hidden()
    page.get_by_label("Filter by status").select_option("completed")
    expect(task).to_be_visible()

    task.get_by_role("button", name=f"Delete {task_title}").click()
    expect(task).to_be_hidden()
    expect(page.locator("#total-count")).to_have_text("0")
