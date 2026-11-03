"""Local episode metadata checks, not CAD or licensing verification."""
import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "episode.schema.json"
CLEARED_RIGHTS = {"confirmed", "synthetic_mit"}


def validate_episode(data, *, for_publication=False):
    """Return readable validation failures without changing the input."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = [
        f"{'.'.join(map(str, error.absolute_path)) or '$'}: {error.message}"
        for error in Draft202012Validator(schema).iter_errors(data)
    ]
    if errors:
        return errors
    constraints = data["constraints"]
    for index, action in enumerate(data["actions"]):
        if action["status"] not in {"executed", "accepted", "reverted"}:
            continue
        kind = action["kind"]
        if kind not in constraints["allowed_actions"] or kind in constraints["forbidden_actions"]:
            errors.append(f"actions.{index}: action is outside declared authorization")
        if kind == "network_mapping" and not action.get("authorization_ref"):
            errors.append(f"actions.{index}: network_mapping needs authorization_ref")
    validation = data["validation"]
    if validation["result_scope"] == "bench_verified" and not validation["hardware_tested"]:
        errors.append("validation: bench_verified requires hardware_tested")
    if validation["board_ready"]:
        drc = validation.get("drc_after")
        if not drc or any(drc.values()):
            errors.append("validation: board_ready requires nonempty zero-count drc_after")
        if validation["result_scope"] not in {"cad_constraints_passed", "bench_verified"}:
            errors.append("validation: board_ready requires a matching result_scope")
        if constraints["unknown_parameters"]:
            errors.append("validation: board_ready conflicts with unresolved parameters")
    rights = data["rights"]
    if rights["training_use_allowed"] and rights["source_license_status"] not in CLEARED_RIGHTS:
        errors.append("rights: training requires confirmed source rights")
    if for_publication:
        if not rights["public_release_allowed"]:
            errors.append("rights: public release is not allowed")
        if rights["source_license_status"] not in CLEARED_RIGHTS:
            errors.append("rights: publication requires confirmed source rights")
        if data["artifacts"]["availability"] == "local_only":
            errors.append("artifacts: local_only is not a publication record")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--for-publication", action="store_true")
    parser.add_argument("files", type=Path, nargs="+")
    args = parser.parse_args(argv)
    failed = False
    for path in args.files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            errors = validate_episode(data, for_publication=args.for_publication)
        except (OSError, ValueError) as exc:
            errors = [str(exc)]
        if errors:
            failed = True
            print(f"FAIL {path}")
            for error in errors:
                print(f"  {error}")
        else:
            print(f"PASS {path} (metadata only)")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
