"""quiz sets belong to a subject

Subject-wide quizzes (Quiz tab, question bank) have no topic, so without this
column they could not be tied to an owner or counted in the quiz average.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-25 12:30:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('quiz_sets', sa.Column('subject_id', sa.Uuid(as_uuid=False), nullable=True))
    op.create_index('ix_quiz_sets_subject_id', 'quiz_sets', ['subject_id'])
    if op.get_bind().dialect.name != 'sqlite':
        # SQLite can't add a constraint to an existing table; the app deletes these rows itself.
        op.create_foreign_key('fk_quiz_sets_subject_id', 'quiz_sets', 'subjects', ['subject_id'], ['id'], ondelete='CASCADE')

    # Backfill from the topic each existing quiz set belongs to.
    op.execute(
        "UPDATE quiz_sets SET subject_id = "
        "(SELECT topics.subject_id FROM topics WHERE topics.id = quiz_sets.topic_id) "
        "WHERE topic_id IS NOT NULL"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != 'sqlite':
        op.drop_constraint('fk_quiz_sets_subject_id', 'quiz_sets', type_='foreignkey')
    op.drop_index('ix_quiz_sets_subject_id', table_name='quiz_sets')
    with op.batch_alter_table('quiz_sets') as batch_op:
        batch_op.drop_column('subject_id')
