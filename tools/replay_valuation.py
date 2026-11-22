"""Replay valuation research in a browser against a disposable real service.

Exit 0 means every requested browser passed; 1 means a replay assertion failed;
2 means a dependency, browser launch, or local service startup blocked the run.
No access keys, cookies, browser profiles, or network traces are saved.
"""

import argparse
from contextlib import ExitStack
import json
import math
from pathlib import Path
import sys
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EXAMPLE_ID = "nvidia_workbook_reproduction"
BASELINE = 199.49058622677524
ADJUSTED = 166.666112841825
ENTRY_CEILING = 116.66627898927749


def is_response(response, method, path):
    return response.request.method == method and urlsplit(response.url).path == path


def json_response(response):
    assert response.status == 200, f"Unexpected HTTP status: {response.status}"
    return response.json()


def close_to(actual, expected):
    assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-8), (
        f"Expected {expected:.12f}; received {actual:.12f}"
    )


def packet_in_form(page):
    return json.loads(page.locator("#advanced-packet").input_value())


def assert_report(report, packet):
    """Pin audited values independently of the application's own evaluator."""
    assert report["request"] == packet
    assert report["currency"] == "USD"
    assert report["as_of"] == "2026-11-21"
    close_to(report["baseline"]["value_per_unit"], BASELINE)
    decision = report["decision"]
    close_to(decision["adjusted_value"], ADJUSTED)
    close_to(decision["entry_ceiling"], ENTRY_CEILING)
    close_to(decision["entry_ceiling"], decision["adjusted_value"] * 0.7)
    close_to(decision["baseline_entry_reference"], BASELINE * 0.7)
    assert BASELINE > ADJUSTED > ENTRY_CEILING
    assert decision["market_price"] == packet["market"]["price"]
    assert decision["price_as_of"] is None
    assert decision["status"] == "hold"
    assert decision["execution_allowed"] is False
    assert report["evidence"]["status"] == "review_required"
    assert packet["market"]["as_of"] is None
    quote = next(s for s in packet["sources"] if s["id"] == packet["market"]["source_id"])
    assert quote["kind"] == "quote" and quote["observed_on"] is None
    assert quote["verified"] is False
    assert "missing_quote_timestamp" in quote["issues"]
    references = report["reference_values"]
    assert references["workbook_input_date"] == "2022-10-31"
    assert references["article_stated_valuation_date"] == "2026-10-29"
    assert references["author_entry_threshold"] == 140
    assert references["author_entry_threshold"] != decision["entry_ceiling"]
    assert len(report["scenarios"]) == 3
    assert packet["assumptions"]["revenue"] == 302_970_000_000
    assert packet["assumptions"]["units"] == 24_315_000_000
    assert packet["assumptions"]["reinvestment_timing"] == "next_year"
    for key in ("growth_path", "margin_path", "tax_path", "discount_path"):
        assert len(packet["assumptions"][key]) == 10


def assert_visible_report(page, expect, price):
    expect(page.locator("#report")).to_be_visible()
    expect(page.locator("#baseline-value")).to_have_text("$199.49")
    expect(page.locator("#adjusted-value")).to_have_text("$166.67")
    expect(page.locator("#entry-value")).to_have_text("$116.67")
    expect(page.locator("#reference-price")).to_have_text(f"${price:.2f}")
    expect(page.locator("#upside-label")).to_have_text("Input gap to value")
    expect(page.locator("#price-context-note")).to_contain_text(
        "Historical input comparison — price unverified"
    )
    expect(page.locator("#price-context-note")).to_contain_text("not current market upside")
    expect(page.locator("#decision-status")).to_have_text("On hold · Review needed")
    expect(page.locator("#evidence-holds")).to_contain_text(
        "valuation_date_conflict_2022_10_31_vs_2026_10_29"
    )
    expect(page.locator("#use-annual-paths")).to_be_checked()
    expect(page.locator("#stale-notice")).to_be_hidden()
    expect(page.locator("#export-button")).to_be_enabled()


def open_workspace(page, url, expect):
    page.goto(f"{url}/valuation.html", wait_until="domcontentloaded")
    # The examples are rendered after both startup requests settle, avoiding a
    # race between a delayed unauthenticated history response and signing in.
    expect(page.locator("#example-select")).to_have_value(EXAMPLE_ID)
    expect(page.locator("#connection-notice")).to_be_hidden()


def sign_in(page, actor, key, expect, touch=False):
    expect(page.locator("#session-button")).to_have_text("Sign in")
    if touch:
        page.locator("#session-button").tap()
    else:
        page.locator("#session-button").focus()
        page.keyboard.press("Enter")
    expect(page.locator("#access-key")).to_be_focused()
    page.locator("#actor").select_option(actor)
    page.locator("#access-key").fill(key)
    with page.expect_response(lambda r: is_response(r, "POST", "/api/session")) as reply:
        if touch:
            page.locator('#sign-in-form button[type="submit"]').tap()
        else:
            page.keyboard.press("Tab")
            expect(page.locator('#sign-in-form button[type="submit"]')).to_be_focused()
            page.keyboard.press("Enter")
    json_response(reply.value)
    expect(page.locator("#session-button")).to_have_text("Sign out")
    expect(page.locator("#sign-in-panel")).to_be_hidden()
    expect(page.locator("#access-key")).to_have_value("")
    expect(page.locator("#evaluate-button")).to_be_focused()


def evaluate(page, packet, expect):
    page.locator("#evaluate-button").focus()
    with page.expect_response(
        lambda r: is_response(r, "POST", "/api/valuation/evaluate")
    ) as reply:
        page.keyboard.press("Enter")
    assert reply.value.request.post_data_json == packet
    report = json_response(reply.value)
    assert_report(report, packet)
    assert_visible_report(page, expect, packet["market"]["price"])
    expect(page.locator("#packet-digest")).to_have_text(report["packet_digest"])
    expect(page.locator("#save-button")).to_be_enabled()
    return report


def history(context, url):
    return json_response(context.request.get(f"{url}/api/valuation/runs"))["runs"]


def saved_run(context, url, run_id):
    return json_response(context.request.get(f"{url}/api/valuation/runs/{run_id}"))


def open_history(page, index, run, expect, touch=False):
    button = page.locator(".history-item").nth(index)
    with page.expect_response(
        lambda r: is_response(r, "GET", f"/api/valuation/runs/{run['run_id']}")
    ) as reply:
        if touch:
            button.tap()
        else:
            button.focus()
            page.keyboard.press("Enter")
    assert json_response(reply.value) == run
    expect(page.locator("#save-status")).to_contain_text(run["run_id"])
    expect(page.locator("#save-button")).to_have_text("Valuation saved")
    expect(page.locator("#save-button")).to_be_disabled()
    expect(page.locator("#packet-digest")).to_have_text(run["packet_digest"])
    assert packet_in_form(page) == run["request"]
    assert_visible_report(page, expect, run["request"]["market"]["price"])


def assert_no_overflow(page):
    sizes = page.evaluate("""() => ({
        document: document.documentElement.scrollWidth,
        viewport: window.innerWidth
    })""")
    assert sizes["document"] <= sizes["viewport"], f"Horizontal overflow: {sizes}"


def walkthrough(url, keys, browser, device, expect, screenshot_dir, engine_name):
    source_packet = json.loads(
        (ROOT / "data/valuation/nvidia_workbook_reproduction.json").read_text(encoding="utf-8")
    )["request"]
    errors = []
    with ExitStack() as stack:
        desktop = stack.enter_context(browser.new_context(
            viewport={"width": 1440, "height": 900},
            accept_downloads=True, reduced_motion="reduce",
        ))
        page = desktop.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        open_workspace(page, url, expect)
        page.keyboard.press("Tab")
        expect(page.locator(".skip-link")).to_be_focused()
        page.keyboard.press("Enter")
        expect(page.locator("#workspace")).to_be_focused()
        sign_in(page, "reviewer", keys["reviewer"], expect)
        assert packet_in_form(page) == source_packet
        assert history(desktop, url) == []

        original_report = evaluate(page, source_packet, expect)
        with page.expect_response(
            lambda r: is_response(r, "POST", "/api/valuation/runs")
        ) as reply:
            page.locator("#save-button").click()
        original_run = json_response(reply.value)
        assert original_run["request"] == source_packet
        assert original_run["report"] == original_report
        expect(page.locator("#save-button")).to_have_text("Valuation saved")
        expect(page.locator(".history-item")).to_have_count(1)

        # Export is the same evaluated request/report, including historical
        # source defects and actual-dollar units; the download is temporary.
        with page.expect_download() as download:
            page.locator("#export-button").click()
        exported = json.loads(Path(download.value.path()).read_text(encoding="utf-8"))
        assert exported == {
            "export_schema_version": "1.0",
            "run_id": original_run["run_id"],
            "packet_digest": original_report["packet_digest"],
            "request": source_packet,
            "report": original_report,
        }
        assert not any(key in json.dumps(exported) for key in keys.values())
        download.value.delete()

        page.get_by_label("Equity price / unit (USD)", exact=False).fill("164")
        expect(page.locator("#stale-notice")).to_be_visible()
        expect(page.locator("#save-button")).to_be_disabled()
        expect(page.locator("#export-button")).to_be_disabled()
        expect(page.locator("#packet-digest")).to_have_text(original_report["packet_digest"])
        edited_packet = packet_in_form(page)
        expected_edit = json.loads(json.dumps(source_packet))
        expected_edit["market"]["price"] = 164
        assert edited_packet == expected_edit
        revised_report = evaluate(page, edited_packet, expect)
        assert revised_report["packet_digest"] != original_report["packet_digest"]

        # Let the service commit the revision, then interrupt only its reply.
        # Capture bodies in memory: retry must reuse both the UUID and packet.
        interrupted = {}

        def lose_save_reply(route):
            assert route.request.method == "POST"
            interrupted["body"] = route.request.post_data
            response = route.fetch()
            interrupted["status"] = response.status
            interrupted["run"] = response.json()
            route.abort("failed")

        page.route("**/api/valuation/runs", lose_save_reply, times=1)
        page.locator("#save-button").click()
        expect(page.locator("#save-button")).to_have_text("Retry save")
        expect(page.locator("#save-button")).to_be_enabled()
        expect(page.locator("#save-status")).to_contain_text("preventing a duplicate record")
        assert interrupted["status"] == 200
        before_retry = history(desktop, url)
        assert len(before_retry) == 2
        assert before_retry[0]["run_id"] == interrupted["run"]["run_id"]
        with page.expect_response(
            lambda r: is_response(r, "POST", "/api/valuation/runs")
        ) as reply:
            page.locator("#save-button").click()
        assert reply.value.request.post_data == interrupted["body"]
        revised_run = json_response(reply.value)
        assert revised_run == interrupted["run"]
        assert revised_run["request"] == edited_packet
        assert revised_run["report"] == revised_report
        expect(page.locator("#save-button")).to_have_text("Valuation saved")
        expect(page.locator(".history-item")).to_have_count(2)
        assert history(desktop, url) == before_retry
        assert saved_run(desktop, url, original_run["run_id"]) == original_run

        # Reload discards browser state. Saved history restores exact server
        # snapshots, with the old revision still available and unchanged.
        page.reload(wait_until="domcontentloaded")
        expect(page.locator(".history-item")).to_have_count(2)
        expect(page.locator("#session-button")).to_have_text("Sign out")
        expect(page.locator("#report")).to_be_hidden()
        open_history(page, 0, revised_run, expect)
        open_history(page, 1, original_run, expect)
        for width in (1440, 1024, 768):
            page.set_viewport_size({"width": width, "height": 900})
            assert_no_overflow(page)
        page.set_viewport_size({"width": 1440, "height": 900})

        # A separate mobile browser context has no inherited session. It signs
        # in as the other commercial actor and resumes the saved revision.
        phone = stack.enter_context(browser.new_context(**device, reduced_motion="reduce"))
        mobile = phone.new_page()
        mobile.on("pageerror", lambda error: errors.append(str(error)))
        open_workspace(mobile, url, expect)
        sign_in(mobile, "founder", keys["founder"], expect, touch=True)
        expect(mobile.locator(".history-item")).to_have_count(2)
        open_history(mobile, 0, revised_run, expect, touch=True)
        assert_no_overflow(mobile)
        mobile.set_viewport_size({"width": 320, "height": 780})
        assert_no_overflow(mobile)
        mobile.set_viewport_size(device["viewport"])
        assert_no_overflow(mobile)

        assert not errors, "Browser JavaScript errors: " + "; ".join(errors)
        if screenshot_dir:
            # Both access-key fields have been emptied before any image exists.
            for client in (page, mobile):
                expect(client.locator("#access-key")).to_have_value("")
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot_dir / f"valuation-{engine_name}-desktop.png"), full_page=True)
            mobile.screenshot(path=str(screenshot_dir / f"valuation-{engine_name}-mobile.png"), full_page=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("chromium", "webkit", "both"), default="chromium")
    parser.add_argument("--screenshots", type=Path, help="Optional directory for screenshots after a successful replay")
    args = parser.parse_args()
    try:
        from playwright.sync_api import Error as PlaywrightError, expect, sync_playwright
        from tools.replay_founder import executable, server
    except ImportError as error:
        print(f"BLOCKED | dependency unavailable: {error}", file=sys.stderr)
        return 2
    expect.set_options(timeout=15000)
    names = ("chromium", "webkit") if args.engine == "both" else (args.engine,)
    failed = blocked = False
    try:
        with sync_playwright() as runtime:
            for name in names:
                with ExitStack() as stack:
                    try:
                        url, keys = stack.enter_context(server())
                    except OSError as error:
                        print(f"BLOCKED | local service startup: {error}", file=sys.stderr)
                        return 2
                    options = {}
                    if name == "chromium" and (path := executable()):
                        options["executable_path"] = path
                    try:
                        browser = stack.enter_context(getattr(runtime, name).launch(**options))
                    except PlaywrightError as error:
                        print(f"BLOCKED | {name} launch: {error}", file=sys.stderr)
                        blocked = True
                        continue
                    device_name = "Pixel 7" if name == "chromium" else "iPhone 13"
                    try:
                        walkthrough(url, keys, browser, runtime.devices[device_name], expect, args.screenshots, name)
                    except Exception as error:
                        message = str(error)
                        for key in keys.values():
                            message = message.replace(key, "[redacted access key]")
                        print(f"FAIL | {name} | {type(error).__name__}: {message}", file=sys.stderr)
                        failed = True
                    else:
                        print(
                            f"PASS | {name} {browser.version} + {device_name} emulation | "
                            "historical source reproduction, stale locks, server evaluation, "
                            "export, immutable history, interrupted-save retry, keyboard and mobile layout"
                        )
    except (OSError, PlaywrightError) as error:
        print(f"BLOCKED | browser runtime startup: {error}", file=sys.stderr)
        return 2
    return 1 if failed else 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
