"""appointments, insemination records, health records, breeding match recommendations

Revision ID: 003
Revises: 002
Create Date: 2026-08-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

# Enum types defined once and reused with create_type=False after first table
appointmenttype = postgresql.ENUM("VIEWING", "INSEMINATION", "CHECKUP", name="appointmenttype")
appointmentstatus = postgresql.ENUM("SCHEDULED", "CONFIRMED", "COMPLETED", "CANCELLED", name="appointmentstatus")
inseminationmethod = postgresql.ENUM("ARTIFICIAL", "NATURAL", name="inseminationmethod")
inseminationstatus = postgresql.ENUM("PERFORMED", "CONFIRMED_PREGNANT", "FAILED", "CALVED", name="inseminationstatus")
healthrecordtype = postgresql.ENUM("CHECKUP", "TREATMENT", "VACCINATION", "DIAGNOSIS", "CALVING", name="healthrecordtype")


def upgrade() -> None:
    bind = op.get_bind()
    appointmenttype.create(bind, checkfirst=True)
    appointmentstatus.create(bind, checkfirst=True)
    inseminationmethod.create(bind, checkfirst=True)
    inseminationstatus.create(bind, checkfirst=True)
    healthrecordtype.create(bind, checkfirst=True)

    op.create_table(
        "appointment",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("jzd_id", sa.Integer, sa.ForeignKey("jzd.id"), nullable=False),
        sa.Column("livestock_id", sa.Integer, sa.ForeignKey("livestock.id"), nullable=False),
        sa.Column("appointment_type", postgresql.ENUM("VIEWING", "INSEMINATION", "CHECKUP", name="appointmenttype", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM("SCHEDULED", "CONFIRMED", "COMPLETED", "CANCELLED", name="appointmentstatus", create_type=False), nullable=False, server_default="SCHEDULED"),
        sa.Column("scheduled_date", sa.Date, nullable=False),
        sa.Column("scheduled_time", sa.Time, nullable=False),
        sa.Column("duration_minutes", sa.Integer, server_default="60"),
        sa.Column("requester_id", sa.Integer, sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("assignee_id", sa.Integer, sa.ForeignKey("app_user.id")),
        sa.Column("notes", sa.Text),
        sa.Column("cancellation_reason", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_appointment_jzd", "appointment", ["jzd_id"])
    op.create_index("idx_appointment_livestock", "appointment", ["livestock_id"])
    op.create_index("idx_appointment_date", "appointment", ["scheduled_date"])
    op.create_index("idx_appointment_requester", "appointment", ["requester_id"])
    op.create_index("idx_appointment_assignee", "appointment", ["assignee_id"])

    op.create_table(
        "insemination_record",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("jzd_id", sa.Integer, sa.ForeignKey("jzd.id"), nullable=False),
        sa.Column("cow_id", sa.Integer, sa.ForeignKey("livestock.id"), nullable=False),
        sa.Column("bull_id", sa.Integer, sa.ForeignKey("livestock.id")),
        sa.Column("inseminator_id", sa.Integer, sa.ForeignKey("app_user.id")),
        sa.Column("method", postgresql.ENUM("ARTIFICIAL", "NATURAL", name="inseminationmethod", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM("PERFORMED", "CONFIRMED_PREGNANT", "FAILED", "CALVED", name="inseminationstatus", create_type=False), nullable=False, server_default="PERFORMED"),
        sa.Column("insemination_date", sa.Date, nullable=False),
        sa.Column("expected_calving_date", sa.Date),
        sa.Column("actual_calving_date", sa.Date),
        sa.Column("pregnancy_confirmed_date", sa.Date),
        sa.Column("pregnancy_confirmed_by_id", sa.Integer, sa.ForeignKey("app_user.id")),
        sa.Column("notes", sa.Text),
        sa.Column("calf_id", sa.Integer, sa.ForeignKey("livestock.id")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_insem_cow", "insemination_record", ["cow_id"])
    op.create_index("idx_insem_bull", "insemination_record", ["bull_id"])
    op.create_index("idx_insem_jzd", "insemination_record", ["jzd_id"])
    op.create_index("idx_insem_date", "insemination_record", ["insemination_date"])

    op.create_table(
        "health_record",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("jzd_id", sa.Integer, sa.ForeignKey("jzd.id"), nullable=False),
        sa.Column("livestock_id", sa.Integer, sa.ForeignKey("livestock.id"), nullable=False),
        sa.Column("veterinarian_id", sa.Integer, sa.ForeignKey("app_user.id")),
        sa.Column("record_type", postgresql.ENUM("CHECKUP", "TREATMENT", "VACCINATION", "DIAGNOSIS", "CALVING", name="healthrecordtype", create_type=False), nullable=False),
        sa.Column("record_date", sa.Date, nullable=False),
        sa.Column("diagnosis", sa.String(500)),
        sa.Column("treatment", sa.Text),
        sa.Column("medication", sa.String(500)),
        sa.Column("dosage", sa.String(200)),
        sa.Column("next_checkup_date", sa.Date),
        sa.Column("temperature", sa.Numeric(4, 1)),
        sa.Column("weight_at_record", sa.Numeric(7, 2)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_health_livestock", "health_record", ["livestock_id"])
    op.create_index("idx_health_jzd", "health_record", ["jzd_id"])
    op.create_index("idx_health_date", "health_record", ["record_date"])
    op.create_index("idx_health_vet", "health_record", ["veterinarian_id"])

    op.create_table(
        "breeding_match_recommendation",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("jzd_id", sa.Integer, sa.ForeignKey("jzd.id"), nullable=False),
        sa.Column("cow_id", sa.Integer, sa.ForeignKey("livestock.id"), nullable=False),
        sa.Column("bull_id", sa.Integer, sa.ForeignKey("livestock.id"), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("distance_km", sa.Float),
        sa.Column("score_details", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_breedmatch_cow", "breeding_match_recommendation", ["cow_id"])
    op.create_index("idx_breedmatch_bull", "breeding_match_recommendation", ["bull_id"])
    op.create_index("idx_breedmatch_jzd", "breeding_match_recommendation", ["jzd_id"])


def downgrade() -> None:
    op.drop_table("breeding_match_recommendation")
    op.drop_table("health_record")
    op.drop_table("insemination_record")
    op.drop_table("appointment")
    bind = op.get_bind()
    healthrecordtype.drop(bind, checkfirst=True)
    inseminationstatus.drop(bind, checkfirst=True)
    inseminationmethod.drop(bind, checkfirst=True)
    appointmentstatus.drop(bind, checkfirst=True)
    appointmenttype.drop(bind, checkfirst=True)
