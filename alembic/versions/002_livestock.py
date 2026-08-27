"""livestock tables and attribute seed data

Revision ID: 002
Revises: 001
Create Date: 2026-08-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

CATTLE_ATTRIBUTES = [
    {
        "attribute_key": "breed",
        "attribute_name": "Breed",
        "data_type": "ENUM",
        "unit": None,
        "is_searchable": True,
        "is_required": True,
        "display_order": 1,
        "enum_values": '["Holstein","Angus","Jersey","Hereford","Czech Fleckvieh","Simmental","Charolais","Limousin","Aberdeen Angus"]',
        "validation_rules": None,
    },
    {
        "attribute_key": "birth_date",
        "attribute_name": "Birth Date",
        "data_type": "DATE",
        "unit": None,
        "is_searchable": True,
        "is_required": True,
        "display_order": 2,
        "enum_values": None,
        "validation_rules": None,
    },
    {
        "attribute_key": "weight",
        "attribute_name": "Weight",
        "data_type": "DECIMAL",
        "unit": "kg",
        "is_searchable": True,
        "is_required": True,
        "display_order": 3,
        "enum_values": None,
        "validation_rules": '{"min": 0, "max": 2000}',
    },
    {
        "attribute_key": "height",
        "attribute_name": "Height at Withers",
        "data_type": "DECIMAL",
        "unit": "cm",
        "is_searchable": True,
        "is_required": False,
        "display_order": 4,
        "enum_values": None,
        "validation_rules": '{"min": 0, "max": 200}',
    },
    {
        "attribute_key": "leg_length",
        "attribute_name": "Leg Length",
        "data_type": "DECIMAL",
        "unit": "cm",
        "is_searchable": True,
        "is_required": False,
        "display_order": 5,
        "enum_values": None,
        "validation_rules": '{"min": 0, "max": 150}',
    },
    {
        "attribute_key": "coat_color",
        "attribute_name": "Coat Color",
        "data_type": "STRING",
        "unit": None,
        "is_searchable": False,
        "is_required": False,
        "display_order": 6,
        "enum_values": None,
        "validation_rules": None,
    },
    {
        "attribute_key": "genetic_markers",
        "attribute_name": "Genetic Markers",
        "data_type": "STRING",
        "unit": None,
        "is_searchable": True,
        "is_required": False,
        "display_order": 7,
        "enum_values": None,
        "validation_rules": None,
    },
    {
        "attribute_key": "milk_production",
        "attribute_name": "Milk Production",
        "data_type": "DECIMAL",
        "unit": "l/day",
        "is_searchable": True,
        "is_required": False,
        "display_order": 8,
        "enum_values": None,
        "validation_rules": '{"min": 0, "max": 100}',
    },
    {
        "attribute_key": "horn_status",
        "attribute_name": "Horn Status",
        "data_type": "ENUM",
        "unit": None,
        "is_searchable": True,
        "is_required": False,
        "display_order": 9,
        "enum_values": '["HORNED","POLLED","DEHORNED"]',
        "validation_rules": None,
    },
]


def upgrade() -> None:
    # Add next_registration_seq to jzd_settings
    op.add_column("jzd_settings", sa.Column(
        "next_registration_seq", sa.Integer(), nullable=False, server_default="1"
    ))

    op.create_table(
        "livestock_type",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(50), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "attribute_definition",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("livestock_type_id", sa.Integer(), sa.ForeignKey("livestock_type.id"), nullable=False),
        sa.Column("attribute_key", sa.String(100), nullable=False),
        sa.Column("attribute_name", sa.String(255), nullable=False),
        sa.Column(
            "data_type",
            sa.Enum("STRING", "NUMBER", "DECIMAL", "BOOLEAN", "DATE", "ENUM", name="attributedatatype"),
            nullable=False,
        ),
        sa.Column("unit", sa.String(50)),
        sa.Column("is_searchable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("enum_values", sa.JSON()),
        sa.Column("validation_rules", sa.JSON()),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("livestock_type_id", "attribute_key", name="uq_attr_type_key"),
    )
    op.create_index("idx_attr_def_type", "attribute_definition", ["livestock_type_id"])
    op.create_index("idx_attr_def_searchable", "attribute_definition", ["is_searchable"])

    op.create_table(
        "livestock",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("jzd_id", sa.Integer(), sa.ForeignKey("jzd.id"), nullable=False),
        sa.Column("farm_id", sa.Integer(), sa.ForeignKey("farm.id"), nullable=False),
        sa.Column("livestock_type_id", sa.Integer(), sa.ForeignKey("livestock_type.id"), nullable=False),
        sa.Column("registration_number", sa.String(14), unique=True, nullable=False),
        sa.Column("name", sa.String(255)),
        sa.Column(
            "sex",
            sa.Enum("MALE", "FEMALE", name="livestocksex"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "INACTIVE", "DECEASED", "SOLD", name="livestockstatus"),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("attributes", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("is_available_for_breeding", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "pregnancy_status",
            sa.Enum("PREGNANT", "CALVED", name="pregnancystatus"),
        ),
        sa.Column("pregnancy_start_date", sa.Date()),
        sa.Column("expected_calving_date", sa.Date()),
        sa.Column("actual_calving_date", sa.Date()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("app_user.id")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_livestock_jzd", "livestock", ["jzd_id"])
    op.create_index("idx_livestock_farm", "livestock", ["farm_id"])
    op.create_index("idx_livestock_type", "livestock", ["livestock_type_id"])
    op.create_index("idx_livestock_status", "livestock", ["status"])
    op.create_index("idx_livestock_available", "livestock", ["is_available_for_breeding"])
    op.create_index("idx_livestock_pregnancy", "livestock", ["pregnancy_status"])

    op.create_table(
        "livestock_photo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "livestock_id",
            sa.Integer(),
            sa.ForeignKey("livestock.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("thumbnail_data", sa.LargeBinary()),
        sa.Column("mime_type", sa.String(50), nullable=False),
        sa.Column("original_filename", sa.String(255)),
        sa.Column("file_size_bytes", sa.Integer()),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("app_user.id")),
        sa.Column("uploaded_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_photo_livestock", "livestock_photo", ["livestock_id"])

    # Seed livestock types and cattle attributes
    conn = op.get_bind()
    conn.execute(text("INSERT INTO livestock_type (code, name) VALUES ('CATTLE', 'Cattle')"))
    cattle_id = conn.execute(text("SELECT id FROM livestock_type WHERE code = 'CATTLE'")).scalar()

    for attr in CATTLE_ATTRIBUTES:
        conn.execute(
            text("""
                INSERT INTO attribute_definition
                    (livestock_type_id, attribute_key, attribute_name, data_type,
                     unit, is_searchable, is_required, display_order, enum_values, validation_rules)
                VALUES
                    (:lt_id, :key, :name, :dtype,
                     :unit, :searchable, :required, :order,
                     CAST(:enum_vals AS json), CAST(:val_rules AS json))
            """),
            {
                "lt_id": cattle_id,
                "key": attr["attribute_key"],
                "name": attr["attribute_name"],
                "dtype": attr["data_type"],
                "unit": attr["unit"],
                "searchable": attr["is_searchable"],
                "required": attr["is_required"],
                "order": attr["display_order"],
                "enum_vals": attr["enum_values"],
                "val_rules": attr["validation_rules"],
            },
        )


def downgrade() -> None:
    op.drop_table("livestock_photo")
    op.drop_index("idx_livestock_pregnancy", "livestock")
    op.drop_index("idx_livestock_available", "livestock")
    op.drop_index("idx_livestock_status", "livestock")
    op.drop_index("idx_livestock_type", "livestock")
    op.drop_index("idx_livestock_farm", "livestock")
    op.drop_index("idx_livestock_jzd", "livestock")
    op.drop_table("livestock")
    op.execute("DROP TYPE livestocksex")
    op.execute("DROP TYPE livestockstatus")
    op.execute("DROP TYPE pregnancystatus")
    op.drop_index("idx_attr_def_searchable", "attribute_definition")
    op.drop_index("idx_attr_def_type", "attribute_definition")
    op.drop_table("attribute_definition")
    op.execute("DROP TYPE attributedatatype")
    op.drop_table("livestock_type")
    op.drop_column("jzd_settings", "next_registration_seq")
