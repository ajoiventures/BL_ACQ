"""HTTP contract checks for authenticated, durable local review."""

import json
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dataclasses import replace
from unittest.mock import patch
from pilot.founder_service import Server, prepare
from pilot.scenario import deal_fixture

TARGET = "/api/workspaces/commercial/records/orchard-01"


class ConnectedReviewTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = Path(self.directory.name) / "review.db"
        self.start()

    def start(self):
        self.server = Server(self.db)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.stop)

    def stop(self):
        if self.worker.is_alive():
            self.server.shutdown()
            self.worker.join()
            self.server.server_close()

    def call(self, path, cookie="", body=None):
        request = Request(
            "http://127.0.0.1:" + str(self.server.server_port) + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json", "Cookie": cookie},
        )
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response), response.headers

    def session(self, actor):
        status, _, headers = self.call(
            "/api/session", body={"actor": actor, "token": self.server.keys[actor]}
        )
        self.assertEqual(status, 200)
        return headers["Set-Cookie"].split(";")[0]

    def test_resume_conflict_role_and_restart(self):
        self.assertEqual(self.call(TARGET)[0], 401)
        civic = self.session("civic-reader")
        self.assertEqual(self.call(TARGET, civic)[0], 403)
        reviewer = self.session("reviewer")
        other = self.session("reviewer")
        body = dict(
            action="draft",
            note="source observed",
            version=0,
            evidence=self.call(TARGET, reviewer)[1]["evidence"],
            request_id="draft-001",
        )
        self.assertEqual(self.call(TARGET, reviewer, body)[0], 200)
        self.assertEqual(self.call(TARGET, other)[1]["draft"]["note"], body["note"])
        self.assertEqual(
            self.call(TARGET, other, body | {"request_id": "draft-002"})[0], 409
        )
        self.assertEqual(
            self.call(
                TARGET,
                other,
                body | {"evidence": "stale", "version": 1, "request_id": "draft-003"},
            )[0],
            409,
        )
        self.assertEqual(self.call(TARGET, other, body | {"note": "changed"})[0], 409)
        self.assertEqual(
            self.call(
                TARGET, other, body | {"action": "approve", "request_id": "wrong-001"}
            )[0],
            403,
        )
        self.stop()
        self.start()
        self.assertEqual(self.call(TARGET, reviewer)[0], 401)
        self.assertEqual(
            self.call(TARGET, self.session("reviewer"))[1]["draft"]["version"], 1
        )
        self.assertEqual(
            self.call(TARGET, self.session("founder"))[1]["draft"]["note"], ""
        )

    def test_competing_and_repeated_decision(self):
        founder = self.session("founder")
        reviewer = self.session("reviewer")
        body = dict(
            action="approve",
            note="Packet checked.",
            version=0,
            evidence=self.call(TARGET, reviewer)[1]["evidence"],
            request_id="approve-001",
        )
        self.assertEqual(self.call(TARGET, founder, body)[0], 409)
        review = body | {"action": "review", "request_id": "review-001"}
        self.assertEqual(self.call(TARGET, reviewer, review)[0], 200)
        barrier = threading.Barrier(2)

        def submit(key):
            command = body | {"version": 1, "request_id": key}
            barrier.wait(timeout=4)
            return command, self.call(TARGET, founder, command)

        with ThreadPoolExecutor(2) as pool:
            outcomes = list(pool.map(submit, ["approve-002", "approve-003"]))
        self.assertEqual(sorted(response[0] for _, response in outcomes), [200, 409])
        original, success = next(pair for pair in outcomes if pair[1][0] == 200)
        self.assertEqual(self.call(TARGET, founder, original)[1], success[1])
        self.assertEqual(
            [e["actor"] for e in success[1]["events"]], ["reviewer", "founder"]
        )
        self.assertEqual(success[1]["underwriting"]["state"], "bid_ready_simulation")
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM pilot_decisions").fetchone()[
                    0
                ],
                2,
            )

            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM founder_actions").fetchone()[
                    0
                ],
                2,
            )

    def test_evidence_revision_is_frozen_and_requires_new_review(self):
        actor = self.session("reviewer")
        old = self.call(TARGET, actor)[1]
        review = dict(
            action="review",
            note="Reviewed version one",
            version=0,
            evidence=old["evidence"],
            request_id="review-version-one",
        )
        self.assertEqual(self.call(TARGET, actor, review)[0], 200)
        candidate, economics, day = deal_fixture()
        # Changed fixture inputs become visible only after publishing the next revision.
        with patch(
            "pilot.scenario.deal_fixture",
            return_value=(candidate, replace(economics, financing_cap_cents=None), day),
        ):
            self.assertEqual(self.call(TARGET, actor)[1]["evidence"], old["evidence"])
            prepare(self.db)
        new = self.call(TARGET, actor)[1]
        self.assertNotEqual(new["evidence"], old["evidence"])
        self.assertEqual(new["underwriting"]["packet_digest"], new["evidence"])
        self.assertFalse(new["underwriting"]["ready"])
        self.assertEqual(new["events"], [])
        self.assertEqual(len(new["history"]), 1)
        self.assertEqual(self.call(TARGET, actor, review)[0], 409)
        self.assertEqual(
            self.call(
                TARGET, actor, review | {"request_id": "old-draft", "action": "draft"}
            )[0],
            409,
        )
        self.assertEqual(
            self.call(
                TARGET,
                actor,
                review | {"evidence": new["evidence"], "request_id": "new-review"},
            )[0],
            200,
        )
        self.assertEqual(
            self.call(
                TARGET,
                self.session("founder"),
                review
                | {
                    "action": "approve",
                    "evidence": new["evidence"],
                    "version": 1,
                    "request_id": "new-approve",
                },
            )[0],
            409,
        )


if __name__ == "__main__":
    unittest.main()
