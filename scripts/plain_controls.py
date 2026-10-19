"""Fit/audit separately declared plain RF-MAF and AR(2)+RF controls; no hosted calls."""

import argparse
import json
from pathlib import Path

from jev_factor.plain_controls import audit_controls, run_controls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "audit"))
    parser.add_argument("--source-run", type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, default=Path("data/raw/mrf-replication.zip"))
    parser.add_argument("--engine", type=Path, default=Path("data/raw/MRF_v210403.R"))
    parser.add_argument("--config", type=Path, default=Path("configs/mrf_plain_controls.json"))
    parser.add_argument(
        "--primary-config", type=Path, default=Path("configs/mrf_unemployment.json")
    )
    parser.add_argument("--rscript", default="Rscript")
    parser.add_argument("--trees", type=int)
    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--max-refits", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    config, primary = (json.loads(p.read_text()) for p in (args.config, args.primary_config))
    if args.mode == "run":
        if args.source_run is None:
            parser.error("run requires --source-run")
        result = run_controls(
            args.source_run,
            args.archive,
            args.engine,
            args.output,
            config,
            primary,
            rscript=args.rscript,
            trees=args.trees,
            seeds=args.seeds,
            max_refits=args.max_refits,
            resume=args.resume,
            prepare_only=args.prepare_only,
        )
    else:
        if args.run is None:
            parser.error("audit requires --run")
        if args.output.exists():
            raise FileExistsError("Choose a fresh plain-control audit output")
        result = audit_controls(
            args.run,
            args.archive,
            args.engine,
            config,
            primary,
            rscript=args.rscript,
            allow_partial=args.allow_partial,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
