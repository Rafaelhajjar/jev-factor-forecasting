"""Synthetic artifact contracts, never simulated author/macro performance evidence."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from jev_factor import fred125_sensitivity as experiment
from jev_factor.replication import LINEAR_X, linear_prediction


@pytest.fixture
def artifacts(tmp_path, monkeypatch):
    def synthetic_matrix(data, original, primary):
        raw = pd.read_csv(original["matrix"], float_precision="round_trip")
        changed = raw.copy()
        # A deliberately synthetic replacement to exercise serialization guards.
        # The actual archived-data builder is exercised by the separate real-R pilot.
        for name in experiment.FACTOR_LAGS:
            changed[name] = 0.8 * raw[name] + 0.15 * raw.y_lag1**2
        return changed

    monkeypatch.setattr(experiment, "build_matrix", synthetic_matrix)

    def create(groups=1, seeds=(101, 202), full=False):
        rng = np.random.default_rng(309)
        source_folder = tmp_path / f"synthetic-source-{groups}"
        output = tmp_path / f"synthetic-artifact-contract-{groups}"
        source_folder.mkdir()
        output.mkdir()
        declaration = json.loads(Path("configs/mrf_fred125_sensitivity.json").read_text())
        config = copy.deepcopy(declaration)
        if not full:
            config.update(trees=2, seeds=list(seeds))
        source = {"config": {"trees": 100, "seeds": [101, 202, 303]}, "jobs": []}
        reference = []
        names = ["target", *[f"y_lag{k}" for k in range(1, 9)], *experiment.FACTOR_LAGS]
        names += ["series_000_lag1", "MAF_000_1", "trend"]
        for group in range(groups):
            raw = pd.DataFrame(rng.normal(size=(78, len(names))), columns=names)
            raw.target = 0.3 * raw.y_lag1 + 0.4 * raw.F1_lag1 + rng.normal(0, 0.1, 78)
            truth = raw.target.iloc[70:].copy()
            raw.loc[70:, "target"] = raw.target.iloc[:70].mean()
            matrix_path = source_folder / f"matrix_{group}.csv"
            raw.to_csv(matrix_path, index=False, float_format="%.17g")
            dates = pd.period_range(pd.Period("2003Q1") + group * 8, periods=8, freq="Q")
            targets = [
                {"target_date": str(d), "origin_date": str(d - 1), "actual": float(y)}
                for d, y in zip(dates, truth, strict=True)
            ]
            for model, columns in (("AR4", experiment.AR), ("FA_AR", experiment.FA)):
                values = linear_prediction(raw.iloc[:70], raw.iloc[70:], columns)
                reference.extend(
                    {**r, "model": model, "prediction": float(p)}
                    for r, p in zip(targets, values, strict=True)
                )
            for seed in seeds:
                settings = source_folder / f"settings_{group}_{seed}.dcf"
                settings.write_text(
                    f"ntrain: 70\nxnames: {','.join(LINEAR_X)}\ntrees: 100\nseed: {seed}\n"
                    "prior: OLS\nstandardization: train_only\nblock: 8\n"
                )
                source["jobs"].append(
                    {
                        "group": group,
                        "seed": seed,
                        "fit_end": str(dates[0] - 1),
                        "matrix": str(matrix_path),
                        "matrix_sha256": experiment._sha(matrix_path),
                        "settings": str(settings),
                        "settings_sha256": experiment._sha(settings),
                        "targets": targets,
                        "prediction_path": "unused.csv",
                    }
                )
                reference.extend(
                    {**r, "model": f"FA_ARRF_seed{seed}", "prediction": float(y + 0.12)}
                    for r, y in zip(targets, truth, strict=True)
                )
        jobs = experiment.prepare_jobs(source, None, output, config, None if full else groups)
        manifest = {
            "config": config,
            "declaration": declaration,
            "jobs": jobs,
            "max_refits": None if full else groups,
            "full_declared_sensitivity": full,
        }
        reference = pd.DataFrame(reference)
        _, linear = experiment.verify_jobs(manifest, source, None, output, reference)
        for job in jobs:
            matrix = pd.read_csv(job["matrix"])
            coefs = pd.DataFrame(
                {"intercept": np.repeat(0.1, 8), **{k: np.repeat(0.2, 8) for k in LINEAR_X}}
            )
            coefs.insert(
                0,
                "prediction",
                coefs.intercept.to_numpy()
                + np.sum(
                    coefs[LINEAR_X].to_numpy() * matrix.iloc[70:][LINEAR_X].to_numpy(), axis=1
                ),
            )
            coefs.to_csv(job["prediction_path"], index=False)
            Path(job["prediction_path"] + ".runtime.dcf").write_text(
                "R_version: synthetic-fixture-not-executed\n"
                "prior: OLS\nstandardization: train_only\n"
            )
        return source, manifest, output, reference, linear

    return create


def test_other_entries_are_exactly_preserved_and_new_linear_baseline_is_distinct(artifacts):
    source, manifest, output, reference, linear = artifacts()
    checks, observed = experiment.verify_jobs(manifest, source, None, output, reference)
    assert len(checks) == 1 and checks[0]["all_nonfactor_entries_exactly_preserved"]
    assert checks[0]["maximum_absolute_differences"]["AR4_unchanged"] < 1e-12
    assert checks[0]["R_version"] is None
    pd.testing.assert_frame_equal(observed, linear)
    old = reference.loc[reference.model.eq("FA_AR"), "prediction"].to_numpy()
    new = linear.loc[linear.model.eq(experiment.BASELINE), "prediction"].to_numpy()
    assert not np.allclose(old, new)
    original = pd.read_csv(source["jobs"][0]["matrix"], float_precision="round_trip")
    variant = pd.read_csv(manifest["jobs"][0]["matrix"], float_precision="round_trip")
    keep = original.columns.difference(experiment.FACTOR_LAGS, sort=False)
    np.testing.assert_array_equal(original[keep], variant[keep])


@pytest.mark.parametrize(
    "problem", ["target", "nonfactor", "factor", "setting", "path", "grid", "dates", "source"]
)
def test_updated_checksums_cannot_hide_an_undeclared_change(artifacts, problem):
    source, manifest, output, reference, _ = artifacts()
    job = manifest["jobs"][0]
    if problem in ("target", "nonfactor", "factor"):
        path = Path(job["matrix"])
        matrix = pd.read_csv(path, float_precision="round_trip")
        column = {"target": "target", "nonfactor": "MAF_000_1", "factor": "F5_lag8"}[problem]
        matrix.loc[0, column] += 1
        matrix.to_csv(path, index=False, float_format="%.17g")
        job["matrix_sha256"] = experiment._sha(path)
    elif problem == "setting":
        path = Path(job["settings"])
        path.write_text(path.read_text().replace("block: 8", "block: 12"))
        job["settings_sha256"] = experiment._sha(path)
    elif problem == "path":
        job["prediction_path"] = str(output.parent / "outside.csv")
    elif problem == "grid":
        manifest["jobs"].pop()
    elif problem == "dates":
        # Deep copy so the source target record is not changed by this mutation.
        job["targets"] = copy.deepcopy(job["targets"])
        job["targets"][0]["origin_date"] = "1999Q4"
    else:
        job["source_matrix_sha256"] = "wrong-source"
    with pytest.raises(ValueError):
        experiment.verify_jobs(manifest, source, None, output, reference)


@pytest.mark.parametrize(
    "problem", ["more_trees", "unknown_seed", "duplicate_seed", "refits", "signs", "rule"]
)
def test_pilot_overrides_cannot_expand_or_change_the_scientific_test(artifacts, problem):
    source, manifest, _, _, _ = artifacts()
    config = manifest["config"]
    limit = 1
    if problem == "more_trees":
        config["trees"] = 101
    elif problem == "unknown_seed":
        config["seeds"] = [999]
    elif problem == "duplicate_seed":
        config["seeds"] = [101, 101]
    elif problem == "refits":
        limit = 7
    elif problem == "signs":
        config["sign_rule"] = "try_R_signs_too"
    else:
        config["factor_rule"] = "independently_complete_a_reduced_panel"
    with pytest.raises(ValueError):
        experiment.select_jobs(source, config, limit)


def test_pilot_suppresses_scores_and_cannot_be_relabelled_full(artifacts):
    _, manifest, _, reference, linear = artifacts()
    result, forecasts = experiment.collect_outputs(manifest, reference, linear)
    assert result["partial_forest_scores_suppressed"]
    assert result["metrics"] == result["published_ratio_comparisons"] == []
    assert (
        result["paired_preparation_effects"]
        == result["forest_gains_over_own_fixed_factor_comparator"]
        == []
    )
    assert result["subset_FA_AR_and_all_individual_forest_seeds_within_tolerance"] is None
    assert set(forecasts.model) == set(reference.model) | {
        experiment.BASELINE,
        f"{experiment.PREFIX}_seed101",
        f"{experiment.PREFIX}_seed202",
        f"{experiment.PREFIX}_seed_mean_prediction",
    }
    manifest["full_declared_sensitivity"] = True
    with pytest.raises(ValueError, match="Incomplete"):
        experiment.collect_outputs(manifest, reference, linear)


def test_full_contract_uses_its_own_factor_baseline_and_retains_every_seed(artifacts):
    _, manifest, _, reference, linear = artifacts(groups=6, seeds=(101, 202, 303), full=True)
    result, frames = experiment.collect_outputs(manifest, reference, linear)
    assert result["jobs_verified"] == 18 and result["targets_per_model"] == 48
    assert not result["partial_forest_scores_suppressed"]
    assert frames.groupby("model").size().eq(48).all()
    compared = {r["model"] for r in result["published_ratio_comparisons"]}
    assert experiment.BASELINE in compared and "FA_AR" not in compared
    assert len(compared) == 5 and len(result["paired_preparation_effects"]) == 3
    assert len(result["forest_gains_over_own_fixed_factor_comparator"]) == 4
    assert (
        result["primary_result_replaced"]
        is result["original_author_preprocessing_recovered"]
        is False
    )


@pytest.mark.parametrize("problem", ["coefficient", "schema", "runtime"])
def test_forest_checkpoint_schema_decomposition_and_runtime_are_verified(artifacts, problem):
    _, manifest, _, _, _ = artifacts()
    job = manifest["jobs"][0]
    if problem == "runtime":
        path = Path(job["prediction_path"] + ".runtime.dcf")
        path.write_text(path.read_text().replace("train_only", "native_all_rows"))
    else:
        path = Path(job["prediction_path"])
        values = pd.read_csv(path)
        if problem == "coefficient":
            values.loc[0, "prediction"] += 1
        else:
            values = values.drop(columns="F2_lag1")
        values.to_csv(path, index=False)
    with pytest.raises(ValueError):
        experiment.check_output(job)


@pytest.mark.parametrize("field", ["source_manifest_sha256", "dependencies_sha256", "declaration"])
def test_resume_rejects_changed_provenance(field):
    expected = {
        "source_manifest_sha256": "original",
        "dependencies_sha256": {"helper": "hash"},
        "declaration": {"trees": 100},
    }
    changed = copy.deepcopy(expected)
    changed[field] = "changed"
    with pytest.raises(ValueError):
        experiment.validate_provenance(changed, expected)


@pytest.mark.parametrize("problem", ["duplicate", "origin", "prediction"])
def test_saved_forecast_rows_cannot_be_replaced_or_duplicated(artifacts, problem):
    _, _, _, _, linear = artifacts()
    changed = linear.copy()
    if problem == "duplicate":
        changed = pd.concat([changed, changed.iloc[:1]])
    elif problem == "origin":
        changed.loc[0, "origin_date"] = "1999Q4"
    else:
        changed.loc[0, "prediction"] += 1
    with pytest.raises(ValueError):
        experiment._verify_frame(changed, linear, "synthetic saved rows")


@pytest.mark.parametrize(
    "problem", ["rank", "cap", "future_rule", "tolerance", "target_ratio", "loss_selection", "mask"]
)
def test_declared_recipe_and_joint_benchmark_rule_cannot_be_changed(artifacts, problem):
    source, manifest, _, _, _ = artifacts()
    config = manifest["config"]
    if problem == "rank":
        config["completion_recipe"]["kmax"] = 5
    elif problem == "cap":
        config["completion_recipe"]["max_iterations"] = 100
    elif problem == "future_rule":
        config["future_completion_rule"] = "pool_future_rows"
    elif problem == "tolerance":
        config["absolute_ratio_diagnostic_tolerance"] = 0.1
    elif problem == "target_ratio":
        config["reported_FA_AR_ratio"] = 0.79
    elif problem == "loss_selection":
        config["recipe_selected_using_forecast_loss"] = True
    else:
        config["all_nonfactor_state_entries_and_target_masks_preserved"] = False
    with pytest.raises(ValueError, match="declared"):
        experiment.select_jobs(source, config, 1)


@pytest.mark.parametrize("problem", ["trees", "seeds"])
def test_full_declaration_cannot_be_shrunk_to_pilot(problem):
    config = json.loads(Path("configs/mrf_fred125_sensitivity.json").read_text())
    config[problem] = 2 if problem == "trees" else [101]
    with pytest.raises(ValueError, match="full declaration"):
        experiment.validate_declaration(config)


def test_joint_gate_cannot_mix_old_linear_with_new_forests(artifacts, monkeypatch):
    _, manifest, _, reference, linear = artifacts(groups=6, seeds=(101, 202, 303), full=True)

    def synthetic_scores(forecasts):
        rows = []
        for name in forecasts.model.unique():
            ratio = (
                0.70
                if name == experiment.BASELINE
                else 0.73
                if name.startswith(experiment.PREFIX)
                else 0.83
                if name == "FA_AR"
                else 1
            )
            rows.append({"model": name, "n": 48, "RMSE": ratio, "RMSE_over_AR4": ratio})
        return pd.DataFrame(rows)

    monkeypatch.setattr(experiment, "score_table", synthetic_scores)
    result, _ = experiment.collect_outputs(manifest, reference, linear)
    assert not result["subset_FA_AR_and_all_individual_forest_seeds_within_tolerance"]
    assert all(
        row["within_diagnostic_tolerance"]
        for row in result["published_ratio_comparisons"]
        if row["model"].startswith(experiment.PREFIX)
    )


@pytest.fixture
def real_builder_inputs(tmp_path):
    """Synthetic inputs with actual completion/PCA, not a mock of the builder."""
    rng = np.random.default_rng(712)
    index = pd.period_range("1960Q1", periods=100, freq="Q")
    columns = [f"X{k}" for k in range(248)]
    factors = rng.normal(size=(100, 2))
    angles = np.linspace(0, 2 * np.pi, 248, endpoint=False)
    values = factors @ np.vstack([np.cos(angles), np.sin(angles)])
    values += rng.normal(0, 0.1, values.shape)
    values[rng.random(values.shape) < 0.02] = np.nan
    data = SimpleNamespace(
        panel=pd.DataFrame(values, index=index, columns=columns),
        sw_membership=pd.Series([1] * 125 + [0] * 123, index=columns),
    )
    names = ["target", *[f"y_lag{k}" for k in range(1, 9)], *experiment.FACTOR_LAGS]
    names += ["indicator_lag1", "MAF_0", "trend"]
    raw = pd.DataFrame(rng.normal(size=(80, len(names))), columns=names, index=index[8:88])
    path = tmp_path / "primary-matrix.csv"
    raw.to_csv(path, index=False, float_format="%.17g")
    original = {
        "fit_end": str(index[79]),
        "targets": [{"target_date": str(d)} for d in index[80:88]],
        "matrix": str(path),
    }
    primary = {"panel_start": str(index[0]), "regression_start": str(index[8])}
    return data, original, primary, raw


def test_actual_builder_only_changes_factor_lags_and_cannot_use_later_rows(real_builder_inputs):
    data, original, primary, raw = real_builder_inputs
    built = experiment.build_matrix(data, original, primary)
    untouched = raw.columns.difference(experiment.FACTOR_LAGS, sort=False)
    np.testing.assert_allclose(built[untouched], raw[untouched], atol=1e-15, rtol=0)
    assert not np.allclose(built[experiment.FACTOR_LAGS], raw[experiment.FACTOR_LAGS])
    changed = copy.deepcopy(data)
    changed.panel.iloc[81:, :5] *= 10000
    altered = experiment.build_matrix(changed, original, primary)
    np.testing.assert_array_equal(
        built.loc[: data.panel.index[81]], altered.loc[: data.panel.index[81]]
    )
    assert list(built) == list(raw) and built.index.equals(raw.index)


@pytest.mark.parametrize("problem", ["order", "nonbinary", "cardinality"])
def test_actual_builder_rejects_changed_membership(real_builder_inputs, problem):
    data, original, primary, _ = real_builder_inputs
    if problem == "order":
        data.sw_membership = data.sw_membership.iloc[::-1]
    elif problem == "nonbinary":
        data.sw_membership.iloc[0] = 2
    else:
        data.sw_membership.iloc[0] = 0
    with pytest.raises(ValueError):
        experiment.build_matrix(data, original, primary)


@pytest.mark.parametrize("converged,at_cap", [(False, False), (False, True), (True, True)])
def test_actual_builder_cannot_silently_accept_nonconvergence_or_cap(
    real_builder_inputs, monkeypatch, converged, at_cap
):
    data, original, primary, _ = real_builder_inputs

    class IncompleteRepresentation:
        def fit(self, frame):
            self.em = SimpleNamespace(converged=converged, at_iteration_cap=at_cap)
            return self

    monkeypatch.setattr(experiment, "FredRecipeRepresentation", IncompleteRepresentation)
    with pytest.raises(ValueError, match="converge before"):
        experiment.build_matrix(data, original, primary)


def test_prepare_only_never_fits_or_scores(artifacts, tmp_path, monkeypatch):
    source, manifest, _, reference, _ = artifacts()
    monkeypatch.setattr(experiment, "_inputs", lambda *args: (source, None, reference))

    def fake_provenance(*args):
        declaration, config, limit = args[-3:]
        return {"declaration": declaration, "config": config, "max_refits": limit}

    def forbidden(*args, **kwargs):
        raise AssertionError("Preparation-only must not fit or score")

    monkeypatch.setattr(experiment, "_provenance", fake_provenance)
    monkeypatch.setattr(experiment, "_run_job", forbidden)
    monkeypatch.setattr(experiment, "score_table", forbidden)
    output = tmp_path / "prepare-only"
    result = experiment.run_sensitivity(
        tmp_path,
        tmp_path,
        tmp_path,
        tmp_path,
        tmp_path,
        output,
        manifest["declaration"],
        {},
        rscript=None,
        trees=2,
        seeds=[101, 202],
        max_refits=1,
        prepare_only=True,
    )
    assert result["jobs_prepared"] == 2 and result["refits_verified"] == 1
    assert not result["completed"] and result["metrics"] == []
    assert not json.loads((output / "manifest.json").read_text())["completed"]
    assert not (output / "result.json").exists() and not (output / "metrics.csv").exists()
