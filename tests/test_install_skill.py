from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from install_skill import SOURCE, install_skill, manifest


class SkillInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.skills = Path(self.temp.name) / "skills"

    def test_install_contains_complete_self_contained_package(self):
        target, created = install_skill(self.skills)
        self.assertTrue(created)
        self.assertEqual(manifest(SOURCE), manifest(target))
        self.assertTrue((target / "SKILL.md").is_file())

    def test_repeated_identical_install_does_not_write(self):
        target, _ = install_skill(self.skills)
        before = {p: p.stat().st_mtime_ns for p in target.rglob("*") if p.is_file()}
        _, created = install_skill(self.skills)
        self.assertFalse(created)
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in before})

    def test_local_edits_are_not_overwritten(self):
        target, _ = install_skill(self.skills)
        entry = target / "SKILL.md"
        entry.write_text("My local edits", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            install_skill(self.skills)
        self.assertEqual("My local edits", entry.read_text(encoding="utf-8"))

    def test_existing_unrelated_directory_untouched(self):
        target = self.skills / "pcbloop"
        target.mkdir(parents=True)
        (target / "notes.txt").write_text("Keep me", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            install_skill(self.skills)
        self.assertEqual(["notes.txt"], [p.name for p in target.iterdir()])

    def test_additional_personal_files_not_lost(self):
        target, _ = install_skill(self.skills)
        (target / "private-notes.txt").write_text("Local only", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            install_skill(self.skills)
        self.assertTrue((target / "private-notes.txt").exists())

    def test_missing_skill_entrypoint_rejected_before_destination_created(self):
        source = Path(self.temp.name) / "invalid-source"
        source.mkdir()
        with self.assertRaises(ValueError):
            install_skill(self.skills, source)
        self.assertFalse(self.skills.exists())

    def test_linked_package_rejected_when_symlinks_available(self):
        source = Path(self.temp.name) / "linked-source"
        source.mkdir()
        try:
            (source / "SKILL.md").symlink_to(SOURCE / "SKILL.md")
        except OSError:
            self.skipTest("Creating symlinks is not permitted on this host")
        with self.assertRaises(ValueError):
            install_skill(self.skills, source)
        self.assertFalse(self.skills.exists())


if __name__ == "__main__":
    unittest.main()
