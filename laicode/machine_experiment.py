"""Registered, replayable experiment for hardware-shaped vocabulary evolution."""

from __future__ import annotations

import hashlib
import platform
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .canonical import (
    CanonicalizationError,
    JsonValue,
    canonical_json_bytes,
    content_id,
    load_json_strict,
)
from .machine_language import (
    EMPTY_VOCABULARY,
    COST_MODEL_VERSION,
    LEARNER_VERSION,
    CostVector,
    LearnedSuperinstruction,
    MachineLanguageError,
    MachineVocabulary,
    WeightedProgram,
    WordInstruction,
    WordProgram,
    encode_program,
    evaluate_cost,
    execute_encoded,
    execute_program,
    learn_one_superinstruction,
)


CORPUS_SCHEMA_VERSION = "MachineProgramCorpusV0"
EXPERIMENT_SCHEMA_VERSION = "MachineLanguageExperimentV0"
CYCLE_SCHEMA_VERSION = "MachineLearningCycleV0"
EVALUATION_SCHEMA_VERSION = "MachinePartitionEvaluationV0"
DECISION_SCHEMA_VERSION = "MachineOfflineDecisionV0"
AUDIT_SCHEMA_VERSION = "MachineResearchAuditV0"
RUN_REPORT_SCHEMA_VERSION = "MachineExperimentRunReportV0"
RUN_REPORT_RECORD_SCHEMA_VERSION = "MachineExperimentRunReportRecordV0"
REPLAY_REPORT_SCHEMA_VERSION = "MachineExperimentReplayReportV0"
IMPLEMENTATION_SCHEMA_VERSION = "MachineImplementationManifestV0"

FIXED_GENERATOR_ID = "FixedHumanVocabularyV0"
RANDOM_GENERATOR_ID = "SeededRandomVocabularyV0"
RANDOM_SEED = 20260801
BOUNDARY_INPUTS = (0, 1, 2, (1 << 63) - 1, 1 << 63, (1 << 64) - 1)


class MachineExperimentError(ValueError):
    """Raised when the registered machine-language study cannot be reproduced."""


def _word(value: int) -> str:
    return f"0x{value:016x}"


def _write_document(path: Path, document: JsonValue) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(canonical_json_bytes(document) + b"\n")
        handle.flush()


def _read_document(path: Path) -> JsonValue:
    try:
        return load_json_strict(path.read_bytes())
    except (OSError, CanonicalizationError) as error:
        raise MachineExperimentError(
            f"cannot read canonical document {path}: {error}"
        ) from error


def _ins(op: str, operand: int) -> WordInstruction:
    return WordInstruction(op, operand)


MOTIF_A = (
    _ins("xor_shift_right", 30),
    _ins("multiply_const", 0xBF58476D1CE4E5B9),
    _ins("xor_shift_right", 27),
)
MOTIF_B = (
    _ins("add_const", 0x9E3779B97F4A7C15),
    _ins("rotate_left", 17),
    _ins("xor_const", 0xD6E8FEB86659FD93),
)


@dataclass(frozen=True)
class MachineCorpus:
    name: str
    role: str
    disclosure: str
    programs: tuple[WeightedProgram, ...]

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": CORPUS_SCHEMA_VERSION,
            "name": self.name,
            "role": self.role,
            "disclosure": self.disclosure,
            "programs": [
                {
                    "program_id": item.program.program_id,
                    "executions": item.executions,
                    "program": item.program.to_document(),
                }
                for item in self.programs
            ],
        }

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> "MachineCorpus":
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "name",
            "role",
            "disclosure",
            "programs",
        }:
            raise MachineExperimentError("machine corpus has invalid fields")
        if value["schema_version"] != CORPUS_SCHEMA_VERSION:
            raise MachineExperimentError("machine corpus has an unknown schema")
        name = value["name"]
        role = value["role"]
        disclosure = value["disclosure"]
        programs = value["programs"]
        if (
            not isinstance(name, str)
            or not isinstance(role, str)
            or not isinstance(disclosure, str)
            or not isinstance(programs, list)
        ):
            raise MachineExperimentError("machine corpus payload is invalid")
        weighted: list[WeightedProgram] = []
        for index, item in enumerate(programs):
            if not isinstance(item, dict) or set(item) != {
                "program_id",
                "executions",
                "program",
            }:
                raise MachineExperimentError(
                    f"machine corpus program {index} has invalid fields"
                )
            program_value = item["program"]
            executions = item["executions"]
            program_id = item["program_id"]
            if not isinstance(program_value, dict):
                raise MachineExperimentError("machine corpus program is invalid")
            program = WordProgram.from_document(program_value)
            if program.program_id != program_id:
                raise MachineExperimentError("machine corpus program identity differs")
            weighted.append(WeightedProgram(program, executions))  # type: ignore[arg-type]
        return cls(name, role, disclosure, tuple(weighted))

    @property
    def corpus_id(self) -> str:
        return content_id(self.to_document())


def _program(*instructions: WordInstruction) -> WordProgram:
    return WordProgram(tuple(instructions))


def registered_corpora() -> dict[str, MachineCorpus]:
    """Return the frozen identity-separated E-H0 workloads."""

    prefixes = (
        _ins("add_const", 7),
        _ins("xor_const", 0x94D049BB133111EB),
        _ins("or_const", 1),
    )
    suffixes = (
        _ins("rotate_left", 9),
        _ins("and_const", 0x7FFFFFFFFFFFFFFF),
        _ins("add_const", 11),
    )
    bridges = (
        _ins("xor_const", 0xA24BAED4963EE407),
        _ins("rotate_left", 23),
        _ins("add_const", 0x000000000000001D),
    )
    cycle_1 = MachineCorpus(
        name="training-cycle-1",
        role="learner_search",
        disclosure="prefreeze",
        programs=tuple(
            WeightedProgram(_program(prefix, *MOTIF_A, suffix), executions)
            for prefix, suffix, executions in zip(
                prefixes, suffixes, (160, 140, 120), strict=True
            )
        ),
    )
    cycle_2 = MachineCorpus(
        name="training-cycle-2",
        role="learner_search",
        disclosure="prefreeze",
        programs=tuple(
            WeightedProgram(
                _program(prefix, *MOTIF_A, bridge, *MOTIF_B, *MOTIF_A, suffix),
                executions,
            )
            for prefix, bridge, suffix, executions in zip(
                prefixes, bridges, suffixes, (140, 130, 120), strict=True
            )
        ),
    )
    operational = MachineCorpus(
        name="operational-holdout",
        role="protected_selection",
        disclosure="aggregate_only_until_decision",
        programs=(
            WeightedProgram(
                _program(
                    _ins("rotate_left", 7),
                    *MOTIF_A,
                    _ins("xor_const", 0xDB4F0B9175AE2165),
                    *MOTIF_B,
                    *MOTIF_A,
                    _ins("add_const", 19),
                ),
                260,
            ),
            WeightedProgram(
                _program(
                    _ins("and_const", 0xFFFFFFFFFFFFFFFE),
                    *MOTIF_B,
                    *MOTIF_A,
                    _ins("or_const", 3),
                    *MOTIF_A,
                ),
                240,
            ),
            WeightedProgram(
                _program(
                    _ins("xor_const", 0x8CB92BA72F3D8DD7),
                    *MOTIF_A,
                    *MOTIF_B,
                    *MOTIF_A,
                    _ins("rotate_left", 31),
                ),
                220,
            ),
        ),
    )
    future = MachineCorpus(
        name="future-shift",
        role="post_decision_negative_transfer",
        disclosure="post_decision",
        programs=(
            WeightedProgram(
                _program(
                    _ins("add_const", 3),
                    _ins("rotate_left", 11),
                    _ins("xor_const", 5),
                    _ins("multiply_const", 0x94D049BB133111EB),
                ),
                300,
            ),
            WeightedProgram(
                _program(
                    _ins("or_const", 8),
                    _ins("xor_shift_right", 19),
                    _ins("add_const", 41),
                    _ins("rotate_left", 5),
                ),
                280,
            ),
        ),
    )
    audit = MachineCorpus(
        name="research-audit",
        role="post_freeze_hidden_audit",
        disclosure="commitment_only_until_decision",
        programs=(
            WeightedProgram(
                _program(
                    _ins("add_const", 0x0000000000000065),
                    *MOTIF_B,
                    *MOTIF_A,
                    _ins("rotate_left", 29),
                ),
                250,
            ),
            WeightedProgram(
                _program(
                    _ins("xor_const", 0xCA5A826395121157),
                    *MOTIF_A,
                    _ins("and_const", 0x7FFFFFFFFFFFFFFF),
                    *MOTIF_B,
                    *MOTIF_A,
                    _ins("or_const", 1),
                ),
                230,
            ),
        ),
    )
    return {
        item.name: item
        for item in (cycle_1, cycle_2, operational, future, audit)
    }


def _catalogs(
    corpora: Mapping[str, MachineCorpus],
) -> tuple[dict[str, JsonValue], dict[str, JsonValue]]:
    audit = corpora["research-audit"]
    public = {
        "schema_version": "MachineEvidenceCatalogV0",
        "training_corpus_ids": [
            corpora["training-cycle-1"].corpus_id,
            corpora["training-cycle-2"].corpus_id,
        ],
        "operational_holdout_corpus_id": corpora[
            "operational-holdout"
        ].corpus_id,
        "future_shift_corpus_id": corpora["future-shift"].corpus_id,
        "research_audit_commitment_id": audit.corpus_id,
        "research_audit_payload_disclosed": False,
        "partition_identity_overlap_allowed": False,
    }
    archived = {
        "schema_version": "MachineArchivedEvidenceCatalogV0",
        "prefreeze_catalog_id": content_id(public),
        "corpus_ids_by_name": {
            name: corpus.corpus_id for name, corpus in sorted(corpora.items())
        },
        "research_audit_payload_disclosed_after_decision": True,
    }
    return public, archived


def _implementation_manifest() -> dict[str, JsonValue]:
    root = Path(__file__).resolve().parents[1]
    selected = (
        root / "laicode" / "canonical.py",
        root / "laicode" / "machine_language.py",
        root / "laicode" / "machine_experiment.py",
    )
    return {
        "schema_version": IMPLEMENTATION_SCHEMA_VERSION,
        "runtime": "python",
        "runtime_version": platform.python_version(),
        "dependency_profile": "stdlib_only",
        "files": {
            path.relative_to(root).as_posix(): "sha256:"
            + hashlib.sha256(path.read_bytes()).hexdigest()
            for path in selected
        },
    }


def _experiment_manifest(
    *,
    implementation_id: str,
    catalog_id: str,
) -> dict[str, JsonValue]:
    return {
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "experiment_name": "hardware-shaped-vocabulary-e-h0-v0",
        "study_mode": "exploratory",
        "system_profile": {
            "r": "R4",
            "m": "M3",
            "g": "G2",
            "l": "L2",
            "d": "D0",
            "f": "F3",
        },
        "research_question": (
            "Can execution-weighted evidence grow a transparent typed machine "
            "vocabulary that reduces held-out total cost under a fixed word kernel?"
        ),
        "hypothesis": (
            "Two learned persistent entries beat primitive-only, fixed-human, "
            "and seeded-random vocabularies on protected held-out total units."
        ),
        "falsification_conditions": [
            "learned_not_best_on_operational_total_units",
            "lowering_or_boundary_equivalence_failure",
            "cycle_1_vocabulary_does_not_change_cycle_2_proposal",
            "audit_payload_enters_offline_selection",
            "exact_replay_failure",
        ],
        "implementation_id": implementation_id,
        "evidence_catalog_id": catalog_id,
        "primitive_kernel": "WordPipelineV0",
        "learner": LEARNER_VERSION,
        "cycles": 2,
        "entries_after_cycle_2": 2,
        "registered_lowering_lengths": [3, 6],
        "generation_budget": {
            "passes_per_variant": 2,
            "maximum_entries": 2,
            "maximum_training_corpora_disclosed": 2,
            "padding_rule": "unused_passes_are_charged",
        },
        "baselines": {
            "primitive": "trusted_kernel_without_learned_entries",
            "fixed_human": "preregistered_generic_hash_idioms",
            "seeded_random": "sha256_ranked_training_windows_seed_20260801",
        },
        "cost_policy": {
            "id": COST_MODEL_VERSION,
            "runtime_units": "weighted_alu_units + weighted_dispatch_units",
            "dispatch_units_per_token": 4,
            "definition_units_per_entry": "8 + 2 * lowering_instructions",
            "verification_units": "8 * library_instructions",
            "compilation_units": "4 * library_instructions",
            "storage_units": "ceil((encoded_bytes + library_bytes) / 64)",
            "primary_outcome": "total_units",
            "direction": "minimize",
        },
        "selection_partition": "operational-holdout",
        "future_use": "post_decision_negative_transfer_only",
        "audit_use": "post_decision_report_only",
        "deployment_authority": "D0_offline_only",
        "registered_at": "2026-08-01T00:00:00Z",
    }


def _make_vocabulary(
    lowerings: Iterable[tuple[WordInstruction, ...]],
    *,
    generator_id: str,
    evidence_catalog_id: str,
) -> MachineVocabulary:
    entries = tuple(
        LearnedSuperinstruction(
            lowering=lowering,
            evidence_catalog_id=evidence_catalog_id,
            parent_vocabulary_id=EMPTY_VOCABULARY.vocabulary_id,
            learned_cycle=0,
            weighted_occurrences=0,
            estimated_saving=0,
            generator_id=generator_id,
        )
        for lowering in lowerings
    )
    return MachineVocabulary(
        parent_vocabulary_id=EMPTY_VOCABULARY.vocabulary_id,
        entries=tuple(sorted(entries, key=lambda item: item.entry_id)),
    )


def _fixed_human_vocabulary(evidence_catalog_id: str) -> MachineVocabulary:
    generic_six = (
        _ins("xor_shift_right", 31),
        _ins("multiply_const", 0x9E3779B97F4A7C15),
        _ins("xor_shift_right", 27),
        _ins("multiply_const", 0x94D049BB133111EB),
        _ins("xor_shift_right", 33),
        _ins("add_const", 0xD6E8FEB86659FD93),
    )
    return _make_vocabulary(
        (MOTIF_A, generic_six),
        generator_id=FIXED_GENERATOR_ID,
        evidence_catalog_id=evidence_catalog_id,
    )


def _training_windows(
    corpora: Iterable[MachineCorpus],
    length: int,
) -> tuple[tuple[WordInstruction, ...], ...]:
    windows: set[tuple[WordInstruction, ...]] = set()
    for corpus in corpora:
        for item in corpus.programs:
            instructions = item.program.instructions
            for index in range(len(instructions) - length + 1):
                windows.add(instructions[index : index + length])
    return tuple(windows)


def _seeded_random_vocabulary(
    training: Iterable[MachineCorpus],
    evidence_catalog_id: str,
) -> MachineVocabulary:
    selected: list[tuple[WordInstruction, ...]] = []
    for length in (3, 6):
        candidates = _training_windows(training, length)
        if not candidates:
            raise MachineExperimentError("random baseline has no training windows")
        selected.append(
            min(
                candidates,
                key=lambda lowering: hashlib.sha256(
                    canonical_json_bytes(
                        {
                            "seed": RANDOM_SEED,
                            "length": length,
                            "lowering": [item.to_document() for item in lowering],
                        }
                    )
                ).digest(),
            )
        )
    return _make_vocabulary(
        selected,
        generator_id=RANDOM_GENERATOR_ID,
        evidence_catalog_id=evidence_catalog_id,
    )


def _learned_vocabulary(
    corpora: Mapping[str, MachineCorpus],
    evidence_catalog_id: str,
) -> tuple[MachineVocabulary, tuple[dict[str, JsonValue], ...]]:
    vocabulary = EMPTY_VOCABULARY
    records: list[dict[str, JsonValue]] = []
    for cycle in (1, 2):
        corpus = corpora[f"training-cycle-{cycle}"]
        before = vocabulary
        counterfactual = learn_one_superinstruction(
            corpus.programs,
            EMPTY_VOCABULARY,
            evidence_catalog_id=evidence_catalog_id,
            cycle=cycle,
        )
        vocabulary = learn_one_superinstruction(
            corpus.programs,
            vocabulary,
            evidence_catalog_id=evidence_catalog_id,
            cycle=cycle,
        )
        if len(vocabulary.entries) != cycle:
            raise MachineExperimentError(f"cycle {cycle} did not add one vocabulary entry")
        before_ids = set(before.by_id())
        new_entries = [entry for entry in vocabulary.entries if entry.entry_id not in before_ids]
        if len(new_entries) != 1:
            raise MachineExperimentError(f"cycle {cycle} lineage is ambiguous")
        selected = new_entries[0]
        counterfactual_new = [
            entry
            for entry in counterfactual.entries
            if entry.entry_id not in EMPTY_VOCABULARY.by_id()
        ][0]
        before_token_count = sum(
            len(encode_program(item.program, before).tokens)
            for item in corpus.programs
        )
        after_token_count = sum(
            len(encode_program(item.program, vocabulary).tokens)
            for item in corpus.programs
        )
        records.append(
            {
                "schema_version": CYCLE_SCHEMA_VERSION,
                "cycle": cycle,
                "training_corpus_id": corpus.corpus_id,
                "input_vocabulary_id": before.vocabulary_id,
                "output_vocabulary_id": vocabulary.vocabulary_id,
                "selected_entry_id": selected.entry_id,
                "selected_lowering": [item.to_document() for item in selected.lowering],
                "input_encoded_tokens": before_token_count,
                "output_encoded_tokens": after_token_count,
                "counterfactual_empty_vocabulary_lowering": [
                    item.to_document() for item in counterfactual_new.lowering
                ],
                "persistent_vocabulary_changed_proposal": (
                    selected.lowering != counterfactual_new.lowering
                    if cycle > 1
                    else False
                ),
            }
        )
    if [len(entry.lowering) for entry in sorted(
        vocabulary.entries, key=lambda item: item.learned_cycle
    )] != [3, 6]:
        raise MachineExperimentError("learner violated the registered [3, 6] shape")
    if not records[1]["persistent_vocabulary_changed_proposal"]:
        raise MachineExperimentError("persisted cycle-1 vocabulary had no cycle-2 effect")
    return vocabulary, tuple(records)


def _evaluate(
    variant: str,
    vocabulary: MachineVocabulary,
    corpus: MachineCorpus,
) -> dict[str, JsonValue]:
    vectors: list[JsonValue] = []
    encoded_ids: list[str] = []
    for weighted in corpus.programs:
        encoded = encode_program(weighted.program, vocabulary)
        encoded_ids.append(encoded.encoded_id)
        for input_value in BOUNDARY_INPUTS:
            expected = execute_program(weighted.program, input_value)
            actual = execute_encoded(encoded, vocabulary, input_value)
            if expected != actual:
                raise MachineExperimentError("encoded execution failed exact equivalence")
            vectors.append(
                {
                    "program_id": weighted.program.program_id,
                    "input": _word(input_value),
                    "output": _word(actual),
                }
            )
    cost = evaluate_cost(corpus.programs, vocabulary)
    payload: dict[str, JsonValue] = {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "variant": variant,
        "vocabulary_id": vocabulary.vocabulary_id,
        "partition": corpus.name,
        "corpus_id": corpus.corpus_id,
        "program_ids": [item.program.program_id for item in corpus.programs],
        "encoded_program_ids": encoded_ids,
        "boundary_vector_digest": content_id({"vectors": vectors}),
        "boundary_vectors_checked": len(vectors),
        "exact_lowering_verified": True,
        "cost": cost.to_document(),
    }
    payload["evaluation_id"] = content_id(payload)
    return payload


def _evaluation_cost(evaluation: Mapping[str, JsonValue]) -> int:
    cost = evaluation["cost"]
    assert isinstance(cost, dict)
    value = cost["total_units"]
    assert isinstance(value, int)
    return value


@dataclass(frozen=True)
class MachineExperimentReport:
    report_id: str
    selected_variant: str
    learned_vocabulary_id: str
    operational_total_units: Mapping[str, int]
    audit_total_units: Mapping[str, int]
    future_total_units: Mapping[str, int]
    exact_replay_supported: bool
    central_hypothesis_passed: bool


def _report_from_record(value: JsonValue) -> MachineExperimentReport:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "report_id",
        "report",
    }:
        raise MachineExperimentError("run report record has invalid fields")
    if value["schema_version"] != RUN_REPORT_RECORD_SCHEMA_VERSION:
        raise MachineExperimentError("run report record has an unknown schema")
    report = value["report"]
    report_id = value["report_id"]
    if not isinstance(report, dict) or not isinstance(report_id, str):
        raise MachineExperimentError("run report payload is invalid")
    if content_id(report) != report_id:
        raise MachineExperimentError("run report identity mismatch")
    operational = report["operational_total_units"]
    audit = report["audit_total_units"]
    future = report["future_total_units"]
    if not all(isinstance(item, dict) for item in (operational, audit, future)):
        raise MachineExperimentError("run report costs are invalid")
    return MachineExperimentReport(
        report_id=report_id,
        selected_variant=str(report["selected_variant"]),
        learned_vocabulary_id=str(report["learned_vocabulary_id"]),
        operational_total_units={str(k): int(v) for k, v in operational.items()},
        audit_total_units={str(k): int(v) for k, v in audit.items()},
        future_total_units={str(k): int(v) for k, v in future.items()},
        exact_replay_supported=bool(report["exact_replay_supported"]),
        central_hypothesis_passed=bool(report["central_hypothesis_passed"]),
    )


def run_machine_experiment(
    output_directory: str | Path,
) -> MachineExperimentReport:
    output = Path(output_directory)
    if output.exists():
        raise MachineExperimentError(f"output directory already exists: {output}")
    output.mkdir(parents=True, exist_ok=False)

    corpora = registered_corpora()
    program_ids = [
        item.program.program_id
        for corpus in corpora.values()
        for item in corpus.programs
    ]
    if len(program_ids) != len(set(program_ids)):
        raise MachineExperimentError("corpus partitions share a program identity")
    public_catalog, archived_catalog = _catalogs(corpora)
    catalog_id = content_id(public_catalog)
    implementation = _implementation_manifest()
    implementation_id = content_id(implementation)
    experiment = _experiment_manifest(
        implementation_id=implementation_id,
        catalog_id=catalog_id,
    )
    experiment_id = content_id(experiment)

    learned, cycle_records = _learned_vocabulary(corpora, catalog_id)
    fixed = _fixed_human_vocabulary(catalog_id)
    random = _seeded_random_vocabulary(
        (corpora["training-cycle-1"], corpora["training-cycle-2"]),
        catalog_id,
    )
    variants = {
        "fixed_human": fixed,
        "learned": learned,
        "primitive": EMPTY_VOCABULARY,
        "seeded_random": random,
    }
    if len(fixed.entries) != len(random.entries) or len(fixed.entries) != len(learned.entries):
        raise MachineExperimentError("non-primitive baseline sizes are not matched")
    learned_lengths = sorted(len(item.lowering) for item in learned.entries)
    if any(
        sorted(len(item.lowering) for item in vocabulary.entries) != learned_lengths
        for vocabulary in (fixed, random)
    ):
        raise MachineExperimentError("non-primitive lowering lengths are not matched")

    evaluations: dict[tuple[str, str], dict[str, JsonValue]] = {}
    for variant, vocabulary in variants.items():
        for corpus_name in (
            "training-cycle-1",
            "training-cycle-2",
            "operational-holdout",
            "future-shift",
        ):
            evaluations[(variant, corpus_name)] = _evaluate(
                variant, vocabulary, corpora[corpus_name]
            )

    operational = {
        variant: _evaluation_cost(evaluations[(variant, "operational-holdout")])
        for variant in variants
    }
    selected_variant = min(operational, key=lambda name: (operational[name], name))
    decision: dict[str, JsonValue] = {
        "schema_version": DECISION_SCHEMA_VERSION,
        "experiment_manifest_id": experiment_id,
        "selection_partition": "operational-holdout",
        "evaluation_ids_by_variant": {
            variant: evaluations[(variant, "operational-holdout")]["evaluation_id"]
            for variant in sorted(variants)
        },
        "total_units_by_variant": dict(sorted(operational.items())),
        "selected_variant": selected_variant,
        "selected_vocabulary_id": variants[selected_variant].vocabulary_id,
        "selection_rule": "minimum_total_units_then_variant_id",
        "generation_passes_charged_by_variant": {
            variant: 2 for variant in sorted(variants)
        },
        "research_audit_evaluation_ids": [],
        "research_audit_payload_used": False,
        "deployment_authority": "D0_offline_only",
    }
    decision_id = content_id(decision)

    for variant, vocabulary in variants.items():
        evaluations[(variant, "research-audit")] = _evaluate(
            variant, vocabulary, corpora["research-audit"]
        )
    audit_costs = {
        variant: _evaluation_cost(evaluations[(variant, "research-audit")])
        for variant in variants
    }
    future_costs = {
        variant: _evaluation_cost(evaluations[(variant, "future-shift")])
        for variant in variants
    }
    audit_report: dict[str, JsonValue] = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "offline_decision_id": decision_id,
        "audit_corpus_id": corpora["research-audit"].corpus_id,
        "evaluation_ids_by_variant": {
            variant: evaluations[(variant, "research-audit")]["evaluation_id"]
            for variant in sorted(variants)
        },
        "total_units_by_variant": dict(sorted(audit_costs.items())),
        "audit_winner": min(audit_costs, key=lambda name: (audit_costs[name], name)),
        "audit_used_for_selection": False,
    }
    future_negative_transfer_retained = (
        future_costs["learned"] > future_costs["primitive"]
    )
    central_hypothesis_passed = (
        selected_variant == "learned"
        and min(audit_costs, key=lambda name: (audit_costs[name], name)) == "learned"
        and bool(cycle_records[1]["persistent_vocabulary_changed_proposal"])
    )

    _write_document(output / "implementation-manifest.json", implementation)
    _write_document(output / "experiment-manifest.json", experiment)
    _write_document(output / "evidence-catalog.json", public_catalog)
    _write_document(output / "archived-evidence-catalog.json", archived_catalog)
    for corpus in corpora.values():
        _write_document(output / "corpora" / f"{corpus.name}.json", corpus.to_document())
    for variant, vocabulary in variants.items():
        _write_document(output / "vocabularies" / f"{variant}.json", vocabulary.to_document())
    for index, record in enumerate(cycle_records, start=1):
        _write_document(output / "cycles" / f"cycle-{index}.json", record)
    for (variant, partition), evaluation in evaluations.items():
        _write_document(
            output / "evaluations" / f"{partition}--{variant}.json",
            evaluation,
        )
    _write_document(output / "offline-decision.json", decision)
    _write_document(output / "audit-report.json", audit_report)

    report: dict[str, JsonValue] = {
        "schema_version": RUN_REPORT_SCHEMA_VERSION,
        "status": "complete",
        "claim_level": "exploratory_transparent_vocabulary_evolution_only",
        "implementation_id": implementation_id,
        "experiment_manifest_id": experiment_id,
        "evidence_catalog_id": catalog_id,
        "archived_evidence_catalog_id": content_id(archived_catalog),
        "offline_decision_id": decision_id,
        "audit_report_id": content_id(audit_report),
        "selected_variant": selected_variant,
        "learned_vocabulary_id": learned.vocabulary_id,
        "vocabulary_ids_by_variant": {
            name: vocabulary.vocabulary_id for name, vocabulary in sorted(variants.items())
        },
        "operational_total_units": dict(sorted(operational.items())),
        "audit_total_units": dict(sorted(audit_costs.items())),
        "future_total_units": dict(sorted(future_costs.items())),
        "central_hypothesis_passed": central_hypothesis_passed,
        "persistent_vocabulary_changed_next_proposal": bool(
            cycle_records[1]["persistent_vocabulary_changed_proposal"]
        ),
        "matched_nonprimitive_entry_count": len(learned.entries),
        "matched_nonprimitive_lowering_lengths": learned_lengths,
        "future_negative_transfer_retained": future_negative_transfer_retained,
        "research_audit_used_for_selection": False,
        "deployment_performed": False,
        "exact_replay_supported": True,
        "host_hardware_measurement_included": False,
        "limitations": [
            "synthetic_word_pipelines",
            "fixed_primitive_semantics",
            "single_deterministic_virtual_cost_model",
            "host_measurement_is_separate_noisy_evidence",
            "no_hardware_generality_claim",
            "no_online_or_autonomous_deployment",
        ],
    }
    report_id = content_id(report)
    _write_document(
        output / "run-report.json",
        {
            "schema_version": RUN_REPORT_RECORD_SCHEMA_VERSION,
            "report_id": report_id,
            "report": report,
        },
    )
    return _report_from_record(_read_document(output / "run-report.json"))


@dataclass(frozen=True)
class MachineReplayReport:
    source_report_id: str
    replay_report_id: str
    files_verified: int

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": REPLAY_REPORT_SCHEMA_VERSION,
            "source_report_id": self.source_report_id,
            "replay_report_id": self.replay_report_id,
            "files_verified": self.files_verified,
            "exact_match": True,
        }


def replay_machine_experiment(
    bundle_directory: str | Path,
) -> MachineReplayReport:
    source = Path(bundle_directory)
    if not source.is_dir():
        raise MachineExperimentError(f"run bundle does not exist: {source}")
    source_report = _report_from_record(_read_document(source / "run-report.json"))
    with tempfile.TemporaryDirectory(prefix="laicode-machine-replay-") as directory:
        replay = Path(directory) / "bundle"
        replay_report = run_machine_experiment(replay)
        source_files = sorted(
            path.relative_to(source) for path in source.rglob("*") if path.is_file()
        )
        replay_files = sorted(
            path.relative_to(replay) for path in replay.rglob("*") if path.is_file()
        )
        if source_files != replay_files:
            raise MachineExperimentError(
                "bundle inventory does not match deterministic replay"
            )
        for relative in source_files:
            if (source / relative).read_bytes() != (replay / relative).read_bytes():
                raise MachineExperimentError(
                    f"replay mismatch in {relative.as_posix()}"
                )
        return MachineReplayReport(
            source_report_id=source_report.report_id,
            replay_report_id=replay_report.report_id,
            files_verified=len(source_files),
        )
