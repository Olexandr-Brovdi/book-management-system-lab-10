"""Alembic supports the configured CLI URL or an injected test connection."""

from alembic import context
from sqlalchemy import engine_from_config, pool
from book_catalog.persistence.models import Base

config = context.config
target_metadata = Base.metadata


def migrate(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    supplied = config.attributes.get("connection")
    if supplied is not None:
        migrate(supplied)
    else:
        engine = engine_from_config(
            config.get_section(config.config_ini_section),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
        with engine.connect() as connection:
            migrate(connection)
        engine.dispose()
