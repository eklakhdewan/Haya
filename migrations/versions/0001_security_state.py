"""Create persistent device security tables.

Revision ID: 0001_security_state
Revises:
Create Date: 2026-10-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_security_state"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "security_devices",
        sa.Column("device_id", sa.String(length=255), primary_key=True),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_security_devices_user_id", "security_devices", ["user_id"])

    op.create_table(
        "security_pending_confirmations",
        sa.Column("intent_id", sa.String(length=255), primary_key=True),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("device_id", sa.String(length=255), nullable=False),
        sa.Column("intent_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_security_pending_confirmations_user_id",
        "security_pending_confirmations",
        ["user_id"],
    )
    op.create_index(
        "ix_security_pending_confirmations_device_id",
        "security_pending_confirmations",
        ["device_id"],
    )
    op.create_index(
        "ix_security_pending_confirmations_expires_at",
        "security_pending_confirmations",
        ["expires_at"],
    )

    op.create_table(
        "security_used_nonces",
        sa.Column("nonce", sa.String(length=512), primary_key=True),
        sa.Column("intent_id", sa.String(length=255), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_security_used_nonces_intent_id", "security_used_nonces", ["intent_id"])
    op.create_index("ix_security_used_nonces_used_at", "security_used_nonces", ["used_at"])

    op.create_table(
        "security_completed_intents",
        sa.Column("intent_id", sa.String(length=255), primary_key=True),
        sa.Column("device_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_security_completed_intents_device_id",
        "security_completed_intents",
        ["device_id"],
    )
    op.create_index(
        "ix_security_completed_intents_user_id",
        "security_completed_intents",
        ["user_id"],
    )

    op.create_table(
        "security_action_audit",
        sa.Column("action_id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("device_id", sa.String(length=255), nullable=False),
        sa.Column("intent_type", sa.String(length=64), nullable=False),
        sa.Column("risk", sa.String(length=16), nullable=False),
        sa.Column("confirmation", sa.String(length=32), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.String(length=64), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
    )
    op.create_index("ix_security_action_audit_user_id", "security_action_audit", ["user_id"])
    op.create_index("ix_security_action_audit_device_id", "security_action_audit", ["device_id"])
    op.create_index(
        "ix_security_audit_user_device_requested",
        "security_action_audit",
        ["user_id", "device_id", "requested_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_security_audit_user_device_requested", table_name="security_action_audit")
    op.drop_index("ix_security_action_audit_device_id", table_name="security_action_audit")
    op.drop_index("ix_security_action_audit_user_id", table_name="security_action_audit")
    op.drop_table("security_action_audit")

    op.drop_index("ix_security_completed_intents_user_id", table_name="security_completed_intents")
    op.drop_index(
        "ix_security_completed_intents_device_id", table_name="security_completed_intents"
    )
    op.drop_table("security_completed_intents")

    op.drop_index("ix_security_used_nonces_used_at", table_name="security_used_nonces")
    op.drop_index("ix_security_used_nonces_intent_id", table_name="security_used_nonces")
    op.drop_table("security_used_nonces")

    op.drop_index(
        "ix_security_pending_confirmations_expires_at", table_name="security_pending_confirmations"
    )
    op.drop_index(
        "ix_security_pending_confirmations_device_id", table_name="security_pending_confirmations"
    )
    op.drop_index(
        "ix_security_pending_confirmations_user_id", table_name="security_pending_confirmations"
    )
    op.drop_table("security_pending_confirmations")

    op.drop_index("ix_security_devices_user_id", table_name="security_devices")
    op.drop_table("security_devices")
