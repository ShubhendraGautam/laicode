"""Command-line entry point for prototype control-plane utilities."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .canonical import canonical_json_bytes
from .contracts import ContractValidationError, load_contract
from .kernel import (
    CommitError,
    ConstructionSession,
    KernelError,
    compile_complete_program,
)
from .prototype import PrototypeError, replay_prototype, run_prototype
from .provenance import ProvenanceError


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
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
        CommitError,
        KernelError,
        PrototypeError,
        ProvenanceError,
    ) as error:
        print(f"invalid input: {error}", file=sys.stderr)
        return 2

    print(f"valid {artifact.artifact_id}")
    if args.canonical:
        print(artifact.canonical_bytes.decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
