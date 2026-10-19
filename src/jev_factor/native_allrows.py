"""Paired native-helper diagnostic; never replace the causal primary run."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pandas as pd

from jev_factor.replication import run_reconstruction
from jev_factor.replication_audit import _dcf, audit_run

PRIMARY_DIGEST = "cd2df267c60250cf06a310b2265421a068c642b33c19b65948a359fb980d15e8"
MODE = "native_all_supplied_rows"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def declaration(primary):
    canonical = json.dumps(primary, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(canonical).hexdigest() != PRIMARY_DIGEST:
        raise ValueError("Native-helper diagnostic requires the unchanged original primary")
    config = deepcopy(primary)
    config["standardization"] = MODE
    config["assumptions_not_verified_paper_settings"][-1] = (
        "native_all_supplied_rows_is_transductive_within_block_not_verified_table_invocation"
    )
    return config


def validate_config(config, primary, *, reduced=False):
    expected = declaration(primary)
    if reduced:
        if (
            type(config.get("trees")) is not int
            or not 1 <= config["trees"] <= expected["trees"]
            or not config.get("seeds")
            or any(type(s) is not int for s in config["seeds"])
            or config["seeds"] != [s for s in expected["seeds"] if s in config["seeds"]]
        ):
            raise ValueError("Only reduced declared tree/seed pilots are supported")
        expected.update(trees=config["trees"], seeds=config["seeds"])
    if config != expected:
        raise ValueError("Native-helper diagnostic changes only normalization and its caveat")


def pair_inputs(source_run, run, primary, *, reduced=True):
    """Prove actual prepared inputs, not only configuration names, are paired."""
    source = json.loads((source_run / "manifest.json").read_text())
    variant = json.loads((run / "manifest.json").read_text())
    validate_config(variant["config"], primary, reduced=reduced)
    if source["config"] != primary or not source["completed"] or source["max_refits"] is not None:
        raise ValueError("Native-helper source must be the complete original primary")
    limit = variant["max_refits"]
    if limit is not None and (type(limit) is not int or not 1 <= limit <= 6):
        raise ValueError("Only one through six original refit windows are supported")
    original = {(j["group"], j["seed"]): j for j in source["jobs"]}
    if len(original) != 18 or set(original) != {(g, s) for g in range(6) for s in primary["seeds"]}:
        raise ValueError("Original native-helper source grid differs")
    groups = range(6 if limit is None else limit)
    keys = [(j["group"], j["seed"]) for j in variant["jobs"]]
    if len(keys) != len(set(keys)) or set(keys) != {
        (g, s) for g in groups for s in variant["config"]["seeds"]
    }:
        raise ValueError("Native-helper diagnostic job grid differs")
    if variant["representations"] != source["representations"][: len(groups)]:
        raise ValueError("Native-helper representation metadata changed")
    if variant["external_engine"] != source["external_engine"] or (
        variant["integration_source_sha256"] != source["integration_source_sha256"]
    ):
        raise ValueError("Native-helper engine or adapter/preparation code changed")
    cases = []
    for job in variant["jobs"]:
        reference = original[job["group"], job["seed"]]
        for field in ("matrix", "settings"):
            for candidate in (job, reference):
                if _sha(candidate[field]) != candidate[field + "_sha256"]:
                    raise ValueError("Native-helper recorded input checksum differs")
        if job["matrix_sha256"] != reference["matrix_sha256"]:
            raise ValueError("Native-helper diagnostic must preserve every matrix byte")
        if any(job[k] != reference[k] for k in ("fit_end", "targets")):
            raise ValueError("Native-helper diagnostic origin/target grid differs")
        expected = _dcf(Path(reference["settings"]))
        expected.update(standardization=MODE, trees=str(variant["config"]["trees"]))
        if _dcf(Path(job["settings"])) != expected:
            raise ValueError("Native-helper settings changed beyond the declared mode/pilot cap")
        cases.append(
            {
                "group": job["group"],
                "seed": job["seed"],
                "matrix_sha256": job["matrix_sha256"],
                "source_settings_sha256": reference["settings_sha256"],
                "native_settings_sha256": job["settings_sha256"],
            }
        )
    baseline = pd.read_csv(source_run / "baseline_predictions.csv", float_precision="round_trip")
    saved = pd.read_csv(run / "baseline_predictions.csv", float_precision="round_trip")
    targets = {r["target_date"] for j in variant["jobs"] for r in j["targets"]}
    expected = baseline.loc[baseline.target_date.isin(targets)]
    keys = ["model", "target_date"]
    try:
        pd.testing.assert_frame_equal(
            saved.sort_values(keys).reset_index(drop=True),
            expected.sort_values(keys).reset_index(drop=True),
            check_exact=True,
        )
    except AssertionError as exc:
        raise ValueError("Native-helper diagnostic linear forecasts changed") from exc
    return cases


def provenance(source_run, config):
    return {
        "declaration": config,
        "source_run": str(source_run.resolve()),
        "source_manifest_sha256": _sha(source_run / "manifest.json"),
        "source_predictions_sha256": _sha(source_run / "predictions.csv"),
        "paired_diagnostic_code_sha256": _sha(__file__),
        "base_verifier_sha256": _sha(Path(__file__).with_name("replication_audit.py")),
        "primary_result_replaced": False,
        "causal_forecast_comparison": False,
        "future_block_covariates_enter_native_moments": True,
        "native_prior_conversion_not_repaired": True,
    }


def audit_diagnostic(run, archive, config, primary, *, allow_partial=False, rscript="Rscript"):
    run = Path(run)
    validate_config(config, primary)
    manifest = json.loads((run / "manifest.json").read_text())
    binding = manifest["native_helper_diagnostic"]
    source_run = Path(binding["source_run"])
    original = audit_run(source_run, archive, primary, rscript=rscript)
    if (
        not original["full_48_quarter_artifacts_verified"]
        or not original["matches_declared_config"]
    ):
        raise ValueError("Native-helper primary source no longer verifies")
    if binding != provenance(source_run, config):
        raise ValueError("Native-helper source, declaration or verification code changed")
    paired = pair_inputs(source_run, run, primary)
    audit = audit_run(run, archive, config, rscript=rscript, allow_partial=True)
    versions = {(r["R_version"], r["pracma_version"]) for r in original["runtime_records"]}
    actual_versions = {(r["R_version"], r["pracma_version"]) for r in audit["runtime_records"]}
    if len(versions) != 1 or not actual_versions.issubset(versions):
        raise ValueError("Native-helper R/pracma runtime differs from the paired primary")
    full = (
        audit["full_48_quarter_artifacts_verified"]
        and audit["matches_declared_config"]
        and manifest["config"] == config
        and manifest["max_refits"] is None
        and len(paired) == audit["jobs_verified"] == 18
    )
    if not full and not allow_partial:
        raise ValueError("Full native-helper diagnostic requires all 18 declared jobs and 48 dates")
    if not full:
        audit.update(
            metrics=[],
            published_ratio_comparisons=[],
            partial_forest_scores_suppressed=True,
            numerical_agreement_FA_AR_and_all_individual_seeds=None,
        )
    gains = []
    if full:
        by_model = {m["model"]: m for m in audit["metrics"]}
        for seed in config["seeds"]:
            model = f"FA_ARRF_seed{seed}"
            gains.append(
                {
                    "model": model,
                    "RMSE_reduction_vs_matching_FA_AR": 1
                    - by_model[model]["RMSE"] / by_model["FA_AR"]["RMSE"],
                }
            )
    return {
        **audit,
        "status": "full_native_helper_diagnostic_verified_not_causal_primary"
        if full
        else "partial_native_helper_integrity_only",
        "full_native_helper_declaration_verified": full,
        "native_manifest_sha256": _sha(run / "manifest.json"),
        "paired_input_checks": paired,
        "source_primary_artifact_audit_repeated": True,
        "primary_manifest_sha256": binding["source_manifest_sha256"],
        "paired_diagnostic_code_sha256": binding["paired_diagnostic_code_sha256"],
        "primary_result_replaced": False,
        "causal_forecast_comparison": False,
        "future_block_covariates_enter_native_moments": True,
        "native_prior_conversion_not_repaired": True,
        "recorded_R_and_pracma_versions_match_primary": True,
        "original_author_caller_recovered": False,
        "matching_FA_AR_RMSE_reductions": gains,
    }


def run_diagnostic(
    source_run,
    archive,
    engine,
    output,
    config,
    primary,
    *,
    r_library,
    rscript="Rscript",
    workers=4,
    trees=None,
    seeds=None,
    max_refits=None,
    prepare_only=False,
    resume=False,
):
    validate_config(config, primary)
    actual = deepcopy(config)
    if trees is not None:
        actual["trees"] = trees
    if seeds is not None:
        actual["seeds"] = list(seeds)
    validate_config(actual, primary, reduced=True)
    if max_refits is not None and (type(max_refits) is not int or not 1 <= max_refits <= 6):
        raise ValueError("Native-helper refit limit must be one through six")
    source_run, output = Path(source_run).resolve(), Path(output).resolve()
    original = audit_run(source_run, archive, primary, rscript=rscript)
    if (
        not original["full_48_quarter_artifacts_verified"]
        or not original["matches_declared_config"]
    ):
        raise ValueError("Native-helper source requires the complete original primary audit")
    expected = provenance(source_run, config)
    if resume:
        saved = json.loads((output / "manifest.json").read_text())
        if saved.get("native_helper_diagnostic") != expected:
            raise ValueError("Native-helper resume provenance differs")
    run_reconstruction(
        actual,
        archive,
        engine,
        output,
        rscript=rscript,
        r_library=r_library,
        workers=workers,
        max_refits=max_refits,
        prepare_only=True,
        resume=resume,
    )
    manifest = json.loads((output / "manifest.json").read_text())
    manifest["native_helper_diagnostic"] = expected
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    paired = pair_inputs(source_run, output, primary)
    if prepare_only:
        return {
            "status": "native_helper_inputs_paired_no_forests_or_scores",
            "paired_jobs": len(paired),
        }
    run_reconstruction(
        actual,
        archive,
        engine,
        output,
        rscript=rscript,
        r_library=r_library,
        workers=workers,
        max_refits=max_refits,
        resume=True,
    )
    result = audit_diagnostic(output, archive, config, primary, allow_partial=True, rscript=rscript)
    (output / "diagnostic_result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
