"""Local stdio tool that queues bounded work for resumption in Founder Command."""

import json
from http.client import HTTPConnection
import os
from uuid import UUID


def queue_simulation(question: str) -> dict:
    """Queue a private Family Office simulation and return its durable app ID."""
    question = question.strip()
    if not 5 <= len(question) <= 3000:
        raise ValueError("Provide 5 to 3000 characters of task text.")
    token = os.environ.get("BR_CHAT_OPERATIONS_TOKEN")
    if not token:
        raise RuntimeError("Configure the local operations credential.")
    connection = HTTPConnection("127.0.0.1", int(os.environ.get("BR_CHAT_APP_PORT", "8000")), timeout=10)
    try:
        connection.request(
            "POST", "/api/jobs",
            body=json.dumps({
                "domain": "FAMILY_OFFICE", "leader": "L4",
                "specialist": "SW-09", "question": question,
            }).encode("utf-8"),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(f"Founder Command returned HTTP {response.status}.")
        job_id = str(UUID(json.loads(response.read(1024))["id"]))
    finally:
        connection.close()
    return {"id": job_id, "domain": "FAMILY_OFFICE", "state": "QUEUED", "mode": "SIMULATION"}


def main():
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("Black River Private Work Queue")
    server.tool()(queue_simulation)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
