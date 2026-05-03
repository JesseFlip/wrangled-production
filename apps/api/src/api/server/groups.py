"""Device group store and CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.server.auth import AuthChecker, build_rest_auth_dep

# ── Models ───────────────────────────────────────────────────────────


class DeviceGroup(BaseModel):
    name: str
    macs: list[str]


class CreateGroupBody(BaseModel):
    name: str
    macs: list[str] = []


# ── Store ────────────────────────────────────────────────────────────


class DeviceGroupStore:
    """In-memory device group storage."""

    def __init__(self) -> None:
        self._groups: dict[str, list[str]] = {}

    def list_groups(self) -> list[DeviceGroup]:
        groups = [DeviceGroup(name="all", macs=[])]
        groups.extend(
            DeviceGroup(name=name, macs=macs) for name, macs in self._groups.items()
        )
        return groups

    def get_group(self, name: str) -> DeviceGroup | None:
        if name == "all":
            return DeviceGroup(name="all", macs=[])
        macs = self._groups.get(name)
        if macs is None:
            return None
        return DeviceGroup(name=name, macs=macs)

    def create_group(self, name: str, macs: list[str]) -> DeviceGroup:
        self._groups[name] = list(macs)
        return DeviceGroup(name=name, macs=macs)

    def delete_group(self, name: str) -> bool:
        if name == "all":
            return False
        return self._groups.pop(name, None) is not None


# ── Router ───────────────────────────────────────────────────────────


def build_groups_router(groups: DeviceGroupStore, auth: AuthChecker) -> APIRouter:
    dep = build_rest_auth_dep(auth)
    router = APIRouter(prefix="/api", dependencies=[Depends(dep)])

    @router.get("/groups")
    def list_groups() -> dict:
        return {"groups": [g.model_dump() for g in groups.list_groups()]}

    @router.post("/groups")
    def create_group(body: CreateGroupBody) -> dict:
        group = groups.create_group(body.name, body.macs)
        return group.model_dump()

    @router.delete("/groups/{name}")
    def delete_group(name: str) -> dict:
        if name == "all":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cannot delete the 'all' group",
            )
        if not groups.delete_group(name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"group '{name}' not found",
            )
        return {"ok": True}

    return router
