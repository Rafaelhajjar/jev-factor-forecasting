"""PCA-only eligibility diagnostics; never select a panel using forecast loss."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from threadpoolctl import threadpool_limits

from jev_factor.pca_basis_audit import compare_rotations, r_rotations
from jev_factor.quarterly import PastRepresentation, load_quarterly
from jev_factor.replication import ensure_engine
from jev_factor.replication_audit import audit_run


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _quarter_index(index: pd.Index) -> None:
    if (
        not isinstance(index, pd.PeriodIndex)
        or not index.freqstr.startswith("Q")
        or not len(index)
        or not index.equals(pd.period_range(index[0], index[-1], freq=index.freq))
    ):
        raise ValueError("Expected consecutive unique quarterly rows")


@threadpool_limits.wrap(limits=1)
def subset_factors(
    completed: pd.DataFrame, membership: pd.Series, fit_end: pd.Period, rank: int = 5
) -> tuple[pd.DataFrame, PCA, list[str]]:
    """Use a frozen completed panel; do not refit cleaning or completion on a subset."""
    _quarter_index(completed.index)
    if not completed.columns.is_unique or not completed.columns.equals(membership.index):
        raise ValueError("Membership must match the completed series/order exactly")
    if not membership.isin([0, 1]).all():
        raise ValueError("Membership must be binary and nonmissing")
    if not np.isfinite(completed.to_numpy(dtype=float)).all():
        raise ValueError("Expected an already completed finite panel")
    selected = list(completed.columns[membership.eq(1)])
    if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
        raise ValueError("PCA rank must be a positive integer")
    if fit_end not in completed.index:
        raise ValueError("Fitting endpoint is absent from the panel")
    training = completed.loc[:fit_end, selected]
    if (
        training.shape[0] <= rank
        or training.shape[1] < rank
        or (training.std(ddof=1) <= 1e-12).any()
        or np.linalg.matrix_rank(training - training.mean()) < rank
    ):
        raise ValueError("Insufficient nonconstant training data for the requested rank")
    # Canonical memory layout avoids last-bit differences from pandas block order.
    training_values = np.ascontiguousarray(training.to_numpy(dtype=float))
    pca = PCA(n_components=rank, svd_solver="full").fit(training_values)
    scores = pd.DataFrame(
        pca.transform(np.ascontiguousarray(completed[selected].to_numpy(dtype=float))),
        index=completed.index,
        columns=[f"F{k + 1}" for k in range(rank)],
    )
    return scores, pca, selected


def replace_factor_lags(design: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    """Replace cross-sectional factor lags only, retaining the final target row."""
    _quarter_index(design.index)
    _quarter_index(scores.index)
    names = [f"F{k + 1}" for k in range(scores.shape[1])]
    if list(scores) != names or not names or not design.columns.is_unique:
        raise ValueError("Unexpected factor names or duplicate design columns")
    expected = [f"{name}_lag{k}" for name in names for k in range(1, 9)]
    actual = [n for n in design if n.startswith("F") and "_lag" in n]
    if set(actual) != set(expected):
        raise ValueError("Design must contain exactly eight lags of every factor")
    if not np.isfinite(scores.to_numpy(dtype=float)).all():
        raise ValueError("Nonfinite factor scores")
    # Extend before shifting: scores end at the final target's origin, not target.
    full_index = pd.period_range(scores.index[0], max(design.index[-1], scores.index[-1]), freq="Q")
    full = scores.reindex(full_index)
    lags = pd.DataFrame(
        {f"{name}_lag{k}": full[name].shift(k) for name in names for k in range(1, 9)}
    ).reindex(design.index)
    if not np.isfinite(lags.to_numpy()).all():
        raise ValueError("Factor history does not cover every target and lag")
    changed = design.copy()
    changed.loc[:, expected] = lags[expected]
    untouched = design.columns.difference(expected, sort=False)
    if not changed[untouched].equals(design[untouched]):
        raise ValueError("A non-factor entry changed")
    return changed


def score_geometry(original: np.ndarray, subset: np.ndarray) -> dict:
    """Compare training score geometry only; there is no outcome argument."""
    original, subset = np.asarray(original, dtype=float), np.asarray(subset, dtype=float)
    if (
        original.ndim != 2
        or original.shape != subset.shape
        or min(original.shape) < 2
        or not np.isfinite(original).all()
        or not np.isfinite(subset).all()
    ):
        raise ValueError("Expected matching finite score matrices")
    centered = [x - x.mean(axis=0) for x in (original, subset)]
    if any(np.linalg.matrix_rank(x) < x.shape[1] for x in centered):
        raise ValueError("Score matrices must have full column rank")
    correlations = np.corrcoef(original.T, subset.T)[: original.shape[1], original.shape[1] :]
    overlap = {}
    for n in sorted({2, original.shape[1]}):
        q0, q1 = (np.linalg.qr(x[:, :n])[0] for x in centered)
        overlap[str(n)] = np.clip(np.linalg.svd(q0.T @ q1, compute_uv=False), 0, 1).tolist()
    return {
        "absolute_training_score_correlations_all_by_subset": np.abs(correlations).tolist(),
        "training_score_subspace_principal_cosines": overlap,
    }


@threadpool_limits.wrap(limits=1)
def audit_eligibility(
    source_run: Path, archive: Path, engine: Path, config: dict, *, rscript: str = "Rscript"
) -> dict:
    primary = audit_run(source_run, archive, config, rscript=rscript)
    if (
        not primary["full_48_quarter_artifacts_verified"]
        or not primary["matches_declared_config"]
        or config["factor_panel"] != "all"
    ):
        raise ValueError("Use the completed all-series primary reconstruction")
    if config["pca_rank"] != 5:
        raise ValueError("This declaration retains the primary five-factor representation")
    engine_metadata = ensure_engine(engine)
    manifest = json.loads((source_run / "manifest.json").read_text())
    data = load_quarterly(archive)
    records = []
    jobs = {j["group"]: j for j in manifest["jobs"]}
    for group, job in sorted(jobs.items()):
        endpoint = pd.Period(job["fit_end"], freq="Q")
        through = pd.Period(job["targets"][-1]["target_date"], freq="Q")
        panel = data.panel.loc[config["panel_start"] : through - 1]
        representation = PastRepresentation(5, config["outlier_iqr"]).fit(panel.loc[:endpoint])
        if not representation.converged or not representation.active.all():
            raise ValueError("The frozen all-248 completion must converge and retain every series")
        z, all_scores = representation.transform(panel)
        subset, pca, selected = subset_factors(z, data.sw_membership, endpoint, rank=5)
        if len(z.columns) != 248 or len(selected) != 125:
            raise ValueError("Unexpected archived panel/subset cardinality")
        original = pd.read_csv(job["matrix"], float_precision="round_trip")
        original.index = pd.period_range(config["regression_start"], through, freq="Q")
        reconstructed = replace_factor_lags(original, all_scores)
        factor_names = [f"F{k}_lag{lag}" for k in range(1, 6) for lag in range(1, 9)]
        error = float(np.max(np.abs(original[factor_names] - reconstructed[factor_names])))
        if error > 1e-10:
            raise ValueError("Original factor lags differ from the completed-panel reconstruction")
        variant = replace_factor_lags(original, subset)
        untouched = original.columns.difference(factor_names, sort=False)
        if not np.array_equal(variant[untouched], original[untouched]):
            raise ValueError("A target, AR term, indicator, MAF or trend changed")
        training = z.loc[:endpoint, selected]
        with TemporaryDirectory(prefix="pca-eligibility-") as scratch:
            rotation, _, _, version = r_rotations(training, 5, engine, rscript, Path(scratch))
        native = compare_rotations(pca.components_, rotation)
        if not native["same_up_to_component_signs"]:
            raise ValueError("Subset PCA disagrees with independent base R beyond signs")
        records.append(
            {
                "group": group,
                "fit_end": str(endpoint),
                "training_panel_rows": int((z.index <= endpoint).sum()),
                "all_series": len(z.columns),
                "PCA_selected_series": selected,
                "original_matrix_sha256": job["matrix_sha256"],
                "original_factor_lag_reconstruction_maximum_error": error,
                "state_columns": len(original.columns) - 1,
                "factor_lag_columns_eligible_to_change": len(factor_names),
                "all_nonfactor_entries_exactly_preserved": True,
                "first_and_last_target_rows_verified": [
                    str(variant.index[0]),
                    str(variant.index[-1]),
                ],
                "subset_PCA_variance_ratios": pca.explained_variance_ratio_.tolist(),
                "subset_factor_loading_leaders": {
                    f"F{k + 1}": [selected[i] for i in np.argsort(-np.abs(row))[:10]]
                    for k, row in enumerate(pca.components_)
                },
                "all_series_factor_loading_leaders": {
                    f"F{k + 1}": list(z.columns[np.argsort(-np.abs(row))[:10]])
                    for k, row in enumerate(representation.pca.components_)
                },
                **score_geometry(
                    all_scores.loc[:endpoint].to_numpy(), subset.loc[:endpoint].to_numpy()
                ),
                "independent_R_subset_PCA_check": native,
                "R_version": version,
            }
        )
    return {
        "status": "training_only_PCA_eligibility_audit_not_forecast_result",
        "primary_manifest_sha256": _sha(source_run / "manifest.json"),
        "primary_artifact_integrity_verified": True,
        "primary_integration_source_sha256": primary["integration_source_sha256"],
        "audit_source_sha256": _sha(Path(__file__)),
        "audit_dependency_sha256": {
            name: _sha(Path(__file__).with_name(name))
            for name in ("pca_basis_audit.py", "reference_pca.R", "replication_audit.py")
        },
        "external_engine": engine_metadata,
        "data": data.metadata,
        "construction": (
            "125_series_PCA_on_frozen_all_248_completed_panel_with_full_state_preserved"
        ),
        "factor_basis_selection_uses_forecast_loss": False,
        "primary_artifacts_changed": False,
        "forests_fitted": 0,
        "new_forecast_losses_computed": False,
        "original_author_PCA_eligibility_recovered": False,
        "replication_completed": False,
        "refits": records,
    }
