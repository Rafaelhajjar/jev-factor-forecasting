"""Training-only cross-language PCA orientation evidence, never score-driven tuning."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from threadpoolctl import threadpool_limits

from jev_factor.quarterly import PastRepresentation, load_quarterly
from jev_factor.replication import ensure_engine
from jev_factor.replication_audit import audit_run


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare_rotations(python: np.ndarray, r: np.ndarray, tolerance: float = 1e-9) -> dict:
    """Rows are component loadings in the identical ordered feature basis.

    A rotated degenerate eigenspace is not mislabeled a simple sign flip.
    """
    python, r = np.asarray(python, dtype=float), np.asarray(r, dtype=float)
    if python.ndim != 2 or python.shape != r.shape or not python.size:
        raise ValueError("PCA loading shapes differ")
    if not np.isfinite(python).all() or not np.isfinite(r).all():
        raise ValueError("Nonfinite PCA loadings")
    identity = np.eye(len(python))
    if any(not np.allclose(v @ v.T, identity, atol=1e-9, rtol=0) for v in (python, r)):
        raise ValueError("PCA loading rows must be orthonormal")
    signs = np.where(np.sum(python * r, axis=1) >= 0, 1, -1)
    error = float(np.max(np.abs(python - signs[:, None] * r)))
    subspace = float(np.max(np.abs(python.T @ python - r.T @ r)))
    sign_only = error <= tolerance
    return {
        "same_up_to_component_signs": sign_only,
        "same_retained_subspace": subspace <= tolerance,
        "signs_to_align_R_with_Python": signs.tolist() if sign_only else None,
        "maximum_loading_difference_after_sign_alignment": error,
        "maximum_retained_subspace_projector_difference": subspace,
    }


def r_rotations(values: pd.DataFrame, rank: int, engine: Path, rscript: str, directory: Path):
    matrix = directory / "training.csv"
    values.to_csv(matrix, index=False, float_format="%.17g")
    helper = Path(str(files("jev_factor").joinpath("reference_pca.R")))
    result = subprocess.run(
        [
            rscript,
            "--vanilla",
            str(helper),
            str(matrix),
            str(directory),
            str(rank),
            str(engine.resolve()),
        ],
        env={
            **os.environ,
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
        },
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Base-R PCA check failed: {result.stderr[-2000:]}")
    rotation = pd.read_csv(directory / "factor_rotation.csv")
    if list(rotation.columns[1:]) != list(values.columns) or list(rotation.component) != list(
        range(1, rank + 1)
    ):
        raise ValueError("R PCA feature/component ordering differs")
    return (
        rotation.iloc[:, 1:].to_numpy(),
        pd.read_csv(directory / "maf_rotation.csv"),
        pd.read_csv(directory / "native_split_weights.csv").weight.to_numpy(),
        (directory / "R_version.txt").read_text().strip(),
    )


@threadpool_limits.wrap(limits=1)
def audit_basis(
    source_run: Path, archive: Path, engine: Path, config: dict, *, rscript: str = "Rscript"
) -> dict:
    primary = audit_run(source_run, archive, config, rscript=rscript)
    if not primary["full_48_quarter_artifacts_verified"] or not primary["matches_declared_config"]:
        raise ValueError("Use the completed declared primary reconstruction")
    if config["factor_panel"] != "all":
        raise ValueError("This audit covers the frozen all-series primary basis")
    engine_metadata = ensure_engine(engine)
    source = json.loads((source_run / "manifest.json").read_text())
    data = load_quarterly(archive)
    records, split_weights = [], None
    refits = {j["group"]: j["fit_end"] for j in source["jobs"]}
    for group, endpoint in sorted(refits.items()):
        panel = data.panel.loc[config["panel_start"] : endpoint]
        representation = PastRepresentation(config["pca_rank"], config["outlier_iqr"]).fit(panel)
        z, _ = representation.transform(panel)
        with TemporaryDirectory(prefix="pca-basis-audit-") as scratch:
            rotation, maf, weights, r_version = r_rotations(
                z, config["pca_rank"], engine, rscript, Path(scratch)
            )
        cross = compare_rotations(representation.pca.components_, rotation)
        expected = {(j, k) for j in range(len(z.columns)) for k in (1, 2)}
        keys = list(zip(maf.series_index, maf.component, strict=True))
        if len(keys) != len(set(keys)) or set(keys) != expected:
            raise ValueError("R MAF component grid differs")
        maf_checks, negative = [], {1: [], 2: []}
        for j, name in enumerate(z):
            x = z[name].to_numpy()
            lagged = np.column_stack([x[8 - k : len(x) - k] for k in range(1, 9)])
            pca = PCA(n_components=2, svd_solver="full").fit(lagged)
            candidate = (
                maf.loc[maf.series_index.eq(j)].sort_values("component").iloc[:, 2:].to_numpy()
            )
            check = compare_rotations(pca.components_, candidate)
            maf_checks.append(check)
            if check["same_up_to_component_signs"]:
                for k, sign in enumerate(check["signs_to_align_R_with_Python"], start=1):
                    if sign < 0:
                        negative[k].append(j)
        if split_weights is None:
            split_weights = weights
        elif not np.array_equal(split_weights, weights):
            raise ValueError("Native split penalty changed between checks")
        records.append(
            {
                "group": group,
                "fit_end": endpoint,
                "training_panel_rows": len(panel),
                "active_series": len(z.columns),
                "active_series_order_sha256": hashlib.sha256(
                    json.dumps(list(z.columns)).encode()
                ).hexdigest(),
                "R_version": r_version,
                "cross_sectional_PCA": cross,
                "MAF_components_checked": len(maf),
                "all_MAFs_match_up_to_component_signs": all(
                    c["same_up_to_component_signs"] for c in maf_checks
                ),
                "all_MAFs_have_same_retained_subspace": all(
                    c["same_retained_subspace"] for c in maf_checks
                ),
                "MAF_maximum_sign_aligned_loading_difference": max(
                    c["maximum_loading_difference_after_sign_alignment"] for c in maf_checks
                ),
                "MAF_maximum_subspace_projector_difference": max(
                    c["maximum_retained_subspace_projector_difference"] for c in maf_checks
                ),
                "MAF1_opposite_R_sign_series_indices": negative[1],
                "MAF2_opposite_R_sign_series_indices": negative[2],
            }
        )
    return {
        "status": "PCA_convention_diagnostic_not_forecast_replication",
        "primary_manifest_sha256": _sha(source_run / "manifest.json"),
        "primary_integrity_checked": True,
        "primary_integration_source_sha256": primary["integration_source_sha256"],
        "external_engine": engine_metadata,
        "data": data.metadata,
        "audit_source_sha256": _sha(Path(__file__)),
        "R_helper_sha256": _sha(Path(str(files("jev_factor").joinpath("reference_pca.R")))),
        "basis_calculation_uses_only_each_refit_training_panel": True,
        "primary_inputs_or_forecasts_changed": False,
        "basis_selected_using_forecast_loss": False,
        "original_author_PCA_build_or_basis_recovered": False,
        "forecast_gap_attributed_to_orientation": False,
        "native_DV_fun_weights_for_ten_equal_split_losses": split_weights.tolist(),
        "native_DV_fun_maximum_reflection_asymmetry": float(
            np.max(np.abs(split_weights - split_weights[::-1]))
        ),
        "refits": records,
    }
