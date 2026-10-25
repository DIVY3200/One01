"""baseline schema: every table as of the first migration

Revision ID: 0001
Revises: 
Create Date: 2026-10-25 12:12:10.893553
"""
from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def _missing(table: str) -> bool:
    if op.get_context().as_sql:  # `alembic upgrade --sql`: no database to inspect, emit everything
        return True
    return not sa.inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    # Only create tables that are missing, so databases created before
    # migrations existed (via create_all) are adopted with their data intact.
    if _missing('users'):
        op.create_table('users',
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('onboarding_completed', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
        )

    if _missing('subjects'):
        op.create_table('subjects',
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('purpose', sa.String(length=50), nullable=True),
        sa.Column('level', sa.String(length=50), nullable=True),
        sa.Column('outline', sa.JSON(), nullable=True),
        sa.Column('current_topic_index', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )

    if _missing('user_preferences'):
        op.create_table('user_preferences',
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('nickname', sa.String(length=100), nullable=True),
        sa.Column('ai_teacher_name', sa.String(length=100), nullable=True),
        sa.Column('ai_gender', sa.String(length=20), nullable=True),
        sa.Column('teaching_style', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )

    if _missing('feedback'):
        op.create_table('feedback',
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('subject_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('categories', sa.JSON(), nullable=True),
        sa.Column('ai_response', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )

    if _missing('progress'):
        op.create_table('progress',
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('subject_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('total_topics', sa.Integer(), nullable=True),
        sa.Column('completed_topics', sa.Integer(), nullable=True),
        sa.Column('avg_quiz_score', sa.Float(), nullable=True),
        sa.Column('weak_concepts', sa.JSON(), nullable=True),
        sa.Column('strong_concepts', sa.JSON(), nullable=True),
        sa.Column('time_spent_minutes', sa.Integer(), nullable=True),
        sa.Column('last_activity', sa.TIMESTAMP(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )

    if _missing('topics'):
        op.create_table('topics',
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('subject_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('index_order', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=True),
        sa.Column('current_subtopic_index', sa.Integer(), nullable=True),
        sa.Column('explanation_content', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )

    if _missing('documents'):
        op.create_table('documents',
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('subject_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('topic_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('source_type', sa.String(length=20), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('num_pages', sa.Integer(), nullable=True),
        sa.Column('num_chunks', sa.Integer(), nullable=True),
        sa.Column('embedding_model', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_documents_subject_id', 'documents', ['subject_id'])

    if _missing('messages'):
        op.create_table('messages',
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('topic_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('agent_type', sa.String(length=50), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )

    if _missing('notes'):
        op.create_table('notes',
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('subject_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('topic_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('is_user_edited', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )

    if _missing('quiz_sets'):
        op.create_table('quiz_sets',
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('topic_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('quiz_type', sa.String(length=30), nullable=False),
        sa.Column('questions', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )

    if _missing('weak_points'):
        op.create_table('weak_points',
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('subject_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('topic_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )

    if _missing('document_chunks'):
        op.create_table('document_chunks',
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('document_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('subject_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('page', sa.Integer(), nullable=True),
        sa.Column('heading', sa.String(length=500), nullable=True),
        sa.Column('embedding', sa.LargeBinary(), nullable=True),
        sa.Column('embedding_model', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_document_chunks_document_id', 'document_chunks', ['document_id'])
        op.create_index('ix_document_chunks_subject_id', 'document_chunks', ['subject_id'])

    if _missing('quiz_attempts'):
        op.create_table('quiz_attempts',
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('quiz_set_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('answers', sa.JSON(), nullable=False),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('wrong_concepts', sa.JSON(), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['quiz_set_id'], ['quiz_sets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )


def downgrade() -> None:
    op.drop_table('quiz_attempts')
    op.drop_index('ix_document_chunks_subject_id', table_name='document_chunks')
    op.drop_index('ix_document_chunks_document_id', table_name='document_chunks')
    op.drop_table('document_chunks')
    op.drop_table('weak_points')
    op.drop_table('quiz_sets')
    op.drop_table('notes')
    op.drop_table('messages')
    op.drop_index('ix_documents_subject_id', table_name='documents')
    op.drop_table('documents')
    op.drop_table('topics')
    op.drop_table('progress')
    op.drop_table('feedback')
    op.drop_table('user_preferences')
    op.drop_table('subjects')
    op.drop_table('users')
