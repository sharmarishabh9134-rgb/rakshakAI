"""Add configurable official education video catalog."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision='0003_official_videos'
down_revision='0002_analyses_user_cascade'
branch_labels=None
depends_on=None

def upgrade():
    # The initial baseline builds every table from the current model metadata.
    # Keep this historical incremental revision safe for fresh databases too.
    if 'official_videos' in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        'official_videos',
        sa.Column('id',sa.String(length=36),nullable=False),
        sa.Column('title',sa.String(length=180),nullable=False),
        sa.Column('description',sa.String(length=800),nullable=False),
        sa.Column('youtube_url',sa.String(length=500),nullable=False),
        sa.Column('thumbnail',sa.String(length=500),nullable=True),
        sa.Column('language',sa.String(length=24),nullable=False),
        sa.Column('authority',sa.String(length=160),nullable=False),
        sa.Column('topic',sa.String(length=64),nullable=False),
        sa.Column('is_official',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('active',sa.Boolean(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('youtube_url'),
    )

def downgrade():
    op.drop_table('official_videos')
