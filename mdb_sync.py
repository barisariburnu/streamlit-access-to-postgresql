"""Separate active and passive records using the full MDB snapshot's IDs."""

from uuid import uuid4

from sqlalchemy import (
    Column, Integer, JSON, MetaData, Table, Text, func, inspect, select, text,
)


RESERVED_TABLES = {"mdb_yukleme_loglari", "mdb_tablo_aktarim_loglari"}


def validate_source_tables(tables):
    """Prevent source tables from overwriting log or passive tables."""
    names = [name.lower() for name in tables]
    if len(set(names)) != len(names):
        raise ValueError("MDB table names collide after converting to lowercase")
    for name in names:
        if name in RESERVED_TABLES or name.endswith("_pasif"):
            raise ValueError(f"Reserved MDB destination table: {name}")


def _validate_database_ids(connection, table):
    """Refuse ambiguous database identities before moving any records."""
    invalid = connection.execute(
        select(table.c.ID).group_by(table.c.ID).having(
            (func.count() > 1) | table.c.ID.is_(None)
        ).limit(1)
    ).first()
    if invalid is not None:
        raise ValueError(f"{table.name} contains null or duplicate ID values")


def _lock_table(connection, table):
    """Keep other writers from changing the set being reconciled."""
    if connection.dialect.name == "postgresql":
        qualified = connection.dialect.identifier_preparer.format_table(table)
        connection.execute(text(f"LOCK TABLE {qualified} IN SHARE ROW EXCLUSIVE MODE"))


def _guard_delete_side_effects(connection, table):
    """Allow a move to fail rather than cascade into unrelated records."""
    if connection.dialect.name == "postgresql":
        qualified = connection.dialect.identifier_preparer.format_table(table)
        cascade = connection.scalar(text("""
            SELECT count(*) FROM pg_constraint
            WHERE contype = 'f' AND confrelid = to_regclass(:table)
              AND confdeltype IN ('c', 'n', 'd')
        """), {"table": qualified})
        if cascade:
            raise ValueError(f"Cannot move {table.name}: foreign keys have cascading delete side effects")


def synchronize_table(connection, name, dataframe):
    """Reconcile one table; the caller commits its data and audit log together."""
    validate_source_tables([name])
    passive_name = name + "_pasif"
    if connection.dialect.name == "postgresql":
        if len(passive_name.encode("utf-8")) > 63:
            raise ValueError(f"Passive table name exceeds PostgreSQL's identifier limit: {passive_name}")
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": "mdb_sync.public." + name},
        )

    result = {
        "source_records": len(dataframe), "records": 0, "skipped_records": 0,
        "deactivated_records": 0, "reactivated_records": 0,
        "status": "Success", "message": "Synchronized successfully",
    }
    if "ID" not in dataframe.columns:
        inspector = inspect(connection)
        if inspector.has_table(name, schema="public"):
            if any(column["name"] == "ID" for column in inspector.get_columns(name, schema="public")):
                raise ValueError(f"MDB is missing the ID column required by public.{name}")
        if dataframe.empty:
            result.update(status="Skipped", message="Empty table without ID")
        else:
            result["records"] = dataframe.to_sql(
                name, connection, schema="public", if_exists="append", index=False,
            ) or 0
            result["message"] = "Appended without ID; passive detection is unavailable"
        return result
    if dataframe["ID"].isna().any() or dataframe["ID"].duplicated().any():
        raise ValueError("MDB contains null or duplicate ID values; no records were moved")

    inspector = inspect(connection)
    if not inspector.has_table(name, schema="public"):
        if dataframe.empty:
            result.update(status="Skipped", message="Empty table")
            return result
        dataframe.head(0).to_sql(name, connection, schema="public", index=False)
    active = Table(name, MetaData(), schema="public", autoload_with=connection)
    if "ID" not in active.c:
        raise ValueError(f"public.{name} has no ID column")
    _lock_table(connection, active)
    _validate_database_ids(connection, active)
    if isinstance(active.c.ID.type, Integer):
        if not dataframe["ID"].astype(str).str.fullmatch(r"[+-]?[0-9]+").all():
            raise ValueError("MDB ID values must be integers for this destination table")

    # Typed, indexed IDs allow the comparison to run inside PostgreSQL and keep
    # large ID lists out of SQL IN clauses and Python database snapshots.
    stage = Table(
        "mdb_ids_" + uuid4().hex, MetaData(),
        Column("ID", active.c.ID.type, primary_key=True),
        Column("source_row", Integer, nullable=False),
        prefixes=["TEMPORARY"], postgresql_on_commit="DROP",
    )
    stage.create(connection)
    for offset in range(0, len(dataframe), 10000):
        batch = dataframe["ID"].iloc[offset:offset + 10000].tolist()
        connection.execute(stage.insert(), [
            {"ID": value, "source_row": offset + index}
            for index, value in enumerate(batch)
        ])
    missing = ~select(stage.c.ID).where(stage.c.ID == active.c.ID).exists()
    missing_count = connection.scalar(select(func.count()).select_from(active).where(missing))
    passive = None
    if inspector.has_table(passive_name, schema="public"):
        passive = Table(passive_name, MetaData(), schema="public", autoload_with=connection)
        if not set(active.c.keys()).issubset(passive.c.keys()):
            raise ValueError(f"public.{passive_name} does not contain all active-table columns")
        for column in active.columns:
            active_type = column.type.compile(dialect=connection.dialect)
            passive_type = passive.c[column.name].type.compile(dialect=connection.dialect)
            if active_type != passive_type:
                raise ValueError(f"public.{passive_name}.{column.name} has a different column type")
        _lock_table(connection, passive)
        _validate_database_ids(connection, passive)

    if missing_count:
        _guard_delete_side_effects(connection, active)
        if passive is None:
            # Copy column types and values without reusing active-table FKs,
            # generated columns, defaults or sequence ownership.
            passive = Table(
                passive_name, MetaData(), *[
                    Column(column.name, column.type, primary_key=column.name == "ID")
                    for column in active.columns
                ], schema="public",
            )
            passive.create(connection)
        missing_ids = select(active.c.ID).where(missing)
        if connection.scalar(select(func.count()).select_from(passive).where(passive.c.ID.in_(missing_ids))):
            _guard_delete_side_effects(connection, passive)
        connection.execute(passive.delete().where(passive.c.ID.in_(missing_ids)))
        copied = connection.execute(passive.insert().from_select(
            active.c.keys(), select(*active.c).where(missing)
        )).rowcount
        if copied != missing_count:
            raise RuntimeError("Passive copy count mismatch; active records were not removed")
        comparisons = []
        for column in active.columns:
            archived = passive.c[column.name]
            # PostgreSQL JSON has no equality operator. Its stored text also
            # preserves whitespace and duplicate keys when verifying the copy.
            if isinstance(column.type, JSON):
                comparisons.append(archived.cast(Text).is_not_distinct_from(column.cast(Text)))
            else:
                comparisons.append(archived.is_not_distinct_from(column))
        preserved = select(passive.c.ID).where(*comparisons).correlate(active).exists()
        if connection.execute(select(active.c.ID).where(missing, ~preserved).limit(1)).first() is not None:
            raise RuntimeError("Passive copy values differ from active data; transfer rolled back")
        removed = connection.execute(active.delete().where(missing)).rowcount
        if removed != copied:
            raise RuntimeError("Active removal count mismatch; transfer rolled back")
        result["deactivated_records"] = removed

    new_rows = connection.execute(select(stage.c.source_row).where(
        ~select(active.c.ID).where(active.c.ID == stage.c.ID).exists()
    )).scalars().all()
    result["skipped_records"] = len(dataframe) - len(new_rows)
    if new_rows:
        result["records"] = dataframe.iloc[new_rows].to_sql(
            name, connection, schema="public", if_exists="append", index=False,
        ) or 0
    if passive is not None:
        # Only remove a passive version after its ID actually exists in active;
        # this also handles databases with insert triggers that skip rows.
        reactivated = passive.c.ID.in_(select(stage.c.ID).where(
            select(active.c.ID).where(active.c.ID == stage.c.ID).exists()
        ))
        expected = connection.scalar(select(func.count()).select_from(passive).where(reactivated))
        if expected:
            _guard_delete_side_effects(connection, passive)
        removed = connection.execute(passive.delete().where(reactivated)).rowcount
        if removed != expected:
            raise RuntimeError("Passive reactivation count mismatch; transfer rolled back")
        result["reactivated_records"] = removed
    stage.drop(connection)
    return result
