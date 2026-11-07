"""Explicit PostgreSQL dataset platform schema. No project or semantic search tables."""

from alembic import op

revision = "0001_dataset_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("""
        CREATE TABLE source_snapshots (
            source_key TEXT NOT NULL,
            canonical_url TEXT NOT NULL,
            title TEXT NOT NULL,
            publisher TEXT NOT NULL,
            authority_type TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            fetched_at TIMESTAMP WITH TIME ZONE NOT NULL,
            checked_at TIMESTAMP WITH TIME ZONE NOT NULL,
            effective_from DATE,
            effective_to DATE,
            sha256 VARCHAR(64) NOT NULL,
            local_artifact_key TEXT NOT NULL,
            extraction_status TEXT NOT NULL,
            review_status TEXT NOT NULL,
            id UUID DEFAULT gen_random_uuid() NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_snapshot_source_hash UNIQUE (source_key, sha256),
            CONSTRAINT ck_snapshot_key CHECK (source_key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
            CONSTRAINT ck_snapshot_hash CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_snapshot_extraction CHECK (extraction_status IN
            ('pending','succeeded','failed')),
            CONSTRAINT ck_snapshot_review CHECK (review_status IN
            ('pending','reviewed','rejected')),
            CONSTRAINT ck_snapshot_effective_dates CHECK (effective_to IS NULL OR effective_from
            IS NULL OR effective_to >= effective_from)
        )
    """)
    op.execute("""
        CREATE TABLE jurisdictions (
            slug TEXT NOT NULL,
            name TEXT NOT NULL,
            state VARCHAR(2) NOT NULL,
            timezone TEXT NOT NULL,
            boundary_snapshot_id UUID,
            id UUID DEFAULT gen_random_uuid() NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_jurisdiction_slug UNIQUE (slug),
            CONSTRAINT ck_jurisdiction_slug CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
            FOREIGN KEY(boundary_snapshot_id) REFERENCES source_snapshots (id)
        )
    """)
    op.execute("""
        CREATE TABLE source_passages (
            snapshot_id UUID NOT NULL,
            locator TEXT NOT NULL,
            excerpt TEXT NOT NULL,
            excerpt_hash VARCHAR(64) NOT NULL,
            id UUID DEFAULT gen_random_uuid() NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_passage_content UNIQUE (snapshot_id, locator, excerpt_hash),
            CONSTRAINT ck_passage_hash CHECK (excerpt_hash ~ '^[0-9a-f]{64}$'),
            FOREIGN KEY(snapshot_id) REFERENCES source_snapshots (id)
        )
    """)
    op.execute("CREATE INDEX ix_source_passages_snapshot_id ON source_passages (snapshot_id)")
    op.execute("""
        CREATE TABLE dataset_releases (
            jurisdiction_id UUID NOT NULL,
            project_type TEXT NOT NULL,
            profile_key TEXT NOT NULL,
            fact_schema JSONB NOT NULL,
            content_hash VARCHAR(64) NOT NULL,
            schema_version INTEGER NOT NULL,
            normalized_manifest JSONB NOT NULL,
            status TEXT NOT NULL,
            data_classification TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            published_at TIMESTAMP WITH TIME ZONE,
            curator_label TEXT NOT NULL,
            id UUID DEFAULT gen_random_uuid() NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_release_content UNIQUE (jurisdiction_id, project_type, profile_key,
            content_hash),
            CONSTRAINT ck_release_type CHECK (project_type ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
            CONSTRAINT ck_release_profile CHECK (profile_key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
            CONSTRAINT ck_release_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_release_schema_version CHECK (schema_version > 0),
            CONSTRAINT ck_release_status CHECK (status IN ('draft','active','retired')),
            CONSTRAINT ck_release_classification CHECK (data_classification IN
            ('synthetic','reviewed_public')),
            CONSTRAINT ck_release_fact_schema CHECK (jsonb_typeof(fact_schema) = 'object'),
            CONSTRAINT ck_release_manifest CHECK (jsonb_typeof(normalized_manifest) = 'object'),
            FOREIGN KEY(jurisdiction_id) REFERENCES jurisdictions (id)
        )
    """)
    op.execute(
        "CREATE INDEX ix_dataset_releases_jurisdiction_id ON dataset_releases (jurisdiction_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_release_active_profile "
        "ON dataset_releases (jurisdiction_id, project_type, profile_key) "
        "WHERE status = 'active'"
    )
    op.execute("""
        CREATE TABLE ingestion_runs (
            manifest_hash VARCHAR(64) NOT NULL,
            command_kind TEXT NOT NULL,
            started_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            finished_at TIMESTAMP WITH TIME ZONE,
            status TEXT NOT NULL,
            counts JSONB DEFAULT '{}'::jsonb NOT NULL,
            error_codes TEXT[] DEFAULT '{}'::text[] NOT NULL,
            resulting_release_id UUID,
            id UUID DEFAULT gen_random_uuid() NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT ck_run_hash CHECK (manifest_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_run_status CHECK (status IN ('running','succeeded','failed')),
            CONSTRAINT ck_run_counts CHECK (jsonb_typeof(counts) = 'object'),
            CONSTRAINT ck_run_dates CHECK (finished_at IS NULL OR finished_at >= started_at),
            FOREIGN KEY(resulting_release_id) REFERENCES dataset_releases (id)
        )
    """)
    op.execute("""
        CREATE TABLE pathways (
            release_id UUID NOT NULL,
            key TEXT NOT NULL,
            title TEXT NOT NULL,
            applicability JSONB NOT NULL,
            explanation TEXT NOT NULL,
            id UUID DEFAULT gen_random_uuid() NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_pathway_release_key UNIQUE (release_id, key),
            CONSTRAINT ck_pathway_key CHECK (key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
            CONSTRAINT ck_pathway_predicate CHECK (jsonb_typeof(applicability) = 'object'),
            FOREIGN KEY(release_id) REFERENCES dataset_releases (id)
        )
    """)
    op.execute("CREATE INDEX ix_pathways_release_id ON pathways (release_id)")
    op.execute("""
        CREATE TABLE requirements (
            release_id UUID NOT NULL,
            key TEXT NOT NULL,
            pathway_keys TEXT[] NOT NULL,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            applicability JSONB NOT NULL,
            required_for_preparation BOOLEAN NOT NULL,
            id UUID DEFAULT gen_random_uuid() NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_requirement_release_key UNIQUE (release_id, key),
            CONSTRAINT ck_requirement_key CHECK (key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
            CONSTRAINT ck_requirement_kind CHECK (kind IN ('permit','document','review')),
            CONSTRAINT ck_requirement_predicate CHECK (jsonb_typeof(applicability) = 'object'),
            FOREIGN KEY(release_id) REFERENCES dataset_releases (id)
        )
    """)
    op.execute("CREATE INDEX ix_requirements_release_id ON requirements (release_id)")
    op.execute("""
        CREATE TABLE milestone_templates (
            release_id UUID NOT NULL,
            pathway_key TEXT NOT NULL,
            key TEXT NOT NULL,
            title TEXT NOT NULL,
            predecessor_keys TEXT[] NOT NULL,
            requirement_keys TEXT[] NOT NULL,
            forecast_min_days INTEGER,
            forecast_max_days INTEGER,
            published_clock JSONB,
            id UUID DEFAULT gen_random_uuid() NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_milestone_release_key UNIQUE (release_id, key),
            CONSTRAINT fk_milestone_release_pathway FOREIGN KEY(release_id, pathway_key)
            REFERENCES pathways (release_id, key),
            CONSTRAINT ck_milestone_key CHECK (key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
            CONSTRAINT ck_milestone_forecast CHECK ((forecast_min_days IS NULL AND
            forecast_max_days IS NULL) OR (forecast_min_days IS NOT NULL AND forecast_max_days
            IS NOT NULL AND forecast_min_days >= 0 AND forecast_max_days >= forecast_min_days)),
            CONSTRAINT ck_milestone_clock CHECK (published_clock IS NULL OR
            jsonb_typeof(published_clock) = 'object'),
            FOREIGN KEY(release_id) REFERENCES dataset_releases (id)
        )
    """)
    op.execute("CREATE INDEX ix_milestone_templates_release_id ON milestone_templates (release_id)")
    op.execute("""
        CREATE TABLE pathway_citations (
            pathway_id UUID NOT NULL,
            passage_id UUID NOT NULL,
            PRIMARY KEY (pathway_id, passage_id),
            FOREIGN KEY(pathway_id) REFERENCES pathways (id),
            FOREIGN KEY(passage_id) REFERENCES source_passages (id)
        )
    """)
    op.execute("""
        CREATE TABLE requirement_citations (
            requirement_id UUID NOT NULL,
            passage_id UUID NOT NULL,
            PRIMARY KEY (requirement_id, passage_id),
            FOREIGN KEY(requirement_id) REFERENCES requirements (id),
            FOREIGN KEY(passage_id) REFERENCES source_passages (id)
        )
    """)
    op.execute("""
        CREATE TABLE milestone_citations (
            milestone_id UUID NOT NULL,
            passage_id UUID NOT NULL,
            PRIMARY KEY (milestone_id, passage_id),
            FOREIGN KEY(milestone_id) REFERENCES milestone_templates (id),
            FOREIGN KEY(passage_id) REFERENCES source_passages (id)
        )
    """)


def downgrade():
    op.drop_table("milestone_citations")
    op.drop_table("requirement_citations")
    op.drop_table("pathway_citations")
    op.drop_table("milestone_templates")
    op.drop_table("requirements")
    op.drop_table("pathways")
    op.drop_table("ingestion_runs")
    op.drop_table("dataset_releases")
    op.drop_table("source_passages")
    op.drop_table("jurisdictions")
    op.drop_table("source_snapshots")
    # Retain the extension: other schemas may use it.
