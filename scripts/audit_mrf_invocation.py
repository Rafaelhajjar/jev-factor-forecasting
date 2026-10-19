"""Audit native initialization on saved jobs; intentionally fit no trees."""

import argparse
import hashlib
import json
from pathlib import Path

from jev_factor.invocation_audit import audit_invocation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--engine", type=Path, default=Path("data/raw/MRF_v210403.R"))
    parser.add_argument("--r-library", type=Path, default=Path("runs/r-library"))
    parser.add_argument("--rscript", default="Rscript")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Choose a fresh invocation-audit output")
    manifest = json.loads((args.run / "manifest.json").read_text())
    jobs = {job["group"]: job for job in manifest["jobs"]}
    for job in jobs.values():
        for key in ("matrix", "settings"):
            if hashlib.sha256(Path(job[key]).read_bytes()).hexdigest() != job[key + "_sha256"]:
                raise ValueError("Prepared invocation input differs from the saved manifest")
    results = [
        {
            "group": group,
            "fit_end": job["fit_end"],
            "representative_seed": job["seed"],
            **audit_invocation(
                Path(job["matrix"]),
                Path(job["settings"]),
                args.engine,
                args.r_library,
                rscript=args.rscript,
            ),
        }
        for group, job in sorted(jobs.items())
    ]
    report = {
        "status": "all_native_initializations_verified_not_forecast_replication",
        "refits_checked": len(results),
        "source_manifest_sha256": hashlib.sha256(
            (args.run / "manifest.json").read_bytes()
        ).hexdigest(),
        "initializations": results,
        "forests_fitted": 0,
        "forecast_scores_computed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "initializations"}, indent=2))


if __name__ == "__main__":
    main()
