"""Command-line entry points. Default runs are local and make no model API calls."""

import argparse
import json
from pathlib import Path

from jev_factor.data import download_fred
from jev_factor.experiment import run


def main() -> None:
    parser = argparse.ArgumentParser(prog="jev-factor")
    sub = parser.add_subparsers(dest="command", required=True)
    download = sub.add_parser("download-fred", help="Fetch and verify the pinned official vintage")
    download.add_argument("--output", type=Path, default=Path("data/raw/fred_md_2026-09.csv"))
    experiment = sub.add_parser("run", help="Run a bounded walk-forward experiment")
    experiment.add_argument("--config", type=Path, required=True)
    experiment.add_argument("--output", type=Path, required=True)
    experiment.add_argument("--max-origins", type=int)
    experiment.add_argument("--seeds", nargs="+", type=int)
    experiment.add_argument("--methods", nargs="+", help="Override the configuration's method list")
    experiment.add_argument("--max-api-calls", type=int, default=0)
    experiment.add_argument("--jev-model", default="jev-1.13.0")
    experiment.add_argument("--llm-model")
    experiment.add_argument("--llm-provider", choices=["openai", "anthropic", "gemini"])
    experiment.add_argument("--reverse-options", action="store_true")
    experiment.add_argument("--anonymize", action="store_true")
    args = parser.parse_args()
    if args.command == "download-fred":
        result = download_fred(args.output)
    else:
        if args.max_origins is not None and args.max_origins < 1:
            parser.error("--max-origins must be positive")
        config = json.loads(args.config.read_text())
        if args.methods:
            config["methods"] = args.methods
        if args.seeds:
            config["seeds"] = args.seeds
        config.update(reverse_options=args.reverse_options, anonymize=args.anonymize)
        api = {
            "jev_model": args.jev_model,
            "llm_model": args.llm_model,
            "llm_provider": args.llm_provider,
        }
        if "gate_llm" in config["methods"] and not args.llm_provider:
            parser.error("--llm-provider is required for gate_llm")
        result = run(
            config,
            args.output,
            api=api,
            max_origins=args.max_origins,
            max_api_calls=args.max_api_calls,
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
