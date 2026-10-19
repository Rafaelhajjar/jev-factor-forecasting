"""Synthetic source-boundary integration, not an unemployment result."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("torch")

from jev_factor import nn_experiment as experiment  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "configs/mrf_nn.json").read_text())
PRIMARY = json.loads((ROOT / "configs/mrf_unemployment.json").read_text())


def _source_fixture(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    rng = np.random.default_rng(87)
    rows, jobs = [], []
    for group in range(6):
        dates = pd.period_range("2003Q1", periods=48, freq="Q")[8 * group : 8 * (group + 1)]
        matrix, settings = source / f"matrix_{group}.csv", source / f"settings_{group}.dcf"
        frame = pd.DataFrame(
            rng.normal(size=(48, 1042)), columns=["target", *[f"state{i}" for i in range(1041)]]
        )
        frame["target"] = 0.02 * frame.state0 + rng.normal(size=48) * 0.02
        frame.iloc[40:, 0] = frame.target.iloc[:40].mean()
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
                    "fit_end": str(dates[0] - 1),
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
        ("members", 11),
        ("members", True),
        ("seeds", [303, 101]),
        ("seeds", [101, 101]),
        ("seeds", [12]),
        ("state_rule", "PCA125"),
        ("reported_RMSE_over_AR4", 0.7),
        ("absolute_ratio_diagnostic_tolerance", 0.1),
        ("chosen_using_new_NN_losses", True),
        ("outer_seed_mean_excluded_from_diagnostic", False),
    ],
)
def test_undeclared_control_change_rejected(key, value):
    changed = deepcopy(CONFIG)
    changed[key] = value
    with pytest.raises(ValueError):
        experiment.validate_config(changed)


def test_changed_primary_rejected_before_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(
        experiment, "audit_run", lambda *a, **kw: pytest.fail("Do not audit a changed primary")
    )
    with pytest.raises(ValueError, match="unchanged"):
        experiment.source_inputs(
            tmp_path, tmp_path / "data.zip", {**PRIMARY, "pca_rank": 2}, "Rscript"
        )


@pytest.mark.parametrize("limit", [0, -1, 7, True])
def test_invalid_refit_limit(tmp_path, limit):
    with pytest.raises(ValueError):
        experiment.jobs_for({"jobs": []}, tmp_path, CONFIG, limit)


def test_complete_grid_preserves_all_inputs_and_rejects_changes(tmp_path):
    _, source = _source_fixture(tmp_path)
    jobs = experiment.jobs_for(source, tmp_path / "out", CONFIG, None)
    assert len(jobs) == 18
    assert sum(len(j["member_directories"]) for j in jobs) == 180
    x, y, future = experiment.equation_arrays(jobs[0])
    assert x.shape == (40, 1041) and y.shape == (40,) and future.shape == (8, 1041)
    frame = pd.read_csv(jobs[0]["matrix"], float_precision="round_trip")
    np.testing.assert_array_equal(x, frame.iloc[:40, 1:])
    np.testing.assert_array_equal(y, frame.target.iloc[:40])
    duplicate = {**source, "jobs": [*source["jobs"], source["jobs"][0]]}
    with pytest.raises(ValueError, match="grid"):
        experiment.jobs_for(duplicate, tmp_path / "bad", CONFIG, None)
    Path(jobs[0]["settings"]).write_text("ntrain: 39\n")
    with pytest.raises(ValueError, match="changed"):
        experiment.equation_arrays(jobs[0])


def _fake_completed(tmp_path, monkeypatch, config=None, limit=None, missing_last=False):
    source_path, source = _source_fixture(tmp_path)
    config = deepcopy(CONFIG if config is None else config)
    output = tmp_path / "out"
    output.mkdir()
    jobs = experiment.jobs_for(source, output, config, limit)
    for job in jobs:
        for i, folder in enumerate(job["member_directories"]):
            if missing_last and job is jobs[-1] and i == len(job["member_directories"]) - 1:
                continue
            directory = Path(folder)
            directory.mkdir(parents=True)
            ratio = {101: 0.79, 202: 0.80, 303: 0.81}[job["seed"]] + (i - 4.5) * 0.001
            (directory / "member.json").write_text(
                json.dumps({"forecast_prediction": [r["actual"] - ratio for r in job["targets"]]})
            )

    def check(job, member, training, **kw):
        record = json.loads((Path(job["member_directories"][member]) / "member.json").read_text())
        return record["forecast_prediction"], {
            "group": job["group"],
            "outer_seed": job["seed"],
            "member": member,
            "deterministic_refit_verified": False,
        }

    monkeypatch.setattr(experiment, "check_member", check)
    return {
        "declaration": CONFIG,
        "config": config,
        "max_refits": limit,
        "jobs": jobs,
        "source_run": str(source_path),
    }


def test_full_180_member_prediction_average_and_all_seed_gate(tmp_path, monkeypatch):
    manifest = _fake_completed(tmp_path, monkeypatch)
    predictions, members, result = experiment.collect(manifest)
    assert len(predictions) == 480 and len(members) == 1440
    assert predictions.groupby("model").size().eq(48).all()
    assert result["ensemble_fits_verified"] == 18 and result["members_verified"] == 180
    assert result["all_seed_ensembles_within_ratio_tolerance"] is True
    assert result["FA_ARRF_replication_established"] is False
    assert result["published_ratio_comparisons"][-1]["outer_seed_mean_excluded_from_diagnostic"]
    for seed, ratio in ((101, 0.79), (202, 0.80), (303, 0.81)):
        row = next(r for r in result["metrics"] if r["model"] == f"NN_seed{seed}")
        assert row["RMSE_over_AR4"] == pytest.approx(ratio)


@pytest.mark.parametrize("kind", ["one_refit", "one_member", "one_epoch", "missing_member"])
def test_partial_comparisons_do_not_publish_accuracy(tmp_path, monkeypatch, kind):
    config = deepcopy(CONFIG)
    if kind == "one_member":
        config["members"] = 1
    if kind == "one_epoch":
        config["training"]["epochs"] = 1
    manifest = _fake_completed(
        tmp_path,
        monkeypatch,
        config,
        limit=1 if kind == "one_refit" else None,
        missing_last=kind == "missing_member",
    )
    _, _, result = experiment.collect(manifest)
    assert result["partial_scores_suppressed"]
    assert result["metrics"] == [] and result["published_ratio_comparisons"] == []
    assert result["all_seed_ensembles_within_ratio_tolerance"] is None


def test_actual_torch_quarterly_pilot_audit_resume_and_changed_artifact_guards(
    tmp_path, monkeypatch
):
    source_path, source = _source_fixture(tmp_path)
    # Only the source boundary is synthetic. Every NN weight/gradient/epoch is real.
    monkeypatch.setattr(experiment, "source_inputs", lambda *a, **kw: source)
    output = tmp_path / "pilot"
    args = (source_path, tmp_path / "unused.zip", output, CONFIG, PRIMARY)
    result = experiment.run_comparison(*args, members=1, epochs=2, seeds=[101], max_refits=1)
    assert result["members_verified"] == 1 and result["metrics"] == []
    audit = experiment.audit_comparison(
        output, tmp_path / "unused.zip", CONFIG, PRIMARY, allow_partial=True
    )
    assert len(audit["deterministic_member_refits"]) == 1
    assert audit["deterministic_member_refits"][0]["all_parameters_and_training_history_identical"]
    with pytest.raises(ValueError, match="180"):
        experiment.audit_comparison(output, tmp_path / "unused.zip", CONFIG, PRIMARY)
    monkeypatch.setattr(
        experiment, "fit_member", lambda *a, **kw: pytest.fail("Do not retrain a valid checkpoint")
    )
    repeated = experiment.run_comparison(
        *args, members=1, epochs=2, seeds=[101], max_refits=1, resume=True
    )
    assert repeated == result
    data = pd.read_csv(output / "member_predictions.csv")
    data.loc[0, "origin_date"] = "2000Q1"
    data.to_csv(output / "member_predictions.csv", index=False)
    with pytest.raises(ValueError, match="identity"):
        experiment.audit_comparison(
            output, tmp_path / "unused.zip", CONFIG, PRIMARY, allow_partial=True
        )


def test_prepare_only_does_not_train_or_score(tmp_path, monkeypatch):
    source_path, source = _source_fixture(tmp_path)
    monkeypatch.setattr(experiment, "source_inputs", lambda *a, **kw: source)
    monkeypatch.setattr(
        experiment, "fit_member", lambda *a, **kw: pytest.fail("No training in preparation")
    )
    output = tmp_path / "prepare"
    result = experiment.run_comparison(
        source_path, tmp_path / "unused.zip", output, CONFIG, PRIMARY, prepare_only=True
    )
    assert result["members_planned"] == 180
    assert not (output / "predictions.csv").exists()
    assert not (output / "metrics.csv").exists()


def test_outer_seed_mean_cannot_rescue_failed_individual_ensembles(tmp_path, monkeypatch):
    manifest = _fake_completed(tmp_path, monkeypatch)
    for job in manifest["jobs"]:
        ratio = {101: 0.75, 202: 0.80, 303: 0.85}[job["seed"]]
        for folder in job["member_directories"]:
            (Path(folder) / "member.json").write_text(
                json.dumps({"forecast_prediction": [r["actual"] - ratio for r in job["targets"]]})
            )
    _, _, result = experiment.collect(manifest)
    assert result["all_seed_ensembles_within_ratio_tolerance"] is False
    assert result["published_ratio_comparisons"][-1]["within_ratio_tolerance"] is True
    assert result["published_ratio_comparisons"][-1]["outer_seed_mean_excluded_from_diagnostic"]


def test_forecast_target_placeholders_cannot_enter_NN_training_arrays(tmp_path):
    _, source = _source_fixture(tmp_path)
    job = experiment.jobs_for(source, tmp_path / "out", CONFIG, None)[0]
    before = experiment.equation_arrays(job)
    frame = pd.read_csv(job["matrix"], float_precision="round_trip")
    frame.iloc[job["ntrain"] :, 0] += 1e6
    frame.to_csv(job["matrix"], index=False, float_format="%.17g")
    # A synthetic boundary probe only: the real primary audit would reject this changed source.
    job["matrix_sha256"] = hashlib.sha256(Path(job["matrix"]).read_bytes()).hexdigest()
    after = experiment.equation_arrays(job)
    for actual, expected in zip(after, before, strict=True):
        np.testing.assert_array_equal(actual, expected)
