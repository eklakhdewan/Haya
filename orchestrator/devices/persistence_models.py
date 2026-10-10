"""SQLAlchemy tables for durable device authorization and replay protection."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class SecurityBase(DeclarativeBase):
    """Declarative base for security persistence tables."""


class DeviceRecord(SecurityBase):
    """Canonical device ownership and revocation state."""

    __tablename__ = "security_devices"

    device_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PendingConfirmationRecord(SecurityBase):
    """Short-lived approval challenge; only a token digest is persisted."""

    __tablename__ = "security_pending_confirmations"

    intent_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    intent_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UsedNonceRecord(SecurityBase):
    """Nonce ledger with a primary-key constraint to prevent cross-worker replay."""

    __tablename__ = "security_used_nonces"

    nonce: Mapped[str] = mapped_column(String(512), primary_key=True)
    intent_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class CompletedIntentRecord(SecurityBase):
    """Durable idempotency ledger for completed intent identifiers."""

    __tablename__ = "security_completed_intents"

    intent_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ActionAuditRecordModel(SecurityBase):
    """Append-oriented audit event storage."""

    __tablename__ = "security_action_audit"

    action_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    intent_type: Mapped[str] = mapped_column(String(64), nullable=False)
    risk: Mapped[str] = mapped_column(String(16), nullable=False)
    confirmation: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


Index(
    "ix_security_audit_user_device_requested",
    ActionAuditRecordModel.user_id,
    ActionAuditRecordModel.device_id,
    ActionAuditRecordModel.requested_at,
)
