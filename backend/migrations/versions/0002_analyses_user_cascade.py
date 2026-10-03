"""Ensure analysis records cascade with their owner on legacy SQLite databases."""
from alembic import op
from sqlalchemy import inspect

revision='0002_analyses_user_cascade'
down_revision='0001_complete_schema'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind()
    foreign_keys=inspect(bind).get_foreign_keys('analyses')
    user_fk=next((fk for fk in foreign_keys if fk['referred_table']=='users'),None)
    if user_fk and (user_fk.get('options') or {}).get('ondelete','').upper()!='CASCADE':
        convention={'fk':'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s'}
        name=user_fk.get('name') or 'fk_analyses_user_id_users'
        with op.batch_alter_table('analyses',recreate='always',naming_convention=convention) as batch:
            batch.drop_constraint(name,type_='foreignkey')
            batch.create_foreign_key('fk_analyses_user_id_users','users',['user_id'],['id'],ondelete='CASCADE')

def downgrade():
    pass
