"""Run/audit the paired native-normalization forecast diagnostic, not a new primary."""

import argparse
import json
from pathlib import Path

from jev_factor.native_allrows import audit_diagnostic, run_diagnostic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "audit"))
    parser.add_argument("--source-run", type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/mrf_native_allrows.json"))
    parser.add_argument(
        "--primary-config", type=Path, default=Path("configs/mrf_unemployment.json")
    )
    parser.add_argument("--archive", type=Path, default=Path("data/raw/mrf-replication.zip"))
    parser.add_argument("--engine", type=Path, default=Path("data/raw/MRF_v210403.R"))
    parser.add_argument("--r-library", type=Path, default=Path("runs/r-library"))
    parser.add_argument("--rscript", default="Rscript")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--trees", type=int)
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
        result = run_diagnostic(
            args.source_run,
            args.archive,
            args.engine,
            args.output,
            config,
            primary,
            r_library=args.r_library,
            rscript=args.rscript,
            workers=args.workers,
            trees=args.trees,
            seeds=args.seeds,
            max_refits=args.max_refits,
            prepare_only=args.prepare_only,
            resume=args.resume,
        )
    else:
        if args.run is None:
            parser.error("audit requires --run")
        if args.output.exists():
            raise FileExistsError("Choose a fresh native-helper audit output")
        result = audit_diagnostic(
            args.run,
            args.archive,
            config,
            primary,
            allow_partial=args.allow_partial,
            rscript=args.rscript,
        )
        saved = args.run / "diagnostic_result.json"
        if saved.exists() and json.loads(saved.read_text()) != result:
            raise ValueError("Saved native-helper diagnostic result differs")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    display = {
        k: v
        for k, v in result.items()
        if k
        in {
            "status",
            "paired_jobs",
            "full_native_helper_declaration_verified",
            "jobs_verified",
            "pending_jobs",
            "partial_forest_scores_suppressed",
            "metrics",
            "published_ratio_comparisons",
            "numerical_agreement_FA_AR_and_all_individual_seeds",
            "maximum_forecast_coefficient_reconstruction_error",
            "matching_FA_AR_RMSE_reductions",
            "primary_result_replaced",
            "causal_forecast_comparison",
        }
    }
    print(json.dumps(display, indent=2))


if __name__ == "__main__":
    main()
