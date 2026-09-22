from collections.abc import Mapping
from typing import Any, ClassVar, Literal
from uuid import UUID

from sqlalchemy.orm import Session

from erp.modules.platform.models import AuditEvent
from erp.modules.platform.repository import AuditEventRepository


class Redactor:
    """Mask secrets and sensitive payroll values in audit details."""

    REDACTED = "[REDACTED]"
    MARKERS: ClassVar[tuple[str, ...]] = (
        "password",
        "secret",
        "token",
        "authorization",
        "salary",
        "bank_account",
        "card_number",
    )

    @classmethod
    def is_sensitive(cls, key: str) -> bool:
        lowered = key.lower()
        return any(marker in lowered for marker in cls.MARKERS)

    @classmethod
    def redact(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                k: cls.REDACTED if cls.is_sensitive(str(k)) else cls.redact(v)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [cls.redact(v) for v in value]
        return value


class AuditTrail:
    """Record audit events inside the caller's transaction.

    Events commit or roll back together with the audited change.
    """

    def __init__(self, session: Session) -> None:
        self._events = AuditEventRepository(session)

    def record(
        self,
        *,
        tenant_id: UUID,
        actor_identity_id: UUID | None,
        action: str,
        target_type: str,
        target_id: str | None,
        outcome: Literal["success", "denied", "failure"],
        reason: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> UUID:
        return self._events.add(
            AuditEvent(
                tenant_id=tenant_id,
                actor_identity_id=actor_identity_id,
                audit_action=action,
                target_type=target_type,
                target_id=target_id,
                audit_outcome=outcome,
                audit_reason=reason,
                audit_details=Redactor.redact(dict(details or {})),
            )
        )
