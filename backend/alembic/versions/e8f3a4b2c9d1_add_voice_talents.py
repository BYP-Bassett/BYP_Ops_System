"""Add voice_talents table and orders.voice_talent

Revision ID: e8f3a4b2c9d1
Revises: c7a9f0e2b1d4
Create Date: 2026-02-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e8f3a4b2c9d1"
down_revision: Union[str, Sequence[str], None] = "c7a9f0e2b1d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Create voice_talents table
    op.create_table(
        "voice_talents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_label", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("section", sa.String(), nullable=False),  # 'IN_HOUSE' or 'OUTSIDE'
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
    )
    op.create_index("ix_voice_talents_section", "voice_talents", ["section"])
    op.create_index("ix_voice_talents_sort_order", "voice_talents", ["sort_order"])

    # 2) Add orders.voice_talent column
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("voice_talent", sa.String(), nullable=True))

    # 3) Seed initial voice talent list (idempotent)
    connection = op.get_bind()
    
    # Check if already seeded
    result = connection.execute(sa.text("SELECT COUNT(*) FROM voice_talents")).scalar()
    if result == 0:
        # IN HOUSE TALENT section
        voices_in_house = [
            # Section label first
            ("IN HOUSE TALENT", True, "IN_HOUSE", 1000),
            # Voices in original order
            ("Brian Nickles", False, "IN_HOUSE", 1001),
            ("John Joiner", False, "IN_HOUSE", 1002),
            ("Jon Shults", False, "IN_HOUSE", 1003),
            ("Kato Sample", False, "IN_HOUSE", 1004),
            ("Matt Kelley", False, "IN_HOUSE", 1005),
            ("TBD by producer", False, "IN_HOUSE", 1006),
            ("NO VOICE", False, "IN_HOUSE", 1007),
        ]
        
        # OUTSIDE TALENT section
        voices_outside = [
            # Section label first
            ("OUTSIDE TALENT", True, "OUTSIDE", 2000),
            # Voices in original order
            ("AJ Allen", False, "OUTSIDE", 2001),
            ("Allan Peck", False, "OUTSIDE", 2002),
            ("Allistair Lewis", False, "OUTSIDE", 2003),
            ("Anna Vocino - Female (MK)", False, "OUTSIDE", 2004),
            ("Austin Keyes - ACM Talent", False, "OUTSIDE", 2005),
            ("Bill Lloyd", False, "OUTSIDE", 2006),
            ("Bob Dunsworth", False, "OUTSIDE", 2007),
            ("Brit M-036 Male US Brit", False, "OUTSIDE", 2008),
            ("Brian Roffey", False, "OUTSIDE", 2009),
            ("Cayman Kelly", False, "OUTSIDE", 2010),
            ("Chris Click", False, "OUTSIDE", 2011),
            ("Chris Marsden UK Brit", False, "OUTSIDE", 2012),
            ("Chris Zaharis", False, "OUTSIDE", 2013),
            ("Dan Lee UK Brit", False, "OUTSIDE", 2014),
            ("David Vickery UK Brit", False, "OUTSIDE", 2015),
            ("Donna McKenzie", False, "OUTSIDE", 2016),
            ("Ellie Goodridge - Female Brit US", False, "OUTSIDE", 2017),
            ("Gil Romero", False, "OUTSIDE", 2018),
            ("Greg O'Brien", False, "OUTSIDE", 2019),
            ("Greg Schweitzer", False, "OUTSIDE", 2020),
            ("Issa Lopez Spanish Female", False, "OUTSIDE", 2021),
            ("Jason Rooney - ACM Talent", False, "OUTSIDE", 2022),
            ("Jay Kennedy", False, "OUTSIDE", 2023),
            ("Jeff Berlin", False, "OUTSIDE", 2024),
            ("Jeff Collins", False, "OUTSIDE", 2025),
            ("Jerry Rohira", False, "OUTSIDE", 2026),
            ("John Guidry", False, "OUTSIDE", 2027),
            ("Jon Lovell UK Brit", False, "OUTSIDE", 2028),
            ("Jyll Gartin", False, "OUTSIDE", 2029),
            ("Larrissa Gallagher - Aussie Female", False, "OUTSIDE", 2030),
            ("Masashe Odate (Japanese)", False, "OUTSIDE", 2031),
            ("Michael Santana - Spanish", False, "OUTSIDE", 2032),
            ("Michele Fisher", False, "OUTSIDE", 2033),
            ("Phil Buckman", False, "OUTSIDE", 2034),
            ("Race Taylor - ACM Talent", False, "OUTSIDE", 2035),
            ("Rebecca Riedy", False, "OUTSIDE", 2036),
            ("Ricardo Rivadeneira - Spanish Male", False, "OUTSIDE", 2037),
            ("Rider", False, "OUTSIDE", 2038),
            ("Roger Rose", False, "OUTSIDE", 2039),
            ("Steve Kelly", False, "OUTSIDE", 2040),
            ("Tom Williams - AU Talent", False, "OUTSIDE", 2041),
        ]
        
        # Insert all voices
        for name, is_label, section, sort_order in voices_in_house + voices_outside:
            connection.execute(
                sa.text(
                    "INSERT INTO voice_talents (name, is_label, section, sort_order) "
                    "VALUES (:name, :is_label, :section, :sort_order)"
                ),
                {"name": name, "is_label": is_label, "section": section, "sort_order": sort_order}
            )


def downgrade() -> None:
    # Remove orders.voice_talent column
    with op.batch_alter_table("orders") as batch:
        batch.drop_column("voice_talent")

    # Drop indexes and table
    op.drop_index("ix_voice_talents_sort_order", table_name="voice_talents")
    op.drop_index("ix_voice_talents_section", table_name="voice_talents")
    op.drop_table("voice_talents")
