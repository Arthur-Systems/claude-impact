"""Store the normalized manifest JSON on dataset releases (SPEC section 5).

Revision ID: 0002_release_manifest
Revises: p5_0001_project_tables
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_release_manifest"
down_revision = "p5_0001_project_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dataset_releases", sa.Column("manifest", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("dataset_releases", "manifest")
