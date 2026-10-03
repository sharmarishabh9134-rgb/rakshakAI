"""Create any model tables missing from databases already at the prior head.

This is a non-destructive repair for databases whose Alembic version was
advanced while their physical schema was incomplete. Table definitions come
from the application's SQLAlchemy metadata so this migration does not duplicate
or invent the model schema.
"""
from alembic import op
from app.models import Base


revision = '0004_repair_missing_model_tables'
down_revision = '0003_official_videos'
branch_labels = None
depends_on = None


def upgrade():
    # SQLAlchemy creates only absent tables, in foreign-key dependency order.
    # Existing tables and their rows are left untouched.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    # Keep this repair irreversible: dropping tables could destroy production data.
    pass
