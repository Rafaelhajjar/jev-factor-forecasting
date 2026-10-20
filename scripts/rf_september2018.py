"""Prepare, fit, or audit the separate September 2018 raw RF reconstruction."""

import argparse
import json
from pathlib import Path

from jev_factor.rf2018 import audit, prepare, run


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["prepare", "run", "audit"])
    p.add_argument("--config", type=Path, default=Path("configs/rf_september2018.json"))
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--r-library", type=Path, required=True)
    p.add_argument("--workers", type=int, default=2)
    a = p.parse_args()
    if a.workers not in [1, 2, 3, 4]:
        p.error("workers must be between one and four")
    if a.action == "prepare":
        prepare(a.config, a.archive, a.output)
    elif a.action == "run":
        run(a.output, a.r_library, a.workers)
    else:
        print(json.dumps(audit(a.output, a.r_library, a.workers), indent=2))


if __name__ == "__main__":
    main()
