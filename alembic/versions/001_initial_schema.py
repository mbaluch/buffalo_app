"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-08-06
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jzd",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("registration_number", sa.String(50), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.Text()),
        sa.Column("city", sa.String(100)),
        sa.Column("postal_code", sa.String(20)),
        sa.Column("country", sa.String(2), nullable=False, server_default="CZ"),
        sa.Column("latitude", sa.Numeric(10, 8)),
        sa.Column("longitude", sa.Numeric(11, 8)),
        sa.Column("contact_phone", sa.String(50)),
        sa.Column("contact_email", sa.String(255)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "jzd_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("jzd_id", sa.Integer(), sa.ForeignKey("jzd.id"), nullable=False, unique=True),
        sa.Column("gestation_days", sa.Integer(), nullable=False, server_default="283"),
        sa.Column("recovery_days", sa.Integer(), nullable=False, server_default="60"),
    )

    op.create_table(
        "app_user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("jzd_id", sa.Integer(), sa.ForeignKey("jzd.id")),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100)),
        sa.Column("last_name", sa.String(100)),
        sa.Column("phone", sa.String(50)),
        sa.Column(
            "role",
            sa.Enum(
                "SUPER_ADMIN", "JZD_ADMIN", "FARM_OWNER",
                "SPERM_COLLECTOR", "INSEMINATOR", "VETERINARIAN",
                name="userrole",
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_login", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_user_jzd", "app_user", ["jzd_id"])
    op.create_index("idx_user_role", "app_user", ["role"])

    op.create_table(
        "refresh_token",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("token_hash", sa.String(255), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "farm",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("jzd_id", sa.Integer(), sa.ForeignKey("jzd.id"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("app_user.id")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("registration_number", sa.String(50)),
        sa.Column("address", sa.Text()),
        sa.Column("city", sa.String(100)),
        sa.Column("postal_code", sa.String(20)),
        sa.Column("latitude", sa.Numeric(10, 8), nullable=False),
        sa.Column("longitude", sa.Numeric(11, 8), nullable=False),
        sa.Column("contact_phone", sa.String(50)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_farm_jzd", "farm", ["jzd_id"])
    op.create_index("idx_farm_owner", "farm", ["owner_id"])
    op.create_index("idx_farm_location", "farm", ["latitude", "longitude"])


def downgrade() -> None:
    op.drop_table("farm")
    op.drop_table("refresh_token")
    op.drop_index("idx_user_role", "app_user")
    op.drop_index("idx_user_jzd", "app_user")
    op.drop_table("app_user")
    op.execute("DROP TYPE userrole")
    op.drop_table("jzd_settings")
    op.drop_table("jzd")
