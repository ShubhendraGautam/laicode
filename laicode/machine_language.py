"""Transparent hardware-shaped vocabulary evolution over a fixed word kernel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .canonical import JsonValue, canonical_json_bytes, content_id


WORD_MASK = (1 << 64) - 1
PIPELINE_SCHEMA_VERSION = "WordPipelineV0"
SUPERINSTRUCTION_SCHEMA_VERSION = "LearnedSuperinstructionV0"
VOCABULARY_SCHEMA_VERSION = "MachineVocabularyV0"
ENCODED_PROGRAM_SCHEMA_VERSION = "EncodedWordPipelineV0"
COST_MODEL_VERSION = "WordDispatchCostModelV0"
LEARNER_VERSION = "ExecutionWeightedNgramLearnerV0"
MAX_PROGRAM_INSTRUCTIONS = 256
MAX_SUPERINSTRUCTION_LENGTH = 8
MAX_VOCABULARY_ENTRIES = 32

_CONST_OPS = {"xor_const", "add_const", "multiply_const", "and_const", "or_const"}
_SHIFT_OPS = {"xor_shift_right", "rotate_left"}
_OPS = _CONST_OPS | _SHIFT_OPS
_ALU_COST = {
    "xor_const": 1,
    "add_const": 1,
    "multiply_const": 3,
    "and_const": 1,
    "or_const": 1,
    "xor_shift_right": 2,
    "rotate_left": 1,
}


class MachineLanguageError(ValueError):
    """Raised when a program or learned vocabulary violates the fixed kernel."""


def _hex_word(value: int) -> str:
    if not 0 <= value <= WORD_MASK:
        raise MachineLanguageError("word constant must be an unsigned 64-bit value")
    return f"0x{value:016x}"


def _decode_hex_word(value: str) -> int:
    if (
        not isinstance(value, str)
        or len(value) != 18
        or not value.startswith("0x")
        or any(character not in "0123456789abcdef" for character in value[2:])
    ):
        raise MachineLanguageError("word constant must be canonical 0x + 16 hex digits")
    return int(value[2:], 16)


@dataclass(frozen=True, order=True)
class WordInstruction:
    op: str
    operand: int

    def __post_init__(self) -> None:
        if self.op not in _OPS:
            raise MachineLanguageError(f"unknown word operation {self.op!r}")
        if isinstance(self.operand, bool) or not isinstance(self.operand, int):
            raise MachineLanguageError("instruction operand must be an integer")
        if self.op in _CONST_OPS and not 0 <= self.operand <= WORD_MASK:
            raise MachineLanguageError("constant operand is outside u64")
        if self.op in _SHIFT_OPS and not 1 <= self.operand <= 63:
            raise MachineLanguageError("shift operand must be between 1 and 63")

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "op": self.op,
            "operand": (
                _hex_word(self.operand)
                if self.op in _CONST_OPS
                else self.operand
            ),
        }

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> "WordInstruction":
        if not isinstance(value, dict) or set(value) != {"op", "operand"}:
            raise MachineLanguageError("instruction has invalid fields")
        op = value["op"]
        if not isinstance(op, str):
            raise MachineLanguageError("instruction op must be a string")
        operand_value = value["operand"]
        if op in _CONST_OPS:
            if not isinstance(operand_value, str):
                raise MachineLanguageError("constant operand must be hexadecimal")
            operand = _decode_hex_word(operand_value)
        else:
            if isinstance(operand_value, bool) or not isinstance(operand_value, int):
                raise MachineLanguageError("shift operand must be an integer")
            operand = operand_value
        return cls(op, operand)


@dataclass(frozen=True)
class WordProgram:
    instructions: tuple[WordInstruction, ...]

    def __post_init__(self) -> None:
        if not self.instructions:
            raise MachineLanguageError("word program cannot be empty")
        if len(self.instructions) > MAX_PROGRAM_INSTRUCTIONS:
            raise MachineLanguageError("word program exceeds the instruction limit")

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": PIPELINE_SCHEMA_VERSION,
            "input_type": "u64",
            "output_type": "u64",
            "effects": [],
            "instructions": [item.to_document() for item in self.instructions],
        }

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> "WordProgram":
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "input_type",
            "output_type",
            "effects",
            "instructions",
        }:
            raise MachineLanguageError("word program has invalid fields")
        if (
            value["schema_version"] != PIPELINE_SCHEMA_VERSION
            or value["input_type"] != "u64"
            or value["output_type"] != "u64"
            or value["effects"] != []
        ):
            raise MachineLanguageError("word program has an incompatible type or schema")
        instructions = value["instructions"]
        if not isinstance(instructions, list) or not all(
            isinstance(item, dict) for item in instructions
        ):
            raise MachineLanguageError("word program instructions must be objects")
        return cls(tuple(WordInstruction.from_document(item) for item in instructions))

    @property
    def program_id(self) -> str:
        return content_id(self.to_document())


def execute_instruction(value: int, instruction: WordInstruction) -> int:
    if not 0 <= value <= WORD_MASK:
        raise MachineLanguageError("program input must be an unsigned 64-bit value")
    operand = instruction.operand
    if instruction.op == "xor_const":
        return value ^ operand
    if instruction.op == "add_const":
        return (value + operand) & WORD_MASK
    if instruction.op == "multiply_const":
        return (value * operand) & WORD_MASK
    if instruction.op == "and_const":
        return value & operand
    if instruction.op == "or_const":
        return value | operand
    if instruction.op == "xor_shift_right":
        return value ^ (value >> operand)
    if instruction.op == "rotate_left":
        return ((value << operand) | (value >> (64 - operand))) & WORD_MASK
    raise AssertionError("validated instruction is not implemented")


def execute_program(program: WordProgram, value: int) -> int:
    current = value
    for instruction in program.instructions:
        current = execute_instruction(current, instruction)
    return current


@dataclass(frozen=True)
class LearnedSuperinstruction:
    lowering: tuple[WordInstruction, ...]
    evidence_catalog_id: str
    parent_vocabulary_id: str
    learned_cycle: int
    weighted_occurrences: int
    estimated_saving: int
    generator_id: str = LEARNER_VERSION

    def __post_init__(self) -> None:
        if not 2 <= len(self.lowering) <= MAX_SUPERINSTRUCTION_LENGTH:
            raise MachineLanguageError("superinstruction length is outside the limit")
        for identifier in (self.evidence_catalog_id, self.parent_vocabulary_id):
            if not identifier.startswith("sha256:") or len(identifier) != 71:
                raise MachineLanguageError("superinstruction provenance ID is invalid")
        for value in (
            self.learned_cycle,
            self.weighted_occurrences,
            self.estimated_saving,
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise MachineLanguageError("superinstruction evidence values are invalid")
        if not self.generator_id or not self.generator_id.isascii():
            raise MachineLanguageError("superinstruction generator ID is invalid")

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": SUPERINSTRUCTION_SCHEMA_VERSION,
            "type": {"input": "u64", "output": "u64", "effects": []},
            "lowering": [item.to_document() for item in self.lowering],
            "learner": {"id": self.generator_id, "cycle": self.learned_cycle},
            "provenance": {
                "evidence_catalog_id": self.evidence_catalog_id,
                "parent_vocabulary_id": self.parent_vocabulary_id,
            },
            "evidence": {
                "weighted_occurrences": self.weighted_occurrences,
                "estimated_saving": self.estimated_saving,
            },
        }

    @classmethod
    def from_document(
        cls,
        value: Mapping[str, object],
    ) -> "LearnedSuperinstruction":
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "type",
            "lowering",
            "learner",
            "provenance",
            "evidence",
        }:
            raise MachineLanguageError("superinstruction has invalid fields")
        if value["schema_version"] != SUPERINSTRUCTION_SCHEMA_VERSION:
            raise MachineLanguageError("superinstruction has an unknown schema")
        type_value = value["type"]
        learner = value["learner"]
        provenance = value["provenance"]
        evidence = value["evidence"]
        lowering = value["lowering"]
        if type_value != {"input": "u64", "output": "u64", "effects": []}:
            raise MachineLanguageError("superinstruction has an incompatible type")
        if (
            not isinstance(learner, dict)
            or not isinstance(provenance, dict)
            or not isinstance(evidence, dict)
            or not isinstance(lowering, list)
            or not all(isinstance(item, dict) for item in lowering)
            or set(learner) != {"id", "cycle"}
            or set(provenance)
            != {"evidence_catalog_id", "parent_vocabulary_id"}
            or set(evidence) != {"weighted_occurrences", "estimated_saving"}
        ):
            raise MachineLanguageError("superinstruction payload is invalid")
        generator_id = learner["id"]
        evidence_catalog_id = provenance["evidence_catalog_id"]
        parent_vocabulary_id = provenance["parent_vocabulary_id"]
        if not all(
            isinstance(item, str)
            for item in (generator_id, evidence_catalog_id, parent_vocabulary_id)
        ):
            raise MachineLanguageError("superinstruction provenance is invalid")
        return cls(
            lowering=tuple(WordInstruction.from_document(item) for item in lowering),
            evidence_catalog_id=evidence_catalog_id,
            parent_vocabulary_id=parent_vocabulary_id,
            learned_cycle=learner["cycle"],  # type: ignore[arg-type]
            weighted_occurrences=evidence["weighted_occurrences"],  # type: ignore[arg-type]
            estimated_saving=evidence["estimated_saving"],  # type: ignore[arg-type]
            generator_id=generator_id,
        )

    @property
    def entry_id(self) -> str:
        return content_id(self.to_document())


@dataclass(frozen=True)
class MachineVocabulary:
    parent_vocabulary_id: str | None
    entries: tuple[LearnedSuperinstruction, ...]

    def __post_init__(self) -> None:
        if len(self.entries) > MAX_VOCABULARY_ENTRIES:
            raise MachineLanguageError("vocabulary exceeds the entry limit")
        ids = [entry.entry_id for entry in self.entries]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise MachineLanguageError("vocabulary entries must be unique and ID-sorted")
        if self.parent_vocabulary_id is not None and (
            not self.parent_vocabulary_id.startswith("sha256:")
            or len(self.parent_vocabulary_id) != 71
        ):
            raise MachineLanguageError("parent vocabulary ID is invalid")

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": VOCABULARY_SCHEMA_VERSION,
            "parent_vocabulary_id": self.parent_vocabulary_id,
            "entry_ids": [entry.entry_id for entry in self.entries],
            "entries": [entry.to_document() for entry in self.entries],
        }

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> "MachineVocabulary":
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "parent_vocabulary_id",
            "entry_ids",
            "entries",
        }:
            raise MachineLanguageError("vocabulary has invalid fields")
        if value["schema_version"] != VOCABULARY_SCHEMA_VERSION:
            raise MachineLanguageError("vocabulary has an unknown schema")
        parent = value["parent_vocabulary_id"]
        entry_ids = value["entry_ids"]
        entries = value["entries"]
        if parent is not None and not isinstance(parent, str):
            raise MachineLanguageError("vocabulary parent ID is invalid")
        if (
            not isinstance(entry_ids, list)
            or not isinstance(entries, list)
            or not all(isinstance(item, dict) for item in entries)
        ):
            raise MachineLanguageError("vocabulary entries must be arrays")
        parsed = tuple(LearnedSuperinstruction.from_document(item) for item in entries)
        vocabulary = cls(parent_vocabulary_id=parent, entries=parsed)
        if entry_ids != [entry.entry_id for entry in parsed]:
            raise MachineLanguageError("vocabulary entry identities do not match")
        return vocabulary

    @property
    def vocabulary_id(self) -> str:
        return content_id(self.to_document())

    def by_id(self) -> dict[str, LearnedSuperinstruction]:
        return {entry.entry_id: entry for entry in self.entries}


EMPTY_VOCABULARY = MachineVocabulary(parent_vocabulary_id=None, entries=())


@dataclass(frozen=True)
class EncodedToken:
    primitive: WordInstruction | None = None
    entry_id: str | None = None

    def __post_init__(self) -> None:
        if (self.primitive is None) == (self.entry_id is None):
            raise MachineLanguageError("encoded token must select one representation")

    def to_document(self) -> dict[str, JsonValue]:
        if self.primitive is not None:
            return {"kind": "primitive", "instruction": self.primitive.to_document()}
        assert self.entry_id is not None
        return {"kind": "superinstruction", "entry_id": self.entry_id}


@dataclass(frozen=True)
class EncodedProgram:
    source_program_id: str
    vocabulary_id: str
    tokens: tuple[EncodedToken, ...]

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": ENCODED_PROGRAM_SCHEMA_VERSION,
            "source_program_id": self.source_program_id,
            "vocabulary_id": self.vocabulary_id,
            "tokens": [token.to_document() for token in self.tokens],
        }

    @property
    def encoded_id(self) -> str:
        return content_id(self.to_document())


def expand_encoded(
    encoded: EncodedProgram,
    vocabulary: MachineVocabulary,
) -> tuple[WordInstruction, ...]:
    if encoded.vocabulary_id != vocabulary.vocabulary_id:
        raise MachineLanguageError("encoded program uses a different vocabulary")
    by_id = vocabulary.by_id()
    expanded: list[WordInstruction] = []
    for token in encoded.tokens:
        if token.primitive is not None:
            expanded.append(token.primitive)
        else:
            assert token.entry_id is not None
            entry = by_id.get(token.entry_id)
            if entry is None:
                raise MachineLanguageError("encoded program references an unknown entry")
            expanded.extend(entry.lowering)
    return tuple(expanded)


def execute_encoded(
    encoded: EncodedProgram,
    vocabulary: MachineVocabulary,
    value: int,
) -> int:
    current = value
    by_id = vocabulary.by_id()
    for token in encoded.tokens:
        if token.primitive is not None:
            current = execute_instruction(current, token.primitive)
            continue
        assert token.entry_id is not None
        entry = by_id.get(token.entry_id)
        if entry is None:
            raise MachineLanguageError("encoded program references an unknown entry")
        for instruction in entry.lowering:
            current = execute_instruction(current, instruction)
    return current


def encode_program(
    program: WordProgram,
    vocabulary: MachineVocabulary,
) -> EncodedProgram:
    by_lowering = {
        entry.lowering: entry for entry in vocabulary.entries
    }
    instructions = program.instructions
    best: list[tuple[EncodedToken, ...] | None] = [None] * (len(instructions) + 1)
    best[len(instructions)] = ()
    ordered_lowerings = sorted(
        by_lowering,
        key=lambda item: (-len(item), by_lowering[item].entry_id),
    )
    for index in range(len(instructions) - 1, -1, -1):
        assert best[index + 1] is not None
        choices = [
            (EncodedToken(primitive=instructions[index]),) + best[index + 1]
        ]
        for lowering in ordered_lowerings:
            end = index + len(lowering)
            if end <= len(instructions) and instructions[index:end] == lowering:
                assert best[end] is not None
                choices.append(
                    (EncodedToken(entry_id=by_lowering[lowering].entry_id),)
                    + best[end]
                )
        best[index] = min(
            choices,
            key=lambda tokens: (
                len(tokens),
                canonical_json_bytes([token.to_document() for token in tokens]),
            ),
        )
    assert best[0] is not None
    encoded = EncodedProgram(
        source_program_id=program.program_id,
        vocabulary_id=vocabulary.vocabulary_id,
        tokens=best[0],
    )
    if expand_encoded(encoded, vocabulary) != program.instructions:
        raise MachineLanguageError("vocabulary encoding failed exact lowering")
    return encoded


@dataclass(frozen=True)
class WeightedProgram:
    program: WordProgram
    executions: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.executions, bool)
            or not isinstance(self.executions, int)
            or self.executions < 1
        ):
            raise MachineLanguageError("program execution weight must be positive")


@dataclass(frozen=True)
class CostVector:
    alu_units: int
    dispatch_units: int
    encoded_bytes: int
    library_bytes: int
    definition_units: int
    verification_units: int
    compilation_units: int
    storage_units: int

    @property
    def runtime_units(self) -> int:
        return self.alu_units + self.dispatch_units

    @property
    def one_time_units(self) -> int:
        return (
            self.definition_units
            + self.verification_units
            + self.compilation_units
            + self.storage_units
        )

    @property
    def total_units(self) -> int:
        return self.runtime_units + self.one_time_units

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "cost_model": COST_MODEL_VERSION,
            "alu_units": self.alu_units,
            "dispatch_units": self.dispatch_units,
            "runtime_units": self.runtime_units,
            "definition_units": self.definition_units,
            "verification_units": self.verification_units,
            "compilation_units": self.compilation_units,
            "storage_units": self.storage_units,
            "one_time_units": self.one_time_units,
            "total_units": self.total_units,
            "encoded_bytes": self.encoded_bytes,
            "library_bytes": self.library_bytes,
        }


def evaluate_cost(
    programs: Iterable[WeightedProgram],
    vocabulary: MachineVocabulary,
    *,
    dispatch_cost: int = 4,
) -> CostVector:
    alu = 0
    dispatch = 0
    encoded_bytes = 0
    for item in programs:
        encoded = encode_program(item.program, vocabulary)
        alu += (
            sum(_ALU_COST[instruction.op] for instruction in item.program.instructions)
            * item.executions
        )
        dispatch += len(encoded.tokens) * dispatch_cost * item.executions
        encoded_bytes += len(canonical_json_bytes(encoded.to_document()))
    library_instruction_count = sum(
        len(entry.lowering) for entry in vocabulary.entries
    )
    library_bytes = len(canonical_json_bytes(vocabulary.to_document()))
    definition_units = sum(
        8 + 2 * len(entry.lowering) for entry in vocabulary.entries
    )
    verification_units = library_instruction_count * 8
    compilation_units = library_instruction_count * 4
    storage_units = (encoded_bytes + library_bytes + 63) // 64
    return CostVector(
        alu_units=alu,
        dispatch_units=dispatch,
        encoded_bytes=encoded_bytes,
        library_bytes=library_bytes,
        definition_units=definition_units,
        verification_units=verification_units,
        compilation_units=compilation_units,
        storage_units=storage_units,
    )


def _token_lowering(
    token: EncodedToken,
    vocabulary: MachineVocabulary,
) -> tuple[WordInstruction, ...]:
    if token.primitive is not None:
        return (token.primitive,)
    assert token.entry_id is not None
    entry = vocabulary.by_id().get(token.entry_id)
    if entry is None:
        raise MachineLanguageError("proposal token references an unknown entry")
    return entry.lowering


def _proposal_occurrences(
    programs: Sequence[WeightedProgram],
    vocabulary: MachineVocabulary,
) -> dict[tuple[WordInstruction, ...], tuple[int, int]]:
    """Return lowering -> (weighted occurrences, dispatches removed).

    Proposal spans are mined over the current encoded token stream. A learned
    entry is therefore atomic in the following cycle, giving vocabulary
    persistence a direct and inspectable effect on the next action space.
    """

    occurrences: dict[tuple[WordInstruction, ...], tuple[int, int]] = {}
    existing = {entry.lowering for entry in vocabulary.entries}
    for item in programs:
        tokens = encode_program(item.program, vocabulary).tokens
        for token_length in range(2, min(4, len(tokens)) + 1):
            for index in range(len(tokens) - token_length + 1):
                lowering = tuple(
                    instruction
                    for token in tokens[index : index + token_length]
                    for instruction in _token_lowering(token, vocabulary)
                )
                if (
                    lowering in existing
                    or len(lowering) > MAX_SUPERINSTRUCTION_LENGTH
                ):
                    continue
                count, removed = occurrences.get(lowering, (0, 0))
                occurrences[lowering] = (
                    count + item.executions,
                    removed + item.executions * (token_length - 1),
                )
    return occurrences


def learn_one_superinstruction(
    programs: Iterable[WeightedProgram],
    vocabulary: MachineVocabulary,
    *,
    evidence_catalog_id: str,
    cycle: int,
    dispatch_cost: int = 4,
) -> MachineVocabulary:
    items = tuple(programs)
    occurrences = _proposal_occurrences(items, vocabulary)
    proposals: list[tuple[int, int, bytes, tuple[WordInstruction, ...]]] = []
    for sequence, (count, dispatches_removed) in occurrences.items():
        definition_cost = 8 + 2 * len(sequence)
        saving = dispatches_removed * dispatch_cost - definition_cost
        if saving > 0:
            proposals.append(
                (
                    -saving,
                    -count,
                    canonical_json_bytes(
                        [instruction.to_document() for instruction in sequence]
                    ),
                    sequence,
                )
            )
    if not proposals:
        return vocabulary
    _, negative_count, _, selected = min(proposals)
    count = -negative_count
    _, dispatches_removed = occurrences[selected]
    saving = dispatches_removed * dispatch_cost - (8 + 2 * len(selected))
    entry = LearnedSuperinstruction(
        lowering=selected,
        evidence_catalog_id=evidence_catalog_id,
        parent_vocabulary_id=vocabulary.vocabulary_id,
        learned_cycle=cycle,
        weighted_occurrences=count,
        estimated_saving=saving,
    )
    return MachineVocabulary(
        parent_vocabulary_id=vocabulary.vocabulary_id,
        entries=tuple(sorted(vocabulary.entries + (entry,), key=lambda item: item.entry_id)),
    )
