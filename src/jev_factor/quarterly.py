"""Pinned FRED-QD ingestion and past-fitted representations for MRF reconstruction.

This is original integration code. The separately downloaded author's GPL engine
is not embedded here. Unspecified preprocessing choices are explicit run inputs.
"""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from threadpoolctl import threadpool_limits

from jev_factor.data import transform

ARCHIVE_URL = (
    "https://journaldata.zbw.eu/dataset/c48432e1-5a25-49f1-95b1-6c681f21e252/resource/"
    "9c8c1313-bb06-4bd1-83ac-be22b0cc12ed/download/"
    "the-macroeconomy-as-a-random-forest-replication-data.zip"
)
ARCHIVE_SHA256 = "5b31cd2ad184ffc8d1710433fbc34a5ac110f8b4bfa69f3c1400fdd828a9de8c"
QD_SHA256 = "69226fbe297c09fdbf011c7c09e9c3abf04db1b1dfbba203b51291b825a00335"
SP_NAMES = ["S&P 500", "S&P: indust", "S&P div yield", "S&P PE ratio"]


@dataclass
class QuarterlyData:
    levels: pd.DataFrame
    panel: pd.DataFrame
    target: pd.Series
    tcodes: pd.Series
    sw_membership: pd.Series
    metadata: dict


def download_archive(path: Path) -> dict:
    if path.exists():
        payload = path.read_bytes()
    else:
        response = httpx.get(ARCHIVE_URL, follow_redirects=True, timeout=90)
        response.raise_for_status()
        payload = response.content
    digest = hashlib.sha256(payload).hexdigest()
    if digest != ARCHIVE_SHA256:
        raise ValueError(f"Replication archive checksum mismatch: {digest}")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return {"path": str(path), "sha256": digest, "url": ARCHIVE_URL}


def parse_quarterly_csv(payload: bytes) -> tuple[pd.DataFrame, pd.Series, pd.Series, dict]:
    rows = list(csv.reader(io.StringIO(payload.decode("utf-8-sig"))))
    if len(rows) < 5 or rows[1][0] != "factors" or rows[2][0] != "transform":
        raise ValueError("Expected FRED-QD factors and transform metadata rows")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("Ragged quarterly CSV")
    repairs = {}
    names = rows[0][1:]
    # The deposited CSV has four multiword names split across ten header fields.
    # Repair only its exact signature, never silently drop populated columns.
    tail = ["S&P", "500", "S&P:", "indust", "S&P", "div", "yield", "S&P", "PE", "ratio"]
    if width == 255 and rows[0][245:] == tail:
        if any(any(value.strip() for value in row[249:]) for row in rows[1:]):
            raise ValueError("Unexpected observations/metadata in split-header padding")
        names = rows[0][1:245] + SP_NAMES
        repairs = {str(i): name for i, name in zip(range(245, 249), SP_NAMES, strict=True)}
    n = len(names)
    if len(set(names)) != n or any(not name for name in names):
        raise ValueError("Unresolved empty or duplicate series names")
    index = pd.to_datetime([row[0] for row in rows[3:]], format="%m/%d/%Y").to_period("Q")
    if not index.is_unique or not index.is_monotonic_increasing:
        raise ValueError("Quarter dates must be unique and increasing")
    if not index.equals(pd.period_range(index[0], index[-1], freq="Q")):
        raise ValueError("Missing calendar quarter")
    levels = pd.DataFrame([row[1 : n + 1] for row in rows[3:]], index=index, columns=names)
    levels = levels.apply(pd.to_numeric, errors="raise")
    codes = pd.Series([int(x) for x in rows[2][1 : n + 1]], index=names, name="tcode")
    flags = pd.Series([int(x) for x in rows[1][1 : n + 1]], index=names, name="SW_membership")
    if not codes.isin(range(1, 8)).all() or not flags.isin([0, 1]).all():
        raise ValueError("Invalid quarterly metadata")
    return levels, codes, flags, repairs


def load_quarterly(path: Path) -> QuarterlyData:
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Use the pinned journal replication archive")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [
            n
            for n in archive.namelist()
            if n.endswith("/FREDQD_2019-03.csv") and not n.startswith("__MACOSX/")
        ]
        if len(members) != 1:
            raise ValueError("Ambiguous quarterly archive member")
        raw = archive.read(members[0])
    if hashlib.sha256(raw).hexdigest() != QD_SHA256:
        raise ValueError("Quarterly member checksum mismatch")
    levels, codes, flags, repairs = parse_quarterly_csv(raw)
    panel = pd.DataFrame({name: transform(levels[name], int(codes[name])) for name in levels})
    # MRF Section 3 explicitly differs from the CSV's UNRATE tcode=2.
    target = np.log(levels["UNRATE"]).diff().rename("delta_log_UNRATE")
    return QuarterlyData(
        levels,
        panel,
        target,
        codes,
        flags,
        {
            "archive_sha256": ARCHIVE_SHA256,
            "member_sha256": QD_SHA256,
            "member": members[0],
            "header_repairs": repairs,
            "series_count": len(codes),
            "SW_membership_semantics": "historical_Stock_Watson_factor_subset_not_MRF_eligibility",
            "target_transform": "delta_log_UNRATE",
            "panel_UNRATE_tcode": int(codes["UNRATE"]),
            "evaluation": "fixed_vintage_retrospective_not_historical_release_vintages",
        },
    )


class PastRepresentation:
    """Train-only outlier thresholds, low-rank missing-data completion and PCA.

    EM rank is fixed, unlike the official FRED routine's estimated IC rank. This
    is an explicit reconstruction choice, not claimed identical author processing.
    Future rows are completed independently with the frozen factor loadings.
    """

    def __init__(self, rank: int = 5, outlier_iqr: float | None = 10, max_iter: int = 100):
        self.rank, self.outlier_iqr, self.max_iter = rank, outlier_iqr, max_iter

    @threadpool_limits.wrap(limits=1)
    def fit(self, frame: pd.DataFrame) -> PastRepresentation:
        self.columns = frame.columns
        values = frame.to_numpy(dtype=float)
        self.median = np.nanmedian(values, axis=0)
        q = np.nanpercentile(values, [25, 75], axis=0, method="hazen")
        self.iqr = q[1] - q[0]
        values = self._clean(values)
        count = np.isfinite(values).sum(axis=0)
        self.active = (count > 2) & (np.nanstd(values, axis=0) > 1e-12)
        if self.active.sum() < self.rank:
            raise ValueError("Insufficient nonconstant past series for PCA")
        x = values[:, self.active]
        missing = ~np.isfinite(x)
        filled = np.where(missing, np.nanmean(x, axis=0), x)
        previous = None
        self.converged = not missing.any()
        self.iterations = 0
        for iteration in range(self.max_iter):
            mean, std = filled.mean(axis=0), filled.std(axis=0, ddof=1)
            std = np.maximum(std, 1e-12)
            z = (filled - mean) / std
            pca = PCA(n_components=self.rank, svd_solver="full").fit(z)
            reconstructed = pca.inverse_transform(pca.transform(z))
            if previous is not None:
                change = np.sum((reconstructed - previous) ** 2) / max(np.sum(previous**2), 1e-12)
                if change <= 1e-6:
                    self.converged = True
                    break
            if not missing.any():
                self.converged = True
                break
            filled[missing] = (reconstructed * std + mean)[missing]
            previous = reconstructed
            self.iterations = iteration + 1
        self.mean, self.std = filled.mean(axis=0), filled.std(axis=0, ddof=1)
        self.pca = PCA(n_components=self.rank, svd_solver="full").fit(
            (filled - self.mean) / self.std
        )
        self.training_filled = filled
        self.training_index = frame.index.copy()
        self.training_z = (filled - self.mean) / self.std
        self.training_outliers = int(np.sum(np.isfinite(frame.to_numpy()) & ~np.isfinite(values)))
        return self

    def _clean(self, values: np.ndarray) -> np.ndarray:
        x = values.copy()
        if self.outlier_iqr is not None:
            outlier = np.abs(x - self.median) > self.outlier_iqr * self.iqr
            x[outlier] = np.nan
        return x

    @threadpool_limits.wrap(limits=1)
    def transform(self, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        if not frame.columns.equals(self.columns):
            raise ValueError("Representation series/order mismatch")
        values = self._clean(frame.to_numpy(dtype=float))[:, self.active]
        z = (values - self.mean) / self.std
        for i, row in enumerate(z):
            present = np.isfinite(row)
            if not present.any():
                raise ValueError("No contemporaneous observed information")
            if not present.all():
                score = np.linalg.lstsq(
                    self.pca.components_[:, present].T,
                    row[present] - self.pca.mean_[present],
                    rcond=None,
                )[0]
                completion = score @ self.pca.components_ + self.pca.mean_
                z[i, ~present] = completion[~present]
        # Retain the past-only EM solution for rows actually used to fit it.
        common = frame.index.intersection(self.training_index)
        z[frame.index.get_indexer(common)] = self.training_z[
            self.training_index.get_indexer(common)
        ]
        factors = self.pca.transform(z)
        return (
            pd.DataFrame(z, index=frame.index, columns=self.columns[self.active]),
            pd.DataFrame(
                factors, index=frame.index, columns=[f"F{i + 1}" for i in range(self.rank)]
            ),
        )


@threadpool_limits.wrap(limits=1)
def make_design(
    data: QuarterlyData,
    fit_end: pd.Period,
    through: pd.Period,
    *,
    panel_start: str = "1959Q3",
    rank: int = 5,
    outlier_iqr: float | None = 10,
    factor_panel: str = "all",
) -> tuple[pd.DataFrame, dict]:
    if through <= fit_end:
        raise ValueError("Need a forecast row after the fitting endpoint")
    panel = data.panel.loc[panel_start : through - 1]
    if factor_panel == "sw_subset":
        panel = panel.loc[:, data.sw_membership.eq(1)]
    elif factor_panel != "all":
        raise ValueError("factor_panel must be all or sw_subset")
    representation = PastRepresentation(rank, outlier_iqr).fit(panel.loc[:fit_end])
    z, factors = representation.transform(panel)
    # Target-date indexing: y[d] is forecast from information through d-1.
    index = data.target.loc[panel_start:through].index
    cols = {f"y_lag{k}": data.target.shift(k).reindex(index) for k in range(1, 9)}
    cols.update(
        {
            f"{name}_lag{k}": factors[name].reindex(index).shift(k)
            for name in factors
            for k in range(1, 9)
        }
    )
    cols.update(
        {
            f"series_{j:03d}_lag{k}": z[name].reindex(index).shift(k)
            for j, name in enumerate(z)
            for k in [1, 2]
        }
    )
    # Each series gets its own two-component compression of its eight lags.
    for j, name in enumerate(z):
        lagged = pd.concat(
            [z[name].reindex(index).shift(k).rename(f"lag{k}") for k in range(1, 9)], axis=1
        )
        valid = lagged.dropna()
        training = valid.loc[:fit_end]
        maf = PCA(n_components=2, svd_solver="full").fit(training)
        scores = pd.DataFrame(maf.transform(valid), index=valid.index)
        for k in range(2):
            cols[f"MAF_{j:03d}_{k + 1}"] = scores[k].reindex(index)
    cols["trend"] = pd.Series(np.arange(len(index), dtype=float), index=index)
    design = pd.DataFrame(cols, index=index)
    design.insert(0, "target", data.target.reindex(index))
    design = design.dropna(subset=design.columns.drop("target"))
    return design, {
        "representation_fit_end": str(fit_end),
        "factor_panel": factor_panel,
        "active_series": list(z.columns),
        "dropped_series": list(panel.columns[~representation.active]),
        "em_iterations": representation.iterations,
        "em_converged": representation.converged,
        "training_outliers": representation.training_outliers,
        "state_columns": len(design.columns) - 1,
        "PCA_variance_ratios": representation.pca.explained_variance_ratio_.tolist(),
        "factor_loading_leaders": {
            f"F{k + 1}": list(z.columns[np.argsort(-np.abs(row))[:10]])
            for k, row in enumerate(representation.pca.components_)
        },
    }
