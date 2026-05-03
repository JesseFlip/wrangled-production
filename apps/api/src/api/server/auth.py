"""Bearer-token auth dependency."""

from __future__ import annotations

from fastapi import Header, HTTPException, Request, status


class AuthChecker:
    """Validates Authorization: Bearer <token> when a token is configured."""

    def __init__(self, token: str | None) -> None:
        self._token = token

    @property
    def enabled(self) -> bool:
        return self._token is not None

    def check_header(self, authorization: str | None) -> None:
        if not self.enabled:
            return
        if authorization is None or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="bearer token required",
            )
        if authorization.removeprefix("Bearer ") != self._token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid token",
            )

    def check_query_token(self, token: str | None) -> None:
        if not self.enabled:
            return
        if token != self._token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid token",
            )


def build_rest_auth_dep(checker: AuthChecker):  # noqa: ANN201
    """Return a FastAPI dependency that rejects unauthorised REST callers."""

    def _dep(
        request: Request,  # noqa: ARG001
        authorization: str | None = Header(default=None),
    ) -> None:
        checker.check_header(authorization)

    return _dep
