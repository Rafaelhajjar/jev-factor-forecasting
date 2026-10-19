"""Pairing/provenance guards; actual scaling behavior has separate real-R contracts."""

import json
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from jev_factor import native_allrows as module


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


@pytest.fixture
def primary():
    path = Path(__file__).resolve().parents[1] / "configs/mrf_unemployment.json"
    return json.loads(path.read_text())


@pytest.fixture
def case(tmp_path, primary):
    source, variant = (tmp_path / name for name in ("primary", "native"))
    for directory in (source, variant):
        directory.mkdir()
    original, changed, baselines = [], [], []
    for group in range(6):
        targets = [
            {"target_date": f"T{group}_{i}", "origin_date": f"O{group}_{i}", "actual": i / 10}
            for i in range(8)
        ]
        for directory, jobs, mode in (
            (source, original, "train_only"),
            (variant, changed, module.MODE),
        ):
            matrix = directory / f"matrix_{group}.csv"
            matrix.write_text("target,y_lag1\n1,2\n3,4\n")
            for seed in primary["seeds"]:
                settings = directory / f"settings_{group}_{seed}.dcf"
                settings.write_text(
                    f"ntrain: 166\nseed: {seed}\ntrees: 100\nstandardization: {mode}\nprior: OLS\n"
                )
                jobs.append(
                    {
                        "group": group,
                        "seed": seed,
                        "fit_end": f"END{group}",
                        "matrix": str(matrix),
                        "matrix_sha256": module._sha(matrix),
                        "settings": str(settings),
                        "settings_sha256": module._sha(settings),
                        "targets": targets,
                    }
                )
        baselines.extend(
            {**record, "model": model, "prediction": 0.01}
            for record in targets
            for model in ("AR4", "FA_AR")
        )
    common = {
        "completed": True,
        "max_refits": None,
        "representations": [{"group": g, "state_columns": 1041} for g in range(6)],
        "external_engine": {"commit": "synthetic_boundary_only"},
        "integration_source_sha256": {"adapter": "synthetic_boundary_only"},
    }
    write_json(source / "manifest.json", {**common, "config": primary, "jobs": original})
    config = module.declaration(primary)
    write_json(variant / "manifest.json", {**common, "config": config, "jobs": changed})
    for directory in (source, variant):
        pd.DataFrame(baselines).to_csv(directory / "baseline_predictions.csv", index=False)
    (source / "predictions.csv").write_text("synthetic source boundary,not macro evidence\n")
    manifest = json.loads((variant / "manifest.json").read_text())
    manifest["native_helper_diagnostic"] = module.provenance(source, config)
    write_json(variant / "manifest.json", manifest)
    return source, variant, config


def test_declaration_changes_only_the_native_mode_and_its_caveat(primary):
    config = module.declaration(primary)
    assert {k for k in primary if primary[k] != config[k]} == {
        "standardization",
        "assumptions_not_verified_paper_settings",
    }
    assert config["standardization"] == module.MODE
    path = Path(__file__).resolve().parents[1] / "configs/mrf_native_allrows.json"
    assert json.loads(path.read_text()) == config


@pytest.mark.parametrize(
    "key,value",
    [
        ("mtry", 0.5),
        ("trees", 101),
        ("seeds", [303, 101]),
        ("prior", "zero"),
        ("standardization", "train_only"),
        ("factor_panel", "SW"),
    ],
)
def test_reduced_config_cannot_hide_unrelated_changes(primary, key, value):
    config = module.declaration(primary)
    config[key] = value
    with pytest.raises(ValueError):
        module.validate_config(config, primary, reduced=True)


def test_changed_primary_is_rejected(primary):
    changed = deepcopy(primary)
    changed["pca_rank"] = 2
    with pytest.raises(ValueError, match="unchanged original"):
        module.declaration(changed)


def test_all_eighteen_cases_are_exactly_paired(case, primary):
    source, variant, _ = case
    checks = module.pair_inputs(source, variant, primary)
    assert len(checks) == 18
    assert {(c["group"], c["seed"]) for c in checks} == {
        (g, s) for g in range(6) for s in primary["seeds"]
    }


@pytest.mark.parametrize(
    "change", ["matrix", "setting", "target", "grid", "representation", "engine"]
)
def test_actual_input_change_is_rejected_even_with_updated_hash(case, primary, change):
    source, variant, _ = case
    manifest = json.loads((variant / "manifest.json").read_text())
    job = manifest["jobs"][0]
    if change == "matrix":
        path = Path(job["matrix"])
        path.write_text("target,y_lag1\n9,2\n3,4\n")
        for j in manifest["jobs"]:
            if j["group"] == 0:
                j["matrix_sha256"] = module._sha(path)
    elif change == "setting":
        path = Path(job["settings"])
        path.write_text(path.read_text().replace("prior: OLS", "prior: zero"))
        job["settings_sha256"] = module._sha(path)
    elif change == "target":
        job["targets"][0]["origin_date"] = "changed"
    elif change == "grid":
        manifest["jobs"].pop()
    elif change == "representation":
        manifest["representations"][0]["state_columns"] = 125
    else:
        manifest["external_engine"]["commit"] = "different"
    write_json(variant / "manifest.json", manifest)
    with pytest.raises(ValueError):
        module.pair_inputs(source, variant, primary)


def test_changed_linear_forecast_is_rejected(case, primary):
    source, variant, _ = case
    frame = pd.read_csv(variant / "baseline_predictions.csv")
    frame.loc[0, "prediction"] += 0.01
    frame.to_csv(variant / "baseline_predictions.csv", index=False)
    with pytest.raises(ValueError, match="linear forecasts"):
        module.pair_inputs(source, variant, primary)


def fake_audit(run, archive, config, **kwargs):
    metrics = [
        {"model": "FA_AR", "RMSE": 1.0},
        *({"model": f"FA_ARRF_seed{s}", "RMSE": 0.9} for s in (101, 202, 303)),
    ]
    return {
        "full_48_quarter_artifacts_verified": True,
        "matches_declared_config": True,
        "jobs_verified": 18,
        "metrics": metrics,
        "published_ratio_comparisons": [{"synthetic": True}],
        "numerical_agreement_FA_AR_and_all_individual_seeds": False,
        "partial_forest_scores_suppressed": False,
        "runtime_records": [{"R_version": "R synthetic", "pracma_version": "synthetic"}],
    }


def test_full_audit_retains_failed_gate_and_does_not_promote_to_causal(case, primary, monkeypatch):
    source, variant, config = case
    monkeypatch.setattr(module, "audit_run", fake_audit)
    report = module.audit_diagnostic(variant, Path("unused"), config, primary)
    assert report["full_native_helper_declaration_verified"]
    assert not report["numerical_agreement_FA_AR_and_all_individual_seeds"]
    assert not report["primary_result_replaced"]
    assert not report["causal_forecast_comparison"]
    assert report["native_prior_conversion_not_repaired"]
    assert report["matching_FA_AR_RMSE_reductions"][0][
        "RMSE_reduction_vs_matching_FA_AR"
    ] == pytest.approx(0.1)


def test_reduced_full_date_run_cannot_publish_performance(case, primary, monkeypatch):
    _, variant, config = case
    monkeypatch.setattr(module, "audit_run", fake_audit)
    manifest = json.loads((variant / "manifest.json").read_text())
    manifest["config"]["trees"] = 2
    for j in manifest["jobs"]:
        path = Path(j["settings"])
        path.write_text(path.read_text().replace("trees: 100", "trees: 2"))
        j["settings_sha256"] = module._sha(path)
    write_json(variant / "manifest.json", manifest)
    # The synthetic source boundary says full; actual config pairing must still catch reduction.
    report = module.audit_diagnostic(variant, Path("unused"), config, primary, allow_partial=True)
    assert report["metrics"] == []
    assert report["matching_FA_AR_RMSE_reductions"] == []
    assert report["published_ratio_comparisons"] == []
    assert report["numerical_agreement_FA_AR_and_all_individual_seeds"] is None
    with pytest.raises(ValueError, match="all 18"):
        module.audit_diagnostic(variant, Path("unused"), config, primary)


def test_source_provenance_change_rejects_resume_before_any_fit(case, primary, monkeypatch):
    source, variant, config = case
    monkeypatch.setattr(module, "audit_run", fake_audit)
    monkeypatch.setattr(module, "run_reconstruction", lambda *a, **kw: pytest.fail("must not run"))
    (source / "predictions.csv").write_text("changed")
    with pytest.raises(ValueError, match="resume provenance"):
        module.run_diagnostic(
            source,
            Path("archive"),
            Path("engine"),
            variant,
            config,
            primary,
            r_library=Path("lib"),
            resume=True,
        )


def test_pairing_failure_stops_before_the_forest_stage(case, primary, monkeypatch):
    source, variant, config = case
    monkeypatch.setattr(module, "audit_run", fake_audit)
    calls = []
    monkeypatch.setattr(module, "run_reconstruction", lambda *a, **kw: calls.append(kw))
    frame = pd.read_csv(variant / "baseline_predictions.csv")
    frame.loc[0, "prediction"] += 0.01
    frame.to_csv(variant / "baseline_predictions.csv", index=False)
    with pytest.raises(ValueError, match="linear forecasts"):
        module.run_diagnostic(
            source,
            Path("archive"),
            Path("engine"),
            variant,
            config,
            primary,
            r_library=Path("lib"),
            resume=True,
        )
    assert len(calls) == 1 and calls[0]["prepare_only"]


def test_prepare_only_makes_no_fitting_call_and_no_scores(case, primary, monkeypatch):
    source, variant, config = case
    monkeypatch.setattr(module, "audit_run", fake_audit)
    calls = []
    monkeypatch.setattr(module, "run_reconstruction", lambda *a, **kw: calls.append(kw))
    result = module.run_diagnostic(
        source,
        Path("archive"),
        Path("engine"),
        variant,
        config,
        primary,
        r_library=Path("lib"),
        resume=True,
        prepare_only=True,
    )
    assert len(calls) == 1 and calls[0]["prepare_only"]
    assert result["paired_jobs"] == 18 and "metrics" not in result


def test_changed_R_runtime_cannot_be_called_normalization_only(case, primary, monkeypatch):
    _, variant, config = case

    def changed_runtime(run, archive, given_config, **kwargs):
        result = fake_audit(run, archive, given_config, **kwargs)
        if given_config["standardization"] == module.MODE:
            result["runtime_records"][0]["R_version"] = "different R"
        return result

    monkeypatch.setattr(module, "audit_run", changed_runtime)
    with pytest.raises(ValueError, match="R/pracma runtime"):
        module.audit_diagnostic(variant, Path("unused"), config, primary)


@pytest.mark.parametrize("limit", [0, 7, True])
def test_invalid_refit_bounds_fail_before_any_source_audit(case, primary, monkeypatch, limit):
    source, variant, config = case
    monkeypatch.setattr(module, "audit_run", lambda *a, **kw: pytest.fail("must not audit"))
    with pytest.raises(ValueError, match="refit limit"):
        module.run_diagnostic(
            source,
            Path("archive"),
            Path("engine"),
            variant,
            config,
            primary,
            r_library=Path("lib"),
            max_refits=limit,
        )
