"""Verify the formatter-only repeat without rewriting either run's provenance."""

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path

from jev_factor.vintage2018 import sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--first", type=Path, required=True)
    p.add_argument("--repeat", type=Path, required=True)
    p.add_argument("--first-commit", required=True)
    p.add_argument("--repeat-commit", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    manifests = [json.loads((d / "manifest.json").read_text()) for d in [args.first, args.repeat]]
    audits = [json.loads((d / "audit.json").read_text()) for d in [args.first, args.repeat]]
    for m, a, commit in zip(
        manifests, audits, [args.first_commit, args.repeat_commit], strict=True
    ):
        if m["status"] != "completed_and_audited" or a["jobs_verified"] != 36:
            raise ValueError("Both complete, audited runs are required")
        for name, digest in m["code"].items():
            blob = subprocess.check_output(["git", "show", f"{commit}:src/jev_factor/{name}"])
            if hashlib.sha256(blob).hexdigest() != digest:
                raise ValueError("Historical source commit differs from run provenance")
    a, b = manifests
    if a["config"] != b["config"] or a["data"] != b["data"]:
        raise ValueError("Config/data changed")
    other_a = {k: v for k, v in a["code"].items() if k != "rf2018.py"}
    other_b = {k: v for k, v in b["code"].items() if k != "rf2018.py"}
    if other_a != other_b:
        raise ValueError("Code other than the orchestrator changed")
    old, new = [
        subprocess.check_output(["git", "show", f"{c}:src/jev_factor/rf2018.py"], text=True)
        for c in [args.first_commit, args.repeat_commit]
    ]
    if ast.dump(ast.parse(old)) != ast.dump(ast.parse(new)):
        raise ValueError("Orchestrator AST changed")
    for w, v in zip(a["windows"], b["windows"], strict=True):
        if w["hashes"] != v["hashes"]:
            raise ValueError("Window inputs differ")
        for entry in [w, v]:
            if {k: sha(Path(path)) for k, path in entry["paths"].items()} != entry["hashes"]:
                raise ValueError("Window bytes changed")
    for j, k in zip(a["jobs"], b["jobs"], strict=True):
        if j["settings_sha256"] != k["settings_sha256"] or j["output_hashes"] != k["output_hashes"]:
            raise ValueError("Job settings, predictions, forests or runtime differ")
        for entry in [j, k]:
            if sha(Path(entry["settings"])) != entry["settings_sha256"]:
                raise ValueError("Settings bytes changed")
            for suffix, digest in entry["output_hashes"].items():
                if sha(Path(entry["prediction"] + suffix)) != digest:
                    raise ValueError("Output bytes changed")
    for name in ["predictions.csv", "metrics.csv"]:
        if sha(args.first / name) != sha(args.repeat / name):
            raise ValueError("Aggregate bytes differ")
    if {k: v for k, v in audits[0].items() if k != "code"} != {
        k: v for k, v in audits[1].items() if k != "code"
    }:
        raise ValueError("Audit outcomes differ")
    result = {
        "first_commit": args.first_commit,
        "repeat_commit": args.repeat_commit,
        "first_manifest_sha256": sha(args.first / "manifest.json"),
        "repeat_manifest_sha256": sha(args.repeat / "manifest.json"),
        "first_audit_sha256": sha(args.first / "audit.json"),
        "repeat_audit_sha256": sha(args.repeat / "audit.json"),
        "config_and_data_equal": True,
        "orchestrator_AST_equal": True,
        "all_other_code_bytes_equal": True,
        "window_inputs_byte_equal": 6,
        "settings_and_predictions_and_complete_forests_byte_equal": 36,
        "complete_audit_outcomes_equal_except_orchestrator_byte_hash": True,
        "both_original_provenance_records_preserved": True,
        "primary_source_cell_gate": audits[1]["plain_RF_approximate_source_cell_gate"],
        "new_experiment_or_retuning": False,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
