"""Synthetic control-grid contracts; these are not macro forecasting evidence."""

import hashlib
import json
import os
import shutil
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from jev_factor import tvp_experiment as experiment

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "configs/mrf_tvp_faar.json").read_text())
PRIMARY = json.loads((ROOT / "configs/mrf_unemployment.json").read_text())


def _source_fixture(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    rng = np.random.default_rng(92)
    columns = ["target", *experiment.EQUATION, *[f"state{i}" for i in range(1033)]]
    rows = []
    jobs = []
    for group in range(6):
        dates = pd.period_range("2003Q1", periods=48, freq="Q")[8 * group : 8 * (group + 1)]
        fit_end = str(dates[0] - 1)
        folder = source / f"refit_{group}"
        folder.mkdir()
        matrix, settings = folder / "matrix.csv", folder / "settings.dcf"
        frame = pd.DataFrame(rng.normal(size=(48, 1042)), columns=columns)
        frame["target"] = 0.7 + frame.y_lag1 - frame.F1_lag1 + rng.normal(size=48)
        frame.iloc[40:, 0] = frame.target.iloc[:40].mean()  # Masked, never passed as future y.
        frame.to_csv(matrix, index=False, float_format="%.17g")
        settings.write_text("ntrain: 40\n")
        records = [
            {"target_date": str(d), "origin_date": str(d - 1), "actual": float(i % 3)}
            for i, d in enumerate(dates)
        ]
        for record in records:
            for model in (
                "AR4",
                "FA_AR",
                "FA_ARRF_seed101",
                "FA_ARRF_seed202",
                "FA_ARRF_seed303",
                "FA_ARRF_seed_mean_prediction",
            ):
                rows.append({**record, "model": model, "prediction": record["actual"] - 1})
        for seed in (101, 202, 303):
            jobs.append(
                {
                    "group": group,
                    "seed": seed,
                    "fit_end": fit_end,
                    "matrix": str(matrix.resolve()),
                    "settings": str(settings.resolve()),
                    "matrix_sha256": hashlib.sha256(matrix.read_bytes()).hexdigest(),
                    "settings_sha256": hashlib.sha256(settings.read_bytes()).hexdigest(),
                    "targets": records,
                }
            )
    pd.DataFrame(rows).to_csv(source / "predictions.csv", index=False, float_format="%.17g")
    manifest = {"jobs": jobs, "completed": True, "max_refits": None}
    (source / "manifest.json").write_text(json.dumps(manifest))
    return source, manifest


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("equation", ["y_lag1", "F1_lag1"]),
        ("factor_rule", "PCA125"),
        ("forecast_schedule", "every_quarter"),
        ("native_CV_seed", 19),
        ("native_CV_is_random_not_chronological", False),
        ("chosen_using_new_TV_FAAR_losses", True),
        ("reported_RMSE_over_AR4", 1.0),
        ("absolute_ratio_diagnostic_tolerance", 0.1),
        ("outer_seed_ensemble_not_applicable", 1),
    ],
)
def test_undeclared_TVP_choice_rejected(key, value):
    changed = deepcopy(CONFIG)
    changed[key] = value
    with pytest.raises(ValueError):
        experiment.validate_declaration(changed)


def test_primary_configuration_pinned_before_source_audit(tmp_path, monkeypatch):
    def must_not_run(*args, **kwargs):
        pytest.fail("Primary audit should not run for a changed declaration")

    monkeypatch.setattr(experiment, "audit_run", must_not_run)
    changed = {**PRIMARY, "pca_rank": 2}
    with pytest.raises(ValueError, match="unchanged"):
        experiment._source(tmp_path, tmp_path / "data.zip", changed, "Rscript")


@pytest.mark.parametrize("limit", [0, -1, 7, True])
def test_invalid_refit_limit(tmp_path, limit):
    with pytest.raises(ValueError):
        experiment.jobs_for({"jobs": []}, tmp_path, limit)


def test_equation_rows_use_training_targets_only_and_grid_is_preserved(tmp_path):
    _, source = _source_fixture(tmp_path)
    jobs = experiment.jobs_for(source, tmp_path / "run", None)
    assert len(jobs) == 6
    assert [j["group"] for j in jobs] == list(range(6))
    x, y, future = experiment._arrays(jobs[0])
    assert x.shape == (40, 8) and y.shape == (40,) and future.shape == (8, 8)
    original = pd.read_csv(jobs[0]["matrix"], float_precision="round_trip")
    np.testing.assert_array_equal(x, original[experiment.EQUATION].iloc[:40])
    bad = deepcopy(source)
    bad["jobs"] += [source["jobs"][0]]
    with pytest.raises(ValueError):
        experiment.jobs_for(bad, tmp_path / "bad", None)
    Path(jobs[0]["settings"]).write_text("ntrain: 39\n")
    with pytest.raises(ValueError, match="changed"):
        experiment._arrays(jobs[0])


def _synthetic_completed(tmp_path, monkeypatch, limit=None, missing_last=False):
    source_path, source = _source_fixture(tmp_path)
    output = tmp_path / "run"
    output.mkdir()
    jobs = experiment.jobs_for(source, output, limit)
    for j in jobs[:-1] if missing_last else jobs:
        folder = Path(j["native_directory"])
        folder.mkdir()
        (folder / "audit.json").write_text("{}")
        pd.DataFrame({"prediction": [r["actual"] - 1.19 for r in j["targets"]]}).to_csv(
            folder / "predictions.csv", index=False, float_format="%.17g"
        )
    monkeypatch.setattr(
        experiment,
        "check_fit",
        lambda j: {
            "runtime": {"R_version": "synthetic test only"},
            "GARCH_optimizer_converged": True,
        },
    )
    return {"jobs": jobs, "source_run": str(source_path), "max_refits": limit}


def test_full_six_fit_grid_and_single_deterministic_control_gate(tmp_path, monkeypatch):
    manifest = _synthetic_completed(tmp_path, monkeypatch)
    predictions, result = experiment.collect(manifest)
    assert len(predictions) == 336
    assert predictions.groupby("model").size().eq(48).all()
    assert result["fits_verified"] == 6
    assert result["TV_FAAR_within_ratio_tolerance"] is True
    assert result["FA_ARRF_replication_established"] is False
    assert result["exact_author_table_pipeline_verified"] is False


@pytest.mark.parametrize("missing_last", [False, True])
def test_reduced_or_missing_fit_withholds_scores(tmp_path, monkeypatch, missing_last):
    manifest = _synthetic_completed(
        tmp_path, monkeypatch, limit=None if missing_last else 1, missing_last=missing_last
    )
    _, result = experiment.collect(manifest)
    assert result["partial_scores_suppressed"]
    assert result["metrics"] == []
    assert result["TV_FAAR_within_ratio_tolerance"] is None


def test_native_runtime_change_is_not_silently_accepted(tmp_path, monkeypatch):
    manifest = _synthetic_completed(tmp_path, monkeypatch)
    monkeypatch.setattr(
        experiment,
        "check_fit",
        lambda j: {
            "runtime": {"R_version": f"changed-{j['group']}"},
            "GARCH_optimizer_converged": True,
        },
    )
    with pytest.raises(ValueError, match="runtime"):
        experiment.collect(manifest)


@pytest.mark.skipif(
    not os.environ.get("JEV_TVP_REFERENCE_ENGINE")
    or not os.environ.get("JEV_MRF_R_LIBRARY")
    or not shutil.which("Rscript"),
    reason="Requires actual pinned TVP engine and prepared R library",
)
def test_actual_native_quarterly_integration_on_synthetic_source_boundary(tmp_path, monkeypatch):
    source_path, source = _source_fixture(tmp_path)
    # Only the source boundary is synthetic. Run the actual R entry point and final native refit.
    monkeypatch.setattr(experiment, "_source", lambda *args: source)
    output = tmp_path / "native-pilot"
    engine = Path(os.environ["JEV_TVP_REFERENCE_ENGINE"])
    library = Path(os.environ["JEV_MRF_R_LIBRARY"])
    result = experiment.run_comparison(
        source_path,
        tmp_path / "unused.zip",
        engine,
        library,
        output,
        CONFIG,
        PRIMARY,
        max_refits=1,
    )
    assert result["fits_verified"] == 1 and result["metrics"] == []
    audit = experiment.audit_comparison(
        output,
        tmp_path / "unused.zip",
        engine,
        library,
        CONFIG,
        PRIMARY,
        allow_partial=True,
    )
    assert audit["deterministic_native_refits"] == [
        {"fit_end": "2002Q4", "all_native_artifacts_reproduced": True}
    ]
    # Valid checkpoints resume without refitting.
    monkeypatch.setattr(
        experiment,
        "run_native_tvp",
        lambda *a, **kw: pytest.fail("Do not refit a valid checkpoint"),
    )
    repeated = experiment.run_comparison(
        source_path,
        tmp_path / "unused.zip",
        engine,
        library,
        output,
        CONFIG,
        PRIMARY,
        max_refits=1,
        resume=True,
    )
    assert repeated == result
    manifest_path = output / "manifest.json"
    changed_manifest = json.loads(manifest_path.read_text())
    changed_manifest["completed"] = False
    manifest_path.write_text(json.dumps(changed_manifest))
    with pytest.raises(ValueError, match="completion marker"):
        experiment.audit_comparison(
            output,
            tmp_path / "unused.zip",
            engine,
            library,
            CONFIG,
            PRIMARY,
            allow_partial=True,
        )
    altered = deepcopy(CONFIG)
    altered["reported_RMSE_over_AR4"] = 1.0
    with pytest.raises(ValueError):
        experiment.run_comparison(
            source_path,
            tmp_path / "unused.zip",
            engine,
            library,
            output,
            altered,
            PRIMARY,
            max_refits=1,
            resume=True,
        )
