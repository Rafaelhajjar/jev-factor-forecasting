"""Prepare, fit or audit the qualified September 2018 MRF reconstruction."""

import argparse
import json
from pathlib import Path

from jev_factor.mrf2018 import audit, prepare, run
from jev_factor.mrf2018_report import write_report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["prepare", "run", "audit", "execute"])
    p.add_argument("--config", type=Path, default=Path("configs/mrf_september2018.json"))
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--source-rf", type=Path, default=Path("runs/rf-september2018-v2"))
    p.add_argument("--engine", type=Path, required=True)
    p.add_argument("--r-library", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--pilot", action="store_true")
    p.add_argument("--allow-partial", action="store_true")
    args = p.parse_args()
    if args.action == "prepare":
        result = prepare(
            args.config, args.archive, args.source_rf, args.engine, args.output, pilot=args.pilot
        )
        print(json.dumps({"status": result["status"], "jobs": len(result["jobs"])}))
    elif args.action == "run":
        run(args.output, args.r_library, args.workers)
    else:
        if args.action == "execute":
            run(args.output, args.r_library, args.workers)
        result = audit(args.output, allow_partial=args.allow_partial)
        if result["full_declaration_verified"]:
            write_report(args.output, result)
        print(
            json.dumps({k: v for k, v in result.items() if k not in ["code", "config"]}, indent=2)
        )


if __name__ == "__main__":
    main()
