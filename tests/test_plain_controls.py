"""Synthetic artifact contracts with actual CART fits, not macro performance evidence."""

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from jev_factor import plain_controls as control


def declaration():
    return json.loads(Path("configs/mrf_plain_controls.json").read_text())


def frame():
    rng = np.random.default_rng(762)
    values = pd.DataFrame(
        rng.normal(size=(78, 9)),
        columns=[
            "target",
            "y_lag1",
            "y_lag2",
            "y_lag3",
            "y_lag4",
            "F1_lag1",
            "F1_lag2",
            "F2_lag1",
            "trend",
        ],
    )
    values.target = (
        0.3 * values.y_lag1 + 0.2 * values.y_lag2 + values.F1_lag1**2 + rng.normal(0, 0.1, 78)
    )
    values.trend = np.arange(len(values))
    values.loc[70:, "target"] = values.target.iloc[:70].mean()
    return values


@pytest.mark.parametrize("model", control.MODELS)
def test_saved_tree_traversal_means_and_averaging_match_actual_cart(model):
    config = {**declaration(), "trees": 3, "seeds": [101]}
    values = frame()
    payload, predictions = control.fit_payload(values, 70, model, 101, config)
    reconstructed, error = control.verify_payload(payload, values, 70, model, 101, config)
    np.testing.assert_allclose(predictions, reconstructed, rtol=0, atol=1e-12)
    assert error < 1e-12 and len(payload["trees"]) == 3
    np.testing.assert_allclose(
        predictions.prediction,
        predictions.base_prediction + predictions.nonlinear_prediction,
        atol=1e-12,
    )
    if model == "RF_MAF":
        assert payload["preprocessing"]["base_coefficients"] == []
        assert predictions.base_prediction.eq(0).all()
    else:
        beta = np.linalg.lstsq(
            np.c_[np.ones(70), values.iloc[:70][["y_lag1", "y_lag2"]]],
            values.target.iloc[:70],
            rcond=None,
        )[0]
        np.testing.assert_array_equal(payload["preprocessing"]["base_coefficients"], beta)


@pytest.mark.parametrize("model", control.MODELS)
def test_future_targets_and_later_covariates_cannot_refit_or_change_earlier_predictions(model):
    config = {**declaration(), "trees": 2, "seeds": [101]}
    original = frame()
    payload, predictions = control.fit_payload(original, 70, model, 101, config)
    changed = original.copy()
    changed.loc[70:, "target"] = 1e12
    altered, future_y = control.fit_payload(changed, 70, model, 101, config)
    assert altered == payload
    np.testing.assert_array_equal(predictions, future_y)
    changed.iloc[71:, 1:] *= 1e5
    altered, future_x = control.fit_payload(changed, 70, model, 101, config)
    assert altered == payload
    np.testing.assert_array_equal(predictions.iloc[0], future_x.iloc[0])


@pytest.mark.parametrize("problem", ["row_count", "names", "constant", "infinite", "model"])
def test_fit_inputs_reject_invalid_layout_or_training_state(problem):
    values, ntrain, model = frame(), 70, "RF_MAF"
    if problem == "row_count":
        ntrain = 78
    elif problem == "names":
        values = values.rename(columns={"y_lag1": "wrong"})
    elif problem == "constant":
        values["trend"] = 1
    elif problem == "infinite":
        values.iloc[0, 2] = np.inf
    else:
        model = "different"
    with pytest.raises(ValueError):
        control.fit_inputs(values, ntrain, model)


@pytest.mark.parametrize(
    "problem", ["recipe", "gate", "source_cell", "loss_selection", "seeds", "trees"]
)
def test_config_cannot_change_the_scientific_comparison(problem):
    config = declaration()
    if problem == "recipe":
        config["forest"]["min_leaf"] = 5
    elif problem == "gate":
        config["absolute_ratio_diagnostic_tolerance"] = 0.1
    elif problem == "source_cell":
        config["reported_ratios"]["RF_MAF"] = 0.9
    elif problem == "loss_selection":
        config["selected_using_new_control_test_losses"] = True
    elif problem == "seeds":
        config["seeds"] = [101, 101]
    else:
        config["trees"] = 101
    with pytest.raises(ValueError):
        control.validate_config(config)


@pytest.fixture
def artifacts(tmp_path):
    def create(groups=1, seeds=(101,), full=False):
        source_folder, output = tmp_path / f"source-{groups}", tmp_path / f"run-{groups}"
        source_folder.mkdir()
        output.mkdir()
        config = declaration() if full else {**declaration(), "trees": 2, "seeds": list(seeds)}
        source, reference = {"jobs": []}, []
        for group in range(groups):
            values = frame()
            path = source_folder / f"matrix_{group}.csv"
            values.to_csv(path, index=False, float_format="%.17g")
            dates = pd.period_range(pd.Period("2003Q1") + group * 8, periods=8, freq="Q")
            # Deliberately artificial source forecasts/outcomes for grid contracts.
            targets = [
                {"target_date": str(d), "origin_date": str(d - 1), "actual": float(y)}
                for d, y in zip(dates, np.arange(8) / 10, strict=True)
            ]
            for model, offset in (
                ("AR4", 0.5),
                ("FA_AR", 0.3),
                ("FA_ARRF_seed_mean_prediction", 0.4),
            ):
                reference.extend(
                    {**r, "model": model, "prediction": r["actual"] + offset} for r in targets
                )
            for seed in seeds:
                settings = source_folder / f"settings_{group}_{seed}.dcf"
                settings.write_text(f"ntrain: 70\nseed: {seed}\n")
                source["jobs"].append(
                    {
                        "group": group,
                        "seed": seed,
                        "fit_end": str(dates[0] - 1),
                        "targets": targets,
                        "matrix": str(path),
                        "matrix_sha256": control._sha(path),
                        "settings": str(settings),
                        "settings_sha256": control._sha(settings),
                    }
                )
                reference.extend(
                    {**r, "model": f"FA_ARRF_seed{seed}", "prediction": r["actual"] + 0.4}
                    for r in targets
                )
        manifest = {
            "config": config,
            "declaration": declaration(),
            "max_refits": None if full else groups,
            "full_declared_comparison": full,
            "completed": True,
            "jobs": control.jobs_for(source, config, output, None if full else groups),
        }
        checks = control.verify_inputs(manifest, source, output, None)
        (output / "linear_checks.json").write_text(json.dumps(checks))
        for job in manifest["jobs"]:
            values = pd.read_csv(job["matrix"], float_precision="round_trip")
            payload, predictions = control.fit_payload(
                values, 70, job["model"], job["seed"], config
            )
            Path(job["tree_path"]).parent.mkdir(exist_ok=True)
            Path(job["tree_path"]).write_text(json.dumps(payload, allow_nan=False))
            predictions.to_csv(job["prediction_path"], index=False, float_format="%.17g")
        return source, manifest, output, pd.DataFrame(reference)

    return create


@pytest.mark.parametrize(
    "problem", ["prediction", "mean", "rows", "node", "preprocessing", "backend"]
)
def test_independent_payload_checks_reject_changed_artifacts(artifacts, problem):
    _, manifest, _, _ = artifacts()
    job = manifest["jobs"][0]
    if problem == "prediction":
        path = Path(job["prediction_path"])
        values = pd.read_csv(path)
        values.loc[0, "prediction"] += 1
        values.to_csv(path, index=False)
    else:
        path = Path(job["tree_path"])
        payload = json.loads(path.read_text())
        if problem == "mean":
            payload["trees"][0]["value"][0] += 1
        elif problem == "rows":
            payload["trees"][0]["rows"] = payload["trees"][0]["rows"][1:]
        elif problem == "node":
            payload["trees"][0]["left"][0] = 0
        elif problem == "preprocessing":
            payload["preprocessing"]["center_y"] += 1
        else:
            payload["backend"]["sklearn"] = "different"
        path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        control.check_job(job, manifest["config"])


def test_deterministic_refit_rejects_a_valid_but_undeclared_stump_forest(artifacts):
    _, manifest, _, _ = artifacts()
    job = manifest["jobs"][0]
    payload = json.loads(Path(job["tree_path"]).read_text())
    values = pd.read_csv(job["matrix"], float_precision="round_trip")
    _, y, _, _ = control.fit_inputs(values, 70, job["model"])
    for tree in payload["trees"]:
        rows = np.asarray(tree["rows"])
        tree.update(
            left=[-1],
            right=[-1],
            feature=[-2],
            threshold=[-2.0],
            value=[float(y[rows].mean())],
            count=[len(rows)],
        )
    expected, _ = control.verify_payload(
        payload, values, 70, job["model"], job["seed"], manifest["config"]
    )
    Path(job["tree_path"]).write_text(json.dumps(payload))
    expected.to_csv(job["prediction_path"], index=False, float_format="%.17g")
    control.check_job(job, manifest["config"], refit=False)
    with pytest.raises(ValueError, match="deterministic refit"):
        control.check_job(job, manifest["config"], refit=True)


@pytest.mark.parametrize("problem", ["grid", "origin", "matrix", "setting", "path"])
def test_control_grid_and_primary_input_provenance_cannot_be_changed(artifacts, problem):
    source, manifest, output, _ = artifacts()
    job = manifest["jobs"][0]
    if problem == "grid":
        manifest["jobs"].pop()
    elif problem == "origin":
        job["targets"] = copy.deepcopy(job["targets"])
        job["targets"][0]["origin_date"] = "1999Q4"
    elif problem in ("matrix", "setting"):
        key = "matrix" if problem == "matrix" else "settings"
        path = Path(job[key])
        path.write_text(path.read_text() + "\n")
        job[key + "_sha256"] = control._sha(path)
    else:
        job["tree_path"] = str(output.parent / "outside.json")
    with pytest.raises(ValueError):
        control.verify_inputs(manifest, source, output, None)


def test_pilot_suppresses_scores_and_cannot_be_relabelled_full(artifacts):
    _, manifest, _, reference = artifacts()
    result, forecasts = control.collect_outputs(manifest, reference)
    assert result["partial_scores_suppressed"]
    assert result["metrics"] == result["published_ratio_comparisons"] == []
    assert result["all_individual_control_seeds_within_tolerance"] is None
    assert {"AR2_filter", "RF_MAF_seed101", "AR_plus_RF_seed101"}.issubset(set(forecasts.model))
    manifest["full_declared_comparison"] = True
    with pytest.raises(ValueError, match="Incomplete"):
        control.collect_outputs(manifest, reference)


def test_full_contract_keeps_both_models_all_seeds_and_their_ensembles(artifacts):
    _, manifest, _, reference = artifacts(groups=6, seeds=(101, 202, 303), full=True)
    result, predictions = control.collect_outputs(manifest, reference)
    assert result["jobs_verified"] == 36 and result["targets_per_model"] == 48
    assert predictions.groupby("model").size().eq(48).all()
    assert len(result["published_ratio_comparisons"]) == 8
    assert (
        sum(
            not row["ensemble_excluded_from_seed_rule"]
            for row in result["published_ratio_comparisons"]
        )
        == 6
    )
    assert not result["FA_ARRF_replication_established"] and not result["primary_result_replaced"]


def test_resume_requires_identical_provenance():
    expected = {"runner_source_sha256": "a", "backend": {"sklearn": "1.9.1"}}
    changed = {**expected, "runner_source_sha256": "b"}
    with pytest.raises(ValueError):
        control.validate_provenance(changed, expected)


def test_original_primary_config_is_pinned_before_any_source_audit(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid original config must be rejected first")

    monkeypatch.setattr(control, "audit_run", forbidden)
    with pytest.raises(ValueError, match="frozen original primary"):
        control._inputs(tmp_path, tmp_path, tmp_path, {"factor_panel": "all"}, None)


@pytest.fixture
def boundary(artifacts, monkeypatch):
    source, _, _, reference = artifacts()
    source_run = Path(source["jobs"][0]["matrix"]).parent
    monkeypatch.setattr(control, "_inputs", lambda *args: (source, reference))

    def provenance(source_run, engine, declaration, config, limit):
        return {
            "source_run": str(source_run),
            "declaration": declaration,
            "config": config,
            "max_refits": limit,
            "runner_source_sha256": "synthetic_source_boundary_not_a_macro_audit",
            "dependencies_sha256": {},
            "backend": control._backend(),
        }

    monkeypatch.setattr(control, "_provenance", provenance)
    return source_run


def test_actual_cart_pilot_round_trips_full_auditor_without_scores(boundary, tmp_path):
    output = tmp_path / "end-to-end-pilot"
    result = control.run_controls(
        boundary,
        tmp_path,
        tmp_path,
        output,
        declaration(),
        {},
        rscript=None,
        trees=2,
        seeds=[101],
        max_refits=1,
    )
    assert result["jobs_verified"] == 2 and result["partial_scores_suppressed"]
    assert not (output / "metrics.csv").exists()
    audited = control.audit_controls(
        output, tmp_path, tmp_path, declaration(), {}, rscript=None, allow_partial=True
    )
    assert audited["jobs_verified"] == 2 and not audited["pending_jobs"]
    assert all(r["deterministic_refit_verified"] for r in audited["output_checks"])
    with pytest.raises(ValueError, match="incomplete"):
        control.audit_controls(output, tmp_path, tmp_path, declaration(), {}, rscript=None)


@pytest.mark.parametrize("problem", ["prediction", "origin", "result", "metric_file"])
def test_pilot_audit_rejects_changed_saved_aggregates(boundary, tmp_path, problem):
    output = tmp_path / "changed-aggregate"
    control.run_controls(
        boundary,
        tmp_path,
        tmp_path,
        output,
        declaration(),
        {},
        rscript=None,
        trees=2,
        seeds=[101],
        max_refits=1,
    )
    if problem in ("prediction", "origin"):
        path = output / "predictions.csv"
        rows = pd.read_csv(path)
        if problem == "prediction":
            rows.loc[0, "prediction"] += 1
        else:
            rows.loc[0, "origin_date"] = "1999Q4"
        rows.to_csv(path, index=False)
    elif problem == "result":
        path = output / "result.json"
        value = json.loads(path.read_text())
        value["jobs_verified"] = 36
        path.write_text(json.dumps(value))
    else:
        (output / "metrics.csv").write_text("model,RMSE\nfake,1\n")
    with pytest.raises(ValueError):
        control.audit_controls(
            output, tmp_path, tmp_path, declaration(), {}, rscript=None, allow_partial=True
        )


def test_prepare_only_never_fits_a_tree_or_calculates_scores(boundary, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Preparation-only must not fit or score")

    monkeypatch.setattr(control, "fit_payload", forbidden)
    monkeypatch.setattr(control, "score_table", forbidden)
    output = tmp_path / "only-prepared"
    result = control.run_controls(
        boundary,
        tmp_path,
        tmp_path,
        output,
        declaration(),
        {},
        rscript=None,
        trees=2,
        seeds=[101],
        max_refits=1,
        prepare_only=True,
    )
    assert result["jobs"] == 2 and not (output / "result.json").exists()
    assert not json.loads((output / "manifest.json").read_text())["completed"]


def test_control_gate_requires_both_model_families_not_a_passing_ensemble(artifacts, monkeypatch):
    _, manifest, _, reference = artifacts(groups=6, seeds=(101, 202, 303), full=True)

    def synthetic_scores(forecasts):
        rows = []
        for model in forecasts.model.unique():
            ratio = (
                0.85
                if model.startswith("RF_MAF")
                else 0.84
                if model.startswith("AR_plus_RF")
                else 1
            )
            if model == "AR_plus_RF_seed303":
                ratio = 1.1
            rows.append({"model": model, "n": 48, "RMSE": ratio, "RMSE_over_AR4": ratio})
        return pd.DataFrame(rows)

    monkeypatch.setattr(control, "score_table", synthetic_scores)
    result, _ = control.collect_outputs(manifest, reference)
    assert not result["all_individual_control_seeds_within_tolerance"]
    assert not result["FA_ARRF_replication_established"]
    failed = [
        row["model"]
        for row in result["published_ratio_comparisons"]
        if not row["within_diagnostic_tolerance"]
    ]
    assert failed == ["AR_plus_RF_seed303"]


def test_resume_preserves_valid_tree_checkpoints_and_linear_check_record(
    boundary, tmp_path, monkeypatch
):
    output = tmp_path / "resume-pilot"
    control.run_controls(
        boundary,
        tmp_path,
        tmp_path,
        output,
        declaration(),
        {},
        rscript=None,
        trees=2,
        seeds=[101],
        max_refits=1,
    )
    manifest = json.loads((output / "manifest.json").read_text())
    snapshots = {j["tree_path"]: control._sha(j["tree_path"]) for j in manifest["jobs"]}
    linear_sha = control._sha(output / "linear_checks.json")

    def forbidden(*args, **kwargs):
        raise AssertionError("Valid checkpoints must not be refitted during resume")

    monkeypatch.setattr(control, "fit_payload", forbidden)
    control.run_controls(
        boundary,
        tmp_path,
        tmp_path,
        output,
        declaration(),
        {},
        rscript=None,
        trees=2,
        seeds=[101],
        max_refits=1,
        resume=True,
    )
    assert all(control._sha(path) == digest for path, digest in snapshots.items())
    assert control._sha(output / "linear_checks.json") == linear_sha
