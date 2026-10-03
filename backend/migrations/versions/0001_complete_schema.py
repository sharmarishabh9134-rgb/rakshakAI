"""Create the complete RAKSHAKAI schema and extend the original demo tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from app.models import Base

revision='0001_complete_schema'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind()
    # Makes this baseline safe for both empty databases and the original SQLite demo DB.
    Base.metadata.create_all(bind=bind,checkfirst=True)
    inspector=inspect(bind)
    for table in ('users','analyses'):
        existing={col['name'] for col in inspector.get_columns(table)}
        if 'updated_at' not in existing:
            op.add_column(table,sa.Column('updated_at',sa.DateTime(timezone=True),nullable=True))
        if 'deleted_at' not in existing:
            op.add_column(table,sa.Column('deleted_at',sa.DateTime(timezone=True),nullable=True))
        bind.execute(text(f'UPDATE {table} SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL'))

def downgrade():
    # The initial migration is the persistent baseline. Avoid dropping user data on downgrade.
    pass
