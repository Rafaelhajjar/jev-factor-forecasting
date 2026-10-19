"""Data acquisition and causal transformations. Raw provider data stay out of Git."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

FRED_URL = (
    "https://www.stlouisfed.org/-/media/project/frbstl/stlouisfed/"
    "research/fred-md/monthly/2026-09-md.csv"
)
FRED_SHA256 = "d6e239038afbdbf4667c2a63c13c942817bc196fedab4355cd7e0d353ecdd65d"


@dataclass
class Dataset:
    X: pd.DataFrame
    y: pd.Series
    metadata: dict


def transform(series: pd.Series, code: int) -> pd.Series:
    """McCracken--Ng codes 1--7, using only present and past observations."""
    if code == 1:
        return series.copy()
    if code == 2:
        return series.diff()
    if code == 3:
        return series.diff().diff()
    if code in (4, 5, 6):
        logs = np.log(series.where(series > 0))
        return {4: logs, 5: logs.diff(), 6: logs.diff().diff()}[code]
    if code == 7:
        return series.pct_change(fill_method=None).diff().replace([np.inf, -np.inf], np.nan)
    raise ValueError(f"Unsupported transformation code: {code}")


def download_fred(destination: Path) -> dict:
    """Fetch a fixed official vintage and reject any unexpected content."""
    if destination.exists():
        payload = destination.read_bytes()
    else:
        response = httpx.get(FRED_URL, timeout=90, follow_redirects=True)
        response.raise_for_status()
        payload = response.content
    digest = hashlib.sha256(payload).hexdigest()
    if digest != FRED_SHA256:
        raise ValueError(f"FRED vintage checksum mismatch: {digest}; expected {FRED_SHA256}")
    parsed = pd.read_csv(io.BytesIO(payload))
    if parsed.iloc[0, 0] != "Transform:" or "INDPRO" not in parsed:
        raise ValueError("Unexpected FRED-MD schema")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    metadata = {"url": FRED_URL, "sha256": digest, "vintage": "2026-09"}
    destination.with_suffix(".metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def load_fred(path: Path, target: str, start: str, end: str) -> Dataset:
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != FRED_SHA256:
        raise ValueError("Use the pinned official FRED-MD vintage; checksum does not match")
    raw = pd.read_csv(io.BytesIO(payload))
    codes = raw.iloc[0, 1:].astype(int)
    panel = raw.iloc[1:, 1:].apply(pd.to_numeric, errors="coerce")
    panel.index = pd.DatetimeIndex(pd.to_datetime(raw.iloc[1:, 0], format="%m/%d/%Y"))
    panel = pd.DataFrame({name: transform(panel[name], int(codes[name])) for name in panel})
    panel = panel.loc[start:end].replace([np.inf, -np.inf], np.nan)
    y = panel[target].rename("target")
    return Dataset(
        X=panel.drop(columns=[target]),
        y=y,
        metadata={
            "dataset": "fred_md",
            "target": target,
            "target_transform": int(codes[target]),
            "sha256": digest,
            "vintage": "2026-09",
            "evaluation": "revised-data retrospective",
        },
    )


def synthetic(seed: int = 7, n_samples: int = 480) -> Dataset:
    """Known factors with changing loadings and noisy proxies; no regime labels in X.

    y[t+1] = .3*y[t] + beta[t] @ f[t] + noise.
    The changing beta is withheld from both classical and language-based methods.
    """
    rng = np.random.default_rng(seed)
    factors = np.zeros((n_samples, 4))
    innovations = rng.normal(size=factors.shape)
    for t in range(1, n_samples):
        factors[t] = 0.6 * factors[t - 1] + innovations[t]
    regimes = (np.arange(n_samples) // 80) % 3
    coefficients = np.array([[1.8, 0, 0.3, 0], [0, -1.8, 0.3, 0], [-1.8, 1, 0.3, 0]])
    errors = rng.normal(scale=0.7, size=n_samples)
    y = np.zeros(n_samples)
    for t in range(n_samples - 1):
        y[t + 1] = 0.3 * y[t] + coefficients[regimes[t]] @ factors[t] + errors[t + 1]
    # Extra noisy measurements allow a separate latent-factor/PCA experiment.
    measurements = factors @ rng.normal(size=(4, 12)) + rng.normal(scale=0.4, size=(n_samples, 12))
    index = pd.date_range("1980-01-01", periods=n_samples, freq="MS")
    values = np.column_stack([factors, measurements])
    names = [f"signal_{i}" for i in range(4)] + [f"measurement_{i}" for i in range(12)]
    return Dataset(
        pd.DataFrame(values, index=index, columns=names),
        pd.Series(y, index=index, name="target"),
        {
            "dataset": "synthetic",
            "seed": seed,
            "n_samples": n_samples,
            "dgp": "switching linear factor loadings; unobserved regime; no oracle supplied",
        },
    )
