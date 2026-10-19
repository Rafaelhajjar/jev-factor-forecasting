"""Check action algebra on saved coefficients; run audit-mrf separately first.

This does not query a selector, read outcomes into a policy, or validate the
missing author's pipeline. It writes no files and does not fit any forests.
"""

import argparse
import json
from pathlib import Path

import pandas as pd

from jev_factor.mrf_actions import (
    ACTION_MULTIPLIERS,
    EQUATION_TERMS,
    IDENTITY_ACTION,
    ForestContributions,
    weighted_forecast,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.run / "manifest.json").read_text())
    if not manifest["completed"]:
        raise ValueError("Use a completed run; this is not a partial performance check")
    identity = {name: float(name == IDENTITY_ACTION) for name in ACTION_MULTIPLIERS}
    uniform = dict.fromkeys(ACTION_MULTIPLIERS, 1 / 25)
    checked = 0
    maximum = 0.0
    for job in manifest["jobs"]:
        predictions = pd.read_csv(job["prediction_path"])
        matrix = pd.read_csv(job["matrix"]).iloc[-len(job["targets"]) :]
        for coefficients, predictors in zip(
            predictions.to_dict("records"),
            matrix[list(EQUATION_TERMS)].to_dict("records"),
            strict=True,
        ):
            parts = ForestContributions.from_coefficients(
                coefficients["intercept"],
                {name: coefficients[name] for name in EQUATION_TERMS},
                predictors,
            )
            for weights in (identity, uniform):
                error = abs(weighted_forecast(parts, weights) - coefficients["prediction"])
                maximum = max(maximum, error)
                if error > 1e-11:
                    raise ValueError("Action identity differs from saved forest prediction")
            checked += 1
    print(
        json.dumps(
            {
                "status": "action_identity_only_not_selector_evaluation",
                "forest_forecasts_checked": checked,
                "actions_per_forecast": 25,
                "maximum_identity_or_uniform_reconstruction_error": maximum,
                "hosted_model_calls": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
