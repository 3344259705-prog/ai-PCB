import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from validate_episode import validate_episode


class EpisodeValidationTests(unittest.TestCase):
    def setUp(self):
        self.episode = json.loads((ROOT / "examples/synthetic_episode.json").read_text(encoding="utf-8"))

    def test_synthetic_increasing_connection_count_is_not_automatic_failure(self):
        self.assertGreater(self.episode["validation"]["drc_after"]["connection"],
                           self.episode["validation"]["drc_before"]["connection"])
        self.assertEqual([], validate_episode(self.episode, for_publication=True))

    def test_missing_required_field(self):
        del self.episode["rights"]
        self.assertTrue(validate_episode(self.episode))

    def test_bad_hash(self):
        self.episode["artifacts"]["before_sha256"] = "bad-hash"
        self.assertTrue(validate_episode(self.episode))

    def test_forbidden_executed_action(self):
        self.episode["constraints"]["forbidden_actions"].append("network_mapping")
        self.assertTrue(validate_episode(self.episode))

    def test_network_mapping_needs_authorization(self):
        del self.episode["actions"][1]["authorization_ref"]
        self.assertTrue(validate_episode(self.episode))

    def test_blocked_action_does_not_need_mutation_authorization(self):
        self.episode["actions"][0]["kind"] = "component_replacement"
        self.assertEqual([], validate_episode(self.episode))

    def test_reverted_action_still_needs_authorization(self):
        self.episode["actions"][1]["status"] = "reverted"
        self.episode["constraints"]["allowed_actions"] = []
        self.assertTrue(validate_episode(self.episode))

    def test_board_ready_conflicts_with_nonzero_drc(self):
        self.episode["validation"]["board_ready"] = True
        self.assertTrue(validate_episode(self.episode))

    def test_bench_verified_requires_hardware_test(self):
        self.episode["validation"]["result_scope"] = "bench_verified"
        self.assertTrue(validate_episode(self.episode))

    def test_training_pending_rights_rejected(self):
        self.episode["rights"]["source_license_status"] = "pending"
        self.assertTrue(validate_episode(self.episode))

    def test_private_record_only_rejected_in_publication_mode(self):
        self.episode["rights"]["public_release_allowed"] = False
        self.assertEqual([], validate_episode(self.episode))
        self.assertTrue(validate_episode(self.episode, for_publication=True))

    def test_local_only_not_publishable(self):
        self.episode["artifacts"]["availability"] = "local_only"
        self.assertTrue(validate_episode(self.episode, for_publication=True))

    def test_board_ready_metadata_consistency(self):
        self.episode["constraints"]["unknown_parameters"] = []
        self.episode["validation"].update(board_ready=True, result_scope="cad_constraints_passed",
                                          drc_after={"connection": 0, "clearance": 0})
        self.assertEqual([], validate_episode(self.episode))

    def test_input_unchanged(self):
        before = copy.deepcopy(self.episode)
        validate_episode(self.episode, for_publication=True)
        self.assertEqual(before, self.episode)

    def test_cli_malformed_json_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{bad", encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "tools/validate_episode.py"), str(path)],
                                    capture_output=True, text=True)
        self.assertEqual(1, result.returncode)
        self.assertIn("FAIL", result.stdout)


if __name__ == "__main__":
    unittest.main()
