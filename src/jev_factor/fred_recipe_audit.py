"""Training-only validation of the pinned FRED completion recipe, not MRF outcomes."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from jev_factor.fred_recipe import FredRecipeRepresentation
from jev_factor.pca_basis_audit import compare_rotations
from jev_factor.pca_eligibility import score_geometry, subset_factors
from jev_factor.quarterly import PastRepresentation, load_quarterly
from jev_factor.replication_audit import _dcf, audit_run

CODE_SHA256 = "cbb4b5f1e9549e506bf12979643422c3fb6fda108f1a94fd5f998a0536399036"
SOURCE_PAGE = "https://www.stlouisfed.org/research/economists/mccracken/fred-databases"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_code_archive(path: Path) -> dict:
    if _sha(path) != CODE_SHA256:
        raise ValueError("Use the inspected checksum-pinned FRED code archive")
    with zipfile.ZipFile(path) as archive:
        names = ["fredfactors.m", "factors_em.m", "remove_outliers.m"]
        members = {
            name: hashlib.sha256(archive.read("fred-database_code/" + name)).hexdigest()
            for name in names
        }
    return {
        "source_page": SOURCE_PAGE,
        "archive_sha256": CODE_SHA256,
        "members_sha256": members,
        "source_driver_is_monthly_FRED_MD_not_the_MRF_runner": True,
        "original_MATLAB_executed": False,
    }


def r_recipe_check(
    frame: pd.DataFrame, fitted: FredRecipeRepresentation, rscript: str, directory: Path
) -> dict:
    if fitted.outlier_iqr != 10:
        raise ValueError("The independent source-recipe check fixes the 10-IQR rule")
    path = directory / "raw_training.csv"
    frame.to_csv(path, index=False, float_format="%.17g")
    helper = Path(__file__).with_name("reference_fred_em.R")
    result = subprocess.run(
        [
            rscript,
            "--vanilla",
            str(helper),
            str(path),
            str(directory),
            str(fitted.kmax),
            str(fitted.max_iter),
            str(fitted.tolerance),
            str(fitted.factor_rank),
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
        raise RuntimeError(f"Independent R FRED-recipe check failed: {result.stderr[-2000:]}")
    tables = {
        name: pd.read_csv(directory / (name + ".csv"), float_precision="round_trip")
        for name in ("cleaned", "filled", "standardized")
    }
    if any(list(x) != list(frame) or x.shape != frame.shape for x in tables.values()):
        raise ValueError("Independent R completion feature/row layout differs")
    history = pd.read_csv(directory / "history.csv")
    metadata = _dcf(directory / "metadata.dcf")
    em = fitted.em
    if (
        list(history.iteration) != list(range(em.iterations + 1))
        or list(history["rank"]) != em.rank_history
        or int(metadata["iterations"]) != em.iterations
        or metadata["converged"] != ("TRUE" if em.converged else "FALSE")
        or metadata["at_iteration_cap"] != ("TRUE" if em.at_iteration_cap else "FALSE")
        or metadata["stopping_reason"] != em.stopping_reason
        or int(metadata["training_outliers"]) != fitted.training_outliers
    ):
        raise ValueError("Independent R rank path or stopping status differs")
    expected_errors = np.array([np.nan if v is None else v for v in em.errors])
    if not np.allclose(history.error, expected_errors, rtol=1e-7, atol=1e-10, equal_nan=True):
        raise ValueError("Independent R relative-reconstruction history differs")
    if not np.array_equal(np.isnan(tables["cleaned"]), np.isnan(fitted.cleaned_training)):
        raise ValueError("Independent R cleaning/missing-cell mask differs")
    finite = np.isfinite(fitted.cleaned_training)
    if not np.allclose(
        tables["cleaned"].to_numpy()[finite],
        fitted.cleaned_training[finite],
        rtol=1e-12,
        atol=1e-12,
    ):
        raise ValueError("Independent R cleaned observations differ")
    fill_error = float(np.max(np.abs((tables["filled"].to_numpy() - em.filled) / em.std)))
    z_error = float(np.max(np.abs(tables["standardized"].to_numpy() - em.standardized)))
    if max(fill_error, z_error) > 1e-8:
        raise ValueError("Independent R completed values differ in standardized units")
    rotation = pd.read_csv(directory / "rotation.csv")
    if list(rotation.columns[1:]) != list(frame):
        raise ValueError("Independent R final loading order differs")
    loading_check = compare_rotations(fitted.pca.components_, rotation.iloc[:, 1:].to_numpy())
    if not loading_check["same_up_to_component_signs"]:
        raise ValueError("Independent R final PCA differs beyond signs")
    return {
        "status": "independent_R_recipe_agrees_not_execution_of_MATLAB",
        "R_version": metadata["R_version"],
        "maximum_filled_difference_in_final_std_units": fill_error,
        "maximum_standardized_matrix_difference": z_error,
        "rank_path_and_stopping_reason_match": True,
        "final_PCA": loading_check,
    }


@threadpool_limits.wrap(limits=1)
def audit_recipe(
    source_run: Path, archive: Path, code_archive: Path, config: dict, *, rscript: str = "Rscript"
) -> dict:
    source = verify_code_archive(code_archive)
    primary = audit_run(source_run, archive, config, rscript=rscript)
    if (
        not primary["full_48_quarter_artifacts_verified"]
        or not primary["matches_declared_config"]
        or config["factor_panel"] != "all"
        or config["pca_rank"] != 5
    ):
        raise ValueError("Use the frozen complete all-248/five-PC primary reconstruction")
    data = load_quarterly(archive)
    names = list(data.panel.columns[data.sw_membership.eq(1)])
    if len(names) != 125:
        raise ValueError("Unexpected historical-subset membership")
    manifest = json.loads((source_run / "manifest.json").read_text())
    refits = {j["group"]: j["fit_end"] for j in manifest["jobs"]}
    records = []
    for group, endpoint in sorted(refits.items()):
        panel = data.panel.loc[config["panel_start"] : endpoint]
        selected = panel[names]
        fitted = FredRecipeRepresentation().fit(selected)
        with TemporaryDirectory(prefix="fred-recipe-audit-") as scratch:
            independent = r_recipe_check(selected, fitted, rscript, Path(scratch))
        original = PastRepresentation(5, config["outlier_iqr"]).fit(panel)
        z, _ = original.transform(panel)
        conditional, _, old_names = subset_factors(z, data.sw_membership, pd.Period(endpoint), 5)
        if old_names != names:
            raise ValueError("Conditional PCA125 series/order changed")
        _, scores = fitted.transform(selected)
        em = fitted.em
        records.append(
            {
                "group": group,
                "fit_end": endpoint,
                "training_rows": len(selected),
                "selected_series_count": len(names),
                "training_missing_or_outlier_cells": int(np.isnan(fitted.cleaned_training).sum()),
                "training_outliers": fitted.training_outliers,
                "completion_rank_path": em.rank_history,
                "relative_reconstruction_error_path": em.errors,
                "completion_rank_final": len(em.completion_basis),
                "EM_iterations": em.iterations,
                "EM_converged": em.converged,
                "at_source_iteration_cap": em.at_iteration_cap,
                "stopping_reason": em.stopping_reason,
                "state_factor_count": 5,
                "small_equation_factor_count": 2,
                "observed_cleaned_cells_exactly_preserved": bool(
                    np.array_equal(
                        em.filled[np.isfinite(fitted.cleaned_training)],
                        fitted.cleaned_training[np.isfinite(fitted.cleaned_training)],
                    )
                ),
                "source_recipe_PCA_loading_leaders": {
                    f"F{k + 1}": [names[j] for j in np.argsort(-np.abs(row))[:10]]
                    for k, row in enumerate(fitted.pca.components_)
                },
                **score_geometry(conditional.to_numpy(), scores.to_numpy()),
                "independent_R_check": independent,
            }
        )
    return {
        "status": "training_only_FRED_recipe_audit_not_forecast_result",
        "source": source,
        "recipe": {
            "DEMEAN": 2,
            "criterion_code": 2,
            "kmax": 8,
            "max_iterations": 50,
            "relative_error_threshold": 1e-6,
            "outlier_IQR_multiplier": 10,
            "PCs_retained_for_MRF_state": 5,
        },
        "primary_manifest_sha256": _sha(source_run / "manifest.json"),
        "primary_artifact_integrity_reverified": True,
        "primary_integration_source_sha256": primary["integration_source_sha256"],
        "code_source_sha256": _sha(Path(__file__).with_name("fred_recipe.py")),
        "auditor_source_sha256": _sha(Path(__file__)),
        "R_helper_sha256": _sha(Path(__file__).with_name("reference_fred_em.R")),
        "selected_series_order": names,
        "refits": records,
        "original_MATLAB_or_Octave_executed": False,
        "independent_R_Gram_eigen_vs_Python_direct_SVD": True,
        "new_forest_fits": 0,
        "new_forecast_losses_computed": False,
        "primary_or_existing_sensitivity_artifacts_changed": False,
        "original_MRF_author_preprocessing_recovered": False,
        "replication_completed": False,
    }
