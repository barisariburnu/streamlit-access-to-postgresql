"""Persistent MDB upload history in explicitly named public-schema tables."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    BigInteger, Column, DateTime, ForeignKey, MetaData, String, Table, Text,
    case, func, inspect, select, text,
)
metadata = MetaData(schema="public")
uploads = Table(
    "mdb_yukleme_loglari", metadata,
    Column("id", String(36), primary_key=True),
    Column("file_name", Text, nullable=False),
    Column("file_size_bytes", BigInteger, nullable=False),
    Column("uploaded_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True)),
    Column("completed_at", DateTime(timezone=True)),
    Column("status", String(20), nullable=False),
    Column("total_records", BigInteger, nullable=False, default=0),
    Column("message", Text, nullable=False, default=""),
)
table_results = Table(
    "mdb_tablo_aktarim_loglari", metadata,
    Column("upload_id", String(36), ForeignKey("public.mdb_yukleme_loglari.id"), primary_key=True),
    Column("source_table", Text, primary_key=True),
    Column("target_table", Text, nullable=False),
    Column("source_records", BigInteger, nullable=False),
    Column("inserted_records", BigInteger, nullable=False),
    Column("skipped_records", BigInteger, nullable=False),
    Column("deactivated_records", BigInteger, nullable=False, server_default="0"),
    Column("reactivated_records", BigInteger, nullable=False, server_default="0"),
    Column("status", String(20), nullable=False),
    Column("message", Text, nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=False),
)


def ensure_audit_tables(engine):
    """Create MDB log tables in the existing public schema on first use."""
    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('mdb_log_schema'))"))
        metadata.create_all(connection)
        existing = {column["name"] for column in inspect(connection).get_columns(
            table_results.name, schema="public"
        )}
        # create_all does not add columns to installations already using logs.
        for column in ("deactivated_records", "reactivated_records"):
            if column not in existing:
                connection.execute(text(
                    f"ALTER TABLE public.mdb_tablo_aktarim_loglari "
                    f"ADD COLUMN {column} BIGINT NOT NULL DEFAULT 0"
                ))


def create_upload(engine, file_name, file_size_bytes, uploaded_at=None):
    """Record an accepted upload even if transfer has not started."""
    upload_id = str(uuid4())
    with engine.begin() as connection:
        connection.execute(uploads.insert().values(
            id=upload_id, file_name=file_name, file_size_bytes=file_size_bytes,
            uploaded_at=uploaded_at or datetime.now(timezone.utc), status="Uploaded",
        ))
    return upload_id


def start_upload(engine, upload_id):
    """Start this upload, or retain a completed attempt and create a new one."""
    with engine.begin() as connection:
        upload = connection.execute(
            select(uploads).where(uploads.c.id == upload_id).with_for_update()
        ).mappings().one()
        if upload["status"] == "In Progress":
            raise RuntimeError("This upload is already being transferred")
        if upload["status"] != "Uploaded":
            upload_id = str(uuid4())
            connection.execute(uploads.insert().values(
                id=upload_id, file_name=upload["file_name"],
                file_size_bytes=upload["file_size_bytes"],
                uploaded_at=upload["uploaded_at"], status="Uploaded",
            ))
        connection.execute(uploads.update().where(uploads.c.id == upload_id).values(
            status="In Progress", started_at=datetime.now(timezone.utc),
        ))
    return upload_id


def record_table_result(connection, upload_id, result):
    """Persist a result in the same transaction as its inserted data."""
    connection.execute(table_results.insert().values(
        upload_id=upload_id, source_table=result["table"],
        target_table=result["target_table"], source_records=result["source_records"],
        inserted_records=result["records"], skipped_records=result["skipped_records"],
        deactivated_records=result.get("deactivated_records", 0),
        reactivated_records=result.get("reactivated_records", 0),
        status=result["status"], message=result["message"],
        completed_at=datetime.now(timezone.utc),
    ))


def finish_upload(engine, upload_id, error=None):
    """Derive the summary from committed table results, including partial failures."""
    with engine.begin() as connection:
        total, errors, successful = connection.execute(select(
            func.coalesce(func.sum(table_results.c.inserted_records), 0),
            func.coalesce(func.sum(case((table_results.c.status == "Error", 1), else_=0)), 0),
            func.coalesce(func.sum(case((table_results.c.status == "Success", 1), else_=0)), 0),
        ).where(table_results.c.upload_id == upload_id)).one()
        status = "Success"
        if error or errors:
            status = "Partial Success" if successful else "Error"
        connection.execute(uploads.update().where(uploads.c.id == upload_id).values(
            status=status, total_records=total, completed_at=datetime.now(timezone.utc),
            message=error or ("Some tables failed; see mdb_tablo_aktarim_loglari" if errors else ""),
        ))
