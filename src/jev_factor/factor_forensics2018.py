"""Post-hoc factor/preprocessing forensics; no alternative forest fitting or selection."""

# ruff: noqa: E501

from __future__ import annotations

import argparse
import copy
import hashlib
import html
import io
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.linalg import subspace_angles
from sklearn.decomposition import PCA
from threadpoolctl import threadpool_limits

from jev_factor.fred_recipe import FredRecipeRepresentation
from jev_factor.fred_recipe_audit import r_recipe_check, verify_code_archive
from jev_factor.mrf2018 import checked, rich_design
from jev_factor.quarterly import PastRepresentation
from jev_factor.vintage2018 import load_vintage

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "runs/mrf-september2018-v1"
WORK = ROOT / "runs/mrf-factor-forensics"
OUTPUT = ROOT / "reports/mrf-factor-forensics"
BASE = "baseline_all247_fixed5"
SUBSET = "SW125_PCA_only_same_completed_panel"
FUTURE = "keep_future_extremes_same_training_representation"
NAMES = {
    BASE: "All 247 · frozen baseline",
    SUBSET: "125-series PCA · same completion",
    FUTURE: "Keep future extremes · frozen PCA",
    "all247_adaptive_completion_same_five_PCs": "All 247 · adaptive EM (crisis cap)",
    "SW125_adaptive_completion_five_PCs": "125-series adaptive completion",
    "no_outlier_cleaning_refit_all247": "No outlier cleaning · refitted PCA",
    "include_last_observed_origin_in_representation_fit": "Include latest known origin in PCA fit",
    "NONCAUSAL_full_vintage_PCA_on_frozen_training_preparation": "NONCAUSAL · full-vintage PCA only",
    "NONCAUSAL_full_vintage_cleaning_completion_and_PCA": "NONCAUSAL · full-vintage preparation",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def component_comparison(base, alternative, cutoff):
    """Fix signs using training correlation; compare in training-SD units, not raw PC scales."""
    train_b, train_a = base.loc[:cutoff], alternative.loc[:cutoff]
    if not train_b.index.equals(train_a.index) or list(base) != list(alternative):
        raise ValueError("PCA comparison rows/components differ")
    correlations = np.array([np.corrcoef(train_b[c], train_a[c])[0, 1] for c in base])
    signs = np.where(correlations < 0, -1, 1)
    scaled = (alternative - train_a.mean()) / train_a.std(ddof=1) * signs
    normalized_base = (base - train_b.mean()) / train_b.std(ddof=1)
    return normalized_base, scaled, correlations, signs


def keep_future_extremes(rep, frame):
    """Keep fitted training data and loadings fixed; only stop screening new observations."""
    other = copy.deepcopy(rep)
    other.outlier_iqr = None
    z, f = other.transform(frame)
    np.testing.assert_array_equal(z.loc[rep.training_index], rep.training_z)
    return z, f


def r_check(rep, z, scores, subset_pca, subset_scores, raw, data, output):
    directory = WORK / "numerical-check"
    directory.mkdir(parents=True, exist_ok=True)
    train = z.loc[rep.training_index]
    train.to_csv(directory / "train.csv", index=False)
    z.to_csv(directory / "query.csv", index=False)
    pd.DataFrame({"selected": data.sw_membership.to_numpy()}).to_csv(
        directory / "flags.csv", index=False
    )
    raw.iloc[: len(raw) - 8, 1:].to_csv(directory / "MAF_train.csv", index=False)
    data.levels.to_csv(directory / "levels.csv", index=False)
    pd.DataFrame({"code": data.tcodes.to_numpy()}).to_csv(directory / "codes.csv", index=False)
    command = [
        shutil.which("Rscript") or "Rscript",
        str(ROOT / "scripts/reference_factor_forensics.R"),
        *[str(directory / s) for s in ["train.csv", "query.csv", "flags.csv", "MAF_train.csv"]],
        str(directory),
        str(directory / "levels.csv"),
        str(directory / "codes.csv"),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"Independent R factor check failed: {result.stderr}")
    checks = {}
    for name, python_basis, python_scores in [
        ("all", rep.pca.components_, scores),
        ("SW125", subset_pca.components_, subset_scores),
    ]:
        rotation = pd.read_csv(directory / f"{name}_rotation.csv").to_numpy()
        sign = np.sign(np.sum(rotation * python_basis, axis=1))
        error = float(np.max(abs(rotation * sign[:, None] - python_basis)))
        score_error = float(
            np.max(
                abs(
                    pd.read_csv(directory / f"{name}_scores.csv").to_numpy() * sign
                    - python_scores.to_numpy()
                )
            )
        )
        if error > 1e-10 or score_error > 1e-10:
            raise ValueError("Independent R PCA check failed")
        checks[name] = dict(
            max_sign_aligned_loading_error=error,
            max_score_error=score_error,
            opposite_sign_components=int((sign < 0).sum()),
        )
    r_maf = pd.read_csv(directory / "MAF_rotation.csv")
    ntrain = len(raw) - 8
    maximum = 0.0
    for j in range(247):
        lagged = raw.iloc[:ntrain, 1 + j * 8 : 1 + (j + 1) * 8]
        pc = PCA(2, svd_solver="full").fit(lagged)
        rot = r_maf.loc[r_maf.series_index.eq(j)].iloc[:, 2:].to_numpy()
        sign = np.sign(np.sum(rot * pc.components_, axis=1))
        maximum = max(maximum, float(np.max(abs(rot * sign[:, None] - pc.components_))))
    if maximum > 1e-9:
        raise ValueError("Independent R MAF check failed")
    transformed = pd.read_csv(directory / "independent-transformed.csv").to_numpy()
    expected = data.panel.to_numpy()
    if not np.array_equal(np.isnan(transformed), np.isnan(expected)):
        raise ValueError("Independent R transformation missingness mismatch")
    transform_error = float(np.nanmax(abs(transformed - expected)))
    transform_scaled_error = float(
        np.nanmax(abs(transformed - expected) / np.maximum(1, abs(expected)))
    )
    if transform_scaled_error > 1e-12:
        raise ValueError("Independent R transformation values differ")
    query_raw = data.panel.loc[z.index].to_numpy()
    expected_mask = np.isfinite(query_raw) & ~np.isfinite(rep._clean(query_raw))
    if not np.array_equal(
        expected_mask,
        pd.read_csv(directory / "independent-outlier-mask.csv").to_numpy().astype(bool),
    ):
        raise ValueError("Independent R outlier masks differ")
    thresholds = pd.read_csv(directory / "independent-outlier-thresholds.csv").to_numpy()
    threshold_error = float(np.max(abs(thresholds - np.column_stack([rep.median, rep.iqr]))))
    if not np.allclose(thresholds, np.column_stack([rep.median, rep.iqr]), rtol=1e-12, atol=1e-12):
        raise ValueError("Independent R outlier thresholds differ")
    checks.update(
        MAF_max_sign_aligned_loading_error=maximum,
        transform_max_error=transform_error,
        transform_max_relative_to_max_one_and_value=transform_scaled_error,
        transform_missing_masks_equal=True,
        outlier_masks_equal=True,
        outlier_threshold_max_error=threshold_error,
        R_runtime=(directory / "runtime.txt").read_text().strip(),
    )
    (output / "independent-numerical-check.json").write_text(json.dumps(checks, indent=2) + "\n")
    return checks


@threadpool_limits.wrap(limits=1)
def audit_preprocessing(output=OUTPUT):
    output.mkdir(parents=True, exist_ok=True)
    manifest = checked(RUN)
    source_before = {
        n: sha(RUN / n) for n in ["manifest.json", "audit.json", "predictions.csv", "metrics.csv"]
    }
    data = load_vintage(Path(manifest["archive"]))
    config = json.loads((ROOT / "configs/factor_forensics2018.json").read_text())
    metadata_zip = ROOT / "../../work/fred-qd-official-appendix.zip"
    with zipfile.ZipFile(metadata_zip) as zf:
        description = pd.read_csv(
            io.BytesIO(zf.read("FRED-QD Appendix/FRED-QD_historic_appendix.csv")), encoding="cp1252"
        )
    description = description.set_index("FRED MNEMONIC")
    whole_panel = data.panel.loc["1959Q3":]
    full_representation = PastRepresentation(5, 10).fit(whole_panel)
    _, full_vintage_scores = full_representation.transform(whole_panel)
    variants, masks, drivers, summary, records, all_scores = [], [], [], [], [], {}
    for window in manifest["windows"]:
        end = pd.Period(window["fit_end"], freq="Q")
        cutoff, through = end - 1, end + 7
        panel = data.panel.loc["1959Q3":through]
        rep = PastRepresentation(5, 10).fit(panel.loc[:cutoff])
        z, factors = rep.transform(panel)
        matrix, raw, _, meta = rich_design(data, end, end + 8, manifest["config"])
        frozen = pd.read_csv(window["matrix"])
        rebuilt = matrix.copy()
        rebuilt.iloc[-8:, 0] = rebuilt.iloc[:-8, 0].mean()
        input_error = float(np.max(abs(rebuilt.to_numpy() - frozen.to_numpy())))
        if input_error > 1e-10:
            raise ValueError("Frozen input reconstruction failed")
        # Verify lag timing against named calendar observations, including every MAF.
        n = meta["ntrain"]
        maf_error = 0.0
        for j, _name in enumerate(z):
            lagged = raw[[f"raw_{j:03d}_lag{k}" for k in range(8)]].to_numpy()
            values, vectors = np.linalg.eigh(np.cov(lagged[:n], rowvar=False, ddof=1))
            basis = vectors[:, np.argsort(values)[-2:][::-1]].T
            expected_basis = np.asarray(meta["MAF_loadings"])[j]
            sign = np.sign(np.sum(basis * expected_basis, axis=1))
            projected = (lagged - lagged[:n].mean(axis=0)) @ (basis * sign[:, None]).T
            actual = matrix[[f"MAF_{j:03d}_{k}" for k in [1, 2]]].to_numpy()
            maf_error = max(maf_error, float(np.max(abs(projected - actual))))
        if maf_error > 1e-9:
            raise ValueError("Independent covariance MAF reconstruction failed")
        # These are diagnostic variants, not candidate models ranked by held-out loss.
        subset = data.sw_membership.eq(1)
        subset_pca = PCA(5, svd_solver="full").fit(z.loc[:cutoff, subset])
        subset_scores = pd.DataFrame(
            subset_pca.transform(z.loc[:, subset]), index=z.index, columns=factors.columns
        )
        _, future_scores = keep_future_extremes(rep, panel)
        adaptive = FredRecipeRepresentation().fit(panel.loc[:cutoff])
        _, adaptive_scores = adaptive.transform(panel)
        adaptive_sw = FredRecipeRepresentation().fit(panel.loc[:cutoff, subset])
        _, adaptive_sw_scores = adaptive_sw.transform(panel.loc[:, subset])
        no_clean = PastRepresentation(5, None).fit(panel.loc[:cutoff])
        _, no_clean_scores = no_clean.transform(panel)
        plus_origin = PastRepresentation(5, 10).fit(panel.loc[:end])
        _, plus_scores = plus_origin.transform(panel)
        extended_z, _ = rep.transform(whole_panel)
        extended_pca = PCA(5, svd_solver="full").fit(extended_z)
        extended_scores = pd.DataFrame(
            extended_pca.transform(extended_z), index=extended_z.index, columns=factors.columns
        ).loc[panel.index]
        bank = {
            BASE: factors,
            SUBSET: subset_scores,
            FUTURE: future_scores,
            "all247_adaptive_completion_same_five_PCs": adaptive_scores,
            "SW125_adaptive_completion_five_PCs": adaptive_sw_scores,
            "no_outlier_cleaning_refit_all247": no_clean_scores,
            "include_last_observed_origin_in_representation_fit": plus_scores,
            "NONCAUSAL_full_vintage_PCA_on_frozen_training_preparation": extended_scores,
            "NONCAUSAL_full_vintage_cleaning_completion_and_PCA": full_vintage_scores.loc[
                panel.index
            ],
        }
        if set(bank) != set(config["variants"]):
            raise ValueError("Undeclared preprocessing diagnostic")
        all_scores[window["group"]] = bank
        for variant, candidate in bank.items():
            base_z, candidate_z, corrs, signs = component_comparison(factors, candidate, cutoff)
            for date in candidate.index:
                if date < pd.Period("2006Q1", freq="Q"):
                    continue
                for k in range(5):
                    variants.append(
                        dict(
                            group=window["group"],
                            fit_end=str(end),
                            origin_date=str(date),
                            variant=variant,
                            component=f"F{k + 1}",
                            raw_score=candidate.loc[date].iloc[k],
                            sign_aligned_training_SD=candidate_z.loc[date].iloc[k],
                            training_correlation=corrs[k],
                            sign=signs[k],
                        )
                    )
            for k in range(2):
                records.append(
                    dict(
                        group=window["group"],
                        fit_end=str(end),
                        variant=variant,
                        component=f"F{k + 1}",
                        training_correlation=corrs[k],
                        normalized_RMS_difference=float(
                            np.sqrt(
                                np.mean(
                                    (
                                        base_z.iloc[:, k].loc[:cutoff]
                                        - candidate_z.iloc[:, k].loc[:cutoff]
                                    )
                                    ** 2
                                )
                            )
                        ),
                    )
                )
        raw_values = panel.to_numpy()
        clean = rep._clean(raw_values)
        removed = np.isfinite(raw_values) & ~np.isfinite(clean)
        for i, date in enumerate(panel.index):
            if date < pd.Period("2006Q1", freq="Q"):
                continue
            for j in np.flatnonzero(removed[i]):
                masks.append(
                    dict(
                        group=window["group"],
                        fit_end=str(end),
                        origin_date=str(date),
                        series=panel.columns[j],
                        raw=raw_values[i, j],
                        median=rep.median[j],
                        IQR=rep.iqr[j],
                        imputed=z.iloc[i, j] * rep.std[j] + rep.mean[j],
                        training_row=date <= cutoff,
                        SW=int(subset.iloc[j]),
                    )
                )
        eigen = rep.pca.explained_variance_ratio_
        summary.append(
            dict(
                group=window["group"],
                fit_end=str(end),
                rep_end=str(cutoff),
                ntrain=n,
                training_outliers=rep.training_outliers,
                frozen_matrix_max_error=input_error,
                MAF_covariance_max_score_error=maf_error,
                all_active=bool(rep.active.all()),
                F1_variance_ratio=eigen[0],
                F2_variance_ratio=eigen[1],
                F3_variance_ratio=eigen[2],
                F2_F3_variance_ratio=eigen[1] / eigen[2],
                adaptive_rank=adaptive.em.rank_history[-1],
                adaptive_converged=adaptive.em.converged,
                adaptive_iterations=adaptive.em.iterations,
                SW_adaptive_rank=adaptive_sw.em.rank_history[-1],
                SW_adaptive_converged=adaptive_sw.em.converged,
                SW_adaptive_iterations=adaptive_sw.em.iterations,
            )
        )
        if window["group"] == 3:
            full_comparison = []
            for variant, candidate in bank.items():
                _, scaled, _, _ = component_comparison(factors, candidate, cutoff)
                for date, row in scaled.iterrows():
                    full_comparison.append(
                        dict(
                            variant=variant,
                            origin_date=str(date),
                            role="training" if date <= cutoff else "later_origin",
                            **row.to_dict(),
                        )
                    )
            pd.DataFrame(full_comparison).to_csv(
                output / "crisis-training-and-query-factors.csv", index=False
            )
            for date in pd.period_range("2007Q1", "2010Q3", freq="Q"):
                for k in range(2):
                    contribution = (z.loc[date].to_numpy() - rep.pca.mean_) * rep.pca.components_[k]
                    if not np.isclose(contribution.sum(), factors.loc[date].iloc[k], atol=1e-10):
                        raise ValueError("PCA contribution accounting failed")
                    for j, name in enumerate(z.columns):
                        drivers.append(
                            dict(
                                origin_date=str(date),
                                component=f"F{k + 1}",
                                series=name,
                                SW=int(subset.iloc[j]),
                                group=int(description.loc[name, "Group"])
                                if name in description.index
                                else 0,
                                description=description.loc[name, "DESCRIPTION"]
                                if name in description.index
                                else "Not matched by exact mnemonic in the separately dated metadata appendix",
                                standardized_value=z.loc[date, name],
                                loading=rep.pca.components_[k, j],
                                contribution=contribution[j],
                                removed_as_outlier=bool(removed[panel.index.get_loc(date), j]),
                            )
                        )
            numerical = r_check(rep, z, factors, subset_pca, subset_scores, raw, data, output)
            numerical["official_recipe_source"] = verify_code_archive(
                ROOT / "../../work/fred-databases-code.zip"
            )
            for name, fitted, training in [
                ("adaptive_all247", adaptive, panel.loc[:cutoff]),
                ("adaptive_SW125", adaptive_sw, panel.loc[:cutoff, subset]),
            ]:
                directory = WORK / name
                directory.mkdir(parents=True, exist_ok=True)
                numerical[name] = r_recipe_check(
                    training, fitted, shutil.which("Rscript") or "Rscript", directory
                )
            (output / "independent-numerical-check.json").write_text(
                json.dumps(numerical, indent=2) + "\n"
            )
            # Save all comparison quantities without using forecast outcomes for fitting them.
            sub_basis = np.zeros((5, 247))
            sub_basis[:, subset] = subset_pca.components_
            subspace = dict(
                first_two_degrees=np.degrees(
                    subspace_angles(rep.pca.components_[:2].T, sub_basis[:2].T)
                ).tolist(),
                first_five_degrees=np.degrees(
                    subspace_angles(rep.pca.components_.T, sub_basis.T)
                ).tolist(),
            )
            pd.DataFrame(rep.pca.components_, index=factors.columns, columns=z.columns).to_csv(
                output / "crisis-baseline-loadings.csv"
            )
            pd.DataFrame(
                subset_pca.components_, index=factors.columns, columns=z.columns[subset]
            ).to_csv(output / "crisis-subset-loadings.csv")
    variant_frame = pd.DataFrame(variants)
    variant_frame.to_csv(output / "factor-variant-scores.csv", index=False)
    pd.DataFrame(masks).to_csv(output / "outlier-cells.csv", index=False)
    pd.DataFrame(drivers).to_csv(output / "factor-drivers.csv", index=False)
    pd.DataFrame(summary).to_csv(output / "preprocessing-checks.csv", index=False)
    pd.DataFrame(records).to_csv(output / "training-factor-comparisons.csv", index=False)
    snapshot = variant_frame.loc[
        variant_frame.group.eq(3)
        & variant_frame.origin_date.eq("2008Q4")
        & variant_frame.component.isin(["F1", "F2"])
    ]
    snapshot.to_csv(output / "crisis-factor-snapshot.csv", index=False)
    # Original forecast arithmetic: these are saved model outputs, not variant forecasts.
    from jev_factor.diagnostics2018 import load_diagnostics

    original = load_diagnostics(RUN)
    original["contributions"].to_csv(output / "original-contributions.csv", index=False)
    original["predictions"].to_csv(output / "original-predictions.csv", index=False)
    checked(RUN)
    if source_before != {n: sha(RUN / n) for n in source_before}:
        raise ValueError("Original artifacts changed during diagnostic")
    record = dict(
        status="preprocessing_audited",
        study=config,
        source_hashes=source_before,
        source_model_code=manifest["code"],
        diagnostic_code_sha256=sha(__file__),
        config_sha256=sha(ROOT / "configs/factor_forensics2018.json"),
        official_metadata_archive_sha256=sha(metadata_zip),
        independent_numerical_check=numerical,
        crisis_subspace_comparison=subspace,
        new_variant_forest_fits=0,
        new_variant_forecast_losses_computed=False,
        original_predictions_replaced=False,
        author_pipeline_recovered=False,
    )
    (output / "audit.json").write_text(json.dumps(record, indent=2) + "\n")
    print(
        snapshot[
            [
                "variant",
                "component",
                "raw_score",
                "sign_aligned_training_SD",
                "training_correlation",
            ]
        ].to_string(index=False),
        flush=True,
    )
    return record


def inspect_replay(output=OUTPUT):
    manifest = checked(RUN)
    job = next(j for j in manifest["jobs"] if j["group"] == 3 and j["seed"] == 101)
    folder = WORK / "crisis-replay"
    original = pd.read_csv(job["prediction_path"])
    replayed = pd.read_csv(folder / "replay.csv")
    difference = float(np.max(abs(original.to_numpy() - replayed.to_numpy())))
    if difference > 1e-12:
        raise ValueError("Crisis replay does not match every original forecast and coefficient")
    subprocess.run(
        [
            shutil.which("Rscript") or "Rscript",
            str(ROOT / "scripts/inspect_crisis_forest.R"),
            str(folder / "replay.csv.fit.rds"),
            job["matrix"],
            str(manifest["windows"][3]["metadata"]["ntrain"]),
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    support = pd.read_csv(output / "crisis-leaf-support.csv")
    align = pd.read_csv(manifest["windows"][3]["alignment"])
    support["training_target_date"] = [
        align.iloc[int(i) - 1].target_date for i in support.row_index
    ]
    support["training_origin_date"] = [
        align.iloc[int(i) - 1].origin_date for i in support.row_index
    ]
    support["actual_training_target"] = [align.iloc[int(i) - 1].actual for i in support.row_index]
    support.to_csv(output / "crisis-leaf-support.csv", index=False)
    leaves = pd.read_csv(output / "crisis-routed-leaves.csv")
    if len(leaves) != 100 or leaves.tree.nunique() != 100:
        raise ValueError("Incomplete crisis routing audit")
    coefficient_error = float(
        np.max(
            abs(leaves[original.columns[1:]].mean().to_numpy() - original.iloc[0, 1:].to_numpy())
        )
    )
    if coefficient_error > 1e-10:
        raise ValueError("Mean routed-leaf coefficients do not reproduce original forecast")
    a = json.loads((output / "audit.json").read_text())
    a["status"] = "preprocessing_and_crisis_routing_audited"
    a["crisis_replay"] = dict(
        seed=101,
        trees=100,
        fit_end="2008Q4",
        target="2009Q1",
        saved_output_max_difference=difference,
        original_output_sha256=sha(job["prediction_path"]),
        replay_output_sha256=sha(folder / "replay.csv"),
        routed_leaf_mean_coefficient_max_difference=coefficient_error,
        within_leaf_coefficient_difference=float(
            pd.read_csv(output / "leaf-verification.csv").iloc[0, 0]
        ),
        leaf_count=len(leaves),
        median_training_leaf_rows=float(leaves.training_leaf_n.median()),
        median_split_sample_rows=float(leaves.split_sample_n.median()),
    )
    (output / "audit.json").write_text(json.dumps(a, indent=2) + "\n")
    print(json.dumps(a["crisis_replay"], indent=2))
    return a


def make_report(output=OUTPUT):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    record = json.loads((output / "audit.json").read_text())
    if record["status"] != "preprocessing_and_crisis_routing_audited":
        raise ValueError("Complete the crisis replay and independent checks before publishing")
    if record["source_hashes"] != {n: sha(RUN / n) for n in record["source_hashes"]}:
        raise ValueError("Frozen original result changed")
    score = pd.read_csv(output / "factor-variant-scores.csv")
    score = score[score.group.eq(3)]
    full = pd.read_csv(output / "crisis-training-and-query-factors.csv")
    drivers = pd.read_csv(output / "factor-drivers.csv")
    masks = pd.read_csv(output / "outlier-cells.csv")
    contributions = pd.read_csv(output / "original-contributions.csv")
    leaves = pd.read_csv(output / "crisis-routed-leaves.csv")
    support = pd.read_csv(output / "crisis-leaf-support.csv")
    snapshot = pd.read_csv(output / "crisis-factor-snapshot.csv")
    prep = pd.read_csv(output / "preprocessing-checks.csv")
    first = snapshot[snapshot.component.eq("F2")].set_index("variant")
    baseline_sd = first.loc[BASE, "raw_score"] / first.loc[BASE, "sign_aligned_training_SD"]
    d = drivers[drivers.origin_date.eq("2008Q4") & drivers.component.eq("F2")].copy()
    by_membership = d.groupby("SW").contribution.sum()
    removed = masks[masks.group.eq(3) & masks.origin_date.eq("2008Q4")]
    comp = contributions[contributions.target_date.eq("2009Q1")].set_index("model")
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": "#a7b1bb",
            "text.color": "#203647",
            "axes.labelcolor": "#203647",
            "grid.color": "#e1e6ec",
            "axes.axisbelow": True,
            "svg.fonttype": "none",
        }
    )
    figs = output / "figures"
    figs.mkdir(exist_ok=True)
    gallery = []

    def save(f, slug, title, caption):
        f.savefig(figs / f"{slug}.png", dpi=170, facecolor="white")
        f.savefig(figs / f"{slug}.svg", facecolor="white")
        plt.close(f)
        gallery.append(dict(slug=slug, title=title, caption=caption))

    def axis_time(ax, dates):
        ticks = np.arange(len(dates))[::2]
        ax.set_xticks(ticks, np.asarray(dates)[ticks], rotation=20)
        ax.set_xlabel("Predictor observation / forecast origin quarter")
        ax.grid(axis="y")
        if "2008Q4" in list(dates):
            ax.axvline(list(dates).index("2008Q4"), color="#a8b1bb", linestyle="--", lw=1)

    colors = {
        BASE: "#2563a6",
        SUBSET: "#c35935",
        FUTURE: "#9365a2",
        "SW125_adaptive_completion_five_PCs": "#35816b",
        "NONCAUSAL_full_vintage_cleaning_completion_and_PCA": "#9365a2",
    }
    f, axes = plt.subplots(2, 1, figsize=(11, 7.2), layout="constrained", sharex=True)
    for ax, component in zip(axes, ["F1", "F2"], strict=True):
        for variant in [
            BASE,
            SUBSET,
            "SW125_adaptive_completion_five_PCs",
            "NONCAUSAL_full_vintage_cleaning_completion_and_PCA",
        ]:
            s = score[score.component.eq(component) & score.variant.eq(variant)]
            ax.plot(
                np.arange(len(s)),
                s.sign_aligned_training_SD,
                "o-",
                ms=3,
                label=NAMES[variant],
                color=colors[variant],
            )
        ax.axhline(0, color="#5a6775", lw=0.8)
        ax.set_ylabel(f"{component} · own training SDs")
        axis_time(ax, s.origin_date)
    axes[0].set_title("The second factor changes direction at the crisis origin")
    axes[0].legend(ncol=2, fontsize=9)
    save(
        f,
        "01-factor-tail-divergence",
        "High training correlation hides a crisis-tail difference",
        "PCA signs are aligned using training observations only; each factor is scaled by its own training SD. "
        "The dashed line is 2008Q4, used to forecast 2009Q1. The 125-series rule changes PCA eligibility, not the fixed benchmark. "
        "It is a source-motivated diagnostic, not proof of the author's rule. Individual component comparisons are not rotation-invariant.",
    )

    f, axes = plt.subplots(1, 2, figsize=(11, 5), layout="constrained")
    base_train = full[full.variant.eq(BASE) & full.role.eq("training")]
    subset_train = full[full.variant.eq(SUBSET) & full.role.eq("training")]
    for ax, k in zip(axes, ["F1", "F2"], strict=True):
        ax.scatter(
            base_train[k],
            subset_train[k],
            s=16,
            color="#8b9aab",
            alpha=0.6,
            label="Training quarters",
        )
        a = snapshot[snapshot.component.eq(k)].set_index("variant")
        bx = a.loc[BASE, "sign_aligned_training_SD"]
        sx = a.loc[SUBSET, "sign_aligned_training_SD"]
        ax.scatter([bx], [sx], s=90, color="#c35935", marker="D", label="2008Q4")
        ax.annotate("2008Q4", (bx, sx), xytext=(7, 8), textcoords="offset points")
        lo = min(base_train[k].min(), subset_train[k].min(), bx, sx) - 0.3
        hi = max(base_train[k].max(), subset_train[k].max(), bx, sx) + 0.3
        ax.plot([lo, hi], [lo, hi], "--", color="#bbc3ca", lw=1)
        ax.set(
            xlabel="All-247 factor · training SD",
            ylabel="Sign-aligned 125-series factor · training SD",
            title=k,
        )
    axes[0].legend(fontsize=9)
    save(
        f,
        "02-training-versus-crisis",
        "Correlation is not a guarantee about rare states",
        "The same 2008Q4 row sits away from the training relationship, especially for F2. These are unsupervised factor comparisons: "
        "no unemployment outcome was used to align signs, scale scores, or select a component.",
    )

    f, ax = plt.subplots(figsize=(10, 4.2), layout="constrained")
    ax.barh(
        ["125 historical-subset indicators", "122 other indicators"],
        [by_membership.loc[1], by_membership.loc[0]],
        color=["#2563a6", "#c35935"],
    )
    ax.axvline(0, color="#586776", lw=1)
    ax.set(
        xlabel="Contribution to the original all-247 F2 score (PCA units)",
        title="2008Q4: excluded-from-subset indicators account for the positive F2 reading",
    )
    for y, v in enumerate([by_membership.loc[1], by_membership.loc[0]]):
        ax.text(
            v + (0.1 if v >= 0 else -0.1),
            y,
            f"{v:+.3f}",
            va="center",
            ha="left" if v >= 0 else "right",
        )
    ax.set_xlim(min(-2, by_membership.min() - 1), by_membership.max() + 1)
    save(
        f,
        "03-membership-contributions",
        "Where the positive F2 score comes from",
        f"Exact accounting under the original loadings: 125-subset columns contribute {by_membership.loc[1]:+.3f}, "
        f"other columns {by_membership.loc[0]:+.3f}, summing to {first.loc[BASE, 'raw_score']:+.3f}. "
        "This grouping is not the same as refitting subset PCA, and contributions are not causal effects.",
    )

    selected = pd.concat(
        [d.nsmallest(10, "contribution"), d.nlargest(10, "contribution")]
    ).sort_values("contribution")
    f, ax = plt.subplots(figsize=(11, 7.2), layout="constrained")
    ax.barh(
        selected.series,
        selected.contribution,
        color=np.where(selected.SW.eq(1), "#2563a6", "#c35935"),
    )
    ax.axvline(0, color="#586776", lw=1)
    ax.set(
        xlabel="Contribution to original F2 (PCA units)",
        title="Deflation and real-money movements offset housing and equity signals",
    )
    ax.legend(
        handles=[
            Patch(color="#2563a6", label="In historical 125 subset"),
            Patch(color="#c35935", label="Outside subset"),
        ],
        fontsize=9,
        loc="lower right",
    )
    save(
        f,
        "04-factor-drivers",
        "Largest positive and negative F2 contributions at 2008Q4",
        "Exact value × loading terms, after the benchmark's cleaning and completion. Large positive terms include M1REALx, "
        "GFDEBTNx, price indexes and M2REALx. Negative terms include equities, permits and housing. "
        "All terms, descriptions and exact-mnemonic metadata coverage are in factor-drivers.csv.",
    )

    f, axes = plt.subplots(1, 2, figsize=(12, 5.3), layout="constrained")
    original = (removed.raw - removed["median"]) / removed.IQR
    after = (removed.imputed - removed["median"]) / removed.IQR
    y = np.arange(len(removed))
    axes[0].plot(original, y, "o", label="Observed transformed value", color="#c35935")
    axes[0].plot(after, y, "s", label="Value after completion", color="#2563a6")
    axes[0].hlines(y, np.minimum(original, after), np.maximum(original, after), color="#c3cbd2")
    axes[0].set_yticks(y, removed.series)
    for v in [-10, 10]:
        axes[0].axvline(v, color="#9ca9b5", linestyle="--", lw=1)
    axes[0].set(
        xlabel="(Value − training median) / training IQR",
        title="Ten observed extremes are replaced",
    )
    axes[0].legend(fontsize=8)
    for variant in [BASE, FUTURE]:
        s = score[score.variant.eq(variant) & score.component.eq("F2")]
        axes[1].plot(
            range(len(s)), s.sign_aligned_training_SD, label=NAMES[variant], color=colors[variant]
        )
    axis_time(axes[1], s.origin_date)
    axes[1].set(ylabel="F2 · baseline training SD", title="Does keeping them reverse F2?")
    axes[1].legend(fontsize=8)
    save(
        f,
        "05-cleaning-extremes",
        "Cleaning removes policy/price extremes, but is a separate mechanism",
        "Left compares actual transformed inputs with their imputed replacements. Right holds all training data, moments and PCA "
        "loadings fixed, and merely stops screening future observations. This is an input-sensitivity check, not a new forecast model.",
    )

    f, axes = plt.subplots(1, 2, figsize=(13, 6), layout="constrained", sharey=True)
    order = list(NAMES)
    labels = [NAMES[v] for v in order]
    for ax, k in zip(axes, ["F1", "F2"], strict=True):
        values = (
            snapshot[snapshot.component.eq(k)]
            .set_index("variant")
            .loc[order, "sign_aligned_training_SD"]
        )
        ax.barh(np.arange(len(order)), values, color=[colors.get(v, "#96a6b7") for v in order])
        ax.axvline(0, color="#586776", lw=1)
        ax.set_yticks(np.arange(len(order)), labels)
        ax.set(xlabel="Sign-aligned own training SD", title=k + " · origin 2008Q4")
    axes[0].invert_yaxis()
    save(
        f,
        "06-variant-isolation",
        "Nine explicitly labeled preparation diagnostics",
        "The subset-only variant preserves all original completed raw indicators and MAFs; adaptive variants change completion. "
        "The latest-origin variant fits unsupervised representations through the already-observed 2008Q4 covariates rather than 2008Q3. "
        "The two NONCAUSAL controls use later predictor data through 2018Q2 and are inadmissible as deployable benchmarks. "
        "The all-panel adaptive EM reaches its 50-iteration cap in the crisis refit. None is chosen by forecast loss or substituted into the benchmark.",
    )

    f, ax = plt.subplots(figsize=(11, 4.5), layout="constrained")
    terms = ["intercept", "AR", "F1", "F2"]
    for j, (model, row) in enumerate(comp.iterrows()):
        delta = [100 * (row[t] - row[f"static_{t}"]) for t in terms]
        ax.bar(
            np.arange(4) + (j - 1) * 0.24,
            delta,
            width=0.23,
            color=["#c35935", "#9f396a", "#8f70b0"][j],
            label=model.replace("FA_ARRF_", ""),
        )
    ax.axhline(0, color="#586776", lw=1)
    ax.set_xticks(range(4), ["Intercept", "Target history", "Factor 1", "Factor 2"])
    ax.set(
        ylabel="MRF − same-equation static contribution (log points)",
        title="The dynamic adjustment makes 2009Q1 worse mainly by weakening F1",
    )
    ax.legend(ncol=3, fontsize=9)
    save(
        f,
        "07-crisis-adjustment-accounting",
        "The immediate forecast failure is not only the F2 input",
        "Every bar is saved forecast accounting with identical factor coordinates and the same four slope terms. "
        "The forest boosts its intercept but lowers F1's positive contribution enough to outweigh that boost. "
        "A questionable F2 crisis signal and the learned coefficient map are distinct links in the failure chain.",
    )

    job = json.loads((RUN / "manifest.json").read_text())["windows"][3]
    matrix = pd.read_csv(job["matrix"])
    values = matrix.iloc[-8]
    f, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
    row = comp.loc["FA_ARRF_seed101"]
    for ax, k in zip(axes, ["F1", "F2"], strict=True):
        tree_contribution = leaves[f"{k}_lag1"] * values[f"{k}_lag1"] * 100
        ax.hist(tree_contribution, bins=18, color="#c58b73", alpha=0.9)
        ax.axvline(
            row[f"static_{k}"] * 100, color="#2563a6", label="Static same-equation OLS", lw=2
        )
        ax.axvline(row[k] * 100, color="#263b4b", label="Original forest mean", lw=2)
        ax.set(
            title=f"{k} contribution · 2009Q1",
            xlabel="Per-tree contribution (log points)",
            ylabel="Trees",
        )
    axes[0].legend(fontsize=8)
    save(
        f,
        "08-routed-leaf-contributions",
        "The actual crisis trees, not a hypothetical refit",
        "Storage-only 2008Q4/seed-101 replay matches all eight forecasts and every coefficient exactly. "
        "Each tree is routed with its original native normalization and saved leaf paths; all row partitions and within-leaf "
        "coefficient blocks are checked. Histograms show model-component dispersion, not predictive uncertainty.",
    )

    f, axes = plt.subplots(1, 2, figsize=(11, 4.3), layout="constrained")
    axes[0].hist(leaves.training_leaf_n, bins=14, color="#2563a6")
    axes[0].set(
        xlabel="All training rows routed to crisis leaf",
        ylabel="Trees",
        title="Local regression support",
    )
    decades = (
        (support.training_target_date.str[:4].astype(int) // 10 * 10).value_counts().sort_index()
    )
    axes[1].bar(decades.index.astype(str), decades, color="#c35935")
    axes[1].set(
        xlabel="Training-target decade",
        ylabel="Row memberships across 100 leaves",
        title="Which history supports the crisis prediction?",
    )
    save(
        f,
        "09-crisis-leaf-support",
        "Training observations behind the crisis forecast",
        "These are full training-leaf memberships, including rows not selected for split construction. "
        "They are not independent observations across trees. Neighbor smoothing and the OLS prior contribute additional information "
        "outside the listed leaf rows; decades are calendar bins, not official recession labels.",
    )

    f, axes = plt.subplots(1, 2, figsize=(11, 4.2), layout="constrained")
    axes[0].plot(prep.fit_end, prep.F2_variance_ratio, "o-", label="PC2")
    axes[0].plot(prep.fit_end, prep.F3_variance_ratio, "s-", label="PC3")
    axes[0].set(
        ylabel="Fraction of standardized training variance", title="PC2 and PC3 are not nearly tied"
    )
    axes[0].legend(fontsize=9)
    axes[1].plot(prep.fit_end, prep.adaptive_rank, "o-", label="All 247")
    axes[1].plot(prep.fit_end, prep.SW_adaptive_rank, "s-", label="125 subset")
    axes[1].set(
        ylabel="Selected completion rank", title="Completion rank ≠ five retained state PCs"
    )
    axes[1].legend(fontsize=9)
    for ax in axes:
        ax.tick_params(axis="x", rotation=25)
        ax.set_xlabel("Refit cutoff")
        ax.grid(axis="y")
    save(
        f,
        "10-eigenspectrum-and-rank",
        "Separate numerical failure from a different factor definition",
        "All six frozen states and all 1,482 per-series MAF constructions are checked. Independent base R verifies crisis-window "
        "transformations, masks, thresholds, PCA scores/loadings, all 247 MAF bases, and adaptive completion on both panels. "
        "A separated eigenvalue pair weakens a numerical near-tie explanation, not every possible rotation or preprocessing explanation.",
    )

    numerical = record["independent_numerical_check"]
    f1 = comp.loc["FA_ARRF_seed101", "F1"] * 100
    f1static = comp.loc["FA_ARRF_seed101", "static_F1"] * 100
    findings = dict(
        baseline_F2_training_standard_deviation=float(baseline_sd),
        baseline_F2_at_2008Q4=float(first.loc[BASE, "raw_score"]),
        baseline_F2_training_SD=float(first.loc[BASE, "sign_aligned_training_SD"]),
        subset_F2_sign_aligned_training_SD=float(first.loc[SUBSET, "sign_aligned_training_SD"]),
        training_F2_correlation=float(first.loc[SUBSET, "training_correlation"]),
        future_extremes_kept_F2_training_SD=float(first.loc[FUTURE, "sign_aligned_training_SD"]),
        NONCAUSAL_full_vintage_preparation_F2_training_SD=float(
            first.loc[
                "NONCAUSAL_full_vintage_cleaning_completion_and_PCA", "sign_aligned_training_SD"
            ]
        ),
        NONCAUSAL_full_vintage_preparation_F2_training_correlation=float(
            first.loc["NONCAUSAL_full_vintage_cleaning_completion_and_PCA", "training_correlation"]
        ),
        NONCAUSAL_PCA_only_F2_training_correlation=float(
            first.loc[
                "NONCAUSAL_full_vintage_PCA_on_frozen_training_preparation", "training_correlation"
            ]
        ),
        F2_score_SW_member_contribution=float(by_membership.loc[1]),
        F2_score_nonmember_contribution=float(by_membership.loc[0]),
        observed_cells_removed_at_crisis_origin=len(removed),
        seed101_F1_contribution_log_points=float(f1),
        same_equation_static_F1_contribution_log_points=float(f1static),
        author_factor_pipeline_recovered=False,
        original_crisis_predictions_replaced=False,
    )
    record["findings"] = findings
    record["figures"] = gallery
    record["figure_count"] = len(gallery)
    record["diagnostic_code_sha256"] = sha(__file__)
    record["forensic_helper_sha256"] = {
        name: sha(ROOT / name)
        for name in [
            "scripts/reference_factor_forensics.R",
            "scripts/inspect_crisis_forest.R",
            "scripts/trace_mrf2018.R",
            "src/jev_factor/reference_fred_em.R",
        ]
    }
    record["FRED_QD_reference_paper"] = {
        "url": "https://www.stlouisfed.org/-/media/project/frbstl/stlouisfed/publications/review/pdfs/2021/01/14/fred-qd-a-quarterly-database-for-macroeconomic-research.pdf",
        "sha256": sha(ROOT / "../../work/fred-qd-reference-paper.pdf"),
        "evidence": "Section 3 distinguishes 125-series comparisons from all-series/full-observation factors; F2 is described as forward-looking in both.",
    }
    (output / "audit.json").write_text(json.dumps(record, indent=2) + "\n")
    note = f"""# Why does our MRF miss the crisis? Factor and preprocessing forensics

The strongest localized finding is a factor-definition problem worth investigating,
not a proven recovery of the original paper. The original benchmark is unchanged.

## What we found

At the 2008Q4 predictor observation used for the 2009Q1 forecast, our all-247 F2 is
{findings["baseline_F2_training_SD"]:+.3f} training SDs. A PCA-only change to the
historical 125-series subset gives {findings["subset_F2_sign_aligned_training_SD"]:+.3f}
training SDs after aligning signs on training data. The training correlation is
{findings["training_F2_correlation"]:.3f}. This is not a cosmetic PCA sign flip:
the rare crisis observation differs substantially despite high ordinary correlation.

Under the original all-247 loadings, the 125-subset columns contribute
{findings["F2_score_SW_member_contribution"]:+.3f} to the raw F2 score, while the
122 other columns contribute {findings["F2_score_nonmember_contribution"]:+.3f}.
Deflation/real-money movements offset housing and equity signals in this factor.
The membership grouping uses the vintage's actual flags; metadata descriptions
are exact-name matches from a separately dated official appendix, with unknown
names explicitly labeled rather than guessed.

Cleaning removes {len(removed)} observed extremes at this origin, replacing them
with low-rank estimates. Keeping future extremes but fixing all training values,
moments and loadings gives an F2 reading of
{findings["future_extremes_kept_F2_training_SD"]:+.3f} training SDs.
This isolates future screening; the no-cleaning refit is a different experiment.
See the comparison plots rather than assuming cleaning caused the factor direction.

There is also a learned-map issue. In the original seed-101 crisis forecast, F1
contributes {f1:.3f} log points, versus {f1static:.3f} for the same-equation static
OLS. The forest's lower F1 contribution outweighs its helpful intercept change.
F2 input construction and dynamic coefficient fitting therefore need to be
distinguished; changing a factor does not automatically repair the model.

## Factor-estimation timing is another live hypothesis

The explicitly NONCAUSAL control fits cleaning, completion and PCA using the
entire September-vintage history through 2018Q2. It retains all 247 series,
but changes the 2008Q4 F2 reading to
{findings["NONCAUSAL_full_vintage_preparation_F2_training_SD"]:+.3f} pre-cutoff training
SDs, with training correlation
{findings["NONCAUSAL_full_vintage_preparation_F2_training_correlation"]:.3f} to the original F2.
Thus subset selection is not the only way to reverse this tail reading.
Factor-estimation timing can matter even with the full indicator panel.

The PCA-only full-vintage control on frozen old moments/completion has only
{findings["NONCAUSAL_PCA_only_F2_training_correlation"]:.3f} training correlation for
component 2, so its nominal F2 is not a close match to the original factor.
Do not interpret that comparison as a mere rescaling of one economic quantity.
No future-informed factor is adopted as a deployable benchmark, and no claim
is made that the paper used future data. The original caller is still missing.

The FRED-QD reference paper (McCracken and Ng, 2021, Section 3) explicitly
compares 125-series subset factors with factors using all series and observations;
it describes F2 as forward-looking in both. Consequently, the MRF paper's
economic label does not establish which eligibility or fitting window it used.
This reinforces the need to check the author's actual preparation rather than
choose whichever variant gives an attractive crisis reading.

## What passed

- All six frozen state matrices rebuild, without replacing them.
- All 247 raw transformations and missingness masks agree with independent base R.
- Crisis-window 10-IQR masks and thresholds agree with independent base R.
- All six sets of 247 MAF scores agree with independent covariance eigensystems.
- Crisis-window all-series and subset PCA scores/loadings agree with base R up to signs.
- All 247 crisis-window MAF loading pairs agree with base R up to signs.
- Source-recipe adaptive completion is independently checked in R for both panels.
- The original 2008Q4/seed-101/100-tree fit is replayed with storage only. Every
  saved forecast and coefficient matches; routed leaf partitions and coefficient
  accounting verify.

Maximum transformation discrepancy: {numerical["transform_max_error"]:.3g}.
Maximum transformation discrepancy divided by max(1, absolute value):
{numerical["transform_max_relative_to_max_one_and_value"]:.3g}; absolute errors are
largest on the federal-debt difference measured in large native units.
Maximum all-panel PCA score discrepancy: {numerical["all"]["max_score_error"]:.3g}.
Maximum R/Python MAF loading discrepancy: {numerical["MAF_max_sign_aligned_loading_error"]:.3g}.

Passing these checks establishes our arithmetic and the saved-input contract,
not the paper's original factor inputs or runner. PC2/PC3 are not nearly tied
in this training sample, weakening a simple numerical component-swap explanation.
Up-to-sign PCA agreement does not establish forecast invariance to signs in
this particular forest engine; the earlier basis audit documented that separate
source behavior. Here, comparison signs are fixed using training correlations.

## What this does not establish

We have not obtained the author's original factor series or preprocessing caller.
The historical 125 flags describe a Stock-Watson subset; they do not prove the
MRF paper selected that subset. The reference paper's economic labels cannot
be used to choose a convenient PCA or sign pattern after seeing test errors.
No new variant forest or alternative forecast-loss table is produced here.
All nine preparations are source-motivated, post-hoc diagnostic comparisons.
The two explicitly NONCAUSAL full-vintage controls use later predictor values,
including the UNRATE panel series, through 2018Q2. They are not fair benchmark
candidates or evidence that the original author used future data.
All-panel adaptive completion reaches the source's 50-iteration cap in the
2004Q4 and 2008Q4 refits; the 125-series versions converge. Capped outputs
are exposed as such, not presented as converged alternatives or used for forecasts.
The last-observed-origin variant uses already-known covariates, not future
unemployment labels. Signs and scaling use training observations only.

Next decisive check: obtain/identify the author's actual factor-construction
rule, or declare a separate factor-only forecast comparison with all other
state columns and forest settings frozen, its own matched static comparator,
and no promotion to an exact replication based on a favorable test score.
Independent confirmation would require data not used for this investigation.

[Open the ten-figure report](index.html), [audit](audit.json),
[factor snapshot](crisis-factor-snapshot.csv), [all factor scores](factor-variant-scores.csv),
[outlier cells](outlier-cells.csv), [F2 drivers](factor-drivers.csv),
[routed crisis leaves](crisis-routed-leaves.csv), [historical leaf support](crisis-leaf-support.csv).

Reproduce from the repository with:

```sh
uv run --frozen --extra plots python -m jev_factor.factor_forensics2018 audit
# First create the storage-only 2008Q4/seed-101 replay using scripts/trace_mrf2018.R
# and the corresponding frozen matrix/settings, writing to runs/mrf-factor-forensics/crisis-replay/replay.csv.
uv run --frozen --extra plots python -m jev_factor.factor_forensics2018 replay-audit
uv run --frozen --extra plots python -m jev_factor.factor_forensics2018 report
```

Sources: [paper](https://doi.org/10.1002/jae.3030),
[FRED-QD reference paper](https://www.stlouisfed.org/-/media/project/frbstl/stlouisfed/publications/review/pdfs/2021/01/14/fred-qd-a-quarterly-database-for-macroeconomic-research.pdf),
[FRED databases/code](https://www.stlouisfed.org/research/economists/mccracken/fred-databases),
[pinned author engine](https://github.com/philgoucou/macrorf/blob/bdb2ed435affb741aafdf78bab12c470ec6d55d0/R/MRF_v210403.R).
No Jev/LLM evaluation, parameter search, original-result replacement or outgoing messages.
"""
    (output / "findings.md").write_text(note)
    cards = "".join(
        f'<figure><h2>{html.escape(g["title"])}</h2><a href="figures/{g["slug"]}.svg"><img src="figures/{g["slug"]}.png" alt="{html.escape(g["title"], quote=True)}" loading="lazy"></a><figcaption>{html.escape(g["caption"])}</figcaption></figure>'
        for g in gallery
    )
    document = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MRF factor forensics</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f4f6f8;color:#203647;font:17px/1.7 system-ui,sans-serif}}main{{max-width:1160px;margin:auto;padding:36px 24px}}h1{{font-size:clamp(30px,5vw,48px);line-height:1.15}}h2{{font-size:22px}}p{{max-width:920px}}a{{color:#2563a6}}figure{{background:white;margin:32px 0;padding:24px;border-radius:8px}}img{{width:100%;height:auto}}figcaption{{font-size:15px;color:#42576a}}.lead{{border-left:4px solid #c35935;padding-left:20px}}details{{margin:28px 0}}@media(max-width:650px){{main{{padding:22px 12px}}figure{{padding:12px}}}}
</style><main><p>POST-HOC INVESTIGATION · ORIGINAL BENCHMARK FROZEN</p><h1>Why does our MRF miss the crisis?</h1>
<p class="lead">We found a concrete tail difference in the leading-factor construction. F2 is {findings["baseline_F2_training_SD"]:+.2f} training SDs using all 247 series, but {findings["subset_F2_sign_aligned_training_SD"]:+.2f} under subset-only PCA after training-sign alignment. Training correlation: {findings["training_F2_correlation"]:.3f}. The original author's exact factor pipeline remains unknown.</p>
<p>The critical input is 2008Q4, used to predict 2009Q1. This is an origin-date analysis, not an extra quarter of foresight. Independent base-R checks reproduce the factor arithmetic. The frozen forest replay reproduces every coefficient and forecast exactly.</p>
<p>A separately labeled NONCAUSAL control uses all later predictor data through 2018Q2 and also reverses F2, to {findings["NONCAUSAL_full_vintage_preparation_F2_training_SD"]:+.2f} pre-cutoff training SDs. This makes factor-estimation timing another live hypothesis, not an acceptable replacement benchmark or a claim about the original author.</p>
<p><a href="findings.md">Research note</a> · <a href="audit.json">Audit and provenance</a> · <a href="crisis-factor-snapshot.csv">Factor snapshot</a> · <a href="factor-drivers.csv">Input contributions</a> · <a href="outlier-cells.csv">Removed observations</a></p>
<details><summary>Interpretation boundaries</summary><p>This is diagnosis, not a newly selected model. No alternative forests are fitted and no variant forecast losses are used to choose a recipe. Subset PCA changes what the factor measures; it is not merely a sign change. Cleaning, eligibility, completion and the learned coefficient map are distinct mechanisms. The actual original paper pipeline has not been recovered. Ten-figure captions distinguish exact accounting, numerical verification and hypotheses.</p></details>{cards}
<p><a href="findings.md">Read the full findings and reproduction details.</a></p></main></html>"""
    (output / "index.html").write_text(document)
    record["artifact_checksums"] = {
        str(p.relative_to(output)): sha(p)
        for p in sorted(output.rglob("*"))
        if p.is_file() and p.name != "audit.json"
    }
    (output / "audit.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(findings, indent=2))
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["audit", "replay-audit", "report"])
    args = p.parse_args()
    if args.action == "audit":
        audit_preprocessing()
    elif args.action == "replay-audit":
        inspect_replay()
    else:
        make_report()


if __name__ == "__main__":
    main()
