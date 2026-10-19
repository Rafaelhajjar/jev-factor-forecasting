"""Synthetic serialization and invariance contracts; no simulated paper results."""

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from jev_factor.orientation_sensitivity import (
    _sha,
    check_output,
    collect_outputs,
    prepare_jobs,
    sign_vector,
    verify_basis,
    verify_jobs,
)
from jev_factor.replication import LINEAR_X, linear_prediction


@pytest.fixture
def toy_artifacts(tmp_path):
    rng = np.random.default_rng(104)
    names = ["target", *[f"y_lag{k}" for k in range(1, 9)]]
    names += [f"F{j}_lag{k}" for j in (1, 2) for k in range(1, 9)]
    names += [f"series_{j:03d}_lag{k}" for j in range(2) for k in (1, 2)]
    names += [f"MAF_{j:03d}_{k}" for j in range(2) for k in (1, 2)] + ["trend"]
    matrix = pd.DataFrame(rng.normal(size=(78, len(names))), columns=names)
    matrix["target"] = 0.3 * matrix.y_lag1 + 0.4 * matrix.F1_lag1 + rng.normal(0, 0.1, 78)
    truth = matrix.target.iloc[70:].to_numpy().copy()
    matrix.loc[70:, "target"] = matrix.target.iloc[:70].mean()
    source_folder = tmp_path / "synthetic-source"
    source_folder.mkdir()
    matrix_path = source_folder / "input.csv"
    matrix.to_csv(matrix_path, index=False, float_format="%.17g")
    dates = pd.period_range("2003Q1", periods=8, freq="Q")
    targets = [
        {"target_date": str(d), "origin_date": str(d - 1), "actual": float(y)}
        for d, y in zip(dates, truth, strict=True)
    ]
    source = {"config": {"seeds": [101, 202], "pca_rank": 2}, "jobs": []}
    for seed in (101, 202):
        settings = source_folder / f"settings_{seed}.dcf"
        settings.write_text(
            f"ntrain: 70\nxnames: {','.join(LINEAR_X)}\ntrees: 100\nseed: {seed}\n"
            "prior: OLS\nstandardization: train_only\nblock: 8\n"
        )
        source["jobs"].append(
            {
                "group": 0,
                "seed": seed,
                "fit_end": "2002Q4",
                "matrix": str(matrix_path),
                "matrix_sha256": _sha(matrix_path),
                "settings": str(settings),
                "settings_sha256": _sha(settings),
                "targets": targets,
                "prediction_path": "unused.csv",
            }
        )
    record = {
        "group": 0,
        "fit_end": "2002Q4",
        "active_series": 2,
        "cross_sectional_PCA": {"signs_to_align_R_with_Python": [-1, 1]},
        "MAF1_opposite_R_sign_series_indices": [0],
        "MAF2_opposite_R_sign_series_indices": [1],
    }
    basis = {"refits": [record]}
    declaration = json.loads(Path("configs/mrf_r_basis_sensitivity.json").read_text())
    config = {**declaration, "trees": 2, "seeds": [101, 202]}
    output = tmp_path / "synthetic-orientation-contract-only"
    output.mkdir()
    jobs = prepare_jobs(source, basis, output, config, 1)
    manifest = {
        "config": config,
        "declaration": declaration,
        "jobs": jobs,
        "max_refits": 1,
        "full_declared_sensitivity": False,
    }
    ar = [f"y_lag{k}" for k in range(1, 5)]
    fa = ar + [f"F{j}_lag{k}" for j in (1, 2) for k in (1, 2)]
    forecasts = []
    for model, terms in (("AR4", ar), ("FA_AR", fa)):
        predictions = linear_prediction(matrix.iloc[:70], matrix.iloc[70:], terms)
        forecasts.extend(
            {**r, "model": model, "prediction": float(p)}
            for r, p in zip(targets, predictions, strict=True)
        )
    for job in jobs:
        signed = pd.read_csv(job["matrix"])
        coefs = pd.DataFrame(
            {"intercept": np.repeat(0.1, 8), **{name: np.repeat(0.2, 8) for name in LINEAR_X}}
        )
        coefs.insert(
            0,
            "prediction",
            coefs.intercept.to_numpy()
            + np.sum(coefs[LINEAR_X].to_numpy() * signed.iloc[70:][LINEAR_X].to_numpy(), axis=1),
        )
        coefs.to_csv(job["prediction_path"], index=False)
        Path(job["prediction_path"] + ".runtime.dcf").write_text(
            "R_version: synthetic-fixture-not-executed\nprior: OLS\nstandardization: train_only\n"
        )
    return source, basis, manifest, output, pd.DataFrame(forecasts)


def test_only_recorded_coordinates_change_and_linear_forecasts_are_invariant(toy_artifacts):
    source, basis, manifest, output, predictions = toy_artifacts
    checks = verify_jobs(manifest, source, basis, output, predictions)
    assert len(checks) == 1 and checks[0]["R_version"] is None
    assert max(checks[0]["maximum_absolute_differences"].values()) < 1e-12
    original = pd.read_csv(source["jobs"][0]["matrix"], float_precision="round_trip")
    signed = pd.read_csv(manifest["jobs"][0]["matrix"], float_precision="round_trip")
    np.testing.assert_array_equal(original.abs(), signed.abs())
    np.testing.assert_array_equal(original.target, signed.target)
    np.testing.assert_array_equal(original.y_lag1, signed.y_lag1)
    np.testing.assert_array_equal(original.series_000_lag1, signed.series_000_lag1)
    np.testing.assert_array_equal(-original.F1_lag8, signed.F1_lag8)
    assert _sha(Path(source["jobs"][0]["matrix"])) == source["jobs"][0]["matrix_sha256"]


@pytest.mark.parametrize("problem", ["target", "nonfactor", "setting", "path", "grid", "dates"])
def test_no_other_change_can_hide_behind_updated_checksums(toy_artifacts, problem):
    source, basis, original, output, predictions = toy_artifacts
    manifest = copy.deepcopy(original)
    job = manifest["jobs"][0]
    if problem in ("target", "nonfactor"):
        path = Path(job["matrix"])
        matrix = pd.read_csv(path)
        matrix.loc[0, "target" if problem == "target" else "series_000_lag1"] += 1
        matrix.to_csv(path, index=False)
        job["matrix_sha256"] = _sha(path)
    elif problem == "setting":
        path = Path(job["settings"])
        path.write_text(path.read_text().replace("block: 8", "block: 12"))
        job["settings_sha256"] = _sha(path)
    elif problem == "path":
        job["prediction_path"] = str(output.parent / "outside.csv")
    elif problem == "grid":
        manifest["jobs"].pop()
    else:
        job["targets"][0]["origin_date"] = "1999Q4"
    with pytest.raises(ValueError):
        verify_jobs(manifest, source, basis, output, predictions)


@pytest.mark.parametrize(
    "problem", ["cross", "duplicate_MAF", "out_of_range_MAF", "missing_coordinate"]
)
def test_invalid_sign_maps_are_rejected(toy_artifacts, problem):
    source, basis, _, _, _ = toy_artifacts
    record = copy.deepcopy(basis["refits"][0])
    columns = pd.read_csv(source["jobs"][0]["matrix"]).columns
    if problem == "cross":
        record["cross_sectional_PCA"]["signs_to_align_R_with_Python"] = [0, 1]
    elif problem == "duplicate_MAF":
        record["MAF1_opposite_R_sign_series_indices"] = [0, 0]
    elif problem == "out_of_range_MAF":
        record["MAF1_opposite_R_sign_series_indices"] = [999]
    else:
        columns = columns.drop("F1_lag8")
    with pytest.raises(ValueError):
        sign_vector(columns, record, 2)


@pytest.mark.parametrize("problem", ["sign", "source", "refit_grid"])
def test_asserted_basis_flags_cannot_replace_recomputed_native_maps(problem):
    observed = json.loads(Path("reports/mrf-pca-basis-audit.json").read_text())
    report = copy.deepcopy(observed)
    if problem == "sign":
        report["refits"][0]["cross_sectional_PCA"]["signs_to_align_R_with_Python"][0] *= -1
    elif problem == "source":
        report["primary_manifest_sha256"] = "not-the-observed-source"
    else:
        report["refits"].append(copy.deepcopy(report["refits"][0]))
    with pytest.raises(ValueError):
        verify_basis(report, observed)


def test_checkpoint_decomposition_and_partial_score_suppression(toy_artifacts):
    _, _, manifest, _, predictions = toy_artifacts
    _, error, _ = check_output(manifest["jobs"][0])
    assert error < 1e-12
    result, frames = collect_outputs(manifest, predictions)
    assert result["jobs_verified"] == 2
    assert result["partial_forest_scores_suppressed"]
    assert (
        result["metrics"]
        == result["published_ratio_comparisons"]
        == result["paired_orientation_effects"]
        == []
    )
    assert result["primary_result_replaced"] is False
    assert result["exact_author_pipeline_verified"] is False
    assert len(frames) == 40


def test_pilot_cannot_be_relabelled_as_full(toy_artifacts):
    _, _, manifest, _, predictions = toy_artifacts
    manifest["full_declared_sensitivity"] = True
    with pytest.raises(ValueError, match="Incomplete"):
        collect_outputs(manifest, predictions)
