"""Audit a PCA-only eligibility change without fitting forests or scoring forecasts."""

import argparse
import json
from pathlib import Path

from jev_factor.pca_eligibility import audit_eligibility


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--archive", type=Path, default=Path("data/raw/mrf-replication.zip"))
    parser.add_argument("--engine", type=Path, default=Path("data/raw/MRF_v210403.R"))
    parser.add_argument("--config", type=Path, default=Path("configs/mrf_unemployment.json"))
    parser.add_argument("--rscript", default="Rscript")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Choose a fresh eligibility audit output")
    report = audit_eligibility(
        args.source_run,
        args.archive,
        args.engine,
        json.loads(args.config.read_text()),
        rscript=args.rscript,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "refits"}, indent=2))
    print(f"Verified {len(report['refits'])} refits; no new forecast performance calculated.")


if __name__ == "__main__":
    main()
