"""Run the paper's ARRF comparator without changing the frozen FA-ARRF run."""

import argparse
import json
from pathlib import Path

from jev_factor.arrf_diagnostic import run_diagnostic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/mrf_arrf_diagnostic.json"))
    parser.add_argument(
        "--primary-config", type=Path, default=Path("configs/mrf_unemployment.json")
    )
    parser.add_argument("--archive", type=Path, default=Path("data/raw/mrf-replication.zip"))
    parser.add_argument("--engine", type=Path, default=Path("data/raw/MRF_v210403.R"))
    parser.add_argument("--r-library", type=Path, default=Path("runs/r-library"))
    parser.add_argument("--rscript", default="Rscript")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--trees", type=int)
    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--max-refits", type=int)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    result = run_diagnostic(
        args.source_run,
        args.archive,
        args.engine,
        args.output,
        json.loads(args.config.read_text()),
        json.loads(args.primary_config.read_text()),
        rscript=args.rscript,
        r_library=args.r_library,
        workers=args.workers,
        trees=args.trees,
        seeds=args.seeds,
        max_refits=args.max_refits,
        resume=args.resume,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
