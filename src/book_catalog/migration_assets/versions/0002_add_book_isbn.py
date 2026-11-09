"""Add optional unique ISBN while retaining existing author and book records."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("books") as batch:
        batch.add_column(sa.Column("isbn", sa.String(32), nullable=True))
        batch.create_unique_constraint("uq_books_isbn", ["isbn"])


def downgrade():
    with op.batch_alter_table("books") as batch:
        batch.drop_constraint("uq_books_isbn", type_="unique")
        batch.drop_column("isbn")
