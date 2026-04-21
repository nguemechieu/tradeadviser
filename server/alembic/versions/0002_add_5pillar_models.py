"""Add 5-pillar institutional dashboard models.

Adds models for:
- User roles and permissions
- Enhanced license system with audit tracking
- Agent deployment and monitoring
- Audit logging for compliance
- Risk limit management
- System health monitoring
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_add_5pillar_models"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add UserRole enum column to users table
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.Enum(
                "TRADER",
                "RISK_MANAGER",
                "OPERATIONS",
                "ADMIN",
                "SUPER_ADMIN",
                name="userrole",
                native_enum=False,
            ),
            server_default="TRADER",
            nullable=False,
        ),
    )
    op.add_column("users", sa.Column("display_name", sa.String(length=128), nullable=True))

    # 2. Create LicenseAudit table
    op.create_table(
        "license_audits",
        sa.Column("license_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("old_status", sa.String(length=64), nullable=True),
        sa.Column("new_status", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["license_id"],
            ["licenses.id"],
            name=op.f("fk_license_audits_license_id_licenses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_license_audits")),
    )
    op.create_index(
        op.f("ix_license_audits_license_id"),
        "license_audits",
        ["license_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_license_audits_created_at"),
        "license_audits",
        ["created_at"],
        unique=False,
    )

    # 3. Create Agent table
    op.create_table(
        "agents",
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "model_type",
            sa.Enum("ML", "RULES", "HYBRID", "LLM", name="modeltype", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "CREATED",
                "DEPLOYING",
                "RUNNING",
                "PAUSED",
                "FAILED",
                "STOPPED",
                name="agentstatus",
                native_enum=False,
            ),
            server_default="CREATED",
            nullable=False,
        ),
        sa.Column("config", postgresql.JSON(), nullable=True),
        sa.Column("cumulative_pnl", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("total_return", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("win_rate", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("sharpe_ratio", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("trades_count", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_agents_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agents")),
    )
    op.create_index(op.f("ix_agents_user_id"), "agents", ["user_id"], unique=False)
    op.create_index(op.f("ix_agents_status"), "agents", ["status"], unique=False)
    op.create_index(op.f("ix_agents_created_at"), "agents", ["created_at"], unique=False)

    # 4. Create AgentAudit table
    op.create_table(
        "agent_audits",
        sa.Column("agent_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("old_status", sa.String(length=64), nullable=True),
        sa.Column("new_status", sa.String(length=64), nullable=True),
        sa.Column("details", postgresql.JSON(), nullable=True),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name=op.f("fk_agent_audits_agent_id_agents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_audits")),
    )
    op.create_index(
        op.f("ix_agent_audits_agent_id"),
        "agent_audits",
        ["agent_id"],
        unique=False,
    )

    # 5. Create AuditLog table
    op.create_table(
        "audit_logs",
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("details", postgresql.JSON(), nullable=True),
        sa.Column("metadata", postgresql.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("impact", sa.String(length=64), nullable=True),
        sa.Column("result", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False)

    # 6. Create RiskLimit table
    op.create_table(
        "risk_limits",
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("daily_loss_limit", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("portfolio_limit", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("position_limit", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("max_leverage", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("trading_start", sa.Time(), nullable=True),
        sa.Column("trading_end", sa.Time(), nullable=True),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_risk_limits_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_limits")),
        sa.UniqueConstraint("user_id", name=op.f("uq_risk_limits_user_id")),
    )

    # 7. Create RiskBreach table
    op.create_table(
        "risk_breaches",
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("breach_type", sa.String(length=64), nullable=False),
        sa.Column("current_value", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("limit_value", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("action_taken", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_risk_breaches_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_breaches")),
    )
    op.create_index(
        op.f("ix_risk_breaches_user_id"),
        "risk_breaches",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_risk_breaches_created_at"),
        "risk_breaches",
        ["created_at"],
        unique=False,
    )

    # 8. Create SystemHealth table
    op.create_table(
        "system_health",
        sa.Column("database_status", sa.String(length=64), nullable=True),
        sa.Column("database_response_ms", sa.Integer(), nullable=True),
        sa.Column("api_status", sa.String(length=64), nullable=True),
        sa.Column("api_response_ms", sa.Integer(), nullable=True),
        sa.Column("websocket_status", sa.String(length=64), nullable=True),
        sa.Column("websocket_connections", sa.Integer(), nullable=True),
        sa.Column("broker_details", postgresql.JSON(), nullable=True),
        sa.Column("cache_status", sa.String(length=64), nullable=True),
        sa.Column("queue_status", sa.String(length=64), nullable=True),
        sa.Column("cpu_percent", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("memory_percent", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("disk_percent", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("connected_clients", sa.Integer(), nullable=True),
        sa.Column("active_connections", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_system_health")),
    )
    op.create_index(
        op.f("ix_system_health_created_at"),
        "system_health",
        ["created_at"],
        unique=False,
    )

    # 9. Create TradeStats table
    op.create_table(
        "trade_stats",
        sa.Column("period", sa.String(length=64), nullable=False),
        sa.Column("total_trades", sa.Integer(), nullable=True),
        sa.Column("total_platform_pnl", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("average_win_rate", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("active_agents", sa.Integer(), nullable=True),
        sa.Column("active_users", sa.Integer(), nullable=True),
        sa.Column("total_volume", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trade_stats")),
    )
    op.create_index(
        op.f("ix_trade_stats_period"),
        "trade_stats",
        ["period"],
        unique=False,
    )

    # 10. Create PerformanceSnapshot table
    op.create_table(
        "performance_snapshots",
        sa.Column("platform_pnl", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("average_return", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("sharpe_ratio", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("win_count", sa.Integer(), nullable=True),
        sa.Column("metrics", postgresql.JSON(), nullable=True),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_performance_snapshots")),
    )
    op.create_index(
        op.f("ix_performance_snapshots_created_at"),
        "performance_snapshots",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("performance_snapshots")
    op.drop_table("trade_stats")
    op.drop_table("system_health")
    op.drop_table("risk_breaches")
    op.drop_table("risk_limits")
    op.drop_table("audit_logs")
    op.drop_table("agent_audits")
    op.drop_table("agents")
    op.drop_table("license_audits")
    
    # Drop new columns from users table
    op.drop_column("users", "role")
    op.drop_column("users", "display_name")
