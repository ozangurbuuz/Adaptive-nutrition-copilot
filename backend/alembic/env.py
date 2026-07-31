from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.core.orm import resolve_sqlalchemy_database_url
from app.models.base import Base


target_metadata = Base.metadata


def get_database_url() -> str:
    return resolve_sqlalchemy_database_url(get_settings())


def configure_logging() -> None:
    config = context.config
    if config.config_file_name is not None:
        fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    config = context.config
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


def alembic_context_is_active() -> bool:
    try:
        context.config
    except (AttributeError, NameError):
        return False
    return True


if alembic_context_is_active():
    configure_logging()
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
