from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from inspect import isawaitable
from typing import cast

from fastapi import Header, HTTPException, Request


@dataclass(frozen=True)
class Identity:
    tenant_id: str
    user_id: str
    permissions: frozenset[str]
    authorized_entity_ids: frozenset[str]
    permission_scope_hash: str

    def can(self, permission: str) -> bool:
        return permission in self.permissions or "admin" in self.permissions


async def get_identity(
    request: Request,
    x_pe_tenant: str | None = Header(default=None),
    x_pe_user: str | None = Header(default=None),
    x_pe_permissions: str | None = Header(default=None),
    x_pe_entities: str | None = Header(default=None),
) -> Identity:
    provider = request.app.state.identity_provider
    if provider is not None:
        supplied = provider()
        if isawaitable(supplied):
            supplied = await supplied
        return normalize_identity(cast(Identity, supplied))
    if request.app.state.settings.environment == "production":
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTHENTICATION_REQUIRED"},
        )

    tenant_id = x_pe_tenant or "synthetic-tenant"
    user_id = x_pe_user or "synthetic-engineer"
    default_permissions = (
        "case.read,yield.read,equipment.read,recipe.read,spc.read,fdc.read,"
        "casebook.read,case.analysis.review,casebook.write"
    )
    permissions = frozenset(
        permission.strip()
        for permission in (x_pe_permissions or default_permissions).split(",")
        if permission.strip()
    )
    if x_pe_entities is None:
        authorized_entity_ids = request.app.state.development_authorized_entity_ids
    else:
        authorized_entity_ids = frozenset(
            entity_id.strip()
            for entity_id in x_pe_entities.split(",")
            if entity_id.strip()
        )
    return normalize_identity(
        Identity(
            tenant_id=tenant_id,
            user_id=user_id,
            permissions=permissions,
            authorized_entity_ids=authorized_entity_ids,
            permission_scope_hash="",
        )
    )


def normalize_identity(identity: Identity) -> Identity:
    scope_value = ":".join(
        (
            identity.tenant_id,
            identity.user_id,
            ",".join(sorted(identity.permissions)),
            ",".join(sorted(identity.authorized_entity_ids)),
        )
    )
    return Identity(
        tenant_id=identity.tenant_id,
        user_id=identity.user_id,
        permissions=identity.permissions,
        authorized_entity_ids=identity.authorized_entity_ids,
        permission_scope_hash=sha256(scope_value.encode()).hexdigest(),
    )


async def refresh_identity(request: Request, expected: Identity) -> Identity | None:
    provider = request.app.state.identity_provider
    if provider is None:
        return expected
    supplied = provider()
    if isawaitable(supplied):
        supplied = await supplied
    current = normalize_identity(cast(Identity, supplied))
    if (
        current.tenant_id != expected.tenant_id
        or current.user_id != expected.user_id
        or current.permission_scope_hash != expected.permission_scope_hash
    ):
        return None
    return current


def require_permission(identity: Identity, permission: str) -> None:
    if not identity.can(permission):
        raise HTTPException(
            status_code=403,
            detail={"code": "PERMISSION_DENIED", "permission": permission},
        )


def require_entity(identity: Identity, entity_id: str) -> None:
    if entity_id not in identity.authorized_entity_ids:
        raise HTTPException(
            status_code=403,
            detail={"code": "CASE_ACCESS_DENIED"},
        )
