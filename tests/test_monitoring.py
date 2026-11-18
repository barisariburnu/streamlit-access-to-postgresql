"""Synthetic SDK and build tests; no business service is contacted."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from sentry_sdk import isolation_scope
from sentry_sdk.transport import Transport

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CANARY = "PRIVATE-canary-password-path-sql-body"

class RecordingTransport(Transport):
    def __init__(self, options):
        super().__init__(options)
        self.events = []
        self.envelopes = []
    def capture_envelope(self, envelope):
        self.envelopes.append(envelope)
        for item in envelope.items:
            if item.type == "event":
                self.events.append(item.payload.json)

class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("monitoring"), "monitoring integration is required")
        self.m = importlib.import_module("monitoring")
        self.env = {"SENTRY_DSN": "https://public@example.invalid/1", "SENTRY_ENVIRONMENT": "production", "SENTRY_RELEASE": self.m.APP + "@" + "a" * 40}
    def monitor(self, transport=RecordingTransport):
        value = self.m.Monitor.from_env(self.env, transport=transport)
        self.addCleanup(value.close)
        return value
    def test_sdk_final_envelope_removes_scope_nested_exception_and_frame_secrets(self):
        monitor = self.monitor()
        try:
            try: raise ValueError(CANARY)
            except ValueError as cause: raise RuntimeError(CANARY) from cause
        except RuntimeError as error:
            with isolation_scope() as scope:
                scope.set_client(monitor.client)
                scope.add_attachment(bytes=CANARY.encode(), filename=CANARY)
                scope.add_breadcrumb(message=CANARY, data={"secret": CANARY})
                scope.set_user({"id": CANARY})
                scope.set_context(CANARY, {"secret": CANARY})
                monitor.report(error, "operation_failed")
        events = monitor.client.transport.events
        self.assertEqual(len(events), 1)
        self.assertEqual([[item.type for item in envelope.items] for envelope in monitor.client.transport.envelopes], [["event"]])
        wire = b"".join(envelope.serialize() for envelope in monitor.client.transport.envelopes)
        self.assertNotIn(CANARY.encode(), wire)
        encoded = json.dumps(events)
        self.assertNotIn(CANARY, encoded)
        event = events[0]
        self.assertEqual(event["release"], self.env["SENTRY_RELEASE"])
        self.assertEqual(event["environment"], "production")
        self.assertEqual(set(event), {"event_id", "timestamp", "platform", "level", "environment", "release", "tags", "message", "fingerprint", "exception"})
        self.assertEqual(event["exception"]["values"][0]["type"], "RuntimeError")
    def test_final_whitelist_revalidates_untrusted_sdk_enrichment(self):
        monitor = self.monitor()
        result = monitor.client.options["before_send"]({"event_id": CANARY, "timestamp": CANARY, "release": CANARY, "environment": CANARY, "tags": {"failure_code": CANARY, "job": CANARY}, "request": {"data": CANARY}, "exception": {"values": [{"type": CANARY, "value": CANARY, "stacktrace": {"frames": [{"filename": CANARY, "vars": {"secret": CANARY}}]}}]}}, {})
        self.assertNotIn(CANARY, json.dumps(result))
    def test_disabled_invalid_release_and_failing_transport_are_fail_open(self):
        self.assertIsNone(self.m.Monitor.from_env({}).report(RuntimeError(CANARY)))
        self.assertIsNone(self.m.Monitor.from_env(dict(self.env, SENTRY_RELEASE=CANARY)).client)
        class Broken(Transport):
            def capture_envelope(self, envelope): raise RuntimeError(CANARY)
        self.assertIsNone(self.monitor(Broken).report(RuntimeError(CANARY)))
    def test_same_exception_and_streamlit_control_flow_are_not_reported_twice(self):
        monitor = self.monitor()
        error = RuntimeError(CANARY)
        monitor.report(error)
        monitor.report(error)
        for name in ["RerunException", "StopException"]:
            control = type(name, (BaseException,), {"__module__": "streamlit.runtime.scriptrunner_utils.exceptions"})
            monitor.report(control(CANARY))
        monitor.report(ValueError(CANARY), expected=(ValueError,))
        self.assertEqual(len(monitor.client.transport.events), 1)
    def test_check_is_synthetic_and_queued_does_not_claim_delivery(self):
        monitor = self.monitor()
        self.assertIsNotNone(monitor.check())
        event = monitor.client.transport.events[0]
        self.assertEqual(event["tags"]["job"], "monitoring-check")
        run = subprocess.run([sys.executable, str(ROOT / "monitoring.py"), "monitoring-check"], env=dict(os.environ, SENTRY_DSN=""), capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertEqual(run.stdout.strip(), "monitoring_disabled_or_unavailable")
    def test_build_rejects_invalid_source_before_any_docker_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            script = tmp / "build.sh"
            script.write_text((ROOT / ".coolify/build.sh").read_text())
            docker = tmp / "docker"
            docker.write_text("#!/bin/sh\necho called >> \"$CALL_LOG\"\n")
            docker.chmod(0o755)
            for source in ["bad", "A" * 40, "a" * 39, "a" * 41]:
                run = subprocess.run(["sh", str(script)], cwd=tmp, env=dict(os.environ, SOURCE_COMMIT=source, PATH=str(tmp) + ":" + os.environ["PATH"], CALL_LOG=str(tmp / "calls")), capture_output=True)
                self.assertEqual(run.returncode, 35)
                self.assertFalse((tmp / "calls").exists())
    def test_real_caught_upload_failure_reports_once_and_validation_is_silent(self):
        from types import SimpleNamespace
        with patch.dict(sys.modules, {"config": SimpleNamespace(config=SimpleNamespace(PG_CONNECTION_STRING="unused"))}):
            sys.modules.pop("app", None)
            app = importlib.import_module("app")
        monitor = self.monitor()
        with patch.object(self.m, "get_monitor", return_value=monitor), patch.object(app, "create_engine", side_effect=RuntimeError(CANARY)), patch.object(app, "logger"):
            result = app.transfer_mdb_to_postgresql("unused")
        self.assertEqual(result[0]["status"], "Error")
        self.assertEqual(len(monitor.client.transport.events), 1)
        with patch.object(self.m, "get_monitor", return_value=monitor), patch.object(app, "create_engine", side_effect=ValueError(CANARY)), patch.object(app, "logger"):
            app.transfer_mdb_to_postgresql("unused")
        self.assertEqual(len(monitor.client.transport.events), 1)

    def test_build_reads_only_source_commit_without_evaluating_other_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            script = tmp / "build.sh"
            script.write_text((ROOT / ".coolify/build.sh").read_text())
            build_env = tmp / "build-time.env"
            build_env.write_text('SOURCE_COMMIT="' + 'b'*40 + '"\nSECRET=$(touch '+str(tmp / "executed")+')\n')
            docker = tmp / "docker"
            service = 'mdb-to-postgresql'
            docker.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALL_LOG"\ncase "$*" in *" config") printf "name: project\\n    container_name: '+service+'-project\\n";; inspect*) exit 1;; esac\n')
            docker.chmod(0o755)
            calls = tmp / "calls"
            run = subprocess.run(["sh", str(script), str(build_env)], cwd=tmp, env=dict(os.environ, SOURCE_COMMIT="", PATH=str(tmp)+":"+os.environ["PATH"], CALL_LOG=str(calls)), capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("--build-arg MONITORING_SOURCE_REVISION=" + "b"*40, calls.read_text())
            self.assertFalse((tmp / "executed").exists())
            calls.unlink()
            build_env.write_text("SOURCE_COMMIT=invalid\n")
            run = subprocess.run(["sh", str(script), str(build_env)], cwd=tmp, env=dict(os.environ, SOURCE_COMMIT="", PATH=str(tmp)+":"+os.environ["PATH"], CALL_LOG=str(calls)), capture_output=True)
            self.assertEqual(run.returncode, 35)
            self.assertFalse(calls.exists())

    def test_uncaught_script_boundary_preserves_failure_without_duplicate_or_control_event(self):
        self.assertTrue(callable(getattr(self.m, "run_guarded", None)), "script boundary is required")
        monitor = self.monitor()
        error = RuntimeError(CANARY)
        def fail(): raise error
        with patch.object(self.m, "get_monitor", return_value=monitor):
            with self.assertRaises(RuntimeError): self.m.run_guarded(fail)
            with self.assertRaises(RuntimeError): self.m.run_guarded(fail)
            control = type("RerunException", (BaseException,), {"__module__": "streamlit.runtime.scriptrunner_utils.exceptions"})
            def rerun(): raise control(CANARY)
            with self.assertRaises(BaseException): self.m.run_guarded(rerun)
        self.assertEqual(len(monitor.client.transport.events), 1)

    def test_image_metadata_is_late_and_compose_does_not_override_release(self):
        docker = (ROOT / "Dockerfile").read_text()
        self.assertIn("ARG MONITORING_SOURCE_REVISION", docker)
        self.assertGreater(docker.index("ARG MONITORING_SOURCE_REVISION"), docker.rfind("RUN "))
        self.assertIn("SENTRY_RELEASE=" + self.m.APP + "@${MONITORING_SOURCE_REVISION}", docker)
        compose = (ROOT / ".coolify/compose.yaml").read_text()
        self.assertNotIn("${SOURCE_COMMIT", compose)
        self.assertIn("SENTRY_DSN: ${SENTRY_DSN:-}", compose)
        self.assertNotIn("SENTRY_RELEASE:", compose)

if __name__ == "__main__": unittest.main()
