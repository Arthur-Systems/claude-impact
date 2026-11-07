"""Initial ClearPath schema. Dataset content uses restrictive foreign keys."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table('jurisdictions',
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('state', sa.String(), nullable=False),
    sa.Column('timezone', sa.String(), server_default='America/Los_Angeles', nullable=False),
    sa.Column('permit_page_url', sa.Text(), nullable=True),
    sa.Column('adu_checklist_url', sa.Text(), nullable=True),
    sa.Column('fee_schedule_url', sa.Text(), nullable=True),
    sa.Column('checked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_table('dataset_releases',
    sa.Column('jurisdiction_id', sa.Uuid(), nullable=False),
    sa.Column('project_type', sa.String(), nullable=False),
    sa.Column('profile_key', sa.String(), nullable=False),
    sa.Column('kind', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('schema_version', sa.Integer(), nullable=False),
    sa.Column('content_hash', sa.String(), nullable=False),
    sa.Column('fact_schema', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('conflicts', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('curator_label', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("kind IN ('synthetic','reviewed_public')", name='ck_release_kind'),
    sa.CheckConstraint("project_type IN ('adu','duplex','multifamily','other_housing')", name='ck_release_project_type'),
    sa.CheckConstraint("status IN ('draft','active','retired')", name='ck_release_status'),
    sa.ForeignKeyConstraint(['jurisdiction_id'], ['jurisdictions.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('content_hash')
    )
    op.create_index('uq_active_release_scope', 'dataset_releases', ['jurisdiction_id', 'project_type', 'profile_key', 'kind'], unique=True, postgresql_where=sa.text("status = 'active'"))
    op.create_table('ingestion_runs',
    sa.Column('manifest_path', sa.Text(), nullable=False),
    sa.Column('content_hash', sa.String(), nullable=False),
    sa.Column('command', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('counts', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('error_codes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('release_id', sa.Uuid(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("status IN ('ok','no_op','failed')", name='ck_ingestion_status'),
    sa.ForeignKeyConstraint(['release_id'], ['dataset_releases.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('milestone_templates',
    sa.Column('key', sa.String(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('predecessors', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('requirement_keys', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('published_clock', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('assumed_days', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('release_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['release_id'], ['dataset_releases.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('release_id', 'key')
    )
    op.create_table('pathways',
    sa.Column('key', sa.String(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('applies_if', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('release_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['release_id'], ['dataset_releases.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('release_id', 'key')
    )
    op.create_table('projects',
    sa.Column('project_label', sa.String(), nullable=False),
    sa.Column('project_type', sa.String(), nullable=False),
    sa.Column('subtype', sa.String(), nullable=True),
    sa.Column('jurisdiction_id', sa.Uuid(), nullable=True),
    sa.Column('location', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('proposed_unit_count', sa.Integer(), nullable=True),
    sa.Column('affordability_goal', sa.String(), nullable=False),
    sa.Column('affordable_unit_count_goal', sa.Integer(), nullable=True),
    sa.Column('state', sa.String(), nullable=False),
    sa.Column('release_id', sa.Uuid(), nullable=True),
    sa.Column('pathway_key', sa.String(), nullable=True),
    sa.Column('rule_facts', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('revision', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("(state = 'draft' AND release_id IS NULL AND pathway_key IS NULL) OR (state = 'active' AND release_id IS NOT NULL AND pathway_key IS NOT NULL)", name='ck_project_release_state'),
    sa.CheckConstraint("affordability_goal IN ('affordable_housing','mixed_income','unspecified')", name='ck_project_affordability'),
    sa.CheckConstraint("project_type IN ('adu','duplex','multifamily','other_housing')", name='ck_project_type'),
    sa.CheckConstraint("state IN ('draft','active')", name='ck_project_state'),
    sa.CheckConstraint('affordable_unit_count_goal <= proposed_unit_count', name='ck_project_affordable_limit'),
    sa.CheckConstraint('affordable_unit_count_goal >= 0', name='ck_project_affordable_units'),
    sa.CheckConstraint('char_length(project_label) BETWEEN 1 AND 80', name='ck_project_label_length'),
    sa.CheckConstraint('proposed_unit_count >= 0', name='ck_project_proposed_units'),
    sa.ForeignKeyConstraint(['jurisdiction_id'], ['jurisdictions.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['release_id'], ['dataset_releases.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('requirements',
    sa.Column('key', sa.String(), nullable=False),
    sa.Column('pathway_keys', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('kind', sa.String(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('applies_if', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('required_for_preparation', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('release_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("kind IN ('permit','document','review')", name='ck_requirement_kind'),
    sa.ForeignKeyConstraint(['release_id'], ['dataset_releases.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('release_id', 'key')
    )
    op.create_table('source_snapshots',
    sa.Column('source_key', sa.String(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('publisher', sa.String(), nullable=False),
    sa.Column('authority_type', sa.String(), nullable=False),
    sa.Column('checked_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('sha256', sa.String(), nullable=True),
    sa.Column('verification_depth', sa.String(), nullable=False),
    sa.Column('terms_note', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('release_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("verification_depth IN ('full_text_read','title_only','blocked')", name='ck_snapshot_verification_depth'),
    sa.ForeignKeyConstraint(['release_id'], ['dataset_releases.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('release_id', 'source_key')
    )
    op.create_table('project_events',
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('event_type', sa.String(), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'revision')
    )
    op.create_table('project_milestones',
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('milestone_key', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('not_started','in_progress','completed')", name='ck_project_milestone_status'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('project_id', 'milestone_key')
    )
    op.create_table('project_requirements',
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('requirement_key', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('not_started','in_progress','ready')", name='ck_project_requirement_status'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('project_id', 'requirement_key')
    )
    op.create_table('source_passages',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('manifest_passage_id', sa.Uuid(), nullable=False),
    sa.Column('snapshot_id', sa.Uuid(), nullable=False),
    sa.Column('locator', sa.Text(), nullable=False),
    sa.Column('excerpt', sa.Text(), nullable=False),
    sa.Column('excerpt_hash', sa.String(), nullable=False),
    sa.Column('review_status', sa.String(), nullable=False),
    sa.Column('release_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("review_status IN ('reviewed','needs_review','failed')", name='ck_passage_review_status'),
    sa.ForeignKeyConstraint(['release_id'], ['dataset_releases.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['snapshot_id'], ['source_snapshots.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('release_id', 'manifest_passage_id')
    )
    op.create_table('citation_links',
    sa.Column('owner_type', sa.String(), nullable=False),
    sa.Column('owner_key', sa.String(), nullable=False),
    sa.Column('passage_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('release_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("owner_type IN ('pathway','requirement','milestone')", name='ck_citation_owner_type'),
    sa.ForeignKeyConstraint(['passage_id'], ['source_passages.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['release_id'], ['dataset_releases.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('release_id', 'owner_type', 'owner_key', 'passage_id')
    )



def downgrade() -> None:

    op.drop_table('citation_links')
    op.drop_table('source_passages')
    op.drop_table('project_requirements')
    op.drop_table('project_milestones')
    op.drop_table('project_events')
    op.drop_table('source_snapshots')
    op.drop_table('requirements')
    op.drop_table('projects')
    op.drop_table('pathways')
    op.drop_table('milestone_templates')
    op.drop_table('ingestion_runs')
    op.drop_index('uq_active_release_scope', table_name='dataset_releases', postgresql_where=sa.text("status = 'active'"))
    op.drop_table('dataset_releases')
    op.drop_table('jurisdictions')
