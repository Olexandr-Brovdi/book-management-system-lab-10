"""Create the original author/book schema without ISBN."""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "authors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.UniqueConstraint("name", name="uq_authors_name"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_authors_name"),
    )
    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=False),
        sa.Column(
            "author_id",
            sa.Integer(),
            sa.ForeignKey("authors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_books_title"),
        sa.CheckConstraint(
            "typeof(year) = 'integer' AND year BETWEEN 1 AND 9999", name="ck_books_year"
        ),
        sa.CheckConstraint(
            "typeof(pages) = 'integer' AND pages > 0", name="ck_books_pages"
        ),
    )
    op.create_index("ix_books_author_id", "books", ["author_id"])


def downgrade():
    op.drop_index("ix_books_author_id", table_name="books")
    op.drop_table("books")
    op.drop_table("authors")
