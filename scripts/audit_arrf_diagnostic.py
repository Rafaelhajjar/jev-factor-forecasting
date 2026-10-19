"""Verify an ARRF run without fitting forests or overwriting its results."""

import argparse
import json
from pathlib import Path

from jev_factor.arrf_audit import audit_arrf


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--archive", type=Path, default=Path("data/raw/mrf-replication.zip"))
    parser.add_argument("--engine", type=Path, default=Path("data/raw/MRF_v210403.R"))
    parser.add_argument("--config", type=Path, default=Path("configs/mrf_arrf_diagnostic.json"))
    parser.add_argument(
        "--primary-config", type=Path, default=Path("configs/mrf_unemployment.json")
    )
    parser.add_argument("--rscript", default="Rscript")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Choose a fresh ARRF audit output")
    report = audit_arrf(
        args.run,
        args.archive,
        args.engine,
        json.loads(args.config.read_text()),
        json.loads(args.primary_config.read_text()),
        rscript=args.rscript,
        allow_partial=args.allow_partial,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
