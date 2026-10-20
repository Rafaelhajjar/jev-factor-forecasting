"""Separate pinned September 2018 path; never changes the old reconstruction."""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from jev_factor.data import transform
from jev_factor.quarterly import PastRepresentation, QuarterlyData, parse_quarterly_csv

VINTAGE_URL = (
    "https://www.stlouisfed.org/-/media/project/frbstl/stlouisfed/research/fred-md/"
    "historical-vintages-of-fred-qd-2018-05-to-2025-12.zip"
)
VINTAGE_ARCHIVE_SHA = "56c5ff7ae60c9ed1468a4219bdda2a3f41644a16e1e1a7520cc38779d03df1df"
VINTAGE_MEMBER = "FRED-QD_2018m09.csv"
VINTAGE_MEMBER_SHA = "44fdb5914a25a560648fccc71f85d2ae02bbe0bebae199ec6d3dbdbc7ae5a1a7"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download_vintage(path: Path) -> None:
    if not path.exists():
        response = httpx.get(VINTAGE_URL, follow_redirects=True, timeout=90)
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != VINTAGE_ARCHIVE_SHA:
            raise ValueError("Historical archive changed; do not silently update the pin")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
    if sha(path) != VINTAGE_ARCHIVE_SHA:
        raise ValueError("Historical archive checksum mismatch")


def load_vintage(path: Path) -> QuarterlyData:
    if sha(path) != VINTAGE_ARCHIVE_SHA:
        raise ValueError("Historical archive checksum mismatch")
    with zipfile.ZipFile(io.BytesIO(path.read_bytes())) as archive:
        raw = archive.read(VINTAGE_MEMBER)
    if hashlib.sha256(raw).hexdigest() != VINTAGE_MEMBER_SHA:
        raise ValueError("September 2018 member checksum mismatch")
    levels, codes, flags, repairs = parse_quarterly_csv(raw)
    if levels.shape != (238, 247) or str(levels.index[-1]) != "2018Q2" or repairs:
        raise ValueError("Unexpected pinned vintage dimensions or header repairs")
    panel = pd.DataFrame({name: transform(levels[name], int(codes[name])) for name in levels})
    return QuarterlyData(
        levels,
        panel,
        np.log(levels.UNRATE).diff().rename("delta_log_UNRATE"),
        codes,
        flags,
        {
            "vintage": "2018-09",
            "url": VINTAGE_URL,
            "archive_sha256": VINTAGE_ARCHIVE_SHA,
            "member": VINTAGE_MEMBER,
            "member_sha256": VINTAGE_MEMBER_SHA,
            "series_count": 247,
            "first_quarter": "1959Q1",
            "last_quarter": "2018Q2",
            "not_augmented_with_later_vintage_series": True,
            "evaluation": "fixed_vintage_retrospective_not_real_time_releases",
        },
    )


def origin_aligned_design(
    z: pd.DataFrame, target: pd.Series, horizon: int = 1
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Forward labels at origin o; eight observations are o,...,o-7.

    Returned rows are labeled by target date d=o+h. No iteration or h=1
    predictions enter h>1 labels. AR terms use the same origin convention.
    """
    if type(horizon) is not int or horizon < 1:
        raise ValueError("Positive integer horizon required")
    if not z.index.equals(target.index) or not z.index.is_unique:
        raise ValueError("Panel and target need the same unique quarterly grid")
    if not z.index.equals(pd.period_range(z.index[0], z.index[-1], freq="Q")):
        raise ValueError("Missing calendar quarter")
    origins = z.index
    raw = pd.DataFrame(
        {f"raw_{j:03d}_lag{k}": z[name].shift(k) for j, name in enumerate(z) for k in range(8)},
        index=origins,
    )
    ar = pd.DataFrame({f"ar_lag{k}": target.shift(k) for k in range(4)}, index=origins)
    raw.insert(0, "target", target.shift(-horizon))
    ar.insert(0, "target", target.shift(-horizon))
    raw.index = ar.index = origins + horizon
    return raw, ar


def prepare_window(data: QuarterlyData, fit_end: pd.Period, through: pd.Period, config: dict):
    horizon = config["horizon"]
    first = config["panel_start"]
    panel = data.panel.loc[first : through - horizon]
    # Only covariates from rows with observed training labels fit preprocessing.
    rep_end = fit_end - horizon
    prep = config["preprocessing"]
    rep = PastRepresentation(prep["completion_rank"], prep["outlier_iqr"]).fit(panel.loc[:rep_end])
    z, _ = rep.transform(panel)
    target = data.target.reindex(z.index)
    raw, ar = origin_aligned_design(z, target, horizon)
    # Labels after the last covariate row are obtained by explicit date lookup.
    # This preserves the final forecast row, unlike a truncated shift(-h).
    raw["target"] = data.target.reindex(raw.index)
    ar["target"] = data.target.reindex(ar.index)
    raw = raw.loc[config["first_training_target"] : through].copy()
    ar = ar.reindex(raw.index).copy()
    if not np.isfinite(raw.to_numpy()).all() or not np.isfinite(ar.to_numpy()).all():
        raise ValueError("Nonfinite model inputs or target")
    train = raw.index <= fit_end
    if not train.any() or train.all():
        raise ValueError("Need training and test rows")
    metadata = {
        "fit_end": str(fit_end),
        "representation_fit_end": str(rep_end),
        "first_training_target": str(raw.index[0]),
        "first_training_origin": str(raw.index[0] - horizon),
        "last_training_origin": str(fit_end - horizon),
        "first_forecast_origin": str(fit_end + 1 - horizon),
        "active_series": list(z.columns),
        "features": raw.shape[1] - 1,
        "ntrain": int(train.sum()),
        "em_converged": rep.converged,
        "em_iterations": rep.iterations,
        "training_outliers": rep.training_outliers,
    }
    if not rep.converged:
        raise ValueError("Missing-data completion did not converge")
    return raw, ar, metadata
