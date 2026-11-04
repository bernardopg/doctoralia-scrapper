"""Run Alembic against the connection supplied by the database initializer."""

from alembic import context

config = context.config
connection = config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Database migrations require an existing connection")

context.configure(connection=connection, transaction_per_migration=True)
with context.begin_transaction():
    context.run_migrations()
