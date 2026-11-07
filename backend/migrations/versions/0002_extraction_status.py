"""Separate extraction progress from curator review without discarding legacy snapshots."""

from alembic import op

revision = "0002_extraction_status"
down_revision = "0001_dataset_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_snapshot_extraction", "source_snapshots", type_="check")
    op.execute(
        "UPDATE source_snapshots SET extraction_status='parsed' WHERE extraction_status='succeeded'"
    )
    op.create_check_constraint(
        "ck_snapshot_extraction",
        "source_snapshots",
        "extraction_status IN ('pending','parsed','needs_review','failed')",
    )


def downgrade():
    op.drop_constraint("ck_snapshot_extraction", "source_snapshots", type_="check")
    # Historical 0001 cannot represent needs_review.
    # Mapping to pending conservatively requires extraction again.
    op.execute(
        "UPDATE source_snapshots SET extraction_status=CASE "
        "WHEN extraction_status='parsed' THEN 'succeeded' "
        "WHEN extraction_status='needs_review' THEN 'pending' ELSE extraction_status END"
    )
    op.create_check_constraint(
        "ck_snapshot_extraction",
        "source_snapshots",
        "extraction_status IN ('pending','succeeded','failed')",
    )
