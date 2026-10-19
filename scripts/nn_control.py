"""Fit/audit the separately declared appendix NN control, without hosted calls."""

import argparse
import json
from pathlib import Path

from jev_factor.nn_experiment import audit_comparison, run_comparison


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "audit"))
    parser.add_argument("--source-run", type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, default=Path("data/raw/mrf-replication.zip"))
    parser.add_argument("--config", type=Path, default=Path("configs/mrf_nn.json"))
    parser.add_argument(
        "--primary-config", type=Path, default=Path("configs/mrf_unemployment.json")
    )
    parser.add_argument("--members", type=int)
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--max-refits", type=int)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    config, primary = (json.loads(p.read_text()) for p in (args.config, args.primary_config))
    if args.mode == "run":
        if args.source_run is None:
            parser.error("run requires --source-run")
        result = run_comparison(
            args.source_run,
            args.archive,
            args.output,
            config,
            primary,
            members=args.members,
            epochs=args.epochs,
            seeds=args.seeds,
            max_refits=args.max_refits,
            prepare_only=args.prepare_only,
            resume=args.resume,
        )
    else:
        if args.run is None:
            parser.error("audit requires --run")
        if args.output.exists():
            raise FileExistsError("Choose a fresh NN audit output")
        result = audit_comparison(
            args.run,
            args.archive,
            config,
            primary,
            allow_partial=args.allow_partial,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    display = {
        k: v for k, v in result.items() if k not in {"member_checks", "deterministic_member_refits"}
    }
    if "deterministic_member_refits" in result:
        display["deterministic_member_refits_verified"] = len(result["deterministic_member_refits"])
    print(json.dumps(display, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
