"""Command-line entry point for the abstraction-discovery research kernel."""

from __future__ import annotations

import argparse
import sys

from .function_benchmark import (
    FunctionExperimentError,
    replay_function_experiment,
    run_function_experiment,
    smoke_function_language,
    validate_function_native,
)
from .function_discovery import DiscoveryError
from .function_language import FunctionLanguageError
from .function_synthesis import (
    REGISTERED_BUDGET,
    SynthesisError,
    replay_synthesis_experiment,
    run_synthesis_experiment,
    smoke_function_synthesis,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m laicode")
    commands = parser.add_subparsers(dest="command", required=True)

    run_function = commands.add_parser(
        "run-function-experiment",
        help="grow the A2 bounded-function and call-graph language",
    )
    run_function.add_argument("output")

    replay_function = commands.add_parser(
        "replay-function-experiment",
        help="exactly replay an A2 function-language bundle",
    )
    replay_function.add_argument("bundle")

    native_function = commands.add_parser(
        "validate-function-native",
        help="compile generated A2 C and run archived function cases",
    )
    native_function.add_argument("bundle")
    native_function.add_argument("output")
    native_function.add_argument("--compiler", default="cc")

    smoke_function = commands.add_parser(
        "smoke-function-language",
        help="grow, replay, compile, and validate the A2 function language",
    )
    smoke_function.add_argument("output")
    smoke_function.add_argument("--compiler", default="cc")

    run_synthesis = commands.add_parser(
        "run-synthesis-experiment",
        help="compare primitive and learned vocabulary search cost on unseen tasks",
    )
    run_synthesis.add_argument("output")
    run_synthesis.add_argument("--budget", type=int, default=REGISTERED_BUDGET)

    replay_synthesis = commands.add_parser(
        "replay-synthesis-experiment",
        help="exactly replay an A2-S synthesis bundle",
    )
    replay_synthesis.add_argument("bundle")
    replay_synthesis.add_argument("--budget", type=int, default=REGISTERED_BUDGET)

    smoke_synthesis = commands.add_parser(
        "smoke-function-synthesis",
        help="run and exactly replay the A2-S synthesis transfer study",
    )
    smoke_synthesis.add_argument("output")
    smoke_synthesis.add_argument("--budget", type=int, default=REGISTERED_BUDGET)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "run-function-experiment":
            report = run_function_experiment(args.output)
            print(
                f"complete {report.report_id} tasks={report.task_count} "
                f"cases={report.case_count} cycles={report.cycle_count} "
                f"valid={str(report.all_valid).lower()}"
            )
            return 0
        if args.command == "replay-function-experiment":
            replay = replay_function_experiment(args.bundle)
            print(
                f"replayed {replay.source_report_id} "
                f"files={replay.files_verified} exact=true"
            )
            return 0
        if args.command == "validate-function-native":
            report = validate_function_native(
                args.bundle,
                args.output,
                compiler=args.compiler,
            )
            print(
                f"validated {report.report_id} compiler={report.compiler} "
                f"translations={report.translations_passed} "
                f"cases={report.cases_passed} valid={str(report.all_valid).lower()}"
            )
            return 0
        if args.command == "smoke-function-language":
            report, replay, native = smoke_function_language(
                args.output,
                compiler=args.compiler,
            )
            print(
                f"complete {report.report_id} tasks={report.task_count} "
                f"cases={report.case_count} cycles={report.cycle_count} "
                f"files={replay.files_verified} exact=true "
                f"native={native.report_id} translations={native.translations_passed} "
                f"native_cases={native.cases_passed} valid=true"
            )
            return 0
        if args.command == "run-synthesis-experiment":
            report = run_synthesis_experiment(args.output, budget=args.budget)
            print(
                f"complete {report.report_id} tasks={report.task_count} "
                f"budget={report.budget} "
                f"treatment_median_ppm={report.treatment_median_ratio_ppm} "
                f"control_median_ppm={report.control_median_ratio_ppm}"
            )
            return 0
        if args.command == "replay-synthesis-experiment":
            replay = replay_synthesis_experiment(args.bundle, budget=args.budget)
            print(
                f"replayed {replay.source_report_id} "
                f"files={replay.files_verified} exact=true"
            )
            return 0
        if args.command == "smoke-function-synthesis":
            report, replay = smoke_function_synthesis(args.output, budget=args.budget)
            print(
                f"complete {report.report_id} tasks={report.task_count} "
                f"budget={report.budget} files={replay.files_verified} exact=true "
                f"treatment_median_ppm={report.treatment_median_ratio_ppm} "
                f"control_median_ppm={report.control_median_ratio_ppm}"
            )
            return 0
    except (
        OSError,
        DiscoveryError,
        FunctionExperimentError,
        FunctionLanguageError,
        SynthesisError,
    ) as error:
        print(f"invalid input: {error}", file=sys.stderr)
        return 2

    raise AssertionError(f"unhandled command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
