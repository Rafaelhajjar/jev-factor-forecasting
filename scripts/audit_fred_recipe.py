"""Audit source-recipe completion on training data only; no new forecast scoring."""

import argparse
import json
from pathlib import Path

from jev_factor.fred_recipe_audit import audit_recipe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--archive", type=Path, default=Path("data/raw/mrf-replication.zip"))
    parser.add_argument("--code-archive", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/mrf_unemployment.json"))
    parser.add_argument("--rscript", default="Rscript")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Choose a fresh FRED-recipe audit output")
    result = audit_recipe(
        args.source_run,
        args.archive,
        args.code_archive,
        json.loads(args.config.read_text()),
        rscript=args.rscript,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "refits": [
                    {
                        k: r[k]
                        for k in (
                            "fit_end",
                            "completion_rank_final",
                            "EM_iterations",
                            "EM_converged",
                            "at_source_iteration_cap",
                            "stopping_reason",
                        )
                    }
                    for r in result["refits"]
                ],
                "new_forecast_losses_computed": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
