from pathlib import Path
import re
import unittest

import yaml

SKILL = Path(__file__).resolve().parents[1] / "skills" / "pcbloop"


class SkillPackageTests(unittest.TestCase):
    def test_skill_frontmatter_meets_discovery_contract(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = yaml.safe_load(text.split("---", 2)[1])
        self.assertEqual(SKILL.name, frontmatter["name"])
        self.assertRegex(frontmatter["name"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        self.assertTrue(0 < len(frontmatter["description"]) <= 1024)

    def test_references_resolve_inside_installed_package(self):
        count = 0
        for page in SKILL.rglob("*.md"):
            for link in re.findall(r"\]\(([^)]+)\)", page.read_text(encoding="utf-8")):
                if "://" in link or link.startswith("#"):
                    continue
                target = (page.parent / link.split("#")[0]).resolve()
                self.assertTrue(target.is_relative_to(SKILL.resolve()), str(target))
                self.assertTrue(target.is_file(), str(target))
                count += 1
        self.assertGreater(count, 0)

    def test_ui_prompt_invokes_skill_and_keeps_normal_discovery(self):
        config = yaml.safe_load((SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8"))
        self.assertIn("$pcbloop", config["interface"]["default_prompt"])
        self.assertTrue(25 <= len(config["interface"]["short_description"]) <= 64)
        self.assertTrue(config.get("policy", {}).get("allow_implicit_invocation", True))


if __name__ == "__main__":
    unittest.main()
