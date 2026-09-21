from __future__ import annotations

from datetime import datetime

from pydantic import Field

from pe_agent.domain.base import DomainModel, NonEmptyStr
from pe_agent.domain.enums import EntityType, EvidenceKind, EvidenceQuality


class EvidenceSource(DomainModel):
    system: NonEmptyStr
    source_id: NonEmptyStr


class EntityReference(DomainModel):
    type: EntityType
    id: NonEmptyStr


class Evidence(DomainModel):
    evidence_id: NonEmptyStr
    kind: EvidenceKind
    observation: NonEmptyStr
    source: EvidenceSource
    entity_refs: tuple[EntityReference, ...] = Field(min_length=1)
    event_time: datetime
    retrieved_at: datetime
    quality: EvidenceQuality
    raw_ref: NonEmptyStr
    warnings: tuple[NonEmptyStr, ...] = ()
