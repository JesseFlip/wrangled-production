"""Tests for bearer-token auth."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.server.auth import AuthChecker, build_rest_auth_dep


def _app_with(checker: AuthChecker) -> TestClient:
    app = FastAPI()
    dep = build_rest_auth_dep(checker)

    @app.get("/guarded", dependencies=[Depends(dep)])
    def guarded() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app)


def test_no_token_configured_allows_anonymous() -> None:
    client = _app_with(AuthChecker(None))
    assert client.get("/guarded").status_code == 200


def test_valid_token_accepted() -> None:
    client = _app_with(AuthChecker("secret"))
    response = client.get("/guarded", headers={"Authorization": "Bearer secret"})
    assert response.status_code == 200


def test_missing_token_rejected() -> None:
    client = _app_with(AuthChecker("secret"))
    assert client.get("/guarded").status_code == 401


def test_wrong_token_rejected() -> None:
    client = _app_with(AuthChecker("secret"))
    response = client.get("/guarded", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


def test_check_query_token() -> None:
    checker = AuthChecker("secret")
    checker.check_query_token("secret")  # does not raise
    with pytest.raises(Exception):  # noqa: B017, PT011
        checker.check_query_token("wrong")
