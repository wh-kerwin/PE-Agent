from enum import StrEnum


class CaseType(StrEnum):
    YIELD_DROP = "YIELD_DROP"


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CaseStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class TaskStatus(StrEnum):
    CREATED = "CREATED"
    CONTEXT_LOADING = "CONTEXT_LOADING"
    INVESTIGATING = "INVESTIGATING"
    ANALYZING = "ANALYZING"
    GENERATING_REPORT = "GENERATING_REPORT"
    COMPLETED = "COMPLETED"
    PARTIAL_RESULT = "PARTIAL_RESULT"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"


class ReviewStatus(StrEnum):
    NOT_REVIEWED = "NOT_REVIEWED"
    CONFIRMED = "CONFIRMED"
    CORRECTED = "CORRECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class ArchiveStatus(StrEnum):
    PENDING = "PENDING"
    ARCHIVED = "ARCHIVED"
    FAILED = "FAILED"


class EvidenceKind(StrEnum):
    CASE = "CASE"
    YIELD = "YIELD"
    WAFER = "WAFER"
    TOOL_EVENT = "TOOL_EVENT"
    RECIPE = "RECIPE"
    SPC = "SPC"
    FDC = "FDC"
    HISTORICAL_CASE = "HISTORICAL_CASE"


class EvidenceQuality(StrEnum):
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    CONFLICTING = "CONFLICTING"


class EntityType(StrEnum):
    CASE = "CASE"
    LOT = "LOT"
    WAFER = "WAFER"
    TOOL = "TOOL"
    CHAMBER = "CHAMBER"
    RECIPE = "RECIPE"
    PARAMETER = "PARAMETER"


class ToolStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ToolErrorCode(StrEnum):
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_FOUND = "NOT_FOUND"


class DecisionPrimitive(StrEnum):
    CHOICE = "choice"
    SCORE = "score"
    NOUL = "noul"
