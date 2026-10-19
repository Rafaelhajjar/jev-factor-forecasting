"""Compare frozen training-only PCA conventions with base R; no forests are fitted."""

import argparse
import json
from pathlib import Path

from jev_factor.pca_basis_audit import audit_basis


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
        raise FileExistsError("Choose a fresh PCA audit output")
    report = audit_basis(
        args.source_run,
        args.archive,
        args.engine,
        json.loads(args.config.read_text()),
        rscript=args.rscript,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "refits_checked": len(report["refits"]),
                "all_cross_sectional_PCA_match_up_to_signs": all(
                    r["cross_sectional_PCA"]["same_up_to_component_signs"] for r in report["refits"]
                ),
                "all_MAFs_match_up_to_signs": all(
                    r["all_MAFs_match_up_to_component_signs"] for r in report["refits"]
                ),
                "native_split_penalty_reflection_asymmetry": report[
                    "native_DV_fun_maximum_reflection_asymmetry"
                ],
                "forecast_gap_attributed_to_orientation": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
