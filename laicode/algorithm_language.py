"""Typed algorithm IR with transparent learned expression intrinsics."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence, TypeAlias

from .canonical import JsonValue, canonical_json_bytes, content_id


PROGRAM_SCHEMA_VERSION = "AlgorithmProgramV0"
VOCABULARY_ENTRY_SCHEMA_VERSION = "AlgorithmVocabularyEntryV0"
VOCABULARY_SCHEMA_VERSION = "AlgorithmVocabularyV0"
ENCODED_PROGRAM_SCHEMA_VERSION = "EncodedAlgorithmProgramV0"
LEARNER_VERSION = "CrossTaskExpressionPatternLearnerV0"
KERNEL_VERSION = "StructuredI64ArrayKernelV0"

I64_MIN = -(1 << 63)
I64_MAX = (1 << 63) - 1
MAX_RUNTIME_STEPS = 100_000
MAX_TRACE_EVENTS = 256
MAX_STATEMENTS = 256
MAX_EXPRESSION_DEPTH = 32
MAX_VOCABULARY_ENTRIES = 16

I64 = "i64"
BOOL = "bool"
ARRAY_I64 = "array_i64"
PAIR_I64 = "pair_i64"
_TYPES = {I64, BOOL, ARRAY_I64, PAIR_I64}
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_CORE_ARITY = {
    "len": 1,
    "get": 2,
    "add": 2,
    "sub": 2,
    "div_trunc": 2,
    "max": 2,
    "eq": 2,
    "lt": 2,
    "le": 2,
    "gt": 2,
    "ge": 2,
    "and": 2,
    "pair": 2,
}
_I64_BINARY = {"add", "sub", "div_trunc", "max"}
_I64_COMPARISON = {"eq", "lt", "le", "gt", "ge"}


class AlgorithmLanguageError(ValueError):
    """Raised when an algorithm program violates the fixed language kernel."""


def _valid_identifier(value: object) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _checked_i64(value: object, description: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AlgorithmLanguageError(f"{description} must be an integer")
    if not I64_MIN <= value <= I64_MAX:
        raise AlgorithmLanguageError(f"{description} is outside signed i64")
    return value


@dataclass(frozen=True)
class Expression:
    op: str
    arguments: tuple["Expression", ...] = ()
    name: str | None = None
    value: int | None = None
    entry_id: str | None = None

    def __post_init__(self) -> None:
        if self.op == "const":
            _checked_i64(self.value, "constant")
            if self.arguments or self.name is not None or self.entry_id is not None:
                raise AlgorithmLanguageError("constant expression has invalid fields")
            return
        if self.op == "var":
            if not _valid_identifier(self.name):
                raise AlgorithmLanguageError("variable expression has an invalid name")
            if self.arguments or self.value is not None or self.entry_id is not None:
                raise AlgorithmLanguageError("variable expression has invalid fields")
            return
        if self.op == "intrinsic":
            if (
                not isinstance(self.entry_id, str)
                or not self.entry_id.startswith("sha256:")
                or len(self.entry_id) != 71
                or self.name is not None
                or self.value is not None
            ):
                raise AlgorithmLanguageError("intrinsic expression is invalid")
            return
        arity = _CORE_ARITY.get(self.op)
        if arity is None:
            raise AlgorithmLanguageError(f"unknown algorithm expression {self.op!r}")
        if (
            len(self.arguments) != arity
            or self.name is not None
            or self.value is not None
            or self.entry_id is not None
        ):
            raise AlgorithmLanguageError(f"expression {self.op!r} has invalid fields")

    def to_document(self) -> dict[str, JsonValue]:
        if self.op == "const":
            assert self.value is not None
            return {"op": "const", "value": self.value}
        if self.op == "var":
            assert self.name is not None
            return {"op": "var", "name": self.name}
        if self.op == "intrinsic":
            assert self.entry_id is not None
            return {
                "op": "intrinsic",
                "entry_id": self.entry_id,
                "arguments": [item.to_document() for item in self.arguments],
            }
        return {
            "op": self.op,
            "arguments": [item.to_document() for item in self.arguments],
        }

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> "Expression":
        if not isinstance(value, dict) or not isinstance(value.get("op"), str):
            raise AlgorithmLanguageError("expression must be an object with an op")
        op = value["op"]
        if op == "const":
            if set(value) != {"op", "value"}:
                raise AlgorithmLanguageError("constant expression has invalid fields")
            return cls("const", value=_checked_i64(value["value"], "constant"))
        if op == "var":
            if set(value) != {"op", "name"} or not isinstance(value["name"], str):
                raise AlgorithmLanguageError("variable expression has invalid fields")
            return cls("var", name=value["name"])
        expected = {"op", "arguments", "entry_id"} if op == "intrinsic" else {
            "op",
            "arguments",
        }
        if set(value) != expected:
            raise AlgorithmLanguageError(f"expression {op!r} has invalid fields")
        arguments = value["arguments"]
        if not isinstance(arguments, list) or not all(
            isinstance(item, dict) for item in arguments
        ):
            raise AlgorithmLanguageError("expression arguments must be objects")
        entry_id = value.get("entry_id")
        if entry_id is not None and not isinstance(entry_id, str):
            raise AlgorithmLanguageError("intrinsic entry identity is invalid")
        return cls(
            op,
            tuple(Expression.from_document(item) for item in arguments),
            entry_id=entry_id,
        )


@dataclass(frozen=True)
class Let:
    name: str
    value: Expression


@dataclass(frozen=True)
class Assign:
    name: str
    value: Expression


@dataclass(frozen=True)
class ForRange:
    index: str
    start: Expression
    stop: Expression
    body: tuple["Statement", ...]


@dataclass(frozen=True)
class While:
    condition: Expression
    body: tuple["Statement", ...]


@dataclass(frozen=True)
class If:
    condition: Expression
    then_body: tuple["Statement", ...]
    else_body: tuple["Statement", ...]


@dataclass(frozen=True)
class Return:
    value: Expression


Statement: TypeAlias = Let | Assign | ForRange | While | If | Return


def statement_to_document(statement: Statement) -> dict[str, JsonValue]:
    if isinstance(statement, Let):
        return {"op": "let", "name": statement.name, "value": statement.value.to_document()}
    if isinstance(statement, Assign):
        return {"op": "assign", "name": statement.name, "value": statement.value.to_document()}
    if isinstance(statement, ForRange):
        return {
            "op": "for_range",
            "index": statement.index,
            "start": statement.start.to_document(),
            "stop": statement.stop.to_document(),
            "body": [statement_to_document(item) for item in statement.body],
        }
    if isinstance(statement, While):
        return {
            "op": "while",
            "condition": statement.condition.to_document(),
            "body": [statement_to_document(item) for item in statement.body],
        }
    if isinstance(statement, If):
        return {
            "op": "if",
            "condition": statement.condition.to_document(),
            "then": [statement_to_document(item) for item in statement.then_body],
            "else": [statement_to_document(item) for item in statement.else_body],
        }
    if isinstance(statement, Return):
        return {"op": "return", "value": statement.value.to_document()}
    raise AssertionError("unknown statement type")


def statement_from_document(value: Mapping[str, object]) -> Statement:
    if not isinstance(value, dict) or not isinstance(value.get("op"), str):
        raise AlgorithmLanguageError("statement must be an object with an op")
    op = value["op"]

    def expression(field: str) -> Expression:
        item = value.get(field)
        if not isinstance(item, dict):
            raise AlgorithmLanguageError(f"statement {op!r} omits {field}")
        return Expression.from_document(item)

    def block(field: str) -> tuple[Statement, ...]:
        item = value.get(field)
        if not isinstance(item, list) or not all(isinstance(row, dict) for row in item):
            raise AlgorithmLanguageError(f"statement {op!r} has an invalid {field} block")
        return tuple(statement_from_document(row) for row in item)

    if op in {"let", "assign"}:
        if set(value) != {"op", "name", "value"} or not isinstance(value["name"], str):
            raise AlgorithmLanguageError(f"statement {op!r} has invalid fields")
        result = Let(value["name"], expression("value")) if op == "let" else Assign(
            value["name"], expression("value")
        )
        return result
    if op == "for_range":
        if set(value) != {"op", "index", "start", "stop", "body"} or not isinstance(
            value["index"], str
        ):
            raise AlgorithmLanguageError("for_range statement has invalid fields")
        return ForRange(value["index"], expression("start"), expression("stop"), block("body"))
    if op == "while":
        if set(value) != {"op", "condition", "body"}:
            raise AlgorithmLanguageError("while statement has invalid fields")
        return While(expression("condition"), block("body"))
    if op == "if":
        if set(value) != {"op", "condition", "then", "else"}:
            raise AlgorithmLanguageError("if statement has invalid fields")
        return If(expression("condition"), block("then"), block("else"))
    if op == "return":
        if set(value) != {"op", "value"}:
            raise AlgorithmLanguageError("return statement has invalid fields")
        return Return(expression("value"))
    raise AlgorithmLanguageError(f"unknown statement operation {op!r}")


@dataclass(frozen=True)
class AlgorithmProgram:
    task_id: str
    return_type: str
    statements: tuple[Statement, ...]

    def __post_init__(self) -> None:
        if not _valid_identifier(self.task_id):
            raise AlgorithmLanguageError("algorithm task identity is invalid")
        if self.return_type not in {I64, PAIR_I64}:
            raise AlgorithmLanguageError("algorithm return type is invalid")
        if not self.statements or len(tuple(_walk_statements(self.statements))) > MAX_STATEMENTS:
            raise AlgorithmLanguageError("algorithm statement count is invalid")

    def to_document(self, *, encoded: bool = False) -> dict[str, JsonValue]:
        return {
            "schema_version": (
                ENCODED_PROGRAM_SCHEMA_VERSION if encoded else PROGRAM_SCHEMA_VERSION
            ),
            "kernel_version": KERNEL_VERSION,
            "task_id": self.task_id,
            "parameters": [
                {"name": "nums", "type": ARRAY_I64},
                {"name": "target", "type": I64},
            ],
            "return_type": self.return_type,
            "effects": [],
            "statements": [statement_to_document(item) for item in self.statements],
        }

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> "AlgorithmProgram":
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "kernel_version",
            "task_id",
            "parameters",
            "return_type",
            "effects",
            "statements",
        }:
            raise AlgorithmLanguageError("algorithm program has invalid fields")
        if value["schema_version"] not in {
            PROGRAM_SCHEMA_VERSION,
            ENCODED_PROGRAM_SCHEMA_VERSION,
        } or value["kernel_version"] != KERNEL_VERSION:
            raise AlgorithmLanguageError("algorithm program has an unknown schema or kernel")
        if value["parameters"] != [
            {"name": "nums", "type": ARRAY_I64},
            {"name": "target", "type": I64},
        ] or value["effects"] != []:
            raise AlgorithmLanguageError("algorithm program ABI is invalid")
        statements = value["statements"]
        if not isinstance(statements, list) or not all(
            isinstance(item, dict) for item in statements
        ):
            raise AlgorithmLanguageError("algorithm statements must be objects")
        task_id = value["task_id"]
        return_type = value["return_type"]
        if not isinstance(task_id, str) or not isinstance(return_type, str):
            raise AlgorithmLanguageError("algorithm program identity or type is invalid")
        return cls(
            task_id,
            return_type,
            tuple(statement_from_document(item) for item in statements),
        )

    @property
    def program_id(self) -> str:
        return content_id(self.to_document())


def _walk_statements(statements: Sequence[Statement]) -> Iterable[Statement]:
    for statement in statements:
        yield statement
        if isinstance(statement, ForRange):
            yield from _walk_statements(statement.body)
        elif isinstance(statement, While):
            yield from _walk_statements(statement.body)
        elif isinstance(statement, If):
            yield from _walk_statements(statement.then_body)
            yield from _walk_statements(statement.else_body)


@dataclass(frozen=True)
class PatternNode:
    op: str
    arguments: tuple["PatternNode", ...] = ()
    hole_index: int | None = None
    hole_type: str | None = None
    value: int | None = None

    def __post_init__(self) -> None:
        if self.op == "hole":
            if (
                isinstance(self.hole_index, bool)
                or not isinstance(self.hole_index, int)
                or self.hole_index < 0
                or self.hole_type not in _TYPES
                or self.arguments
                or self.value is not None
            ):
                raise AlgorithmLanguageError("vocabulary pattern hole is invalid")
            return
        if self.op == "const":
            _checked_i64(self.value, "pattern constant")
            if self.arguments or self.hole_index is not None or self.hole_type is not None:
                raise AlgorithmLanguageError("vocabulary pattern constant is invalid")
            return
        arity = _CORE_ARITY.get(self.op)
        if (
            arity is None
            or len(self.arguments) != arity
            or self.hole_index is not None
            or self.hole_type is not None
            or self.value is not None
        ):
            raise AlgorithmLanguageError("vocabulary pattern operator is invalid")

    def to_document(self) -> dict[str, JsonValue]:
        if self.op == "hole":
            assert self.hole_index is not None and self.hole_type is not None
            return {"op": "hole", "index": self.hole_index, "type": self.hole_type}
        if self.op == "const":
            assert self.value is not None
            return {"op": "const", "value": self.value}
        return {
            "op": self.op,
            "arguments": [item.to_document() for item in self.arguments],
        }

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> "PatternNode":
        if not isinstance(value, dict) or not isinstance(value.get("op"), str):
            raise AlgorithmLanguageError("vocabulary pattern node is invalid")
        op = value["op"]
        if op == "hole":
            if set(value) != {"op", "index", "type"} or not isinstance(value["type"], str):
                raise AlgorithmLanguageError("vocabulary pattern hole has invalid fields")
            index = value["index"]
            if isinstance(index, bool) or not isinstance(index, int):
                raise AlgorithmLanguageError("vocabulary pattern hole index is invalid")
            return cls("hole", hole_index=index, hole_type=value["type"])
        if op == "const":
            if set(value) != {"op", "value"}:
                raise AlgorithmLanguageError("vocabulary pattern constant has invalid fields")
            return cls("const", value=_checked_i64(value["value"], "pattern constant"))
        if set(value) != {"op", "arguments"} or not isinstance(value["arguments"], list):
            raise AlgorithmLanguageError("vocabulary pattern operator has invalid fields")
        arguments = value["arguments"]
        if not all(isinstance(item, dict) for item in arguments):
            raise AlgorithmLanguageError("vocabulary pattern arguments are invalid")
        return cls(op, tuple(cls.from_document(item) for item in arguments))

    @property
    def operator_count(self) -> int:
        if self.op in {"hole", "const"}:
            return 0
        return 1 + sum(item.operator_count for item in self.arguments)

    @property
    def hole_count(self) -> int:
        indexes = {
            node.hole_index
            for node in self.walk()
            if node.op == "hole"
        }
        return len(indexes)

    def walk(self) -> Iterable["PatternNode"]:
        yield self
        for argument in self.arguments:
            yield from argument.walk()


@dataclass(frozen=True)
class AlgorithmVocabularyEntry:
    lowering: PatternNode
    result_type: str
    hole_types: tuple[str, ...]
    evidence_catalog_id: str
    parent_vocabulary_id: str
    learned_cycle: int
    training_task_ids: tuple[str, ...]
    occurrences: int
    estimated_dispatch_saving: int
    learner_id: str = LEARNER_VERSION

    def __post_init__(self) -> None:
        if self.result_type not in {I64, BOOL} or self.lowering.operator_count < 2:
            raise AlgorithmLanguageError("vocabulary entry result or lowering is invalid")
        indexes = sorted(
            {int(item.hole_index) for item in self.lowering.walk() if item.op == "hole"}
        )
        if indexes != list(range(len(self.hole_types))):
            raise AlgorithmLanguageError("vocabulary entry holes must be contiguous")
        for index, expected in enumerate(self.hole_types):
            actual = {
                item.hole_type
                for item in self.lowering.walk()
                if item.op == "hole" and item.hole_index == index
            }
            if actual != {expected}:
                raise AlgorithmLanguageError("vocabulary entry hole types differ")
        for identifier in (self.evidence_catalog_id, self.parent_vocabulary_id):
            if not identifier.startswith("sha256:") or len(identifier) != 71:
                raise AlgorithmLanguageError("vocabulary entry provenance is invalid")
        if (
            isinstance(self.learned_cycle, bool)
            or self.learned_cycle < 1
            or self.training_task_ids != tuple(sorted(set(self.training_task_ids)))
            or len(self.training_task_ids) < 2
            or self.occurrences < 2
            or self.estimated_dispatch_saving < 1
            or self.learner_id != LEARNER_VERSION
        ):
            raise AlgorithmLanguageError("vocabulary entry evidence is invalid")

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": VOCABULARY_ENTRY_SCHEMA_VERSION,
            "kind": "transparent_expression_intrinsic",
            "result_type": self.result_type,
            "hole_types": list(self.hole_types),
            "lowering": self.lowering.to_document(),
            "learner": {"id": self.learner_id, "cycle": self.learned_cycle},
            "provenance": {
                "evidence_catalog_id": self.evidence_catalog_id,
                "parent_vocabulary_id": self.parent_vocabulary_id,
                "training_task_ids": list(self.training_task_ids),
            },
            "evidence": {
                "cross_task_occurrences": self.occurrences,
                "primitive_operator_count": self.lowering.operator_count,
                "estimated_dispatch_saving": self.estimated_dispatch_saving,
            },
        }

    @classmethod
    def from_document(
        cls,
        value: Mapping[str, object],
    ) -> "AlgorithmVocabularyEntry":
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "kind",
            "result_type",
            "hole_types",
            "lowering",
            "learner",
            "provenance",
            "evidence",
        }:
            raise AlgorithmLanguageError("algorithm vocabulary entry has invalid fields")
        if (
            value["schema_version"] != VOCABULARY_ENTRY_SCHEMA_VERSION
            or value["kind"] != "transparent_expression_intrinsic"
        ):
            raise AlgorithmLanguageError("algorithm vocabulary entry has an unknown schema")
        result_type = value["result_type"]
        hole_types = value["hole_types"]
        lowering = value["lowering"]
        learner = value["learner"]
        provenance = value["provenance"]
        evidence = value["evidence"]
        if (
            not isinstance(result_type, str)
            or not isinstance(hole_types, list)
            or not all(isinstance(item, str) for item in hole_types)
            or not isinstance(lowering, dict)
            or not isinstance(learner, dict)
            or set(learner) != {"id", "cycle"}
            or not isinstance(provenance, dict)
            or set(provenance)
            != {"evidence_catalog_id", "parent_vocabulary_id", "training_task_ids"}
            or not isinstance(evidence, dict)
            or set(evidence)
            != {
                "cross_task_occurrences",
                "primitive_operator_count",
                "estimated_dispatch_saving",
            }
        ):
            raise AlgorithmLanguageError("algorithm vocabulary entry payload is invalid")
        training_tasks = provenance["training_task_ids"]
        if (
            not isinstance(learner["id"], str)
            or isinstance(learner["cycle"], bool)
            or not isinstance(learner["cycle"], int)
            or not isinstance(provenance["evidence_catalog_id"], str)
            or not isinstance(provenance["parent_vocabulary_id"], str)
            or not isinstance(training_tasks, list)
            or not all(isinstance(item, str) for item in training_tasks)
            or any(
                isinstance(evidence[field], bool) or not isinstance(evidence[field], int)
                for field in (
                    "cross_task_occurrences",
                    "primitive_operator_count",
                    "estimated_dispatch_saving",
                )
            )
        ):
            raise AlgorithmLanguageError("algorithm vocabulary entry evidence is invalid")
        entry = cls(
            lowering=PatternNode.from_document(lowering),
            result_type=result_type,
            hole_types=tuple(hole_types),
            evidence_catalog_id=provenance["evidence_catalog_id"],
            parent_vocabulary_id=provenance["parent_vocabulary_id"],
            learned_cycle=learner["cycle"],
            training_task_ids=tuple(training_tasks),
            occurrences=evidence["cross_task_occurrences"],
            estimated_dispatch_saving=evidence["estimated_dispatch_saving"],
            learner_id=learner["id"],
        )
        if evidence["primitive_operator_count"] != entry.lowering.operator_count:
            raise AlgorithmLanguageError("algorithm vocabulary operator count differs")
        return entry

    @property
    def entry_id(self) -> str:
        return content_id(self.to_document())


@dataclass(frozen=True)
class AlgorithmVocabulary:
    parent_vocabulary_id: str | None
    entries: tuple[AlgorithmVocabularyEntry, ...]

    def __post_init__(self) -> None:
        if len(self.entries) > MAX_VOCABULARY_ENTRIES:
            raise AlgorithmLanguageError("algorithm vocabulary exceeds its entry limit")
        ids = [item.entry_id for item in self.entries]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise AlgorithmLanguageError("algorithm vocabulary entries must be ID-sorted")
        if self.parent_vocabulary_id is not None and (
            not self.parent_vocabulary_id.startswith("sha256:")
            or len(self.parent_vocabulary_id) != 71
        ):
            raise AlgorithmLanguageError("algorithm vocabulary parent is invalid")

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": VOCABULARY_SCHEMA_VERSION,
            "kernel_version": KERNEL_VERSION,
            "parent_vocabulary_id": self.parent_vocabulary_id,
            "entry_ids": [item.entry_id for item in self.entries],
            "entries": [item.to_document() for item in self.entries],
        }

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> "AlgorithmVocabulary":
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "kernel_version",
            "parent_vocabulary_id",
            "entry_ids",
            "entries",
        }:
            raise AlgorithmLanguageError("algorithm vocabulary has invalid fields")
        if (
            value["schema_version"] != VOCABULARY_SCHEMA_VERSION
            or value["kernel_version"] != KERNEL_VERSION
        ):
            raise AlgorithmLanguageError("algorithm vocabulary has an unknown schema")
        parent = value["parent_vocabulary_id"]
        entry_ids = value["entry_ids"]
        entries = value["entries"]
        if (
            parent is not None
            and not isinstance(parent, str)
            or not isinstance(entry_ids, list)
            or not isinstance(entries, list)
            or not all(isinstance(item, dict) for item in entries)
        ):
            raise AlgorithmLanguageError("algorithm vocabulary payload is invalid")
        parsed = tuple(AlgorithmVocabularyEntry.from_document(item) for item in entries)
        vocabulary = cls(parent, parsed)
        if entry_ids != [item.entry_id for item in parsed]:
            raise AlgorithmLanguageError("algorithm vocabulary entry identities differ")
        return vocabulary

    @property
    def vocabulary_id(self) -> str:
        return content_id(self.to_document())

    def by_id(self) -> dict[str, AlgorithmVocabularyEntry]:
        return {item.entry_id: item for item in self.entries}


EMPTY_ALGORITHM_VOCABULARY = AlgorithmVocabulary(None, ())


def expression_type(
    expression: Expression,
    environment: Mapping[str, str],
    vocabulary: AlgorithmVocabulary = EMPTY_ALGORITHM_VOCABULARY,
    *,
    depth: int = 0,
) -> str:
    if depth > MAX_EXPRESSION_DEPTH:
        raise AlgorithmLanguageError("algorithm expression is too deeply nested")
    if expression.op == "const":
        return I64
    if expression.op == "var":
        assert expression.name is not None
        try:
            return environment[expression.name]
        except KeyError as error:
            raise AlgorithmLanguageError(
                f"algorithm variable {expression.name!r} is not defined"
            ) from error
    if expression.op == "intrinsic":
        assert expression.entry_id is not None
        entry = vocabulary.by_id().get(expression.entry_id)
        if entry is None:
            raise AlgorithmLanguageError("algorithm intrinsic is not in the vocabulary")
        actual = tuple(
            expression_type(item, environment, vocabulary, depth=depth + 1)
            for item in expression.arguments
        )
        if actual != entry.hole_types:
            raise AlgorithmLanguageError("algorithm intrinsic argument types differ")
        return entry.result_type
    argument_types = tuple(
        expression_type(item, environment, vocabulary, depth=depth + 1)
        for item in expression.arguments
    )
    if expression.op == "len" and argument_types == (ARRAY_I64,):
        return I64
    if expression.op == "get" and argument_types == (ARRAY_I64, I64):
        return I64
    if expression.op in _I64_BINARY and argument_types == (I64, I64):
        return I64
    if expression.op in _I64_COMPARISON and argument_types == (I64, I64):
        return BOOL
    if expression.op == "and" and argument_types == (BOOL, BOOL):
        return BOOL
    if expression.op == "pair" and argument_types == (I64, I64):
        return PAIR_I64
    raise AlgorithmLanguageError(
        f"algorithm expression {expression.op!r} has incompatible operand types"
    )


def validate_program(
    program: AlgorithmProgram,
    vocabulary: AlgorithmVocabulary = EMPTY_ALGORITHM_VOCABULARY,
) -> None:
    environment: dict[str, str] = {"nums": ARRAY_I64, "target": I64}

    def block(statements: Sequence[Statement], *, nested: bool) -> None:
        for statement in statements:
            if isinstance(statement, Let):
                if nested:
                    raise AlgorithmLanguageError("local declarations are top-level only")
                if not _valid_identifier(statement.name) or statement.name in environment:
                    raise AlgorithmLanguageError("algorithm declaration name is invalid")
                value_type = expression_type(statement.value, environment, vocabulary)
                if value_type not in {I64, BOOL}:
                    raise AlgorithmLanguageError("algorithm local type is not supported")
                environment[statement.name] = value_type
            elif isinstance(statement, Assign):
                if statement.name not in environment or statement.name in {"nums", "target"}:
                    raise AlgorithmLanguageError("algorithm assignment target is invalid")
                if expression_type(statement.value, environment, vocabulary) != environment[
                    statement.name
                ]:
                    raise AlgorithmLanguageError("algorithm assignment type differs")
            elif isinstance(statement, ForRange):
                if not statement.body or not _valid_identifier(statement.index):
                    raise AlgorithmLanguageError("algorithm for_range is invalid")
                if statement.index in environment:
                    raise AlgorithmLanguageError("algorithm loop index shadows a variable")
                if expression_type(statement.start, environment, vocabulary) != I64 or expression_type(
                    statement.stop, environment, vocabulary
                ) != I64:
                    raise AlgorithmLanguageError("algorithm loop bounds must be i64")
                environment[statement.index] = I64
                block(statement.body, nested=True)
                del environment[statement.index]
            elif isinstance(statement, While):
                if not statement.body or expression_type(
                    statement.condition, environment, vocabulary
                ) != BOOL:
                    raise AlgorithmLanguageError("algorithm while condition or body is invalid")
                block(statement.body, nested=True)
            elif isinstance(statement, If):
                if expression_type(statement.condition, environment, vocabulary) != BOOL:
                    raise AlgorithmLanguageError("algorithm if condition must be bool")
                block(statement.then_body, nested=True)
                block(statement.else_body, nested=True)
            elif isinstance(statement, Return):
                if nested or expression_type(
                    statement.value, environment, vocabulary
                ) != program.return_type:
                    raise AlgorithmLanguageError("algorithm return is misplaced or mistyped")
            else:
                raise AssertionError("unknown algorithm statement")

    block(program.statements, nested=False)
    if not isinstance(program.statements[-1], Return) or any(
        isinstance(item, Return) for item in program.statements[:-1]
    ):
        raise AlgorithmLanguageError("algorithm must end with its only return")


def _expression_children(statement: Statement) -> Iterable[Expression]:
    if isinstance(statement, (Let, Assign, Return)):
        yield statement.value
    elif isinstance(statement, ForRange):
        yield statement.start
        yield statement.stop
    elif isinstance(statement, (While, If)):
        yield statement.condition


def _walk_expressions(expression: Expression) -> Iterable[Expression]:
    yield expression
    for argument in expression.arguments:
        yield from _walk_expressions(argument)


def _patternize(
    expression: Expression,
    environment: Mapping[str, str],
) -> tuple[PatternNode, tuple[str, ...]]:
    holes: dict[bytes, int] = {}
    types: list[str] = []

    def visit(item: Expression) -> PatternNode:
        if item.op == "const":
            return PatternNode("const", value=item.value)
        if item.op == "var":
            item_type = expression_type(item, environment)
            key = canonical_json_bytes({"type": item_type, "value": item.to_document()})
            if key not in holes:
                holes[key] = len(types)
                types.append(item_type)
            return PatternNode("hole", hole_index=holes[key], hole_type=item_type)
        if item.op == "intrinsic":
            raise AlgorithmLanguageError("learner only accepts primitive expressions")
        return PatternNode(item.op, tuple(visit(argument) for argument in item.arguments))

    return visit(expression), tuple(types)


def _typed_expression_roots(
    program: AlgorithmProgram,
) -> Iterable[tuple[Expression, Mapping[str, str]]]:
    environment: dict[str, str] = {"nums": ARRAY_I64, "target": I64}

    def block(statements: Sequence[Statement]) -> Iterable[tuple[Expression, Mapping[str, str]]]:
        for statement in statements:
            snapshot = dict(environment)
            for root in _expression_children(statement):
                for item in _walk_expressions(root):
                    yield item, snapshot
            if isinstance(statement, Let):
                environment[statement.name] = expression_type(statement.value, environment)
            elif isinstance(statement, ForRange):
                environment[statement.index] = I64
                yield from block(statement.body)
                del environment[statement.index]
            elif isinstance(statement, While):
                yield from block(statement.body)
            elif isinstance(statement, If):
                yield from block(statement.then_body)
                yield from block(statement.else_body)

    yield from block(program.statements)


def learn_expression_intrinsic(
    programs: Sequence[AlgorithmProgram],
    vocabulary: AlgorithmVocabulary,
    *,
    evidence_catalog_id: str,
    cycle: int,
) -> AlgorithmVocabularyEntry:
    if len({program.task_id for program in programs}) < 2:
        raise AlgorithmLanguageError("algorithm learner requires at least two tasks")
    for program in programs:
        validate_program(program)
    existing = {
        canonical_json_bytes(item.lowering.to_document()) for item in vocabulary.entries
    }
    candidates: dict[
        bytes,
        tuple[PatternNode, tuple[str, ...], str, int, set[str]],
    ] = {}
    for program in programs:
        for expression, environment in _typed_expression_roots(program):
            if expression.op in {"const", "var", "intrinsic"}:
                continue
            pattern, hole_types = _patternize(expression, environment)
            if pattern.operator_count < 2:
                continue
            key = canonical_json_bytes(
                {
                    "pattern": pattern.to_document(),
                    "holes": list(hole_types),
                    "result": expression_type(expression, environment),
                }
            )
            if canonical_json_bytes(pattern.to_document()) in existing:
                continue
            if key not in candidates:
                candidates[key] = (
                    pattern,
                    hole_types,
                    expression_type(expression, environment),
                    0,
                    set(),
                )
            current_pattern, current_holes, result_type, count, tasks = candidates[key]
            tasks.add(program.task_id)
            candidates[key] = (
                current_pattern,
                current_holes,
                result_type,
                count + 1,
                tasks,
            )
    eligible = [
        (key, value)
        for key, value in candidates.items()
        if len(value[4]) >= 2
    ]
    if not eligible:
        raise AlgorithmLanguageError("algorithm learner found no cross-task expression")
    key, (pattern, hole_types, result_type, occurrences, tasks) = min(
        eligible,
        key=lambda item: (
            -((item[1][0].operator_count - 1) * item[1][3]),
            -item[1][0].operator_count,
            item[0],
        ),
    )
    del key
    return AlgorithmVocabularyEntry(
        lowering=pattern,
        result_type=result_type,
        hole_types=hole_types,
        evidence_catalog_id=evidence_catalog_id,
        parent_vocabulary_id=vocabulary.vocabulary_id,
        learned_cycle=cycle,
        training_task_ids=tuple(sorted(tasks)),
        occurrences=occurrences,
        estimated_dispatch_saving=(pattern.operator_count - 1) * occurrences,
    )


def extend_vocabulary(
    vocabulary: AlgorithmVocabulary,
    entry: AlgorithmVocabularyEntry,
) -> AlgorithmVocabulary:
    if entry.parent_vocabulary_id != vocabulary.vocabulary_id:
        raise AlgorithmLanguageError("algorithm vocabulary extension parent differs")
    return AlgorithmVocabulary(
        vocabulary.vocabulary_id,
        tuple(sorted((*vocabulary.entries, entry), key=lambda item: item.entry_id)),
    )


def _match_pattern(
    pattern: PatternNode,
    expression: Expression,
    environment: Mapping[str, str],
    bindings: dict[int, Expression],
) -> bool:
    if pattern.op == "hole":
        assert pattern.hole_index is not None and pattern.hole_type is not None
        if expression_type(expression, environment) != pattern.hole_type:
            return False
        existing = bindings.get(pattern.hole_index)
        if existing is not None and existing.to_document() != expression.to_document():
            return False
        bindings[pattern.hole_index] = expression
        return True
    if pattern.op == "const":
        return expression.op == "const" and expression.value == pattern.value
    return expression.op == pattern.op and len(expression.arguments) == len(
        pattern.arguments
    ) and all(
        _match_pattern(pattern_item, expression_item, environment, bindings)
        for pattern_item, expression_item in zip(
            pattern.arguments, expression.arguments, strict=True
        )
    )


def encode_program(
    program: AlgorithmProgram,
    vocabulary: AlgorithmVocabulary,
) -> AlgorithmProgram:
    validate_program(program)
    environment: dict[str, str] = {"nums": ARRAY_I64, "target": I64}
    ordered_entries = sorted(
        vocabulary.entries,
        key=lambda item: (-item.lowering.operator_count, item.entry_id),
    )

    def encode_expression(expression: Expression) -> Expression:
        for entry in ordered_entries:
            bindings: dict[int, Expression] = {}
            if _match_pattern(entry.lowering, expression, environment, bindings):
                arguments = tuple(
                    encode_expression(bindings[index])
                    for index in range(len(entry.hole_types))
                )
                return Expression("intrinsic", arguments, entry_id=entry.entry_id)
        if expression.op in {"const", "var"}:
            return expression
        return Expression(
            expression.op,
            tuple(encode_expression(item) for item in expression.arguments),
            entry_id=expression.entry_id,
        )

    def encode_block(statements: Sequence[Statement]) -> tuple[Statement, ...]:
        encoded: list[Statement] = []
        for statement in statements:
            if isinstance(statement, Let):
                value = encode_expression(statement.value)
                encoded.append(Let(statement.name, value))
                environment[statement.name] = expression_type(
                    statement.value, environment
                )
            elif isinstance(statement, Assign):
                encoded.append(Assign(statement.name, encode_expression(statement.value)))
            elif isinstance(statement, ForRange):
                start = encode_expression(statement.start)
                stop = encode_expression(statement.stop)
                environment[statement.index] = I64
                body = encode_block(statement.body)
                del environment[statement.index]
                encoded.append(ForRange(statement.index, start, stop, body))
            elif isinstance(statement, While):
                condition = encode_expression(statement.condition)
                encoded.append(While(condition, encode_block(statement.body)))
            elif isinstance(statement, If):
                condition = encode_expression(statement.condition)
                encoded.append(
                    If(
                        condition,
                        encode_block(statement.then_body),
                        encode_block(statement.else_body),
                    )
                )
            elif isinstance(statement, Return):
                encoded.append(Return(encode_expression(statement.value)))
        return tuple(encoded)

    result = AlgorithmProgram(program.task_id, program.return_type, encode_block(program.statements))
    validate_program(result, vocabulary)
    return result


RuntimeValue: TypeAlias = int | bool | tuple[int, int] | tuple[int, ...]


@dataclass(frozen=True)
class ExecutionResult:
    value: int | tuple[int, int]
    steps: int
    dispatches: int
    trace: tuple[Mapping[str, JsonValue], ...]
    trace_truncated: bool


class _Runtime:
    def __init__(
        self,
        nums: Sequence[int],
        target: int,
        vocabulary: AlgorithmVocabulary,
        *,
        trace: bool,
    ) -> None:
        self.environment: dict[str, RuntimeValue] = {
            "nums": tuple(_checked_i64(item, "array element") for item in nums),
            "target": _checked_i64(target, "target"),
        }
        if len(nums) > I64_MAX:
            raise AlgorithmLanguageError("algorithm input array is too large")
        self.vocabulary = vocabulary
        self.steps = 0
        self.dispatches = 0
        self.events: list[Mapping[str, JsonValue]] = []
        self.trace_enabled = trace
        self.trace_truncated = False

    def tick(self, *, dispatch: bool = False) -> None:
        self.steps += 1
        if dispatch:
            self.dispatches += 1
        if self.steps > MAX_RUNTIME_STEPS:
            raise AlgorithmLanguageError("algorithm exceeded its runtime step budget")

    def event(self, value: Mapping[str, JsonValue]) -> None:
        if not self.trace_enabled:
            return
        if len(self.events) < MAX_TRACE_EVENTS:
            self.events.append(dict(value))
        else:
            self.trace_truncated = True


def _require_i64(value: RuntimeValue, operation: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AlgorithmLanguageError(f"{operation} requires i64")
    return value


def _require_bool(value: RuntimeValue, operation: str) -> bool:
    if not isinstance(value, bool):
        raise AlgorithmLanguageError(f"{operation} requires bool")
    return value


def _apply_operator(op: str, arguments: Sequence[RuntimeValue]) -> RuntimeValue:
    if op == "len":
        array = arguments[0]
        if not isinstance(array, tuple):
            raise AlgorithmLanguageError("len requires an array")
        return len(array)
    if op == "get":
        array = arguments[0]
        index = _require_i64(arguments[1], "get")
        if not isinstance(array, tuple) or not 0 <= index < len(array):
            raise AlgorithmLanguageError("array index is outside the input")
        return array[index]
    if op in _I64_BINARY:
        left = _require_i64(arguments[0], op)
        right = _require_i64(arguments[1], op)
        if op == "add":
            return _checked_i64(left + right, "addition result")
        if op == "sub":
            return _checked_i64(left - right, "subtraction result")
        if op == "div_trunc":
            if right == 0 or (left == I64_MIN and right == -1):
                raise AlgorithmLanguageError("division is undefined")
            quotient = abs(left) // abs(right)
            return -quotient if (left < 0) != (right < 0) else quotient
        return max(left, right)
    if op in _I64_COMPARISON:
        left = _require_i64(arguments[0], op)
        right = _require_i64(arguments[1], op)
        return {
            "eq": left == right,
            "lt": left < right,
            "le": left <= right,
            "gt": left > right,
            "ge": left >= right,
        }[op]
    if op == "and":
        return _require_bool(arguments[0], op) and _require_bool(arguments[1], op)
    if op == "pair":
        return (
            _require_i64(arguments[0], op),
            _require_i64(arguments[1], op),
        )
    raise AssertionError("validated operator is not implemented")


def _evaluate_pattern(pattern: PatternNode, arguments: Sequence[RuntimeValue]) -> RuntimeValue:
    if pattern.op == "hole":
        assert pattern.hole_index is not None
        return arguments[pattern.hole_index]
    if pattern.op == "const":
        assert pattern.value is not None
        return pattern.value
    return _apply_operator(
        pattern.op,
        tuple(_evaluate_pattern(item, arguments) for item in pattern.arguments),
    )


def _evaluate_expression(expression: Expression, runtime: _Runtime) -> RuntimeValue:
    runtime.tick(dispatch=expression.op not in {"const", "var"})
    if expression.op == "const":
        assert expression.value is not None
        return expression.value
    if expression.op == "var":
        assert expression.name is not None
        return runtime.environment[expression.name]
    if expression.op == "intrinsic":
        assert expression.entry_id is not None
        entry = runtime.vocabulary.by_id()[expression.entry_id]
        arguments = tuple(_evaluate_expression(item, runtime) for item in expression.arguments)
        return _evaluate_pattern(entry.lowering, arguments)
    arguments = tuple(_evaluate_expression(item, runtime) for item in expression.arguments)
    return _apply_operator(expression.op, arguments)


def execute_program(
    program: AlgorithmProgram,
    nums: Sequence[int],
    target: int,
    vocabulary: AlgorithmVocabulary = EMPTY_ALGORITHM_VOCABULARY,
    *,
    trace: bool = False,
) -> ExecutionResult:
    validate_program(program, vocabulary)
    runtime = _Runtime(nums, target, vocabulary, trace=trace)
    returned: int | tuple[int, int] | None = None

    def block(statements: Sequence[Statement]) -> None:
        nonlocal returned
        for statement in statements:
            runtime.tick(dispatch=True)
            if isinstance(statement, Let):
                value = _evaluate_expression(statement.value, runtime)
                runtime.environment[statement.name] = value
                runtime.event({"event": "let", "name": statement.name, "value": _json_value(value)})
            elif isinstance(statement, Assign):
                value = _evaluate_expression(statement.value, runtime)
                runtime.environment[statement.name] = value
                runtime.event(
                    {"event": "assign", "name": statement.name, "value": _json_value(value)}
                )
            elif isinstance(statement, ForRange):
                start = _require_i64(_evaluate_expression(statement.start, runtime), "for_range")
                stop = _require_i64(_evaluate_expression(statement.stop, runtime), "for_range")
                for index in range(start, stop):
                    runtime.tick()
                    runtime.environment[statement.index] = index
                    runtime.event(
                        {"event": "for_iteration", "index": statement.index, "value": index}
                    )
                    block(statement.body)
                runtime.environment.pop(statement.index, None)
            elif isinstance(statement, While):
                iteration = 0
                while _require_bool(
                    _evaluate_expression(statement.condition, runtime), "while"
                ):
                    runtime.tick()
                    runtime.event({"event": "while_iteration", "iteration": iteration})
                    block(statement.body)
                    iteration += 1
            elif isinstance(statement, If):
                condition = _require_bool(
                    _evaluate_expression(statement.condition, runtime), "if"
                )
                runtime.event({"event": "if", "branch": "then" if condition else "else"})
                block(statement.then_body if condition else statement.else_body)
            elif isinstance(statement, Return):
                value = _evaluate_expression(statement.value, runtime)
                if isinstance(value, bool) or not isinstance(value, (int, tuple)):
                    raise AlgorithmLanguageError("algorithm returned an invalid value")
                returned = value
                runtime.event({"event": "return", "value": _json_value(value)})

    block(program.statements)
    if returned is None:
        raise AlgorithmLanguageError("algorithm did not return")
    return ExecutionResult(
        returned,
        runtime.steps,
        runtime.dispatches,
        tuple(runtime.events),
        runtime.trace_truncated,
    )


def _json_value(value: RuntimeValue) -> JsonValue:
    if isinstance(value, tuple):
        return list(value)
    return value


def primitive_operator_count(program: AlgorithmProgram) -> int:
    return sum(
        1
        for statement in _walk_statements(program.statements)
        for root in _expression_children(statement)
        for expression in _walk_expressions(root)
        if expression.op not in {"const", "var"}
    )


def intrinsic_uses(program: AlgorithmProgram) -> tuple[str, ...]:
    return tuple(
        sorted(
            expression.entry_id
            for statement in _walk_statements(program.statements)
            for root in _expression_children(statement)
            for expression in _walk_expressions(root)
            if expression.op == "intrinsic" and expression.entry_id is not None
        )
    )


def _render_expression(expression: Expression) -> str:
    if expression.op == "const":
        return str(expression.value)
    if expression.op == "var":
        return str(expression.name)
    if expression.op == "intrinsic":
        assert expression.entry_id is not None
        arguments = ", ".join(_render_expression(item) for item in expression.arguments)
        return f"op_{expression.entry_id[7:15]}({arguments})"
    arguments = [_render_expression(item) for item in expression.arguments]
    if expression.op == "len":
        return f"len({arguments[0]})"
    if expression.op == "get":
        return f"{arguments[0]}[{arguments[1]}]"
    if expression.op == "max":
        return f"max({arguments[0]}, {arguments[1]})"
    if expression.op == "pair":
        return f"pair({arguments[0]}, {arguments[1]})"
    symbols = {
        "add": "+",
        "sub": "-",
        "div_trunc": "/",
        "eq": "==",
        "lt": "<",
        "le": "<=",
        "gt": ">",
        "ge": ">=",
        "and": "and",
    }
    return f"({arguments[0]} {symbols[expression.op]} {arguments[1]})"


def render_program(program: AlgorithmProgram) -> str:
    lines = [
        f"algorithm {program.task_id}(nums: array<i64>, target: i64) -> {program.return_type} {{"
    ]

    def block(statements: Sequence[Statement], indentation: int) -> None:
        prefix = "    " * indentation
        for statement in statements:
            if isinstance(statement, Let):
                lines.append(f"{prefix}let {statement.name} = {_render_expression(statement.value)}")
            elif isinstance(statement, Assign):
                lines.append(f"{prefix}{statement.name} = {_render_expression(statement.value)}")
            elif isinstance(statement, ForRange):
                lines.append(
                    f"{prefix}for {statement.index} in {_render_expression(statement.start)}..{_render_expression(statement.stop)} {{"
                )
                block(statement.body, indentation + 1)
                lines.append(f"{prefix}}}")
            elif isinstance(statement, While):
                lines.append(f"{prefix}while {_render_expression(statement.condition)} {{")
                block(statement.body, indentation + 1)
                lines.append(f"{prefix}}}")
            elif isinstance(statement, If):
                lines.append(f"{prefix}if {_render_expression(statement.condition)} {{")
                block(statement.then_body, indentation + 1)
                if statement.else_body:
                    lines.append(f"{prefix}}} else {{")
                    block(statement.else_body, indentation + 1)
                lines.append(f"{prefix}}}")
            elif isinstance(statement, Return):
                lines.append(f"{prefix}return {_render_expression(statement.value)}")

    block(program.statements, 1)
    lines.append("}")
    return "\n".join(lines) + "\n"


def _lower_pattern(pattern: PatternNode, arguments: Sequence[Expression]) -> Expression:
    if pattern.op == "hole":
        assert pattern.hole_index is not None
        return arguments[pattern.hole_index]
    if pattern.op == "const":
        assert pattern.value is not None
        return Expression("const", value=pattern.value)
    return Expression(
        pattern.op,
        tuple(_lower_pattern(item, arguments) for item in pattern.arguments),
    )


def _c_i64(value: int) -> str:
    if value == I64_MIN:
        return "INT64_MIN"
    if value < 0:
        return f"(-INT64_C({-value}))"
    return f"INT64_C({value})"


class _CCompiler:
    def __init__(self, vocabulary: AlgorithmVocabulary) -> None:
        self.vocabulary = vocabulary
        self.environment: dict[str, str] = {"nums": ARRAY_I64, "target": I64}
        self.serial = 0

    def temporary(self, prefix: str) -> str:
        self.serial += 1
        return f"lai_{prefix}_{self.serial}"

    def expression(self, value: Expression) -> str:
        if value.op == "const":
            assert value.value is not None
            return _c_i64(value.value)
        if value.op == "var":
            assert value.name is not None
            return value.name
        if value.op == "intrinsic":
            assert value.entry_id is not None
            entry = self.vocabulary.by_id()[value.entry_id]
            lowered = _lower_pattern(entry.lowering, value.arguments)
            return f"(/* learned op_{value.entry_id[7:15]} */ {self.expression(lowered)})"
        arguments = [self.expression(item) for item in value.arguments]
        if value.op == "len":
            return "((int64_t)nums_len)"
        if value.op == "get":
            return f"lai_get({arguments[0]}, nums_len, {arguments[1]}, &ok)"
        if value.op == "add":
            return f"lai_add({arguments[0]}, {arguments[1]}, &ok)"
        if value.op == "sub":
            return f"lai_sub({arguments[0]}, {arguments[1]}, &ok)"
        if value.op == "div_trunc":
            return f"lai_div({arguments[0]}, {arguments[1]}, &ok)"
        if value.op == "max":
            return f"lai_max({arguments[0]}, {arguments[1]})"
        if value.op == "and":
            return f"lai_bool_and({arguments[0]}, {arguments[1]})"
        symbols = {"eq": "==", "lt": "<", "le": "<=", "gt": ">", "ge": ">="}
        if value.op in symbols:
            return f"({arguments[0]} {symbols[value.op]} {arguments[1]})"
        if value.op == "pair":
            raise AlgorithmLanguageError("pair expression is only valid at return")
        raise AssertionError("validated expression is not compilable")

    def block(self, statements: Sequence[Statement], indentation: int) -> list[str]:
        lines: list[str] = []
        prefix = "    " * indentation
        for statement in statements:
            if isinstance(statement, Let):
                value_type = expression_type(statement.value, self.environment, self.vocabulary)
                c_type = "int64_t" if value_type == I64 else "bool"
                lines.append(
                    f"{prefix}{c_type} {statement.name} = {self.expression(statement.value)};"
                )
                lines.append(f"{prefix}if (!ok) return false;")
                self.environment[statement.name] = value_type
            elif isinstance(statement, Assign):
                lines.append(f"{prefix}{statement.name} = {self.expression(statement.value)};")
                lines.append(f"{prefix}if (!ok) return false;")
            elif isinstance(statement, ForRange):
                start_name = self.temporary("start")
                stop_name = self.temporary("stop")
                lines.append(f"{prefix}int64_t {start_name} = {self.expression(statement.start)};")
                lines.append(f"{prefix}int64_t {stop_name} = {self.expression(statement.stop)};")
                lines.append(f"{prefix}if (!ok) return false;")
                lines.append(
                    f"{prefix}for (int64_t {statement.index} = {start_name}; {statement.index} < {stop_name};) {{"
                )
                lines.append(
                    f"{prefix}    if (++lai_loop_steps > UINT64_C({MAX_RUNTIME_STEPS})) return false;"
                )
                self.environment[statement.index] = I64
                lines.extend(self.block(statement.body, indentation + 1))
                del self.environment[statement.index]
                lines.append(
                    f"{prefix}    if ({statement.index} == INT64_MAX) return false;"
                )
                lines.append(f"{prefix}    ++{statement.index};")
                lines.append(f"{prefix}}}")
            elif isinstance(statement, While):
                condition = self.temporary("while_condition")
                lines.append(f"{prefix}while (true) {{")
                lines.append(
                    f"{prefix}    bool {condition} = {self.expression(statement.condition)};"
                )
                lines.append(f"{prefix}    if (!ok) return false;")
                lines.append(f"{prefix}    if (!{condition}) break;")
                lines.append(
                    f"{prefix}    if (++lai_loop_steps > UINT64_C({MAX_RUNTIME_STEPS})) return false;"
                )
                lines.extend(self.block(statement.body, indentation + 1))
                lines.append(f"{prefix}}}")
            elif isinstance(statement, If):
                condition = self.temporary("condition")
                lines.append(f"{prefix}bool {condition} = {self.expression(statement.condition)};")
                lines.append(f"{prefix}if (!ok) return false;")
                lines.append(f"{prefix}if ({condition}) {{")
                lines.extend(self.block(statement.then_body, indentation + 1))
                if statement.else_body:
                    lines.append(f"{prefix}}} else {{")
                    lines.extend(self.block(statement.else_body, indentation + 1))
                lines.append(f"{prefix}}}")
            elif isinstance(statement, Return):
                if statement.value.op == "pair":
                    first, second = statement.value.arguments
                    lines.append(f"{prefix}int64_t lai_first = {self.expression(first)};")
                    lines.append(f"{prefix}int64_t lai_second = {self.expression(second)};")
                    lines.append(f"{prefix}if (!ok) return false;")
                    lines.append(f"{prefix}out->kind = LAI_PAIR;")
                    lines.append(f"{prefix}out->first = lai_first;")
                    lines.append(f"{prefix}out->second = lai_second;")
                else:
                    lines.append(
                        f"{prefix}int64_t lai_value = {self.expression(statement.value)};"
                    )
                    lines.append(f"{prefix}if (!ok) return false;")
                    lines.append(f"{prefix}out->kind = LAI_SCALAR;")
                    lines.append(f"{prefix}out->first = lai_value;")
                    lines.append(f"{prefix}out->second = INT64_C(0);")
                lines.append(f"{prefix}return true;")
        return lines


def generate_c_source(
    program: AlgorithmProgram,
    vocabulary: AlgorithmVocabulary,
    cases: Sequence[Mapping[str, JsonValue]],
) -> str:
    """Generate one self-checking C11 translation unit for an encoded program."""

    validate_program(program, vocabulary)
    compiler = _CCompiler(vocabulary)
    body = compiler.block(program.statements, 1)
    if not cases:
        raise AlgorithmLanguageError("generated C validation requires cases")
    case_arrays: list[str] = []
    case_rows: list[str] = []
    for index, case in enumerate(cases):
        nums = case.get("nums")
        target = case.get("target")
        expected = case.get("expected")
        if not isinstance(nums, list) or not all(
            isinstance(item, int) and not isinstance(item, bool) for item in nums
        ):
            raise AlgorithmLanguageError("generated C case array is invalid")
        target_value = _checked_i64(target, "generated C target")
        array_values = ", ".join(_c_i64(int(item)) for item in nums) or "INT64_C(0)"
        case_arrays.append(
            f"static const int64_t case_{index:03d}_nums[{max(1, len(nums))}] = {{{array_values}}};"
        )
        if program.return_type == I64:
            expected_value = _checked_i64(expected, "generated C expected scalar")
            kind = "LAI_SCALAR"
            first = _c_i64(expected_value)
            second = "INT64_C(0)"
        else:
            if not isinstance(expected, list) or len(expected) != 2:
                raise AlgorithmLanguageError("generated C expected pair is invalid")
            kind = "LAI_PAIR"
            first = _c_i64(_checked_i64(expected[0], "generated C expected pair"))
            second = _c_i64(_checked_i64(expected[1], "generated C expected pair"))
        case_rows.append(
            "    {"
            f"case_{index:03d}_nums, {len(nums)}U, {_c_i64(target_value)}, "
            f"{{{kind}, {first}, {second}}}"
            "},"
        )
    entry_comments = "\n".join(
        f"/* op_{entry.entry_id[7:15]} lowers to "
        f"{canonical_json_bytes(entry.lowering.to_document()).decode('utf-8')} */"
        for entry in vocabulary.entries
    )
    encoded_program_id = content_id(program.to_document(encoded=True))
    return f'''/* Generated by LAIcode {KERNEL_VERSION}; do not edit. */
/* task_id={program.task_id} encoded_program_id={encoded_program_id} vocabulary_id={vocabulary.vocabulary_id} */
#include <inttypes.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

typedef enum {{ LAI_SCALAR = 1, LAI_PAIR = 2 }} LaiResultKind;
typedef struct {{ LaiResultKind kind; int64_t first; int64_t second; }} LaiResult;
typedef struct {{ const int64_t *nums; size_t nums_len; int64_t target; LaiResult expected; }} LaiCase;

static inline int64_t lai_get(const int64_t *values, size_t count, int64_t index, bool *ok) {{
    if (index < 0 || (uint64_t)index >= (uint64_t)count) {{ *ok = false; return INT64_C(0); }}
    return values[index];
}}
static inline int64_t lai_add(int64_t left, int64_t right, bool *ok) {{
    if ((right > 0 && left > INT64_MAX - right) || (right < 0 && left < INT64_MIN - right)) {{
        *ok = false; return INT64_C(0);
    }}
    return left + right;
}}
static inline int64_t lai_sub(int64_t left, int64_t right, bool *ok) {{
    if ((right > 0 && left < INT64_MIN + right) || (right < 0 && left > INT64_MAX + right)) {{
        *ok = false; return INT64_C(0);
    }}
    return left - right;
}}
static inline int64_t lai_div(int64_t left, int64_t right, bool *ok) {{
    if (right == 0 || (left == INT64_MIN && right == -1)) {{ *ok = false; return INT64_C(0); }}
    return left / right;
}}
static inline int64_t lai_max(int64_t left, int64_t right) {{ return left > right ? left : right; }}
static inline bool lai_bool_and(bool left, bool right) {{ return left && right; }}

{entry_comments}
static bool lai_run(const int64_t *nums, size_t nums_len, int64_t target, LaiResult *out) {{
    if (nums_len > (size_t)INT64_MAX) return false;
    bool ok = true;
    uint64_t lai_loop_steps = UINT64_C(0);
    (void)nums;
    (void)target;
{chr(10).join(body)}
    return false;
}}

{chr(10).join(case_arrays)}
static const LaiCase cases[{len(cases)}] = {{
{chr(10).join(case_rows)}
}};

static uint64_t fold(uint64_t state, int64_t value) {{
    uint64_t word = (uint64_t)value;
    return (state << 7U) ^ (state >> 3U) ^ word ^ UINT64_C(0x9e3779b97f4a7c15);
}}

int main(void) {{
    uint64_t checksum = UINT64_C(0x6a09e667f3bcc909);
    for (size_t index = 0; index < {len(cases)}U; ++index) {{
        LaiResult actual = {{LAI_SCALAR, INT64_C(0), INT64_C(0)}};
        if (!lai_run(cases[index].nums, cases[index].nums_len, cases[index].target, &actual)) return 10;
        if (actual.kind != cases[index].expected.kind || actual.first != cases[index].expected.first || actual.second != cases[index].expected.second) return 11;
        checksum = fold(checksum, actual.first);
        checksum = fold(checksum, actual.second);
    }}
    printf("cases=%zu\\n", (size_t){len(cases)}U);
    printf("checksum=%016" PRIx64 "\\n", checksum);
    return 0;
}}
'''
