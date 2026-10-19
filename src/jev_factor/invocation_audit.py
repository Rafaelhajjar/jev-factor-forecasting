"""Inspect real adapter/native initialization, deliberately before tree fitting."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from jev_factor.replication import ensure_engine
from jev_factor.replication_audit import _close, _dcf


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_invocation(
    matrix: Path, settings: Path, engine: Path, r_library: Path, *, rscript: str = "Rscript"
) -> dict:
    """The actual adapter and pinned engine execute in a separate instrumented R process.

    Only the probe process is instrumented; no on-disk source or running forest
    process is changed. This is an initialization contract, not a forecast result.
    """
    engine_metadata = ensure_engine(engine)
    adapter = Path(__file__).with_name("reference_mrf.R")
    helper = Path(__file__).with_name("reference_invocation.R")
    raw = pd.read_csv(matrix, float_precision="round_trip")
    config = _dcf(settings)
    terms = config["xnames"].split(",")
    ntrain = int(config["ntrain"])
    if (
        raw.columns[0] != "target"
        or not raw.columns.is_unique
        or not 20 <= ntrain < len(raw)
        or not np.isfinite(raw.to_numpy()).all()
    ):
        raise ValueError("Invalid native invocation matrix or fitting split")
    if config["standardization"] != "train_only" or config["prior"] != "OLS":
        raise ValueError("This initialization contract covers the declared train-only OLS path")
    with TemporaryDirectory(prefix="mrf-invocation-") as scratch:
        result = subprocess.run(
            [
                rscript,
                "--vanilla",
                str(helper),
                str(engine.resolve()),
                str(matrix.resolve()),
                str(settings.resolve()),
                str(r_library.resolve()),
                str(adapter),
                scratch,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env={
                **os.environ,
                "OPENBLAS_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
                "VECLIB_MAXIMUM_THREADS": "1",
            },
        )
        if result.returncode:
            raise RuntimeError(f"Native initialization probe failed: {result.stderr[-2000:]}")
        metadata = _dcf(Path(scratch) / "invocation.dcf")
        features = pd.read_csv(Path(scratch) / "features.csv")
        prior = pd.read_csv(Path(scratch) / "prior.csv")
    expected_features = pd.DataFrame(
        [
            {"role": role, "name": name, "position": int(raw.columns.get_loc(name)) + 1}
            for role, names in (("linear", terms), ("state", list(raw.columns[1:])))
            for name in names
        ]
    )
    if not features.equals(expected_features):
        raise ValueError("Native linear/state names, ordering or positions differ")
    numbers = {
        "native_rows": len(raw),
        "native_columns": len(raw.columns),
        "training_rows": ntrain,
        "forecast_rows": len(raw) - ntrain,
        "target_position": 1,
        "nominal_parent_size": int(config["minsize"]),
        "mtry_fraction": float(config["mtry"]),
        "ridge_lambda": float(config["ridge_lambda"]),
        "RWR": float(config["RWR"]),
        "MLF": float(config["MLF"]),
        "HRW": 0,
        "trend_push": float(config["trend_push"]),
        "trend_position_in_state": list(raw.columns[1:]).index("trend") + 1,
        "subsampling_rate": 0.75,
        "block_size": int(config["block"]),
        "resampling_option": 2,
        "declared_trees": int(config["trees"]),
        "mtry_state_candidates": round((len(raw.columns) - 1) * float(config["mtry"])),
    }
    # Pinned engine safeguard, tested after actual execution rather than just
    # trusting this algebra or a nominal configuration field.
    nominal, mlf, count = int(config["minsize"]), float(config["MLF"]), len(terms)
    numbers["effective_parent_size"] = (
        2 * mlf * (count + 1) + 2 if nominal < 2 * mlf * (count + 2) else nominal
    )
    for name, value in numbers.items():
        _close([float(metadata[name])], [value], f"native initialization {name}")
    expected_modes = {
        "fast_RW": "TRUE",
        "VI": "FALSE",
        "cheap_coefficient_plot": "FALSE",
        "ERT": "FALSE",
        "no_RW_trespassing": "TRUE",
        "default_state_priorities": "TRUE",
    }
    if any(metadata[k] != v for k, v in expected_modes.items()):
        raise ValueError("Unexpected native execution mode")
    for name in (
        "maximum_masked_target_magnitude",
        "maximum_training_mean",
        "maximum_training_std_error",
    ):
        if not np.isfinite(float(metadata[name])) or float(metadata[name]) > 1e-11:
            raise ValueError(f"Native normalization or mask differs: {name}")
    training = raw.iloc[:ntrain]
    means, stds = training.mean(), training.std(ddof=1)
    z = (training - means) / stds
    beta = np.linalg.lstsq(np.column_stack([np.ones(ntrain), z[terms]]), z.target, rcond=None)[0]
    prior_error = _close(prior["mean"], beta, "native standardized OLS prior")
    _close(prior["precision"], [0.01, *np.ones(len(terms))], "native prior precision")
    return {
        "status": "native_initialization_verified_before_tree_fitting",
        "matrix_sha256": _sha(matrix),
        "settings_sha256": _sha(settings),
        "external_engine": engine_metadata,
        "adapter_sha256": _sha(adapter),
        "probe_source_sha256": _sha(helper),
        "auditor_source_sha256": _sha(Path(__file__)),
        "R_version": metadata["R_version"],
        "pracma_version": metadata["pracma_version"],
        "linear_names": terms,
        "state_columns": len(raw.columns) - 1,
        "native_settings": numbers,
        "native_modes": {k: metadata[k] for k in expected_modes},
        "maximum_standardized_prior_error": prior_error,
        "maximum_masked_target_magnitude": float(metadata["maximum_masked_target_magnitude"]),
        "forests_fitted": 0,
        "forecast_scores_computed": False,
        "on_disk_source_or_live_forest_process_modified": False,
        "exact_author_pipeline_recovered": False,
    }
