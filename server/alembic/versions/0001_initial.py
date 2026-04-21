"""Initial SQS schema."""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "licenses",
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("license_key", sa.String(length=64), nullable=False),
        sa.Column(
            "tier",
            sa.Enum("FREE", "PRO", "ENTERPRISE", name="licensetier", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "EXPIRED", "REVOKED", name="licensestatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("allowed_features", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_licenses_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_licenses")),
        sa.UniqueConstraint("user_id", name=op.f("uq_licenses_user_id")),
    )
    op.create_index(op.f("ix_licenses_expires_at"), "licenses", ["expires_at"], unique=False)
    op.create_index(op.f("ix_licenses_license_key"), "licenses", ["license_key"], unique=True)

    op.create_table(
        "trades",
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column(
            "side",
            sa.Enum("BUY", "SELL", name="tradeside", native_enum=False),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("pnl", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("strategy", sa.String(length=128), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_trades_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trades")),
    )
    op.create_index(op.f("ix_trades_strategy"), "trades", ["strategy"], unique=False)
    op.create_index(op.f("ix_trades_symbol"), "trades", ["symbol"], unique=False)
    op.create_index(op.f("ix_trades_timestamp"), "trades", ["timestamp"], unique=False)
    op.create_index(op.f("ix_trades_user_id"), "trades", ["user_id"], unique=False)

    op.create_table(
        "signals",
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("strategy", sa.String(length=128), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("timeframe", sa.String(length=32), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_signals_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_signals")),
    )
    op.create_index(op.f("ix_signals_strategy"), "signals", ["strategy"], unique=False)
    op.create_index(op.f("ix_signals_symbol"), "signals", ["symbol"], unique=False)
    op.create_index(op.f("ix_signals_timestamp"), "signals", ["timestamp"], unique=False)
    op.create_index(op.f("ix_signals_user_id"), "signals", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_signals_user_id"), table_name="signals")
    op.drop_index(op.f("ix_signals_timestamp"), table_name="signals")
    op.drop_index(op.f("ix_signals_symbol"), table_name="signals")
    op.drop_index(op.f("ix_signals_strategy"), table_name="signals")
    op.drop_table("signals")

    op.drop_index(op.f("ix_trades_user_id"), table_name="trades")
    op.drop_index(op.f("ix_trades_timestamp"), table_name="trades")
    op.drop_index(op.f("ix_trades_symbol"), table_name="trades")
    op.drop_index(op.f("ix_trades_strategy"), table_name="trades")
    op.drop_table("trades")

    op.drop_index(op.f("ix_licenses_license_key"), table_name="licenses")
    op.drop_index(op.f("ix_licenses_expires_at"), table_name="licenses")
    op.drop_table("licenses")

    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

