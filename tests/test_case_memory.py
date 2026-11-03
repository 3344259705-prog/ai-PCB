import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import case_memory as memory


class CaseMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.db = self.directory / "cases.sqlite3"
        memory.init_db(self.db)
        self.episode = json.loads((ROOT / "examples/synthetic_episode.json").read_text(encoding="utf-8"))
        self.context = json.loads((ROOT / "examples/synthetic_context.json").read_text(encoding="utf-8"))
        self.evidence = ROOT / "examples/synthetic_evidence.md"
        self.case_id = self.episode["episode_id"]

    def add(self, episode=None, context=None):
        return memory.add_case(self.db, episode or self.episode, context or self.context, consent=True)

    def approve(self, role="solution"):
        memory.review_case(self.db, self.case_id, "approved", role, "Synthetic review only", self.evidence)

    def search(self, **kwargs):
        return memory.search_cases(self.db, "gate mapping", self.context, include_synthetic=True, **kwargs)

    def test_full_closed_loop_and_negative_feedback_quarantine(self):
        self.assertTrue(self.add())
        self.assertEqual([], self.search())
        self.approve()
        self.assertEqual(self.case_id, self.search()[0]["case_id"])
        memory.record_feedback(self.db, self.case_id, "run-1", "new-fictional-family", "worked", "Local checks passed", self.evidence)
        self.assertEqual(1, len(self.search()))
        memory.record_feedback(self.db, self.case_id, "run-2", "new-fictional-family", "failed", "Not applicable", self.evidence)
        self.assertEqual([], self.search())
        record = memory.show_case(self.db, self.case_id)
        self.assertEqual("needs_review", record["reviews"][-1]["decision"])
        self.assertEqual(2, len(record["feedback"]))
        self.approve()
        self.assertEqual(1, len(self.search()))

    def test_no_local_storage_without_consent(self):
        with self.assertRaises(ValueError):
            memory.add_case(self.db, self.episode, self.context)
        with memory.connection(self.db) as db:
            self.assertEqual(0, db.execute("SELECT COUNT(*) FROM cases").fetchone()[0])

    def test_synthetic_cases_excluded_by_default(self):
        self.add()
        self.approve()
        self.assertEqual([], memory.search_cases(self.db, "gate mapping", self.context))

    def test_context_mismatch_excluded(self):
        self.add()
        self.approve()
        for change in [{"copper_layers": 2}, {"topology": "different"}, {"cad": "different"}, {"cad_version": "unrecorded"}]:
            context = {**self.context, **change}
            self.assertEqual([], memory.search_cases(self.db, "gate", context, include_synthetic=True))

    def test_unknown_requested_parameter_not_assumed_compatible(self):
        self.add(context={**self.context, "finished_copper_um": None})
        self.approve()
        self.assertEqual([], memory.search_cases(self.db, "gate", {**self.context, "finished_copper_um": 35}, include_synthetic=True))

    def test_stored_constraint_cannot_be_omitted_to_get_a_match(self):
        self.add(context={**self.context, "cad_version": "fictional-1"})
        self.approve()
        self.assertEqual([], self.search())

    def test_retrieval_permission_enforced(self):
        self.episode["rights"]["retrieval_use_allowed"] = False
        self.add()
        self.approve()
        self.assertEqual([], self.search())

    def test_failed_cases_can_only_be_returned_as_reviewed_pitfalls(self):
        self.episode["validation"]["result_scope"] = "failed"
        self.add()
        with self.assertRaises(ValueError):
            self.approve()
        self.approve("pitfall")
        self.assertEqual([], self.search())
        self.assertEqual("pitfall", self.search(role="pitfall")[0]["role"])

    def test_rejected_case_not_retrieved(self):
        self.add()
        self.approve()
        memory.review_case(self.db, self.case_id, "rejected", "solution", "Withdrawn", self.evidence)
        self.assertEqual([], self.search())

    def test_no_review_without_evidence(self):
        self.add()
        with self.assertRaises(ValueError):
            memory.review_case(self.db, self.case_id, "approved", "solution", "No evidence", self.directory / "missing")

    def test_empty_evidence_summary_not_approved(self):
        self.episode["validation"]["evidence_summary"] = [""]
        self.add()
        with self.assertRaises(ValueError):
            self.approve()

    def test_duplicate_case_does_not_change_original(self):
        self.assertTrue(self.add())
        self.approve()
        self.assertFalse(self.add())
        changed = copy.deepcopy(self.episode)
        changed["task"]["instruction_summary"] = "Different content"
        with self.assertRaises(ValueError):
            self.add(changed)
        self.assertEqual(1, len(self.search()))

    def test_duplicate_feedback_rolls_back_without_demotion(self):
        self.add()
        self.approve()
        memory.record_feedback(self.db, self.case_id, "same-run", "fictional", "worked", "OK", self.evidence)
        with self.assertRaises(sqlite3.IntegrityError):
            memory.record_feedback(self.db, self.case_id, "same-run", "fictional", "failed", "Duplicate", self.evidence)
        self.assertEqual(1, len(self.search()))
        self.assertEqual(1, len(memory.show_case(self.db, self.case_id)["feedback"]))

    def test_positive_feedback_does_not_promote_pending_case(self):
        self.add()
        memory.record_feedback(self.db, self.case_id, "new-run", "fictional", "worked", "User accepted", self.evidence)
        self.assertEqual([], self.search())

    def test_parameterized_values_do_not_execute_sql(self):
        self.episode["episode_id"] = "x'); DROP TABLE cases;--"
        self.add()
        record = memory.show_case(self.db, self.episode["episode_id"])
        self.assertEqual(self.episode, record["episode"])
        self.assertEqual([], memory.search_cases(self.db, "'); DROP TABLE cases;--", self.context))

    def test_foreign_database_refused_and_preserved(self):
        foreign = self.directory / "foreign.db"
        db = sqlite3.connect(foreign)
        try:
            db.execute("CREATE TABLE keep(value TEXT)")
            db.execute("INSERT INTO keep VALUES('keep')")
            db.commit()
        finally:
            db.close()
        before = foreign.read_bytes()
        with self.assertRaises(ValueError):
            memory.init_db(foreign)
        self.assertEqual(before, foreign.read_bytes())

    def test_read_does_not_create_database(self):
        absent = self.directory / "absent.sqlite3"
        with self.assertRaises(ValueError):
            memory.search_cases(absent, "gate", self.context)
        self.assertFalse(absent.exists())

    def test_invalid_episode_refused(self):
        del self.episode["rights"]
        with self.assertRaises(ValueError):
            self.add()

    def test_export_requires_separate_consent_and_excludes_private_review_feedback(self):
        self.add()
        self.approve()
        memory.record_feedback(self.db, self.case_id, "run", "private-family", "worked", "Private review note", self.evidence)
        output = self.directory / "export.json"
        with self.assertRaises(ValueError):
            memory.export_case(self.db, self.case_id, output)
        memory.export_case(self.db, self.case_id, output, consent=True)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(self.episode, payload["episode"])
        self.assertNotIn("feedback", payload)
        self.assertNotIn("Private review note", output.read_text(encoding="utf-8"))
        self.assertNotIn("evidence_sha256", payload["review"])
        with self.assertRaises(FileExistsError):
            memory.export_case(self.db, self.case_id, output, consent=True)

    def test_private_case_cannot_be_exported(self):
        self.episode["rights"]["public_release_allowed"] = False
        self.add()
        self.approve()
        with self.assertRaises(ValueError):
            memory.export_case(self.db, self.case_id, self.directory / "out.json", consent=True)

    def test_negative_feedback_blocks_export_until_reviewed(self):
        self.add()
        self.approve()
        memory.record_feedback(self.db, self.case_id, "bad-run", "fictional", "failed", "Failed", self.evidence)
        with self.assertRaises(ValueError):
            memory.export_case(self.db, self.case_id, self.directory / "out.json", consent=True)

    def test_windows_private_path_blocked_during_export(self):
        private_path = chr(92).join(["C:", "Users", "example-user", "private.txt"])
        self.episode["task"]["instruction_summary"] += " at " + private_path
        self.add()
        self.approve()
        with self.assertRaises(ValueError):
            memory.export_case(self.db, self.case_id, self.directory / "out.json", consent=True)

    def test_chinese_keyword_search(self):
        self.episode["task"]["instruction_summary"] = "栅极网络映射修复"
        self.add()
        self.approve()
        results = memory.search_cases(self.db, "栅极映射", self.context, include_synthetic=True)
        self.assertEqual(self.case_id, results[0]["case_id"])

    def test_context_requires_real_layer_count(self):
        with self.assertRaises(ValueError):
            self.add(context={**self.context, "copper_layers": True})

    def test_cli_init_reports_json(self):
        result = subprocess.run([sys.executable, str(ROOT / "tools/case_memory.py"), "--db", str(self.db), "init"],
                                text=True, capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"created": False}, json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
