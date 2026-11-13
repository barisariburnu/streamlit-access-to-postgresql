"""Audit and transfer tests using real SQLAlchemy transactions."""

import importlib
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

import pandas as pd
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url


class UploadAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # Never load application secrets or connect to the configured database.
        self.config = SimpleNamespace(
            PG_CONNECTION_STRING="unused", UPLOAD_FOLDER=self.tmp.name,
            MAX_FILE_SIZE=1000000,
        )
        self.config_patch = patch.dict(
            sys.modules, {"config": SimpleNamespace(config=self.config)}
        )
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        sys.modules.pop("app", None)
        self.app = importlib.import_module("app")
        self.audit = importlib.import_module("upload_audit")
        database_url = os.environ.get("TEST_DATABASE_URL")
        if database_url:
            # Use a new database for every test; never reuse application data.
            admin_url = make_url(database_url)
            if admin_url.database != "mdb_audit_tests":
                raise ValueError("TEST_DATABASE_URL must use the disposable mdb_audit_tests database")
            self.admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
            database_name = "audit_test_" + uuid4().hex
            with self.admin_engine.connect() as connection:
                connection.execute(text(f'CREATE DATABASE "{database_name}"'))

            def remove_database():
                with self.admin_engine.connect() as connection:
                    connection.execute(text(f'DROP DATABASE "{database_name}"'))
                self.admin_engine.dispose()

            self.addCleanup(remove_database)
            self.engine = create_engine(admin_url.set(database=database_name))
        else:
            self.engine = create_engine("sqlite://")

            @event.listens_for(self.engine, "connect")
            def attach_audit_schema(connection, _):
                connection.execute("ATTACH DATABASE ':memory:' AS public")

        self.addCleanup(self.engine.dispose)
        self.audit.ensure_audit_tables(self.engine)
        self.ui = patch.object(self.app, "st")
        self.st = self.ui.start()
        self.st.session_state = {}
        self.addCleanup(self.ui.stop)
        self.log_capture = self.assertLogs(self.app.logger, level="DEBUG")
        # Expected errors belong to the failure scenarios, not test output.
        self.log_capture.__enter__()
        self.addCleanup(self.log_capture.__exit__, None, None, None)
        self.app.logger.debug("Starting audit scenario")
        self.path = Path(self.tmp.name) / "sample.mdb"
        self.path.write_bytes(b"fixture")

    def rows(self, table):
        with self.engine.connect() as connection:
            return connection.execute(
                text(f"SELECT * FROM public.{table}")
            ).mappings().all()

    def transfer(self, tables, csv_data, upload_id=None):
        def export(_path, table, output_path):
            value = csv_data[table]
            if isinstance(value, Exception):
                raise value
            Path(output_path).write_text(value)

        with patch.object(self.app, "create_engine", return_value=self.engine), \
                patch.object(self.app, "test_postgresql_connection", return_value=(True, "OK")), \
                patch.object(self.app, "check_mdb_tools"), \
                patch.object(self.app, "get_tables", return_value=tables), \
                patch.object(self.app, "export_table_to_csv", side_effect=export), \
                patch.object(self.engine, "dispose"):
            return self.app.transfer_mdb_to_postgresql(str(self.path), upload_id)

    def test_upload_is_recorded_once_per_selection_not_per_rerun(self):
        upload = SimpleNamespace(name="data.mdb", size=15, file_id="first")
        first = self.app.register_uploaded_file(upload, self.engine)
        again = self.app.register_uploaded_file(upload, self.engine)
        self.assertEqual(first, again)
        rows = self.rows("mdb_yukleme_loglari")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["file_name"], "data.mdb")
        self.assertEqual(rows[0]["file_size_bytes"], 15)
        self.assertEqual(rows[0]["status"], "Uploaded")
        self.assertIsNotNone(rows[0]["uploaded_at"])
        upload.file_id = "second"
        self.app.register_uploaded_file(upload, self.engine)
        self.assertEqual(len(self.rows("mdb_yukleme_loglari")), 2)

    def test_counts_only_new_rows_and_keeps_upload_time(self):
        pd.DataFrame({"ID": [1], "name": ["existing"]}).to_sql(
            "people", self.engine, schema="public", index=False
        )
        upload_id = self.app.register_uploaded_file(
            SimpleNamespace(name="sample.mdb", size=7, file_id="first"), self.engine
        )
        uploaded_at = self.rows("mdb_yukleme_loglari")[0]["uploaded_at"]
        results = self.transfer(
            ["People"], {"People": "ID,name\n1,existing\n2,new\n3,newer\n"}, upload_id
        )
        self.assertEqual(results[0]["records"], 2)
        detail = self.rows("mdb_tablo_aktarim_loglari")[0]
        self.assertEqual(detail["source_table"], "People")
        self.assertEqual(detail["target_table"], "people")
        self.assertEqual(detail["source_records"], 3)
        self.assertEqual(detail["inserted_records"], 2)
        self.assertEqual(detail["skipped_records"], 1)
        upload = self.rows("mdb_yukleme_loglari")[0]
        self.assertEqual(upload["uploaded_at"], uploaded_at)
        self.assertEqual(upload["status"], "Success")
        self.assertEqual(upload["total_records"], 2)
        self.assertIsNotNone(upload["started_at"])
        self.assertIsNotNone(upload["completed_at"])
        with self.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM public.people")), 3)

    def test_partial_failure_and_empty_table_remain_in_history(self):
        self.transfer(
            ["Good", "Broken", "Empty"],
            {"Good": "name\nAda\n", "Broken": RuntimeError("export failed"), "Empty": "ID,name\n"},
        )
        details = {row["source_table"]: row for row in self.rows("mdb_tablo_aktarim_loglari")}
        self.assertEqual(details["Good"]["inserted_records"], 1)
        self.assertEqual(details["Broken"]["status"], "Error")
        self.assertEqual(details["Broken"]["inserted_records"], 0)
        self.assertIn("export failed", details["Broken"]["message"])
        self.assertEqual(details["Empty"]["status"], "Skipped")
        self.assertEqual(self.rows("mdb_yukleme_loglari")[0]["status"], "Partial Success")
        self.assertEqual(self.rows("mdb_yukleme_loglari")[0]["total_records"], 1)

    def test_failed_insert_is_rolled_back_and_logged_as_zero(self):
        with self.engine.begin() as connection:
            connection.execute(text('CREATE TABLE public.people ("ID" INTEGER PRIMARY KEY)'))
        self.transfer(["People"], {"People": "ID\n2\n2\n"})
        with self.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM public.people")), 0)
        self.assertEqual(self.rows("mdb_tablo_aktarim_loglari")[0]["inserted_records"], 0)
        self.assertEqual(self.rows("mdb_yukleme_loglari")[0]["status"], "Error")

    def test_preflight_error_is_saved_without_table_results(self):
        with patch.object(self.app, "check_mdb_tools", side_effect=RuntimeError("MDBTools missing")):
            # The transfer helper's patch is intentionally bypassed for this case.
            with patch.object(self.app, "create_engine", return_value=self.engine), \
                    patch.object(self.app, "test_postgresql_connection", return_value=(True, "OK")), \
                    patch.object(self.engine, "dispose"):
                results = self.app.transfer_mdb_to_postgresql(str(self.path))
        self.assertEqual(results[0]["status"], "Error")
        self.assertEqual(self.rows("mdb_yukleme_loglari")[0]["status"], "Error")
        self.assertIn("MDBTools missing", self.rows("mdb_yukleme_loglari")[0]["message"])
        self.assertEqual(self.rows("mdb_tablo_aktarim_loglari"), [])

    def test_repeated_transfer_preserves_previous_attempt(self):
        upload_id = self.app.register_uploaded_file(
            SimpleNamespace(name="sample.mdb", size=7, file_id="first"), self.engine
        )
        for _ in range(2):
            self.transfer(["People"], {"People": "ID\n1\n"}, upload_id)
        uploads = self.rows("mdb_yukleme_loglari")
        self.assertEqual(len(uploads), 2)
        self.assertEqual(sorted(row["total_records"] for row in uploads), [0, 1])
        self.assertEqual(len(self.rows("mdb_tablo_aktarim_loglari")), 2)

    def test_log_failure_rolls_back_data_and_reports_failure(self):
        pd.DataFrame({"ID": [1]}).to_sql("people", self.engine, schema="public", index=False)
        real_record = self.app.record_table_result

        def reject_success(connection, upload_id, result):
            if result["status"] == "Success":
                raise RuntimeError("audit write failed")
            return real_record(connection, upload_id, result)

        with patch.object(self.app, "record_table_result", side_effect=reject_success):
            self.transfer(["People"], {"People": "ID\n2\n"})
        with self.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM public.people")), 1)
        self.assertEqual(self.rows("mdb_tablo_aktarim_loglari")[0]["inserted_records"], 0)
        self.assertEqual(self.rows("mdb_yukleme_loglari")[0]["status"], "Error")

    def test_all_duplicates_are_recorded_as_zero_inserts(self):
        pd.DataFrame({"ID": [1]}).to_sql("people", self.engine, schema="public", index=False)
        self.transfer(["People"], {"People": "ID\n1\n"})
        detail = self.rows("mdb_tablo_aktarim_loglari")[0]
        self.assertEqual(detail["inserted_records"], 0)
        self.assertEqual(detail["skipped_records"], 1)
        self.assertEqual(detail["status"], "Success")

    def test_quoted_target_name_uses_correct_duplicate_check(self):
        pd.DataFrame({"ID": [1]}).to_sql('some "people"', self.engine, schema="public", index=False)
        self.transfer(['Some "People"'], {'Some "People"': "ID\n1\n2\n"})
        detail = self.rows("mdb_tablo_aktarim_loglari")[0]
        self.assertEqual(detail["inserted_records"], 1)
        self.assertEqual(detail["skipped_records"], 1)

    def test_count_matches_rows_actually_inserted_when_trigger_skips_a_row(self):
        with self.engine.begin() as connection:
            connection.execute(text('CREATE TABLE public.people ("ID" INTEGER PRIMARY KEY)'))
            if self.engine.dialect.name == "postgresql":
                connection.execute(text('''
                    CREATE FUNCTION skip_second_row() RETURNS trigger AS $$
                    BEGIN
                        IF NEW."ID" = 2 THEN RETURN NULL; END IF;
                        RETURN NEW;
                    END; $$ LANGUAGE plpgsql
                '''))
                connection.execute(text('''
                    CREATE TRIGGER skip_second BEFORE INSERT ON public.people
                    FOR EACH ROW EXECUTE FUNCTION skip_second_row()
                '''))
            else:
                connection.execute(text('''
                    CREATE TRIGGER public.skip_second BEFORE INSERT ON public.people
                    WHEN NEW."ID" = 2 BEGIN SELECT RAISE(IGNORE); END
                '''))
        self.transfer(["People"], {"People": "ID\n1\n2\n"})
        with self.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM public.people")), 1)
        self.assertEqual(self.rows("mdb_tablo_aktarim_loglari")[0]["inserted_records"], 1)
        self.assertEqual(self.rows("mdb_yukleme_loglari")[0]["total_records"], 1)

    def test_missing_mdb_ids_move_to_passive_with_all_values_preserved(self):
        pd.DataFrame({
            "ID": [1, 125307524, 125307525],
            "name": ["active", "old parcel A", "old parcel B"],
        }).to_sql("zemin", self.engine, schema="public", index=False)
        self.transfer(["Zemin"], {"Zemin": "ID,name\n1,active\n2,new\n"})
        self.assertEqual(sorted(row["ID"] for row in self.rows("zemin")), [1, 2])
        archived = {row["ID"]: row["name"] for row in self.rows("zemin_pasif")}
        self.assertEqual(archived, {125307524: "old parcel A", 125307525: "old parcel B"})
        log = self.rows("mdb_tablo_aktarim_loglari")[0]
        self.assertEqual(log["deactivated_records"], 2)
        self.assertEqual(log["inserted_records"], 1)
        self.assertEqual(log["reactivated_records"], 0)

    def test_reappearing_id_returns_to_active_using_mdb_values(self):
        pd.DataFrame({"ID": [1, 2], "name": ["one", "old two"]}).to_sql(
            "people", self.engine, schema="public", index=False
        )
        self.transfer(["People"], {"People": "ID,name\n1,one\n"})
        self.transfer(["People"], {"People": "ID,name\n1,one\n2,new two\n"})
        self.assertEqual(self.rows("people_pasif"), [])
        self.assertEqual({row["ID"]: row["name"] for row in self.rows("people")}, {1: "one", 2: "new two"})
        self.assertEqual(sum(row["reactivated_records"] for row in self.rows("mdb_tablo_aktarim_loglari")), 1)
        self.transfer(["People"], {"People": "ID,name\n1,one\n"})
        self.transfer(["People"], {"People": "ID,name\n1,one\n"})
        self.assertEqual([(r["ID"], r["name"]) for r in self.rows("people_pasif")], [(2, "new two")])

    def test_empty_snapshot_with_id_moves_all_existing_rows_to_passive(self):
        pd.DataFrame({"ID": [1, 2]}).to_sql("people", self.engine, schema="public", index=False)
        self.transfer(["People"], {"People": "ID\n"})
        self.assertEqual(self.rows("people"), [])
        self.assertEqual(sorted(r["ID"] for r in self.rows("people_pasif")), [1, 2])
        log = self.rows("mdb_tablo_aktarim_loglari")[0]
        self.assertEqual(log["deactivated_records"], 2)
        self.assertEqual(log["status"], "Success")

    def test_invalid_source_ids_do_not_deactivate_anything(self):
        for invalid_csv in ["ID\n2\n2\n", "ID,name\n,missing\n"]:
            with self.subTest(csv=invalid_csv):
                pd.DataFrame({"ID": [1]}).to_sql(
                    "people", self.engine, schema="public", if_exists="replace", index=False
                )
                results = self.transfer(["People"], {"People": invalid_csv})
                self.assertEqual(results[0]["status"], "Error")
                self.assertEqual([row["ID"] for row in self.rows("people")], [1])

    def test_archive_failure_retains_active_rows_and_logs_zero_moves(self):
        pd.DataFrame({"ID": [1, 2], "name": ["keep", "blocked"]}).to_sql(
            "people", self.engine, schema="public", index=False
        )
        with self.engine.begin() as connection:
            connection.execute(text('''
                CREATE TABLE public.people_pasif (
                    "ID" BIGINT PRIMARY KEY, name TEXT CHECK (name <> 'blocked')
                )
            '''))
        result = self.transfer(["People"], {"People": "ID,name\n1,keep\n3,new\n"})
        self.assertEqual(result[0]["status"], "Error")
        self.assertEqual(sorted(row["ID"] for row in self.rows("people")), [1, 2])
        self.assertEqual(self.rows("people_pasif"), [])
        self.assertEqual(self.rows("mdb_tablo_aktarim_loglari")[0]["deactivated_records"], 0)

    def test_tables_without_id_keep_append_behavior(self):
        pd.DataFrame({"name": ["old"]}).to_sql("notes", self.engine, schema="public", index=False)
        self.transfer(["Notes"], {"Notes": "name\nnew\n"})
        self.assertEqual(sorted(row["name"] for row in self.rows("notes")), ["new", "old"])
        self.assertEqual(self.rows("mdb_tablo_aktarim_loglari")[0]["deactivated_records"], 0)

    def test_old_audit_rows_survive_addition_of_passive_count_columns(self):
        self.transfer(["People"], {"People": "ID\n1\n"})
        with self.engine.begin() as connection:
            for column in ["deactivated_records", "reactivated_records"]:
                connection.execute(text(f'ALTER TABLE public.mdb_tablo_aktarim_loglari DROP COLUMN {column}'))
        self.audit.ensure_audit_tables(self.engine)
        row = self.rows("mdb_tablo_aktarim_loglari")[0]
        self.assertEqual(row["inserted_records"], 1)
        self.assertEqual(row["deactivated_records"], 0)
        self.assertEqual(row["reactivated_records"], 0)

    def test_missing_entire_source_table_is_not_treated_as_an_empty_snapshot(self):
        pd.DataFrame({"ID": [1]}).to_sql("people", self.engine, schema="public", index=False)
        self.transfer(["Notes"], {"Notes": "name\nnew\n"})
        self.assertEqual([row["ID"] for row in self.rows("people")], [1])

    def test_missing_id_header_cannot_insert_null_ids_into_an_id_table(self):
        pd.DataFrame({"ID": [1], "name": ["keep"]}).to_sql(
            "people", self.engine, schema="public", index=False
        )
        result = self.transfer(["People"], {"People": "name\nnew\n"})
        self.assertEqual(result[0]["status"], "Error")
        self.assertEqual([row["ID"] for row in self.rows("people")], [1])

    def test_reserved_passive_source_table_aborts_before_moving_any_records(self):
        pd.DataFrame({"ID": [1]}).to_sql("people", self.engine, schema="public", index=False)
        result = self.transfer(["People", "People_pasif"], {"People": "ID\n2\n"})
        self.assertEqual(result[0]["status"], "Error")
        self.assertEqual([row["ID"] for row in self.rows("people")], [1])

    def test_archive_trigger_skipping_rows_does_not_remove_active_data(self):
        with self.engine.begin() as connection:
            connection.execute(text('CREATE TABLE public.people ("ID" BIGINT PRIMARY KEY)'))
            connection.execute(text('CREATE TABLE public.people_pasif ("ID" BIGINT PRIMARY KEY)'))
            connection.execute(text('INSERT INTO public.people VALUES (1)'))
            if connection.dialect.name == "postgresql":
                connection.execute(text('''
                    CREATE FUNCTION skip_archive_row() RETURNS trigger AS $$
                    BEGIN RETURN NULL; END; $$ LANGUAGE plpgsql
                '''))
                connection.execute(text('''
                    CREATE TRIGGER skip_archive BEFORE INSERT ON public.people_pasif
                    FOR EACH ROW EXECUTE FUNCTION skip_archive_row()
                '''))
            else:
                connection.execute(text('''
                    CREATE TRIGGER public.skip_archive BEFORE INSERT ON people_pasif
                    BEGIN SELECT RAISE(IGNORE); END
                '''))
        result = self.transfer(["People"], {"People": "ID\n2\n"})
        self.assertEqual(result[0]["status"], "Error")
        self.assertEqual([row["ID"] for row in self.rows("people")], [1])
        self.assertEqual(self.rows("people_pasif"), [])

    def test_cascading_foreign_key_cannot_remove_unrelated_child_rows(self):
        if self.engine.dialect.name != "postgresql":
            self.skipTest("PostgreSQL foreign key metadata guard")
        with self.engine.begin() as connection:
            connection.execute(text('CREATE TABLE public.people ("ID" BIGINT PRIMARY KEY)'))
            connection.execute(text('''CREATE TABLE public.children (
                parent_id BIGINT REFERENCES public.people("ID") ON DELETE CASCADE
            )'''))
            connection.execute(text('INSERT INTO public.people VALUES (1)'))
            connection.execute(text('INSERT INTO public.children VALUES (1)'))
        result = self.transfer(["People"], {"People": "ID\n2\n"})
        self.assertEqual(result[0]["status"], "Error")
        self.assertEqual([row["ID"] for row in self.rows("people")], [1])
        self.assertEqual([row["parent_id"] for row in self.rows("children")], [1])

    def test_reactivation_does_not_cascade_from_passive_into_child_tables(self):
        if self.engine.dialect.name != "postgresql":
            self.skipTest("PostgreSQL foreign key metadata guard")
        with self.engine.begin() as connection:
            connection.execute(text('CREATE TABLE public.people ("ID" BIGINT PRIMARY KEY)'))
            connection.execute(text('CREATE TABLE public.people_pasif ("ID" BIGINT PRIMARY KEY)'))
            connection.execute(text('''CREATE TABLE public.archive_children (
                parent_id BIGINT REFERENCES public.people_pasif("ID") ON DELETE CASCADE
            )'''))
            connection.execute(text('INSERT INTO public.people_pasif VALUES (1)'))
            connection.execute(text('INSERT INTO public.archive_children VALUES (1)'))
        result = self.transfer(["People"], {"People": "ID\n1\n"})
        self.assertEqual(result[0]["status"], "Error")
        self.assertEqual(self.rows("people"), [])
        self.assertEqual([row["ID"] for row in self.rows("people_pasif")], [1])
        self.assertEqual([row["parent_id"] for row in self.rows("archive_children")], [1])

    def test_existing_passive_column_types_cannot_silently_truncate_values(self):
        if self.engine.dialect.name != "postgresql":
            self.skipTest("PostgreSQL assignment cast behavior")
        with self.engine.begin() as connection:
            connection.execute(text('CREATE TABLE public.people ("ID" BIGINT, amount NUMERIC(10,2))'))
            connection.execute(text('CREATE TABLE public.people_pasif ("ID" BIGINT PRIMARY KEY, amount BIGINT)'))
            connection.execute(text('INSERT INTO public.people VALUES (2, 12.34)'))
        result = self.transfer(["People"], {"People": "ID,amount\n1,1.00\n"})
        self.assertEqual(result[0]["status"], "Error")
        self.assertEqual([row["ID"] for row in self.rows("people")], [2])
        self.assertEqual(str(self.rows("people")[0]["amount"]), "12.34")
        self.assertEqual(self.rows("people_pasif"), [])

    def test_archive_trigger_rewriting_values_does_not_lose_original_record(self):
        if self.engine.dialect.name != "postgresql":
            self.skipTest("PostgreSQL BEFORE INSERT row rewriting")
        with self.engine.begin() as connection:
            connection.execute(text('CREATE TABLE public.people ("ID" BIGINT, name TEXT)'))
            connection.execute(text('CREATE TABLE public.people_pasif ("ID" BIGINT PRIMARY KEY, name TEXT)'))
            connection.execute(text("INSERT INTO public.people VALUES (2, 'original')"))
            connection.execute(text('''
                CREATE FUNCTION change_archive_value() RETURNS trigger AS $$
                BEGIN NEW.name := 'changed'; RETURN NEW; END; $$ LANGUAGE plpgsql
            '''))
            connection.execute(text('''
                CREATE TRIGGER change_archive BEFORE INSERT ON public.people_pasif
                FOR EACH ROW EXECUTE FUNCTION change_archive_value()
            '''))
        result = self.transfer(["People"], {"People": "ID,name\n1,new\n"})
        self.assertEqual(result[0]["status"], "Error")
        self.assertEqual([(row["ID"], row["name"]) for row in self.rows("people")], [(2, "original")])
        self.assertEqual(self.rows("people_pasif"), [])

    def test_json_column_is_preserved_when_archiving(self):
        if self.engine.dialect.name != "postgresql":
            self.skipTest("PostgreSQL JSON type equality behavior")
        with self.engine.begin() as connection:
            connection.execute(text('CREATE TABLE public.people ("ID" BIGINT, payload JSON)'))
            connection.execute(text('''INSERT INTO public.people
                VALUES (2, '{"nested": [1, null, "value"]}')'''))
        result = self.transfer(["People"], {"People": "ID,payload\n"})
        self.assertEqual(result[0]["status"], "Success")
        self.assertEqual(self.rows("people"), [])
        self.assertEqual(self.rows("people_pasif")[0]["payload"], {"nested": [1, None, "value"]})


if __name__ == "__main__":
    unittest.main()
