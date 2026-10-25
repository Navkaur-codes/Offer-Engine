"""Keeps each session's unit tests isolated from the other sessions' real modules (owned by Main).

Every test folder was written against `app.stubs` for the ports it does not own. After a gate merges the real
modules, `ports` would route those calls to real code that needs a seeded DB, so here each folder's foreign
ports are pinned back to their stubs. Whole-system behaviour is covered by the gate smoke test instead.
Mark a test `@pytest.mark.real_ports` to opt out.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app import ports

DATA_PORTS = {
    "build_profile",
    "assign_policy",
    "uplift_predict",
    "impact_estimate",
    "create_profile_from_answers",
    "realism_compute",
    "experiments_compute",
}

# test folder -> ports that must answer from stubs there
STUBBED_BY_FOLDER: dict[str, set[str]] = {
    # B tests its harness on fixture profiles
    "core": DATA_PORTS,
    # C renders fixture decisions
    "bot": DATA_PORTS | {"decide", "decide_batch", "explain", "get_context", "daily_digest"},
    # Main tests plumbing on fixtures
    "api": DATA_PORTS | {"decide", "decide_batch", "explain", "get_context"},
}


def pytest_configure(config):
    config.addinivalue_line("markers", "real_ports: use the real modules behind every port")


@pytest.fixture(autouse=True)
def _isolate_foreign_ports(request, monkeypatch):
    if request.node.get_closest_marker("real_ports"):
        return
    stubbed = STUBBED_BY_FOLDER.get(Path(str(request.node.fspath)).parent.name, set())
    if not stubbed:
        return
    real_resolve = ports._resolve

    def resolve(name: str):
        if name in stubbed:
            return ports._PORTS[name][2], False
        return real_resolve(name)

    resolve.cache_clear = real_resolve.cache_clear  # some tests reset the port cache
    monkeypatch.setattr(ports, "_resolve", resolve)
