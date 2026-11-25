import uuid

import httpx
import pytest

from tools import run_leased_acquisition_worker as worker


@pytest.mark.parametrize("committed", [True, False])
def test_worker_reads_durable_cursor_after_lost_step_response(monkeypatch, committed):
    run = dict(version=1, cursor=0, total=1, state="READY", backend="cuda",
               actual_backend=None, error=None, offer_ready=0)
    steps = []

    def handle(request):
        import json
        if request.url.path.endswith("/worker-lease"):
            data = json.loads(request.content)
            return httpx.Response(200,json={"lease_id":data["lease_id"],"remaining":1})
        if request.method == "DELETE":
            return httpx.Response(204)
        if request.url.path.endswith("/step"):
            steps.append(request)
            if committed:
                run.update(version=2,cursor=1,state="COMPLETED",actual_backend="cuda")
            raise httpx.ReadTimeout("lost reply", request=request)
        return httpx.Response(200,json=run)

    client = httpx.Client
    monkeypatch.setattr(worker.httpx,"Client",
                        lambda **kwargs: client(transport=httpx.MockTransport(handle), **kwargs))
    args = (8000,"fixture",str(uuid.uuid4()),1,30)
    if committed:
        result = worker.advance_run(*args)
        assert result["state"] == "COMPLETED"
        assert result["committed_batches"] == 1
    else:
        with pytest.raises(httpx.ReadTimeout,match="lost reply"):
            worker.advance_run(*args)
    assert len(steps) == 1
