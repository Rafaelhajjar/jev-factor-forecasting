"""Post-hoc scientific figures for the frozen September-2018 MRF reconstruction.

No model selection, forecast replacement, API calls, or changes to the original run.
Plotting is optional: install with ``uv sync --extra plots``.
"""

# Long captions and the self-contained HTML template intentionally keep readable prose.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from jev_factor.mrf2018 import checked
from jev_factor.replication import LINEAR_X, score_table
from jev_factor.vintage2018 import load_vintage

SEEDS = [101, 202, 303]
MRF = [f"FA_ARRF_seed{s}" for s in SEEDS]
OLS = "OLS_same_equation_exploratory"
LABELS = {"AR4": "AR(4)", "FA_AR": "Fixed FA-AR", OLS: "Static same-equation OLS*"}
LABELS.update({m: f"MRF · seed {s}" for m, s in zip(MRF, SEEDS, strict=True)})
COLORS = {"AR4": "#9097a0", "FA_AR": "#2563a6", OLS: "#34816b"}
COLORS.update(dict(zip(MRF, ["#c45835", "#a03468", "#8b6ab0"], strict=True)))
TERMS = ["intercept", *LINEAR_X]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_diagnostics(run: Path) -> dict:
    """Read and verify complete frozen artifacts, then calculate labeled diagnostics."""
    manifest = checked(run)
    audit = json.loads((run / "audit.json").read_text())
    if not manifest["completed"] or not audit["full_declaration_verified"]:
        raise ValueError("Only a complete audited run may be plotted")
    if audit["jobs_verified"] != 18 or audit["partial_scores_suppressed"]:
        raise ValueError("Incomplete declaration")
    for name in ["predictions", "metrics"]:
        if (
            digest(run / f"{name}.csv")
            != audit[f"{name[:-1] if name == 'predictions' else name}_sha256"]
        ):
            raise ValueError(f"Changed {name}")
    for job in manifest["jobs"]:
        for suffix, expected in job["output_hashes"].items():
            if digest(Path(job["prediction_path"] + suffix)) != expected:
                raise ValueError("Frozen native output changed")
    pred = pd.read_csv(run / "predictions.csv")
    dates = pd.period_range("2003Q1", "2014Q4", freq="Q")
    if set(pred.model) != {"AR4", "FA_AR", *MRF}:
        raise ValueError("Unexpected method set")
    for _, f in pred.groupby("model"):
        if list(f.target_date) != dates.astype(str).tolist():
            raise ValueError("Forecast calendar changed")
        if not (pd.PeriodIndex(f.origin_date, freq="Q") == dates - 1).all():
            raise ValueError("Forecast origin misaligned")
    coefficient_rows, static_rows, components, windows = [], [], [], []
    max_decomp = 0.0
    for w in manifest["windows"]:
        matrix = pd.read_csv(w["matrix"])
        align = pd.read_csv(w["alignment"])
        n = w["metadata"]["ntrain"]
        train, test = matrix.iloc[:n], matrix.iloc[n:]
        target_dates = align.iloc[n:].target_date.to_numpy()
        xtrain = np.column_stack([np.ones(n), train[LINEAR_X]])
        xtest = np.column_stack([np.ones(len(test)), test[LINEAR_X]])
        beta = np.linalg.lstsq(xtrain, train.target, rcond=None)[0]
        actual = align.iloc[n:].actual.to_numpy()
        for k, date in enumerate(target_dates):
            static_rows.append(
                dict(
                    model=OLS,
                    target_date=date,
                    origin_date=align.iloc[n + k].origin_date,
                    actual=actual[k],
                    prediction=float(xtest[k] @ beta),
                )
            )
        jobs = [j for j in manifest["jobs"] if j["group"] == w["group"]]
        for job in jobs:
            native = pd.read_csv(job["prediction_path"])
            b = native[TERMS].to_numpy()
            terms = xtest * b
            max_decomp = max(max_decomp, float(np.max(abs(terms.sum(axis=1) - native.prediction))))
            for k, date in enumerate(target_dates):
                coefficient_rows.append(
                    dict(
                        model=f"FA_ARRF_seed{job['seed']}",
                        target_date=date,
                        group=w["group"],
                        **dict(zip(TERMS, b[k], strict=True)),
                    )
                )
                components.append(
                    dict(
                        model=f"FA_ARRF_seed{job['seed']}",
                        target_date=date,
                        group=w["group"],
                        intercept=terms[k, 0],
                        AR=terms[k, 1:3].sum(),
                        F1=terms[k, 3],
                        F2=terms[k, 4],
                        static_intercept=beta[0],
                        static_AR=float(xtest[k, 1:3] @ beta[1:3]),
                        static_F1=xtest[k, 3] * beta[3],
                        static_F2=xtest[k, 4] * beta[4],
                    )
                )
        windows.append(
            dict(
                group=w["group"],
                fit_end=w["fit_end"],
                ntrain=n,
                state_columns=matrix.shape[1] - 1,
                em_iterations=w["metadata"]["em_iterations"],
                training_outliers=w["metadata"]["training_outliers"],
            )
        )
    if max_decomp > 1e-10:
        raise ValueError("Coefficient decomposition failed")
    pred = pd.concat([pred, pd.DataFrame(static_rows)], ignore_index=True)
    metrics = score_table(pred)
    pred["error"] = pred.prediction - pred.actual
    pred["squared_error"] = pred.error**2
    levels = load_vintage(Path(manifest["archive"])).levels.UNRATE
    truth = pred.loc[pred.model.eq("AR4"), "actual"].to_numpy()
    if not np.allclose(
        np.log(levels.loc[dates].to_numpy() / levels.loc[dates - 1].to_numpy()),
        truth,
        rtol=0,
        atol=1e-12,
    ):
        raise ValueError("Archived level/target alignment failed")
    return dict(
        manifest=manifest,
        audit=audit,
        predictions=pred,
        metrics=metrics,
        coefficients=pd.DataFrame(coefficient_rows),
        contributions=pd.DataFrame(components),
        windows=pd.DataFrame(windows),
        dates=dates,
        levels=levels,
        max_decomposition_error=max_decomp,
    )


def verify_trace(data: dict, trace: Path) -> dict:
    """A replay may only be described as matched after every saved coefficient agrees."""
    original = pd.read_csv(data["manifest"]["jobs"][0]["prediction_path"])
    replay = pd.read_csv(trace / "replay.csv")
    if list(original.columns) != list(replay.columns) or original.shape != replay.shape:
        raise ValueError("Replay schema changed")
    difference = float(np.max(abs(original.to_numpy() - replay.to_numpy())))
    if difference > 1e-12:
        raise ValueError(f"Storage-only replay did not reproduce the first fit: {difference}")
    trees = pd.read_csv(trace / "replay.csv.trees.csv")
    columns = [f"tree_{b}" for b in range(1, 101)]
    if not set(columns).issubset(trees) or not np.isfinite(trees[columns]).all().all():
        raise ValueError("Missing/nonfinite per-tree forecasts")
    train = trees.role.eq("train").to_numpy()
    n = data["manifest"]["windows"][0]["metadata"]["ntrain"]
    if trees.shape[0] != n + 8 or train.sum() != n:
        raise ValueError("Unexpected trace sample")
    align = pd.read_csv(data["manifest"]["windows"][0]["alignment"])
    if trees.loc[~train, "observed_training_target"].notna().any():
        raise ValueError("Forecast outcomes were supplied to the trace")
    if not np.allclose(
        trees.loc[train, "observed_training_target"], align.loc[train, "actual"], rtol=0, atol=1e-12
    ):
        raise ValueError("Trace training truth mismatch")
    individual = trees[columns].to_numpy()
    prefixes = individual.cumsum(axis=1) / np.arange(1, 101)
    if not np.allclose(prefixes[~train, -1], original.prediction, rtol=0, atol=1e-12):
        raise ValueError("Tree average does not match original forecasts")
    truth = align.actual.to_numpy()
    curves = pd.DataFrame(
        dict(
            trees=np.arange(1, 101),
            training_MSE=np.mean((prefixes[train] - truth[train, None]) ** 2, axis=0),
            heldout_MSE=np.mean((prefixes[~train] - truth[~train, None]) ** 2, axis=0),
        )
    )
    leaves = pd.read_csv(trace / "replay.csv.leaves.csv")
    if set(leaves.tree) != set(range(1, 101)):
        raise ValueError("Incomplete retained forest")
    return dict(
        match_max_abs=difference,
        trees=trees,
        individual=individual,
        prefixes=prefixes,
        train=train,
        truth=truth,
        curves=curves,
        leaves=leaves,
    )


def replay(run: Path, trace: Path, r_library: Path) -> None:
    data = load_diagnostics(run)
    job = data["manifest"]["jobs"][0]
    trace.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    command = [
        shutil.which("Rscript") or "Rscript",
        str(root / "scripts/trace_mrf2018.R"),
        str(root / "src/jev_factor/reference_mrf.R"),
        data["manifest"]["engine_path"],
        job["matrix"],
        job["settings"],
        str((trace / "replay.csv").resolve()),
        str(r_library.resolve()),
    ]
    subprocess.run(command, check=True)
    verify_trace(data, trace)


def build_report(run: Path, output: Path, trace: Path | None = None) -> dict:
    # Keep scientific plotting out of model imports and out of the frozen runtime path.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = load_diagnostics(run)
    output.mkdir(parents=True, exist_ok=True)
    figures = output / "figures"
    figures.mkdir(exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": "#acb4bd",
            "axes.labelcolor": "#263442",
            "text.color": "#182d3d",
            "xtick.color": "#415262",
            "ytick.color": "#415262",
            "grid.color": "#dce3e9",
            "grid.alpha": 0.6,
            "axes.axisbelow": True,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "svg.fonttype": "none",
        }
    )
    dates, pred = data["dates"], data["predictions"]
    x = np.arange(len(dates))
    wide = pred.pivot(index="target_date", columns="model", values="prediction").reindex(
        dates.astype(str)
    )
    errors = pred.pivot(index="target_date", columns="model", values="error").reindex(
        dates.astype(str)
    )
    loss = errors**2 * 10000
    actual = pred.loc[pred.model.eq("AR4"), "actual"].to_numpy() * 100
    metrics = data["metrics"].set_index("model")
    gallery = []

    def fig(n=1, **kwargs):
        return plt.subplots(n, 1, figsize=(11, 3.1 * n + 0.8), layout="constrained", **kwargs)

    def time_axis(ax, indices=x):
        ticks = np.asarray(indices)[:: max(1, len(indices) // 7)]
        ax.set_xticks(ticks, [str(dates[t]) for t in ticks])
        ax.set_xlabel("Forecast target quarter")
        ax.grid(axis="y")

    def boundaries(ax):
        for v in np.arange(7.5, 47, 8):
            ax.axvline(v, color="#cbd1d7", linewidth=0.8)

    def series(ax, values=wide, models=("FA_AR", *MRF), scale=100):
        for model in models:
            ax.plot(
                x,
                values[model].to_numpy() * scale,
                color=COLORS[model],
                lw=1.7,
                label=LABELS[model],
                alpha=0.9,
            )
        time_axis(ax)

    def save(f, slug, title, caption, section):
        f.savefig(figures / f"{slug}.png", dpi=165)
        f.savefig(figures / f"{slug}.svg")
        plt.close(f)
        gallery.append(dict(slug=slug, title=title, caption=caption, section=section))

    # Training explanation: a forest is not an epoch-based optimizer.
    f, ax = plt.subplots(figsize=(12, 6.3), layout="constrained")
    ax.axis("off")
    boxes = [
        (
            0.02,
            0.57,
            "1 · Fit representations",
            "Past data only\n247 indicator series → 5 PCA factors\n2 moving-average factors per series",
        ),
        (
            0.36,
            0.57,
            "2 · Grow 100 trees",
            "Block-subsample training rows\nTry ~⅓ of 1,037 state columns\nChoose splits using local regression error",
        ),
        (
            0.70,
            0.57,
            "3 · Fit each leaf",
            "Intercept + 2 target lags + 2 factors\nRidge toward the training OLS prior\nSmooth with neighboring training rows",
        ),
        (
            0.36,
            0.13,
            "4 · Average the trees",
            "Each tree supplies 5 local coefficients\nAverage them → 1 point forecast\nRepeat at 6 refits; keep all 3 seeds",
        ),
    ]
    for bx, by, title, body in boxes:
        ax.text(bx, by + 0.25, title, transform=ax.transAxes, fontsize=13, weight="bold")
        ax.text(
            bx,
            by + 0.03,
            body,
            transform=ax.transAxes,
            fontsize=10.5,
            linespacing=1.7,
            bbox=dict(boxstyle="round,pad=.8", facecolor="#eef3f7", edgecolor="none"),
        )
    for a, b in [
        ((0.29, 0.72), (0.34, 0.72)),
        ((0.63, 0.72), (0.68, 0.72)),
        ((0.81, 0.56), (0.64, 0.39)),
    ]:
        ax.annotate(
            "",
            xy=b,
            xytext=a,
            xycoords="axes fraction",
            arrowprops=dict(arrowstyle="->", color="#6c7c8b", lw=1.8),
        )
    ax.set_title("How this MRF trains — no epochs, no gradient-descent loss curve", loc="left")
    save(
        f,
        "01-training-map",
        "What training actually does",
        "The 1,037 state variables choose regimes; the forecast equation has only five coefficients. "
        "The forest averages separately grown trees. It does not optimize one neural-network loss over epochs.",
        "Training",
    )

    f, axes = fig(2)
    e = np.linspace(-10, 10, 201)
    axes[0].plot(e, e**2, color=COLORS[MRF[0]], lw=2)
    axes[0].set(
        xlabel="Forecast − actual (100 × Δlog UNRATE)",
        ylabel="Squared error (log points²)",
        title="Forecast scoring: large misses get squared",
    )
    axes[0].grid()
    axes[1].axis("off")
    axes[1].text(
        0.02,
        0.82,
        r"Leaf fit:  $\sum_i w_i(y_i - z_i^T\beta)^2 + \lambda(\beta-\beta_0)^T D(\beta-\beta_0)$",
        fontsize=16,
    )
    axes[1].text(
        0.02,
        0.38,
        "β₀ = training OLS prior. Ridge λ = 0.1. D = diag(0.01, 1, 1, 1, 1).\n"
        "Neighbor rows are multiplied by 0.75 / 0.75² → loss weights 0.75² / 0.75⁴.\n"
        "Split search uses regularized child fits and rank-weighted SSE; fast.rw skips neighbor\n"
        "augmentation during split search. Terminal fits then include that smoothing.",
        linespacing=1.8,
    )
    save(
        f,
        "02-loss-functions",
        "What the losses mean",
        "Top is the actual forecast scoring rule, not a fitted curve. Bottom summarizes the local leaf objective in standardized units. "
        "The source's split criterion differs from its terminal-fit objective; there is no single globally minimized training loss.",
        "Training",
    )

    f, ax = fig()
    for i, w in enumerate(data["manifest"]["windows"]):
        first = pd.Period(w["metadata"]["first_training_target"], freq="Q").ordinal
        end = pd.Period(w["fit_end"], freq="Q").ordinal
        ax.broken_barh([(first, end - first + 1)], (i - 0.23, 0.46), facecolors="#94afc8")
        ax.broken_barh([(end + 1, 8)], (i - 0.23, 0.46), facecolors=COLORS[MRF[0]])
        ax.text(
            end + 10, i, f"{w['metadata']['ntrain']} train · 8 forecast", va="center", fontsize=9
        )
    ticks = [
        pd.Period(s, freq="Q") for s in ["1961Q3", "1970Q1", "1980Q1", "1990Q1", "2000Q1", "2014Q4"]
    ]
    ax.set_xticks([t.ordinal for t in ticks], [str(t) for t in ticks])
    ax.set_yticks(range(6), [f"Fit through {w['fit_end']}" for w in data["manifest"]["windows"]])
    ax.invert_yaxis()
    ax.set(
        title="Six expanding fits — blue is training, orange is the next 8 targets",
        xlabel="Target quarter",
    )
    save(
        f,
        "03-training-calendar",
        "Training versus forecasting calendar",
        "Representations stop at the last training origin, one quarter before the training target cutoff. "
        "Forecasting is h=1 with observed lag updates, not an eight-step recursive path. The model is refitted every two years.",
        "Training",
    )

    f, axes = plt.subplots(1, 2, figsize=(11, 4.6), layout="constrained")
    groups = ["Target lags", "PCA-factor lags", "Raw-indicator lags", "MAFs", "Trend"]
    counts = [8, 40, 494, 494, 1]
    axes[0].barh(groups[::-1], counts[::-1], color="#487ca5")
    axes[0].set(xlabel="State columns", title="1,037 ways to identify the state")
    for i, c in enumerate(counts[::-1]):
        axes[0].text(c + 6, i, str(c), va="center")
    axes[0].set_xlim(0, 565)
    axes[1].plot(
        range(6), data["windows"].ntrain, "o-", color=COLORS["FA_AR"], label="Training rows"
    )
    axes[1].axhline(5, color=COLORS[MRF[0]], label="Coefficients in each local equation")
    axes[1].set_xticks(range(6), data["windows"].fit_end, rotation=25)
    axes[1].set(ylabel="Count", xlabel="Refit cutoff", title="166–206 rows; 5 local coefficients")
    axes[1].legend(loc="center left", fontsize=9)
    save(
        f,
        "04-state-and-sample-size",
        "The large state and the small equation",
        "The state is large relative to the training history. Trees select splits rather than fitting 1,037 regression slopes. "
        "This is a capacity/noise concern, not proof that overfitting caused the forecast gap.",
        "Training",
    )

    f, axes = plt.subplots(1, 2, figsize=(11, 4.2), layout="constrained")
    axes[0].bar(range(6), data["windows"].em_iterations, color=COLORS["FA_AR"])
    axes[0].set(ylabel="Recorded completion iterations", title="Factor preparation converged")
    axes[1].bar(range(6), data["windows"].training_outliers, color=COLORS[MRF[0]])
    axes[1].set(ylabel="Training observations flagged", title="10-IQR preprocessing outliers")
    for ax in axes:
        ax.set_xticks(range(6), data["windows"].fit_end, rotation=25)
        ax.set_xlabel("Refit cutoff")
    save(
        f,
        "05-preparation-diagnostics",
        "Recorded preprocessing diagnostics",
        "These are recorded counts, not per-iteration loss histories. All six state rebuilds agreed exactly with the frozen inputs. "
        "The original run did not retain a factor-completion objective trajectory.",
        "Training",
    )

    order = ["AR4", "FA_AR", *MRF, OLS]
    f, ax = fig()
    y = np.arange(len(order))
    ratios = metrics.loc[order, "RMSE_over_AR4"]
    ax.barh(y, ratios, color=[COLORS[m] for m in order], alpha=0.9)
    ax.set_yticks(y, [LABELS[m] for m in order])
    ax.invert_yaxis()
    ax.axvline(0.72, color="#333e48", linestyle="--", label="Paper MRF: 0.72")
    ax.axvline(0.83, color=COLORS["FA_AR"], linestyle=":", label="Paper fixed FA-AR: 0.83")
    for yy, v in zip(y, ratios, strict=True):
        ax.text(v + 0.009, yy, f"{v:.3f}", va="center")
    ax.set(
        xlim=(0, 1.1),
        xlabel="RMSE / matching AR(4) RMSE · lower is better",
        title="The forest does not recover the paper's nonlinear gain",
    )
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2, fontsize=9)
    save(
        f,
        "06-scorecard",
        "The actual result versus the paper",
        "All 48 quarters and all seeds. Fixed FA-AR is 0.833; MRF is 0.824–0.852, not 0.72. "
        "*Same-equation OLS is a new post-hoc control with the MRF's four slope terms, not the paper's nine-coefficient FA-AR or a replacement primary.",
        "Forecasts",
    )

    f, axes = plt.subplots(1, 2, figsize=(12, 5.0), layout="constrained", sharey=True)
    for ax, metric, title in zip(
        axes,
        ["RMSE", "MAE"],
        ["RMSE · big misses hurt", "MAE · smaller typical errors"],
        strict=True,
    ):
        values = metrics.loc[order, metric] * 100
        ax.barh(y, values, color=[COLORS[m] for m in order])
        ax.axvline(metrics.loc["FA_AR", metric] * 100, color="#263442", linestyle="--")
        ax.set_yticks(y, [LABELS[m] for m in order])
        ax.set(xlabel=f"{metric} (log points)", title=title)
        for yy, v in zip(y, values, strict=True):
            ax.text(v + 0.025, yy, f"{v:.2f}", va="center", fontsize=9)
        ax.set_xlim(0, float(values.max()) * 1.17)
    axes[0].invert_yaxis()
    save(
        f,
        "31-rmse-versus-mae",
        "A useful nuance: better MAE, little or no RMSE gain",
        "All three MRF seeds have lower MAE than fixed FA-AR and the exploratory static control. "
        "They do not uniformly improve the primary RMSE metric. Squaring errors makes rare large misses more costly. "
        "The dashed line is each metric's fixed FA-AR value; reporting MAE does not change the primary criterion.",
        "Forecasts",
    )

    f, ax = fig()
    series(ax)
    ax.plot(x, actual, color="#1d2934", lw=2, label="Actual", zorder=5)
    ax.axhline(0, color="#98a3ad", lw=0.8)
    ax.set(
        ylabel="100 × Δlog UNRATE (log points)",
        title="Forecasts track the cycle, but miss the abrupt rise",
    )
    ax.legend(ncol=3, fontsize=9)
    save(
        f,
        "07-forecasts",
        "Actual versus forecast changes",
        "The target is the quarterly change in log unemployment, multiplied by 100 for readability. "
        "These are log points, not unemployment-rate percentage-point changes.",
        "Forecasts",
    )

    zoom = np.arange(16, 32)
    f, ax = fig()
    for m in ["AR4", "FA_AR", *MRF]:
        ax.plot(zoom, wide[m].iloc[zoom] * 100, color=COLORS[m], label=LABELS[m], lw=1.8)
    ax.plot(zoom, actual[zoom], "o-", color="#1d2934", label="Actual", lw=2)
    time_axis(ax, zoom)
    ax.set(ylabel="100 × Δlog UNRATE (log points)", title="2007–2010 close-up: 2009Q1 is costly")
    ax.annotate(
        "2009Q1",
        xy=(24, actual[24]),
        xytext=(26, actual[24] + 1),
        arrowprops=dict(arrowstyle="->", color="#445568"),
    )
    ax.legend(ncol=3, fontsize=9)
    save(
        f,
        "08-crisis-closeup",
        "Where the large miss happens",
        "In 2009Q1 the actual log change is 0.1856, fixed FA-AR predicts 0.1185, and MRF predicts 0.0881/0.1034/0.0969. "
        "The forest underreacts more than the fixed-factor comparator at this quarter.",
        "Forecasts",
    )

    f, ax = fig()
    previous = data["levels"].loc[dates - 1].to_numpy()
    ax.plot(x, data["levels"].loc[dates], color="#1d2934", label="Actual", lw=2.2)
    for m in ["FA_AR", *MRF]:
        ax.plot(x, previous * np.exp(wide[m].to_numpy()), color=COLORS[m], label=LABELS[m], lw=1.5)
    time_axis(ax)
    ax.set(
        ylabel="Unemployment (% of labor force)",
        title="The same one-quarter forecasts in unemployment-rate units",
    )
    ax.legend(ncol=3, fontsize=9)
    save(
        f,
        "09-unemployment-levels",
        "Forecasts in familiar units",
        "Each level forecast equals the observed previous-quarter unemployment rate × exp(predicted log change). "
        "It is a sequence of one-step forecasts with observed lag updates, not a recursive multi-year forecast. Main scoring stays in the original log-change target.",
        "Forecasts",
    )

    f, ax = fig()
    for m in ["FA_AR", *MRF]:
        ax.plot(
            x[7:], np.sqrt(loss[m].rolling(8).mean().iloc[7:]), color=COLORS[m], label=LABELS[m]
        )
    time_axis(ax)
    ax.set(
        ylabel="Trailing 8-quarter RMSE (log points)",
        title="Error is concentrated around the sharp macro transition",
    )
    ax.legend(ncol=2, fontsize=9)
    save(
        f,
        "10-rolling-rmse",
        "Rolling forecast error",
        "Overlapping trailing eight-quarter windows are descriptive and dependent. They were not used to choose settings, seeds or a favorable evaluation interval.",
        "Forecasts",
    )

    periods = [("2003–2007", 0, 20), ("2008–2009", 20, 28), ("2010–2014", 28, 48)]
    f, ax = fig()
    for j, m in enumerate(MRF):
        values = [
            np.sqrt(loss[m].iloc[a:b].mean() / loss.FA_AR.iloc[a:b].mean()) for _, a, b in periods
        ]
        ax.bar(np.arange(3) + (j - 1) * 0.23, values, width=0.22, color=COLORS[m], label=LABELS[m])
    ax.axhline(1, color="#344555", lw=1)
    ax.set_xticks(range(3), [f"{s}\n{b - a} quarters" for s, a, b in periods])
    ax.set(
        ylabel="RMSE / fixed FA-AR RMSE",
        title="Better before 2008; not better in the harder windows",
        ylim=(0, 1.3),
    )
    ax.legend(ncol=3, fontsize=9)
    save(
        f,
        "11-period-comparison",
        "When the forest helps or hurts",
        "Post-hoc calendar windows, not official recession dates. MRF improves 8–11% before 2008, "
        "but has 4–11% higher RMSE in 2008–09 and 3–4% higher RMSE in 2010–14. This is diagnosis, not a newly chosen benchmark.",
        "Forecasts",
    )

    f, axes = plt.subplots(1, 3, figsize=(12, 4.3), layout="constrained", sharex=True, sharey=True)
    for ax, m in zip(axes, MRF, strict=True):
        ax.scatter(actual, wide[m] * 100, color=COLORS[m], s=28, alpha=0.8)
        limits = (
            min(actual.min(), wide[MRF].min().min() * 100) - 1,
            max(actual.max(), wide[MRF].max().max() * 100) + 1,
        )
        ax.plot(limits, limits, "--", color="#98a3ad", lw=1)
        slope, intercept = np.polyfit(actual, wide[m] * 100, 1)
        ax.set(title=LABELS[m], xlabel="Actual log change × 100", xlim=limits, ylim=limits)
        ax.text(0.04, 0.93, f"Descriptive slope: {slope:.2f}", transform=ax.transAxes, fontsize=9)
    axes[0].set_ylabel("Predicted log change × 100")
    save(
        f,
        "12-actual-predicted",
        "Prediction range and underreaction",
        "Dashed line is perfect prediction. Slopes regress forecasts on actuals for description only; "
        "they are not probability calibration tests or fitted forecast corrections. Only 48 points per panel.",
        "Forecasts",
    )

    f, ax = fig()
    series(ax, errors)
    ax.axhline(0, color="#1d2934", lw=1)
    ax.set(
        ylabel="Forecast − actual (log points)",
        title="Signed forecast errors — negative means underprediction",
    )
    ax.legend(ncol=2, fontsize=9)
    save(
        f,
        "13-residual-timeline",
        "Residuals through time",
        "A residual here is forecast minus actual, so negative errors mean the rise in unemployment was underpredicted. "
        "All residual plots use held-out target dates.",
        "Errors",
    )

    f, ax = plt.subplots(figsize=(12, 4), layout="constrained")
    im = ax.imshow(loss[["FA_AR", *MRF]].T, aspect="auto", cmap="YlOrRd", interpolation="nearest")
    ax.set_yticks(range(4), [LABELS[m] for m in ["FA_AR", *MRF]])
    ax.set_xticks(x[::4], dates.astype(str)[::4], rotation=25)
    ax.set(
        xlabel="Forecast target quarter",
        title="Squared loss by quarter — a few large misses dominate",
    )
    f.colorbar(im, ax=ax, label="Squared error (log points²)")
    save(
        f,
        "14-loss-heatmap",
        "Where the squared loss comes from",
        "Identical color scale for every method. No normalization within rows; this preserves the magnitude of unusually costly quarters.",
        "Errors",
    )

    f, ax = fig()
    for m in MRF:
        ax.plot(x, (loss[m] - loss.FA_AR).cumsum(), color=COLORS[m], label=LABELS[m], lw=2)
    ax.axhline(0, color="#344555", lw=1)
    time_axis(ax)
    ax.set(
        ylabel="Cumulative excess SSE (log points²)",
        title="Below zero: MRF is ahead of fixed FA-AR; above zero: behind",
    )
    ax.legend(fontsize=9)
    save(
        f,
        "15-cumulative-excess-loss",
        "How small wins and large losses accumulate",
        "This accumulates each seed's squared error minus fixed FA-AR squared error. It is not a sequential model-selection rule. "
        "The 2009Q1 jump offsets many earlier gains.",
        "Errors",
    )

    f, axes = plt.subplots(1, 3, figsize=(12, 5.0), layout="constrained", sharex=True)
    for ax, m in zip(axes, MRF, strict=True):
        delta = loss[m] - loss.FA_AR
        worst = delta.sort_values(ascending=False).head(6).sort_values()
        ax.barh(worst.index, worst.to_numpy(), color=COLORS[m])
        ax.set(title=LABELS[m], xlabel="Extra squared loss vs FA-AR")
        ax.grid(axis="x")
    save(
        f,
        "16-costliest-quarters",
        "The six most expensive relative misses per seed",
        "Quarters are ranked after observing results, solely to locate failures. These are individual contributions to total excess squared loss, not independently selected test tasks.",
        "Errors",
    )

    f, axes = plt.subplots(1, 3, figsize=(12, 4.2), layout="constrained", sharey=True)
    for ax, m in zip(axes, MRF, strict=True):
        ax.scatter(wide[m] * 100, errors[m] * 100, color=COLORS[m], s=27, alpha=0.8)
        ax.axhline(0, color="#344555", lw=1)
        ax.set(title=LABELS[m], xlabel="Forecast (log points)")
    axes[0].set_ylabel("Forecast − actual (log points)")
    save(
        f,
        "17-error-versus-forecast",
        "Do errors depend on the forecast size?",
        "Residual-versus-fitted diagnostic, using held-out forecasts. Patterns may reflect rare regimes or misspecification; "
        "this small sample cannot identify a unique cause.",
        "Errors",
    )

    f, axes = plt.subplots(1, 2, figsize=(11, 4.6), layout="constrained")
    for m in MRF:
        axes[0].hist(
            errors[m] * 100,
            bins=np.linspace(-11, 7, 16),
            histtype="step",
            color=COLORS[m],
            label=LABELS[m],
            lw=1.8,
        )
        (q, v), (slope, intercept, _) = stats.probplot(errors[m] * 100)
        axes[1].scatter(q, v, s=19, color=COLORS[m], alpha=0.7)
        axes[1].plot(q, slope * q + intercept, color=COLORS[m], lw=1, alpha=0.7)
    axes[0].set(
        xlabel="Forecast error (log points)", ylabel="Quarters", title="Residual distribution"
    )
    axes[1].set(
        xlabel="Theoretical normal quantile",
        ylabel="Ordered error (log points)",
        title="Normal Q–Q diagnostic",
    )
    axes[0].legend(fontsize=9)
    save(
        f,
        "18-residual-distribution",
        "Tails and unusual errors",
        "Only 48 held-out quarters. Q–Q lines describe the empirical error distribution, not an assumed Gaussian predictive distribution or a calibrated interval.",
        "Errors",
    )

    f, axes = plt.subplots(1, 3, figsize=(12, 3.8), layout="constrained", sharey=True)
    for ax, m in zip(axes, MRF, strict=True):
        e = errors[m].to_numpy() - errors[m].mean()
        acf = [float(e[k:] @ e[:-k] / (e @ e)) for k in range(1, 9)]
        ax.bar(np.arange(1, 9), acf, color=COLORS[m])
        ax.axhline(0, color="#344555", lw=0.8)
        ax.set(title=LABELS[m], xlabel="Lag (quarters)", ylim=(-0.5, 0.5))
    axes[0].set_ylabel("Residual autocorrelation")
    save(
        f,
        "19-residual-acf",
        "Is forecast error serially structured?",
        "Descriptive autocorrelations, with denominator equal to the full centered error sum of squares. "
        "No iid significance bands or multiple-testing claims are added to this 48-quarter sample.",
        "Errors",
    )

    f, axes = fig(5, sharex=True)
    coeff = data["coefficients"]
    names = ["Intercept", "Target lag 1", "Target lag 2", "PCA factor 1", "PCA factor 2"]
    for ax, term, name in zip(axes, TERMS, names, strict=True):
        for m in MRF:
            ax.plot(
                x, coeff.loc[coeff.model.eq(m), term].to_numpy(), color=COLORS[m], label=LABELS[m]
            )
        ax.axhline(0, color="#a5afb9", lw=0.7)
        boundaries(ax)
        ax.set_ylabel(name)
        ax.grid(axis="y")
    axes[0].set_title("The coefficients really do change — this is not a fixed linear model")
    axes[0].legend(ncol=3, fontsize=9)
    time_axis(axes[-1])
    save(
        f,
        "20-coefficient-paths",
        "All five changing coefficients",
        "Units are the saved original-scale coefficients; the intercept is in Δlog units. Vertical lines mark refits. "
        "PCA factors are refitted and can change sign/rotation: F1/F2 coefficients across boundaries are not an invariant economic quantity or a causal effect.",
        "Inside the forecast",
    )

    f, axes = fig(3, sharex=True)
    cc = data["contributions"]
    for ax, m in zip(axes, MRF, strict=True):
        c = cc.loc[cc.model.eq(m)]
        for term, color in zip(
            ["intercept", "AR", "F1", "F2"],
            ["#77828d", "#2563a6", "#34816b", "#ae7632"],
            strict=True,
        ):
            ax.plot(x, c[term].to_numpy() * 100, color=color, label=term, lw=1.5)
        ax.plot(x, wide[m] * 100, color="#202e39", label="Sum = forecast", lw=2)
        boundaries(ax)
        ax.set(ylabel="Contribution (log points)", title=LABELS[m])
        ax.grid(axis="y")
    axes[0].legend(ncol=5, fontsize=9)
    time_axis(axes[-1])
    save(
        f,
        "21-forecast-contributions",
        "What actually contributes to each forecast",
        "These terms sum to every saved forecast within numerical precision. Contributions are predictive accounting, not causal attribution. "
        "The individual F1/F2 decomposition is tied to each refit's PCA basis.",
        "Inside the forecast",
    )

    f, axes = fig(3, sharex=True)
    for ax, m in zip(axes, MRF, strict=True):
        c = cc.loc[cc.model.eq(m)]
        for term, color in zip(
            ["intercept", "AR", "F1", "F2"],
            ["#77828d", "#2563a6", "#34816b", "#ae7632"],
            strict=True,
        ):
            ax.plot(x, (c[term] - c[f"static_{term}"]).to_numpy() * 100, color=color, label=term)
        ax.axhline(0, color="#344555", lw=0.8)
        boundaries(ax)
        ax.set(ylabel="Dynamic − static (log points)", title=LABELS[m])
    axes[0].legend(ncol=4, fontsize=9)
    time_axis(axes[-1])
    save(
        f,
        "22-dynamic-adjustments",
        "What the nonlinear model changes versus its own static equation",
        "Post-hoc same-equation OLS isolates the addition of dynamic fitting more closely than the larger paper FA-AR equation. "
        "MRF has 0.6–4.1% higher RMSE than this control. No model was refitted using test outcomes, and this control does not replace the preregistered benchmark.",
        "Inside the forecast",
    )

    f, axes = plt.subplots(1, 2, figsize=(12, 5.5), layout="constrained")
    meta = data["manifest"]["windows"][0]["metadata"]
    for k, ax in enumerate(axes):
        load = np.asarray(meta["cross_sectional_PCA_loadings"])[k]
        idx = np.argsort(abs(load))[-12:]
        ax.barh(np.asarray(meta["active_series"])[idx], load[idx], color=COLORS["FA_AR"])
        ax.axvline(0, color="#a1adb7", lw=0.8)
        ax.set(
            title=f"PCA factor {k + 1} · first refit only", xlabel="Training PCA loading (signed)"
        )
    save(
        f,
        "23-factor-loadings",
        "Which indicators enter the two equation factors?",
        "Twelve largest absolute loadings in the first refit (through 2002Q3 origin data). Signs are conventional, "
        "and PCA factors are statistical summaries, not identified structural causes or validated economic labels.",
        "Inside the forecast",
    )

    f, axes = fig(2, sharex=True)
    for m in MRF:
        axes[0].plot(x, (wide[m] - wide.FA_AR) * 100, label=LABELS[m], color=COLORS[m])
    axes[0].axhline(0, color="#344555", lw=0.8)
    axes[0].set(
        ylabel="Forecast difference (log points)",
        title="Seeds mostly agree — and all remain close to fixed FA-AR",
    )
    spread = (wide[MRF].max(axis=1) - wide[MRF].min(axis=1)) * 100
    axes[1].fill_between(x, 0, spread, color="#d9c4cd")
    axes[1].plot(x, spread, color=COLORS[MRF[1]], label="Max − min across 3 seeds")
    axes[1].set_ylabel("Seed range (log points)")
    axes[0].legend(ncol=3, fontsize=9)
    axes[1].legend(fontsize=9)
    time_axis(axes[-1])
    save(
        f,
        "24-seed-stability",
        "Seed sensitivity versus the common forecasting error",
        "The three seeds' forecasts correlate above 0.997 with one another. Narrow seed spread is not calibrated uncertainty: "
        "all seeds can make the same large mistake.",
        "Stability",
    )

    f, ax = fig()
    for m in MRF:
        values = [
            np.sqrt(
                loss[m].iloc[g * 8 : (g + 1) * 8].mean()
                / loss.FA_AR.iloc[g * 8 : (g + 1) * 8].mean()
            )
            for g in range(6)
        ]
        ax.plot(range(6), values, "o-", color=COLORS[m], label=LABELS[m])
    ax.axhline(1, color="#344555", lw=1)
    ax.set_xticks(range(6), [f"{dates[g * 8]}–{dates[g * 8 + 7]}" for g in range(6)], rotation=15)
    ax.set(
        ylabel="RMSE / fixed FA-AR RMSE",
        xlabel="Eight-quarter forecast block",
        title="The incremental gain changes across refit blocks",
    )
    ax.legend(ncol=3, fontsize=9)
    save(
        f,
        "25-refit-block-performance",
        "Performance by refit block",
        "Only eight targets per block, so these ratios are noisy. They locate instability; they do not prove a regime mechanism or authorize choosing a different model in each block.",
        "Stability",
    )

    trace_result = None
    if trace is not None:
        trace_result = verify_trace(data, trace)
        t = trace_result
        curves = t["curves"]
        f, ax = fig()
        ax.plot(
            curves.trees,
            curves.training_MSE * 10000,
            label=f"Training fit · {t['train'].sum()} rows",
            color=COLORS["FA_AR"],
            lw=2,
        )
        ax.plot(
            curves.trees,
            curves.heldout_MSE * 10000,
            label="Next 8 quarters · held-out forecast error",
            color=COLORS[MRF[0]],
            lw=2,
        )
        ax.set(
            xlabel="Number of trees averaged (same fixed tree order)",
            ylabel="Mean squared error (log points²)",
            title="Training and held-out loss as the forest grows · first refit, seed 101",
        )
        ax.grid()
        ax.legend(fontsize=9)
        save(
            f,
            "26-training-loss",
            "Training loss versus number of trees",
            "New storage-only replay: first refit, seed 101, all 100 trees. Final forecasts and all coefficients match the original saved fit. "
            "The training curve is in-sample and optimistic; the orange curve is the already-observed next eight test quarters. "
            "Neither curve is a new validation set or a rule for selecting the tree count. Test and training periods have different difficulty.",
            "Instrumented replay",
        )

        f, axes = plt.subplots(
            2, 4, figsize=(13, 6.7), layout="constrained", sharex=True, sharey=True
        )
        future = t["prefixes"][~t["train"]] * 100
        targets = t["truth"][~t["train"]] * 100
        for i, ax in enumerate(axes.flat):
            ax.plot(
                np.arange(1, 101), future[i], color=COLORS[MRF[0]], label="Tree-prefix forecast"
            )
            ax.axhline(targets[i], color="#263442", linestyle="--", label="Actual")
            ax.set(title=str(dates[i]), xlabel="Trees averaged", ylabel="Log points")
        axes[0, 0].legend(fontsize=8)
        save(
            f,
            "27-tree-prefix-forecasts",
            "How averaging more trees changes each forecast",
            "The eight forecasts from the same first-window replay. Trees are added in their original random order, "
            "not trained to correct previous trees' residuals. The fixed 100-tree choice is unchanged.",
            "Instrumented replay",
        )

        f, axes = plt.subplots(2, 4, figsize=(13, 6.7), layout="constrained", sharex=True)
        individual = t["individual"][~t["train"]] * 100
        for i, ax in enumerate(axes.flat):
            ax.hist(individual[i], bins=14, color="#c58b73", alpha=0.8)
            ax.axvline(targets[i], color="#263442", linestyle="--", label="Actual")
            ax.axvline(individual[i].mean(), color=COLORS[MRF[0]], label="Forest mean", lw=2)
            ax.set(title=str(dates[i]), xlabel="Tree forecast (log points)", ylabel="Trees")
        axes[0, 0].legend(fontsize=8)
        save(
            f,
            "28-tree-dispersion",
            "The distribution of individual tree forecasts",
            "These are 100 correlated model components from one fit, not 100 independent future outcomes. "
            "Tree dispersion is not a posterior, prediction interval or calibrated confidence band.",
            "Instrumented replay",
        )

        leaves = t["leaves"].copy()
        leaves["depth"] = leaves.path.str.count(" & ") + 1
        # Deduplicate ancestor path prefixes within each tree; do not overcount shared splits.
        split_rows = []
        for tree, rows in leaves.groupby("tree"):
            prefixes = set()
            for path in rows.path:
                conditions = str(path).split(" & ")
                for depth in range(1, len(conditions) + 1):
                    # The two children of one split have different final inequalities.
                    parent = " & ".join(conditions[: depth - 1])
                    match = re.search(r"([A-Za-z][A-Za-z0-9_]*)\s*(?:<|>)", conditions[depth - 1])
                    if match:
                        key = (parent, match[1])
                        if key not in prefixes:
                            prefixes.add(key)
                            split_rows.append(dict(tree=int(tree), feature=match[1], depth=depth))
        splits = pd.DataFrame(split_rows)
        if splits.empty:
            raise ValueError("Could not parse native forest split paths")
        splits["group"] = splits.feature.map(
            lambda s: (
                "Raw indicators"
                if s.startswith("series_")
                else "MAFs"
                if s.startswith("MAF_")
                else "PCA factors"
                if re.match(r"F\d", s)
                else "Target lags"
                if s.startswith("y_lag")
                else "Trend"
                if s == "trend"
                else "Other"
            )
        )
        f, axes = plt.subplots(1, 3, figsize=(12, 4.2), layout="constrained")
        axes[0].hist(leaves.groupby("tree").size(), bins=12, color=COLORS["FA_AR"])
        axes[0].set(xlabel="Terminal leaves per tree", ylabel="Trees", title="Tree complexity")
        axes[1].hist(
            leaves.depth, bins=np.arange(0.5, leaves.depth.max() + 1.5), color=COLORS[MRF[0]]
        )
        axes[1].set(xlabel="Leaf depth (split decisions)", ylabel="Leaves", title="Path length")
        axes[2].hist(leaves.n_split_sample, bins=15, color="#34816b")
        axes[2].set(xlabel="Split-sample rows in leaf", ylabel="Leaves", title="Leaf support")
        save(
            f,
            "29-tree-structure",
            "How complex are the fitted trees?",
            "Retained trees from the first-window replay only. NOBS counts rows used in the split sample, "
            "not every training outcome used by the final leaf regression or its neighboring-row smoother.",
            "Instrumented replay",
        )

        f, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
        observed = (
            splits.group.value_counts()
            .reindex(
                ["Trend", "Target lags", "PCA factors", "MAFs", "Raw indicators"], fill_value=0
            )
            .sort_values()
        )
        axes[0].barh(observed.index, observed, color=COLORS["FA_AR"])
        axes[0].set(
            xlabel="Distinct split nodes across 100 trees", title="Which state groups are used?"
        )
        top = splits.feature.value_counts().head(12).sort_values()

        def feature_label(name):
            match = re.match(r"series_(\d+)_(lag\d+)", name)
            return f"{meta['active_series'][int(match[1])]} · {match[2]}" if match else name

        axes[1].barh([feature_label(v) for v in top.index], top, color=COLORS[MRF[0]])
        axes[1].set(xlabel="Distinct split nodes", title="Twelve most-used split variables")
        save(
            f,
            "30-split-usage",
            "What the trees actually split on",
            "Usage frequency, not permutation importance or causal attribution. More numerous groups have more opportunities; "
            "correlated features can substitute for each other. Ancestor splits shared by leaves are counted once per tree node.",
            "Instrumented replay",
        )
        curves.to_csv(output / "training-curves.csv", index=False)
        leaves.to_csv(output / "trace-leaves.csv", index=False)
        splits.to_csv(output / "trace-split-usage.csv", index=False)
        # Portable data sufficient to independently recompute both curves.
        replay_data = t["trees"].copy()
        replay_data.insert(
            2, "target_date", pd.read_csv(data["manifest"]["windows"][0]["alignment"]).target_date
        )
        replay_data["actual_for_posthoc_scoring"] = t["truth"]
        replay_data.to_csv(output / "trace-tree-predictions.csv", index=False)

    pred.to_csv(output / "diagnostic-predictions.csv", index=False)
    data["metrics"].to_csv(output / "diagnostic-metrics.csv", index=False)
    data["coefficients"].to_csv(output / "coefficients.csv", index=False)
    data["contributions"].to_csv(output / "contributions.csv", index=False)
    for filename in ["predictions.csv", "metrics.csv", "audit.json", "result.md"]:
        shutil.copyfile(run / filename, output / filename)
    # Every chart gets a caption and a portable original-resolution asset.
    entries = []
    sections = list(dict.fromkeys(item["section"] for item in gallery))
    for section in sections:
        entries.append(
            f'<h2 id="{html.escape(section.lower().replace(" ", "-"))}">{html.escape(section)}</h2>'
        )
        for item in [g for g in gallery if g["section"] == section]:
            slug = item["slug"]
            entries.append(
                f'<figure id="{slug}"><h3>{html.escape(item["title"])}</h3>'
                f'<a href="figures/{slug}.svg"><img loading="lazy" src="figures/{slug}.png" '
                f'alt="{html.escape(item["title"] + ". " + item["caption"], quote=True)}"></a>'
                f"<figcaption>{html.escape(item['caption'])} "
                f'<a href="figures/{slug}.png">PNG</a> · <a href="figures/{slug}.svg">SVG</a></figcaption></figure>'
            )
    navigation = " · ".join(f'<a href="#{s.lower().replace(" ", "-")}">{s}</a>' for s in sections)
    table = (
        data["metrics"]
        .assign(model=lambda d: d.model.map(LABELS))
        .to_html(index=False, float_format=lambda n: f"{n:.6f}", border=0)
    )
    document = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inside the MRF · September 2018 diagnostic atlas</title><style>
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f5f6f8;color:#213343;font:17px/1.65 system-ui,sans-serif}
main{max-width:1150px;margin:auto;padding:42px 24px}h1{font-size:clamp(32px,5vw,54px);line-height:1.1;margin:12px 0 20px;letter-spacing:-1.7px}
h2{margin-top:64px;border-bottom:1px solid #c9d2db;padding-bottom:12px}h3{font-size:21px;margin:0 0 16px}p{max-width:880px}
a{color:#215f9c;text-underline-offset:3px}nav{line-height:2.1}figure{background:white;padding:24px;margin:24px 0 38px;border-radius:8px}
img{display:block;max-width:100%;height:auto}figcaption{font-size:15px;line-height:1.65;max-width:1000px;margin-top:14px;color:#405366}
.eyebrow{font-size:13px;text-transform:uppercase;letter-spacing:1.8px;color:#566b7e}.summary{border-left:4px solid #bc5a39;padding-left:20px}
table{border-collapse:collapse;font-size:14px;background:white;width:100%}th,td{padding:10px 12px;text-align:right;border-bottom:1px solid #dce3e9}th:first-child,td:first-child{text-align:left}
.table-wrap{overflow:auto}details{margin:25px 0}code{font-size:14px;overflow-wrap:anywhere}footer{font-size:14px;color:#566b7e;margin-top:50px}
@media(max-width:600px){main{padding:24px 12px}figure{padding:12px;margin:20px 0}h3{font-size:18px}figcaption{font-size:14px}}@media print{body{background:white}figure{break-inside:avoid}nav{display:none}}
</style><main><div class="eyebrow">Qualified reconstruction · October 21, 2026</div><h1>Inside the MRF</h1>
<p class="summary">It learned changing coefficients. It did not reproduce the paper’s gain. This report shows what was trained, where the loss comes from, and what the fitted forest actually does.</p>
<p>Target: one-quarter-ahead Δlog unemployment. Evaluation: 48 quarters, 2003Q1–2014Q4. Six expanding refits, 100 trees per fit, three seeds. No Jev or LLM forecast evaluation has run.</p>
<nav>NAVIGATION</nav><h2>The readout</h2><p>Fixed FA-AR: <b>0.833</b> RMSE / AR(4). MRF: <b>0.852 / 0.829 / 0.824</b>. Paper MRF: <b>0.72</b>. The declared joint agreement check fails. All seeds are retained.</p>
<p>Before 2008, the forest helps. Its extra 2009Q1 loss and its later weak gains offset that benefit. The post-hoc same-equation OLS control also beats every MRF seed on RMSE. But all forest seeds improve MAE: average absolute misses are smaller, while the largest misses hurt squared-error performance. This locates the tradeoff; it does not prove its cause.</p>
<details><summary>Read this before interpreting the charts</summary><ul>
<li>All new diagnostic views and the same-equation OLS control are post-hoc. No settings, seeds, tree count or evaluation dates were selected from them.</li>
<li>The archive has 247 of the paper’s original 248 indicators. The complete original author caller is unavailable. These remain qualified reconstructions, not an exact replication or real-time-vintage forecasting study.</li>
<li>Training curves come from a newly instrumented replay of the first refit, seed 101. Every final coefficient and forecast must match the original saved output. No original per-tree log existed.</li>
<li>The source’s split-omitted rows can still enter terminal regressions. We do not label their predictions as clean OOB validation. There is no new independent validation set here.</li>
<li>Seed spread and tree dispersion are not predictive uncertainty or calibrated confidence intervals. Coefficients and factor contributions are not causal effects.</li>
<li>PCA bases are refitted. Factor signs and rotations can change across refits. Do not read a factor coefficient across boundaries as the same identified economic quantity.</li>
<li>Tree usage is frequency, not feature importance. Calendar subperiods and worst-quarter rankings are descriptive, not new benchmark definitions.</li></ul></details>
GALLERY
<h2>Data and verification</h2><div class="table-wrap">METRICS</div><p>*Static same-equation OLS is exploratory, with an intercept, two target lags, and two lagged PCA factors. The source fixed FA-AR has nine coefficients.</p>
<p><a href="predictions.csv">Original predictions</a> · <a href="metrics.csv">Original metrics</a> · <a href="audit.json">Original full audit</a> · <a href="diagnostics.json">Diagnostic provenance</a> · <a href="diagnostic-metrics.csv">Metrics including exploratory OLS</a> · <a href="coefficients.csv">Coefficients</a> · <a href="contributions.csv">Contributions</a></p>
<p>Sources: <a href="https://doi.org/10.1002/jae.3030">Goulet Coulombe (2024)</a>; <a href="https://github.com/philgoucou/macrorf/blob/bdb2ed435affb741aafdf78bab12c470ec6d55d0/R/MRF_v210403.R">pinned author engine</a>; <a href="https://www.stlouisfed.org/research/economists/mccracken/fred-databases">FRED-QD archive</a>. The GPL engine is external and unmodified, not redistributed under this repository’s MIT license.</p>
<footer>All charts use saved or reproducibly replayed numerical artifacts. Scientific figures are available as PNG and editable SVG. This report works offline.</footer></main></html>"""
    document = (
        document.replace("NAVIGATION", navigation)
        .replace("GALLERY", "\n".join(entries))
        .replace("METRICS", table)
    )
    (output / "index.html").write_text(document)
    # Self-contained companion for sharing locally without a relative-assets folder.
    standalone = document
    for g in gallery:
        png = (figures / f"{g['slug']}.png").read_bytes()
        standalone = standalone.replace(
            f'src="figures/{g["slug"]}.png"',
            f'src="data:image/png;base64,{base64.b64encode(png).decode()}"',
        )
    (output / "standalone.html").write_text(standalone)
    record = dict(
        status="completed",
        diagnostic_type="posthoc_not_model_selection",
        source_manifest_sha256=digest(run / "manifest.json"),
        source_audit_sha256=digest(run / "audit.json"),
        source_prediction_sha256=digest(run / "predictions.csv"),
        source_metrics_sha256=digest(run / "metrics.csv"),
        source_config=data["manifest"]["config"],
        engine=data["manifest"]["engine"],
        original_model_code=data["manifest"]["code"],
        diagnostic_code_sha256=digest(Path(__file__)),
        trace_adapter_sha256=digest(
            Path(__file__).resolve().parents[2] / "scripts/trace_mrf2018.R"
        ),
        figure_count=len(gallery),
        figures=gallery,
        max_coefficient_reconstruction_error=data["max_decomposition_error"],
        exploratory_control=OLS,
        original_predictions_replaced=False,
        replay=None
        if trace_result is None
        else dict(
            first_refit="2002Q4",
            seed=101,
            trees=100,
            maximum_saved_output_difference=trace_result["match_max_abs"],
            training_curve="in_sample",
            forecast_curve="already_observed_8_quarter_test_block",
            strict_oob_validation=False,
            tree_dispersion_is_prediction_interval=False,
            replay_sha256=digest(trace / "replay.csv"),
            tree_predictions_sha256=digest(trace / "replay.csv.trees.csv"),
            leaves_sha256=digest(trace / "replay.csv.leaves.csv"),
        ),
    )
    # Hash every shareable artifact except this self-referential record and the ZIP.
    record["artifact_checksums"] = {
        str(p.relative_to(output)): digest(p)
        for p in sorted(output.rglob("*"))
        if p.is_file()
        and p.name not in {"diagnostics.json", "standalone.html"}
        and p.suffix != ".zip"
    }
    record["local_standalone_sha256"] = digest(output / "standalone.html")
    (output / "diagnostics.json").write_text(json.dumps(record, indent=2) + "\n")
    with zipfile.ZipFile(
        output / "mrf-diagnostics.zip", "w", compression=zipfile.ZIP_DEFLATED
    ) as z:
        for p in sorted(output.rglob("*")):
            if p.is_file() and p.suffix != ".zip":
                z.write(p, arcname=str(p.relative_to(output)))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["replay", "report"])
    parser.add_argument("--run", type=Path, default=Path("runs/mrf-september2018-v1"))
    parser.add_argument("--trace", type=Path, default=Path("runs/mrf-september2018-trace-v1"))
    parser.add_argument(
        "--output", type=Path, default=Path("reports/mrf-september2018-diagnostics")
    )
    parser.add_argument("--r-library", type=Path)
    args = parser.parse_args()
    if args.action == "replay":
        if args.r_library is None:
            parser.error("--r-library is required for replay")
        replay(args.run, args.trace, args.r_library)
    else:
        result = build_report(args.run, args.output, args.trace)
        print(
            json.dumps(
                {
                    "figures": result["figure_count"],
                    "replay": result["replay"],
                    "report": str((args.output / "index.html").resolve()),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
