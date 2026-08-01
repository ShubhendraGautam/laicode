"""Command-line entry point for prototype control-plane utilities."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from .algorithm_benchmark import (
    AlgorithmExperimentError,
    replay_algorithm_experiment,
    run_algorithm_experiment,
    smoke_algorithm_language,
    validate_algorithm_native,
)
from .algorithm_language import AlgorithmLanguageError
from .cache import CacheError, generate_trace
from .canonical import canonical_json_bytes
from .contracts import ContractValidationError, load_contract
from .isolation import IsolationError
from .kernel import (
    CommitError,
    ConstructionSession,
    KernelError,
    compile_complete_program,
)
from .hardware_feedback import (
    replay_hardware_feedback_study,
    run_hardware_feedback_study,
    smoke_hardware_feedback,
)
from .language_benchmark import (
    prepare_comparator_package,
    replay_comparator_package,
    run_comparator_benchmark,
)
from .machine_experiment import (
    MachineExperimentError,
    replay_machine_experiment,
    run_machine_experiment,
)
from .machine_hardware import measure_machine_hardware
from .machine_language import MachineLanguageError
from .prototype import PrototypeError, replay_prototype, run_prototype
from .provenance import ProvenanceError
from .shadow import ShadowError, replay_shadow, run_shadow


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m laicode")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser(
        "validate-contract", help="validate and identify an evolution contract"
    )
    validate.add_argument("contract")
    validate.add_argument(
        "--canonical", action="store_true", help="also print canonical JSON"
    )

    compile_program = commands.add_parser(
        "compile-program", help="compile and identify an R2 complete program"
    )
    compile_program.add_argument("contract")
    compile_program.add_argument("program")
    compile_program.add_argument(
        "--canonical", action="store_true", help="also print canonical artifact JSON"
    )

    construct_program = commands.add_parser(
        "construct-program", help="apply R3 actions and commit a complete program"
    )
    construct_program.add_argument("contract")
    construct_program.add_argument("actions", nargs="+")
    construct_program.add_argument(
        "--canonical", action="store_true", help="also print canonical artifact JSON"
    )

    run = commands.add_parser(
        "run-prototype", help="run the complete exploratory D0 prototype"
    )
    run.add_argument("contract")
    run.add_argument("output")

    replay = commands.add_parser(
        "replay-prototype", help="verify and exactly replay a prototype run bundle"
    )
    replay.add_argument("bundle")

    smoke = commands.add_parser(
        "smoke-prototype", help="run and exactly replay the exploratory D0 prototype"
    )
    smoke.add_argument("contract")
    smoke.add_argument("output")

    generate = commands.add_parser(
        "generate-trace", help="generate a canonical deterministic cache trace"
    )
    generate.add_argument(
        "scenario",
        choices=("scan_resistance", "recency_shift", "mixed_bursts"),
    )
    generate.add_argument("--seed", type=int, required=True)
    generate.add_argument("--events", type=int, default=256)
    generate.add_argument("--capacity", type=int, default=8)
    generate.add_argument("--name")

    shadow = commands.add_parser(
        "run-shadow", help="run a selected artifact in D1 counterfactual shadow"
    )
    shadow.add_argument("source_run")
    shadow.add_argument("trace")
    shadow.add_argument("output")
    shadow.add_argument("--minimum-events", type=int, default=64)
    shadow.add_argument("--checkpoint-interval", type=int, default=32)
    shadow.add_argument("--regression-tolerance-ppm", type=int, default=50_000)

    replay_d1 = commands.add_parser(
        "replay-shadow", help="verify and exactly replay a D1 shadow bundle"
    )
    replay_d1.add_argument("bundle")

    alternative = commands.add_parser(
        "smoke-alternative",
        help="run D0 selection plus D1 shadow revocation and exact replay",
    )
    alternative.add_argument("contract")
    alternative.add_argument("output")
    alternative.add_argument("--seed", type=int, default=401)
    alternative.add_argument("--events", type=int, default=256)
    alternative.add_argument("--capacity", type=int, default=8)

    run_machine = commands.add_parser(
        "run-machine-experiment",
        help="run the deterministic E-H0 vocabulary-evolution experiment",
    )
    run_machine.add_argument("output")

    replay_machine = commands.add_parser(
        "replay-machine-experiment",
        help="exactly replay an E-H0 deterministic evidence bundle",
    )
    replay_machine.add_argument("bundle")

    measure_machine = commands.add_parser(
        "measure-machine-hardware",
        help="compile and measure a deterministic E-H0 bundle on this host",
    )
    measure_machine.add_argument("bundle")
    measure_machine.add_argument("output")
    measure_machine.add_argument("--compiler", default="cc")
    measure_machine.add_argument("--trials", type=int, default=9)
    measure_machine.add_argument("--scale", type=int, default=1000)

    smoke_machine = commands.add_parser(
        "smoke-machine-language",
        help="run, replay, compile, and measure the E-H0 working prototype",
    )
    smoke_machine.add_argument("output")
    smoke_machine.add_argument("--compiler", default="cc")
    smoke_machine.add_argument("--trials", type=int, default=9)
    smoke_machine.add_argument("--scale", type=int, default=1000)

    prepare_benchmark = commands.add_parser(
        "prepare-language-benchmark",
        help="generate a deterministic cross-language comparator package",
    )
    prepare_benchmark.add_argument("machine_bundle")
    prepare_benchmark.add_argument("output")
    prepare_benchmark.add_argument("--scale", type=int, default=50)
    prepare_benchmark.add_argument("--trials", type=int, default=7)
    prepare_benchmark.add_argument("--warmups", type=int, default=3)
    prepare_benchmark.add_argument("--startup-trials", type=int, default=5)

    replay_benchmark = commands.add_parser(
        "replay-language-benchmark",
        help="exactly regenerate a cross-language comparator package",
    )
    replay_benchmark.add_argument("machine_bundle")
    replay_benchmark.add_argument("package")

    run_benchmark = commands.add_parser(
        "run-language-benchmark",
        help="run a comparator package on available local language toolchains",
    )
    run_benchmark.add_argument("machine_bundle")
    run_benchmark.add_argument("package")
    run_benchmark.add_argument("output")

    smoke_benchmark = commands.add_parser(
        "smoke-language-comparators",
        help="build, replay, and run the complete cross-language benchmark",
    )
    smoke_benchmark.add_argument("output")
    smoke_benchmark.add_argument("--scale", type=int, default=50)
    smoke_benchmark.add_argument("--trials", type=int, default=7)
    smoke_benchmark.add_argument("--warmups", type=int, default=3)
    smoke_benchmark.add_argument("--startup-trials", type=int, default=5)

    run_feedback = commands.add_parser(
        "run-hardware-feedback",
        help="run replicated host evidence and freeze a target vocabulary profile",
    )
    run_feedback.add_argument("machine_bundle")
    run_feedback.add_argument("comparator_package")
    run_feedback.add_argument("output")
    run_feedback.add_argument("--sessions", type=int, default=5)
    run_feedback.add_argument("--minimum-improvement-ppm", type=int, default=50_000)
    run_feedback.add_argument("--required-win-rate-ppm", type=int, default=800_000)

    replay_feedback = commands.add_parser(
        "replay-hardware-feedback",
        help="rederive a lifecycle decision from archived noisy host sessions",
    )
    replay_feedback.add_argument("machine_bundle")
    replay_feedback.add_argument("comparator_package")
    replay_feedback.add_argument("study")

    smoke_feedback = commands.add_parser(
        "smoke-hardware-feedback",
        help="run machine evolution, comparators, replicated feedback, and replay",
    )
    smoke_feedback.add_argument("output")
    smoke_feedback.add_argument("--sessions", type=int, default=5)
    smoke_feedback.add_argument("--scale", type=int, default=50)
    smoke_feedback.add_argument("--trials", type=int, default=7)
    smoke_feedback.add_argument("--warmups", type=int, default=3)
    smoke_feedback.add_argument("--startup-trials", type=int, default=5)

    run_algorithm = commands.add_parser(
        "run-algorithm-experiment",
        help="grow the typed algorithm language and validate registered tasks",
    )
    run_algorithm.add_argument("output")

    replay_algorithm = commands.add_parser(
        "replay-algorithm-experiment",
        help="exactly replay an algorithm-language growth bundle",
    )
    replay_algorithm.add_argument("bundle")

    native_algorithm = commands.add_parser(
        "validate-algorithm-native",
        help="compile generated C and run archived algorithm validity cases",
    )
    native_algorithm.add_argument("bundle")
    native_algorithm.add_argument("output")
    native_algorithm.add_argument("--compiler", default="cc")

    smoke_algorithm = commands.add_parser(
        "smoke-algorithm-language",
        help="grow, replay, compile, and validate the A0 algorithm language",
    )
    smoke_algorithm.add_argument("output")
    smoke_algorithm.add_argument("--compiler", default="cc")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "run-algorithm-experiment":
            report = run_algorithm_experiment(args.output)
            print(
                f"complete {report.report_id} tasks={report.task_count} "
                f"cases={report.case_count} cycles={report.cycle_count} "
                f"valid={str(report.all_valid).lower()}"
            )
            return 0
        if args.command == "replay-algorithm-experiment":
            replay = replay_algorithm_experiment(args.bundle)
            print(
                f"replayed {replay.source_report_id} "
                f"files={replay.files_verified} exact=true"
            )
            return 0
        if args.command == "validate-algorithm-native":
            report = validate_algorithm_native(
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
        if args.command == "smoke-algorithm-language":
            report, replay, native = smoke_algorithm_language(
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
        if args.command == "run-hardware-feedback":
            report = run_hardware_feedback_study(
                args.machine_bundle,
                args.comparator_package,
                args.output,
                sessions=args.sessions,
                minimum_improvement_ppm=args.minimum_improvement_ppm,
                required_win_rate_ppm=args.required_win_rate_ppm,
            )
            selected = ",".join(
                f"{pit}:{cycle}"
                for pit, cycle in sorted(report.selected_cycles_by_pit.items())
            )
            print(
                f"complete {report.report_id} target={report.target_id} "
                f"sessions={report.session_count} selected={selected} deployed=false"
            )
            return 0
        if args.command == "replay-hardware-feedback":
            replay = replay_hardware_feedback_study(
                args.machine_bundle,
                args.comparator_package,
                args.study,
            )
            print(
                f"replayed {replay.source_report_id} "
                f"sessions={replay.session_reports_verified} "
                f"files={replay.files_verified} decision_exact=true timings_rerun=false"
            )
            return 0
        if args.command == "smoke-hardware-feedback":
            report, replay = smoke_hardware_feedback(
                args.output,
                sessions=args.sessions,
                scale=args.scale,
                trials=args.trials,
                warmups=args.warmups,
                startup_trials=args.startup_trials,
            )
            selected = ",".join(
                f"{pit}:{cycle}"
                for pit, cycle in sorted(report.selected_cycles_by_pit.items())
            )
            print(
                f"complete {report.report_id} target={report.target_id} "
                f"sessions={report.session_count} selected={selected} "
                f"files={replay.files_verified} decision_exact=true deployed=false"
            )
            return 0
        if args.command == "prepare-language-benchmark":
            report = prepare_comparator_package(
                args.machine_bundle,
                args.output,
                scale=args.scale,
                trials=args.trials,
                warmups=args.warmups,
                startup_trials=args.startup_trials,
            )
            print(
                f"complete {report.package_id} "
                f"files={report.files_written} deterministic=true"
            )
            return 0
        if args.command == "replay-language-benchmark":
            replay = replay_comparator_package(args.machine_bundle, args.package)
            print(
                f"replayed {replay.package_id} "
                f"files={replay.files_verified} exact=true"
            )
            return 0
        if args.command == "run-language-benchmark":
            report = run_comparator_benchmark(
                args.machine_bundle,
                args.package,
                args.output,
            )
            print(
                f"measured {report.report_id} "
                f"adapters={len(report.completed_adapters)} "
                f"skipped={len(report.skipped_adapters)} "
                f"correct={str(report.correctness_passed).lower()}"
            )
            return 0
        if args.command == "smoke-language-comparators":
            root = Path(args.output)
            if root.exists():
                raise MachineExperimentError(f"output directory already exists: {root}")
            machine = root / "machine"
            package = root / "benchmark-package"
            host = root / "host-results"
            machine_report = run_machine_experiment(machine)
            package_report = prepare_comparator_package(
                machine,
                package,
                scale=args.scale,
                trials=args.trials,
                warmups=args.warmups,
                startup_trials=args.startup_trials,
            )
            replay = replay_comparator_package(machine, package)
            host_report = run_comparator_benchmark(machine, package, host)
            print(
                f"complete machine={machine_report.report_id} "
                f"package={package_report.package_id} "
                f"files={replay.files_verified} exact=true "
                f"host={host_report.report_id} "
                f"adapters={len(host_report.completed_adapters)} "
                f"correct={str(host_report.correctness_passed).lower()}"
            )
            return 0
        if args.command == "run-machine-experiment":
            report = run_machine_experiment(args.output)
            print(
                f"complete {report.report_id} "
                f"selected={report.selected_variant} "
                f"hypothesis_passed={str(report.central_hypothesis_passed).lower()}"
            )
            return 0
        if args.command == "replay-machine-experiment":
            replay = replay_machine_experiment(args.bundle)
            print(
                f"replayed {replay.source_report_id} "
                f"files={replay.files_verified} exact=true"
            )
            return 0
        if args.command == "measure-machine-hardware":
            report = measure_machine_hardware(
                args.bundle,
                args.output,
                compiler=args.compiler,
                trials=args.trials,
                scale=args.scale,
            )
            print(
                f"measured {report.report_id} "
                f"primitive_median_ns={report.primitive_median_ns} "
                f"learned_median_ns={report.learned_median_ns} "
                f"model_direction_agrees={str(report.model_direction_agrees).lower()}"
            )
            return 0
        if args.command == "smoke-machine-language":
            root = Path(args.output)
            if root.exists():
                raise MachineExperimentError(f"output directory already exists: {root}")
            report = run_machine_experiment(root / "deterministic")
            replay = replay_machine_experiment(root / "deterministic")
            hardware = measure_machine_hardware(
                root / "deterministic",
                root / "hardware",
                compiler=args.compiler,
                trials=args.trials,
                scale=args.scale,
            )
            print(
                f"complete {report.report_id} "
                f"selected={report.selected_variant} "
                f"files={replay.files_verified} exact=true "
                f"hardware={hardware.report_id} "
                f"model_direction_agrees={str(hardware.model_direction_agrees).lower()}"
            )
            return 0
        if args.command == "generate-trace":
            trace = generate_trace(
                args.scenario,
                args.seed,
                event_count=args.events,
                capacity=args.capacity,
                name=args.name,
            )
            sys.stdout.buffer.write(trace.canonical_bytes + b"\n")
            return 0
        if args.command == "run-shadow":
            report = run_shadow(
                args.source_run,
                args.trace,
                args.output,
                minimum_events=args.minimum_events,
                checkpoint_interval=args.checkpoint_interval,
                regression_tolerance_ppm=args.regression_tolerance_ppm,
            )
            print(
                f"complete {report.report_id} "
                f"disposition={report.disposition} "
                f"served={report.champion_artifact_id}"
            )
            return 0
        if args.command == "replay-shadow":
            replay = replay_shadow(args.bundle)
            print(
                f"replayed {replay.source_report_id} "
                f"files={replay.files_verified} exact=true"
            )
            return 0
        if args.command == "smoke-alternative":
            trace = generate_trace(
                "recency_shift",
                args.seed,
                event_count=args.events,
                capacity=args.capacity,
                name=f"alternative-recency-shift-{args.seed}",
            )
            with tempfile.TemporaryDirectory(prefix="laicode-d0-source-") as directory:
                source = Path(directory) / "run"
                run_prototype(args.contract, source)
                report = run_shadow(source, trace, args.output)
            replay = replay_shadow(args.output)
            print(
                f"complete {report.report_id} "
                f"disposition={report.disposition} "
                f"served={report.champion_artifact_id} "
                f"files={replay.files_verified} exact=true"
            )
            return 0
        if args.command == "smoke-prototype":
            report = run_prototype(args.contract, args.output)
            replay = replay_prototype(args.output)
            print(
                f"complete {report.report_id} "
                f"selected={report.selected_strategy_id} "
                f"files={replay.files_verified} exact=true"
            )
            return 0
        if args.command == "replay-prototype":
            replay = replay_prototype(args.bundle)
            print(
                f"replayed {replay.source_report_id} "
                f"files={replay.files_verified} exact=true"
            )
            return 0
        if args.command == "run-prototype":
            report = run_prototype(args.contract, args.output)
            print(
                f"complete {report.report_id} "
                f"selected={report.selected_strategy_id} "
                f"artifact={report.selected_artifact_id}"
            )
            return 0

        contract = load_contract(args.contract)
        if args.command == "validate-contract":
            print(f"valid {contract.epoch_id}")
            if args.canonical:
                print(contract.canonical_bytes.decode("utf-8"))
            return 0

        if args.command == "compile-program":
            artifact = compile_complete_program(
                contract,
                Path(args.program).read_bytes(),
            )
        else:
            session = ConstructionSession.open(contract)
            for action_path in args.actions:
                result = session.step(Path(action_path).read_bytes())
                if not result.accepted:
                    print(
                        canonical_json_bytes(result.to_document()).decode("utf-8"),
                        file=sys.stderr,
                    )
                    return 2
            artifact = session.commit()
    except (
        OSError,
        ContractValidationError,
        CacheError,
        CommitError,
        IsolationError,
        KernelError,
        AlgorithmExperimentError,
        AlgorithmLanguageError,
        MachineExperimentError,
        MachineLanguageError,
        PrototypeError,
        ProvenanceError,
        ShadowError,
    ) as error:
        print(f"invalid input: {error}", file=sys.stderr)
        return 2

    print(f"valid {artifact.artifact_id}")
    if args.canonical:
        print(artifact.canonical_bytes.decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
