"""Replay the founder demo in a real browser against a disposable local server.

The two browser contexts represent separate devices. Real physical-phone testing
still requires loading the demo on a handset. No external services are contacted.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pilot.founder_service import Server


@contextmanager
def server():
    with (
        tempfile.TemporaryDirectory() as folder,
        Server(Path(folder) / "pilot.sqlite3") as httpd,
    ):
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{httpd.server_port}", httpd.keys
        finally:
            httpd.shutdown()
            thread.join()


def press(page, name):
    page.get_by_role("button", name=name, exact=True).click()


def select_item(page, title):
    page.get_by_role("button", name=title, exact=False).first.click()
    expect(page.get_by_role("heading", name=title, exact=True)).to_be_visible()


def walkthrough(url, browser, engine_name, device, screenshot_dir=None):
    desktop = browser.new_context(viewport={"width": 1440, "height": 900})
    phone = browser.new_context(**device)
    page = desktop.new_page()
    mobile = phone.new_page()
    errors = []
    for client in (page, mobile):
        client.on("pageerror", lambda error: errors.append(str(error)))
        client.goto(url)
    expect(page.locator("#modules button")).to_have_count(10)
    page.bring_to_front()
    page.keyboard.press("Tab")
    expect(page.locator(".skip")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#workspace")).to_be_focused()

    # Prove the hold by driving the exact visible controls, then repeat from a stale second tab.
    press(page, "Select parcel")
    press(page, "Record underwriting")
    expect(
        page.get_by_role("button", name="Approve simulated bid review", exact=True)
    ).to_be_disabled()
    press(page, "Load verified funding fixture")
    second = desktop.new_page()
    second.goto(url)
    press(page, "Approve simulated bid review")
    press(second, "Approve simulated bid review")
    expect(second.locator("#feedback")).to_contain_text("already changed")
    page.reload()
    expect(page.locator(".task-panel li")).to_have_count(3)
    second.close()

    select_item(page, "Incoming project brief")
    for action in (
        "Ingest sample message",
        "Review extracted document",
        "Create review task",
    ):
        press(page, action)
    select_item(page, "Service invoice")
    expect(
        page.get_by_role("button", name="Reconcile simulated receipt", exact=True)
    ).to_have_count(0)
    for action in (
        "Review invoice",
        "Attach settlement receipt",
        "Reconcile simulated receipt",
    ):
        press(page, action)
    page.locator("#scope").select_option("family")
    expect(page.get_by_text("Orchard parcel")).to_have_count(0)
    for action in ("Review request", "Review estimate", "Approve simulated dispatch"):
        press(page, action)
    expect(page.get_by_text("Simulation complete", exact=True)).to_be_visible()
    page.get_by_label("Review note").fill("Synthetic checkpoint A")
    press(page, "Save draft")
    expect(page.locator("#feedback")).to_have_text("Draft saved.")
    page.reload()
    expect(page.get_by_label("Review note")).to_have_value("Synthetic checkpoint A")
    page.get_by_text("Device handoff", exact=True).click()
    with page.expect_download() as handle:
        press(page, "Export draft")
    raw = handle.value.path().read_bytes()
    exported = json.loads(raw)
    assert set(exported) == {"format", "scope", "id", "version", "note", "checkpoint"}
    assert exported["checkpoint"] == {
        "count": 3,
        "lastStep": "Approve simulated dispatch",
    }

    # Test cross-device handoff using a new storage context. Imported drafts have zero approvals.
    select_item(mobile, "Orchard parcel")
    mobile.get_by_text("Device handoff", exact=True).click()
    upload = mobile.get_by_label("Import draft")

    def send(data):
        upload.set_input_files(
            {
                "name": "draft.json",
                "mimeType": "application/json",
                "buffer": json.dumps(data).encode(),
            }
        )

    send(exported)
    expect(mobile.locator("#feedback")).to_contain_text("this workspace")
    mobile.locator("#scope").select_option("family")
    select_item(mobile, "Pump maintenance")
    mobile.get_by_text("Device handoff", exact=True).click()
    obsolete = {**exported, "version": "obsolete"}
    send(obsolete)
    expect(mobile.locator("#feedback")).to_contain_text("evidence version")
    send(exported)
    expect(mobile.get_by_label("Review note")).to_have_value("Synthetic checkpoint A")
    expect(
        mobile.get_by_text("Originating device recorded", exact=False)
    ).to_contain_text("Approve simulated dispatch")
    expect(mobile.locator(".task-panel li")).to_have_count(0)
    expect(
        mobile.get_by_role("button", name="Review request", exact=True)
    ).to_be_visible()
    assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if screenshot_dir:
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        mobile.screenshot(
            path=str(screenshot_dir / f"{engine_name}-phone.png"), full_page=True
        )
        page.screenshot(
            path=str(screenshot_dir / f"{engine_name}-desktop.png"), full_page=True
        )
    mobile.get_by_role("button", name="Modules", exact=True).tap()
    press(mobile, "System")
    expect(mobile.locator("#body li")).to_have_count(12)
    press(page, "Agents")
    expect(page.locator("#body li")).to_have_count(3)
    page.locator("#scope").select_option("civic")
    for action in ("Review field note", "Record evidence"):
        press(page, action)
    for width in (320, 768, 1024, 1440):
        page.set_viewport_size({"width": width, "height": 900})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
            width
        )
    # Local history survives a failed decode until the operator archives and restarts the scope.
    damaged = "damaged sample"
    page.evaluate(
        "(value)=>localStorage.setItem('br-review-fixtures:v1:civic',value)", damaged
    )
    page.reload()
    expect(page.get_by_role("heading", name="Workspace recovery")).to_be_visible()
    press(page, "Archive snapshot and restart")
    expect(page.get_by_role("heading", name="District field note")).to_be_visible()
    assert page.evaluate(
        "Object.keys(localStorage).filter(k=>k.includes(':recovery:')).map(k=>localStorage[k])"
    ) == [damaged]
    assert not errors, errors
    desktop.close()
    phone.close()
    return raw, (json.dumps(obsolete, indent=2) + "\n").encode()


def connected(url, browser, device, keys):
    desktop = browser.new_context()
    phone = browser.new_context(**device)
    page = desktop.new_page()
    mobile = phone.new_page()

    def sign_in(client, actor):
        client.goto(url + "/connected.html")
        # Wait for the unauthenticated bootstrap GET before submitting credentials.
        expect(client.locator("#feedback")).to_contain_text("Sign in")
        client.get_by_label("Synthetic account").select_option(actor)
        client.get_by_label("Local access key").fill(keys[actor])
        client.get_by_role("button", name="Sign in", exact=True).press("Enter")
        expect(client.locator("#identity")).to_contain_text(actor)

    sign_in(page, "reviewer")
    sign_in(mobile, "reviewer")
    page.locator("summary").press("Enter")
    expect(page.locator("#gates")).to_contain_text("title-review")
    page.get_by_label("Review note").fill("Evidence checked on desktop")
    page.get_by_role("button", name="Save checkpoint").press("Enter")
    expect(page.locator("#feedback")).to_have_text("Checkpoint saved.")
    mobile.get_by_label("Review note").fill("Older copy")
    press(mobile, "Save checkpoint")
    expect(mobile.locator("#feedback")).to_contain_text("changed on another device")
    press(mobile, "Reload checkpoint")
    expect(mobile.get_by_label("Review note")).to_have_value(
        "Evidence checked on desktop"
    )

    # Let the request commit, then drop the response. A retry must reuse the original key.
    def lose_reply(route):
        reply = route.fetch()
        assert reply.status == 200
        route.abort()

    target = "**/api/workspaces/commercial/records/orchard-01"
    page.route(target, lose_reply, times=1)
    page.get_by_role("button", name="Record independent review").press("Enter")
    expect(page.get_by_role("button", name="Retry last request")).to_be_visible()
    press(page, "Retry last request")
    expect(page.locator("#events li")).to_have_count(1)
    press(mobile, "Sign out")
    expect(mobile.locator("#login")).to_be_visible()
    sign_in(mobile, "founder")
    expect(mobile.locator("#events")).to_contain_text("reviewer")
    expect(mobile.get_by_label("Review note")).to_have_value("")
    mobile.get_by_label("Review note").fill("Approve reviewed fixture")
    mobile.get_by_role("button", name="Approve simulated decision").tap()
    expect(mobile.locator("#events li")).to_have_count(2)
    expect(mobile.locator("#summary")).to_contain_text("bid ready simulation")
    assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth")
    desktop.close()
    phone.close()


def executable():
    candidates = [
        os.environ.get("FOUNDER_REPLAY_BROWSER"),
        shutil.which("chromium"),
        shutil.which("google-chrome"),
    ]
    for root in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        if root in os.environ:
            candidates += [
                str(Path(os.environ[root]) / suffix)
                for suffix in (
                    "Microsoft/Edge/Application/msedge.exe",
                    "Google/Chrome/Application/chrome.exe",
                )
            ]
    return next((path for path in candidates if path and Path(path).is_file()), None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--screenshots", type=Path, help="Optional folder for synthetic screenshots"
    )
    parser.add_argument(
        "--engine", choices=("chromium", "webkit", "both"), default="chromium"
    )
    parser.add_argument(
        "--handoff-fixtures",
        type=Path,
        help="New directory for the verified synthetic draft and stale control from each engine",
    )
    args = parser.parse_args()
    if args.handoff_fixtures and args.handoff_fixtures.exists():
        parser.error("--handoff-fixtures requires a new output directory")
    with sync_playwright() as engine:
        for name in ("chromium", "webkit") if args.engine == "both" else (args.engine,):
            options = {"executable_path": executable()} if name == "chromium" else {}
            device_name = "Pixel 7" if name == "chromium" else "iPhone 13"
            with (
                server() as (url, keys),
                getattr(engine, name).launch(**options) as browser,
            ):
                valid_draft, stale_draft = walkthrough(
                    url, browser, name, engine.devices[device_name], args.screenshots
                )
                connected(url, browser, engine.devices[device_name], keys)
                # Publish the exact exported fixture and its stale control after the replay passes.
                if args.handoff_fixtures:
                    folder = args.handoff_fixtures / name
                    folder.mkdir(parents=True)
                    (folder / "valid-draft.json").write_bytes(valid_draft)
                    (folder / "stale-draft.json").write_bytes(stale_draft)
                print(
                    f"PASS | {name} {browser.version} + {device_name} emulation | five local workflows, authenticated resume, conflict, interrupted retry, independent decisions, keyboard and touch"
                )
