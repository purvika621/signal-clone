from alembic import context

from app.database import Base, UTCDateTime, engine
from app import models  # noqa: F401 -- register metadata for migrations

target_metadata = Base.metadata

def render_item(type_, item, _autogen_context):
    if type_ == "type" and isinstance(item, UTCDateTime):
        return "sa.DateTime()"
    return False

if context.is_offline_mode():
    context.configure(url=engine.url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True, render_item=render_item)
        with context.begin_transaction():
            context.run_migrations()

