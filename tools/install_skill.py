"""Install the bundled PCBLoop skill locally; no network or CAD access."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil

SOURCE = Path(__file__).resolve().parents[1] / "skills" / "pcbloop"


def manifest(directory):
    """Reject links and fingerprint regular package files."""
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Skill directory must be a regular directory, not a symlink")
    result = {}
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError("Skill packages must not contain symbolic links")
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def install_skill(skills_dir, source=SOURCE):
    source = Path(source)
    expected = manifest(source)
    if "SKILL.md" not in expected:
        raise ValueError("Source package has no SKILL.md")
    root = Path(skills_dir).expanduser().resolve()
    target = root / "pcbloop"
    if target.is_symlink():
        raise ValueError("Refusing a symbolic-link installation target")
    if target.exists():
        if target.is_dir() and manifest(target) == expected:
            return target, False
        raise FileExistsError("Existing pcbloop differs; back it up or choose another skills directory. Nothing overwritten.")
    root.mkdir(parents=True, exist_ok=True)
    # copytree refuses existing targets; there is intentionally no overwrite/delete mode.
    shutil.copytree(source, target)
    if manifest(target) != expected:
        raise OSError("Installed files did not match; inspect the partial installation before retrying")
    return target, True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(os.environ["CODEX_HOME"]).expanduser() if os.environ.get("CODEX_HOME") else Path.home() / ".codex"
    parser.add_argument("--skills-dir", type=Path, default=default_root / "skills",
                        help="Parent directory for pcbloop (default: CODEX_HOME/skills or ~/.codex/skills)")
    args = parser.parse_args(argv)
    try:
        target, created = install_skill(args.skills_dir)
    except (OSError, ValueError) as exc:
        print(f"Installation failed: {exc}")
        return 1
    print(f"{'Installed' if created else 'Already installed, identical'}: {target}")
    print("Start a new Codex conversation and invoke $pcbloop. CAD tools are separate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
