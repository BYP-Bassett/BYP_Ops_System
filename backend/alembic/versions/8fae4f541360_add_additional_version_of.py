"""add additional_version_of

Revision ID: 8fae4f541360
Revises: a213a7221254
Create Date: 2025-12-30 10:51:28.706667

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8fae4f541360"
down_revision: Union[str, Sequence[str], None] = "a213a7221254"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Only add the new linkage column for additional versions.
    op.add_column("sp_master", sa.Column("additional_version_of", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sp_master", "additional_version_of")
