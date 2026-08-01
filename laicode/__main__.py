"""Command-line entry point for prototype control-plane utilities."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
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
