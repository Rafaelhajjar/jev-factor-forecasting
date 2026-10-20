"""Local result artifact, generated only after the entire MRF audit succeeds."""

from pathlib import Path


def write_report(output: Path, result: dict) -> Path:
    if not result["full_declaration_verified"] or result["partial_scores_suppressed"]:
        raise ValueError("Do not publish accuracy from a partial or pilot run")
    if result["jobs_verified"] != 18 or result["actual_trees"] != 100:
        raise ValueError("The complete 18-fit declaration is required")
    lines = [
        "# Qualified September 2018 MRF: completed and audited",
        "",
        "All 18 native fits (100 trees each), six refits and 48 target quarters are verified.",
        "This is a qualified reconstruction, not a recovered original author pipeline.",
        "The earlier plain-RF source-cell criterion remains failed; the user authorized",
        "advancing with that limitation. The served archive has 247 series, not the original 248.",
        "",
        "## Results",
        "",
        "| Model | RMSE | RMSE / AR(4) |",
        "| --- | ---: | ---: |",
    ]
    for row in result["metrics"]:
        lines.append(f"| {row['model']} | {row['RMSE']:.10f} | {row['RMSE_over_AR4']:.6f} |")
    passed = result["joint_source_cell_diagnostic"]
    lines += [
        "",
        f"Joint source-cell diagnostic: **{'passes' if passed else 'fails'}**.",
        "It requires the matching fixed FA-AR within 0.03 of 0.83 and every individual",
        "MRF seed within 0.03 of 0.72. This is a project diagnostic, not a statistical test.",
        "A numerical match would not establish exact replication. No ensemble rescues a miss.",
        "",
        "MRF RMSE reductions versus its own matching fixed FA-AR:",
        "",
    ]
    for seed, gain in result["RMSE_reduction_vs_matching_FA_AR"].items():
        lines.append(f"- Seed {seed}: {100 * gain:.3f}%.")
    lines += [
        "",
        "## What is checked?",
        "",
        "States are rebuilt from the checksum-pinned archive and paired with the frozen",
        "RF preprocessing/calendar. The AR denominator is unchanged from that RF run.",
        "Independent base-R QR checks the linear forecasts. Native coefficients are finite",
        "and reconstruct every forecast; all completed outputs and runtimes are bound.",
        "This is not an independent refit of every full native tree.",
        "",
        "[Audit record](audit.json), [predictions](predictions.csv), [metrics](metrics.csv).",
        "",
        "No Jev/LLM forecasts were made. Earlier results and failure flags remain unchanged.",
        "Original preprocessing, factor orientation, settings and runtime remain qualified.",
    ]
    destination = output / "result.md"
    destination.write_text("\n".join(lines) + "\n")
    return destination
