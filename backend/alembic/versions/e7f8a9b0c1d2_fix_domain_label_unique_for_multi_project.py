"""Fix domain label unique constraint for multi-project support.

The partial unique index UNIQUE(label) WHERE state='domain' prevents
creating domain nodes with the same label under different projects.
Changed to UNIQUE(parent_id, label) WHERE state='domain' to allow
each project to have its own 'general', 'backend', etc. domains.

Revision ID: e7f8a9b0c1d2
Revises: c487dd6ecb16
Create Date: 2026-04-11
"""

from alembic import op

# revision identifiers
revision = "e7f8a9b0c1d2"
down_revision = "c487dd6ecb16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old index (label-only)
    op.drop_index("uq_prompt_cluster_domain_label", table_name="prompt_cluster")
    # Create composite index (COALESCE(parent_id,'') + label) for multi-project.
    # COALESCE ensures NULL parent_ids are treated as equal for uniqueness
    # (SQLite treats NULL != NULL in unique indexes).
    op.execute(
        "CREATE UNIQUE INDEX uq_prompt_cluster_domain_label "
        "ON prompt_cluster (COALESCE(parent_id, ''), label) WHERE state = 'domain'"
    )


def downgrade() -> None:
    op.drop_index("uq_prompt_cluster_domain_label", table_name="prompt_cluster")
    op.execute(
        "CREATE UNIQUE INDEX uq_prompt_cluster_domain_label "
        "ON prompt_cluster (label) WHERE state = 'domain'"
    )
