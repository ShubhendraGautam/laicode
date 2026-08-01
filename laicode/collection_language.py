"""A1 typed collection language with bounded owned vectors and records."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence, TypeAlias

from .canonical import JsonValue, canonical_json_bytes, content_id


PROGRAM_SCHEMA_VERSION = "CollectionProgramV1"
ENCODED_PROGRAM_SCHEMA_VERSION = "EncodedCollectionProgramV1"
VOCABULARY_ENTRY_SCHEMA_VERSION = "CollectionVocabularyEntryV1"
VOCABULARY_SCHEMA_VERSION = "CollectionVocabularyV1"
KERNEL_VERSION = "OwnedVectorRecordKernelV1"
LEARNER_VERSION = "CrossTaskStatementPatternLearnerV1"

I64_MIN = -(1 << 63)
I64_MAX = (1 << 63) - 1
MAX_RUNTIME_STEPS = 100_000
MAX_TRACE_EVENTS = 256
MAX_STATEMENTS = 256
MAX_EXPRESSION_DEPTH = 32
MAX_OWNED_ELEMENTS = 256
MAX_RECORD_FIELDS = 8
MAX_VOCABULARY_ENTRIES = 16

I64 = "i64"
BOOL = "bool"
ARRAY_I64 = "array_i64"
VECTOR_I64 = "vector_i64"
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_CONTENT_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_ARITY = {
    "len": 1,
    "get": 2,
    "add": 2,
    "sub": 2,
    "max": 2,
    "eq": 2,
    "ne": 2,
    "lt": 2,
    "le": 2,
    "gt": 2,
    "ge": 2,
}
_I64_BINARY = {"add", "sub", "max"}
_I64_COMPARISON = {"eq", "ne", "lt", "le", "gt", "ge"}


class CollectionLanguageError(ValueError):
    """Raised when an A1 program violates the fixed collection kernel."""


def _valid_identifier(value: object) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _valid_content_id(value: object) -> bool:
    return isinstance(value, str) and _CONTENT_ID.fullmatch(value) is not None


def _checked_i64(value: object, description: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CollectionLanguageError(f"{description} must be an integer")
    if not I64_MIN <= value <= I64_MAX:
        raise CollectionLanguageError(f"{description} is outside signed i64")
    return value


@dataclass(frozen=True)
class Expression:
    op: str
    arguments: tuple["Expression", ...] = ()
    name: str | None = None
    value: int | None = None

    def __post_init__(self) -> None:
        if self.op == "const":
            _checked_i64(self.value, "constant")
            if self.arguments or self.name is not None:
                raise CollectionLanguageError("constant expression has invalid fields")
            return
        if self.op == "var":
            if not _valid_identifier(self.name) or self.arguments or self.value is not None:
                raise CollectionLanguageError("variable expression has invalid fields")
            return
        arity = _ARITY.get(self.op)
        if arity is None:
            raise CollectionLanguageError(f"unknown collection expression {self.op!r}")
        if len(self.arguments) != arity or self.name is not None or self.value is not None:
            raise CollectionLanguageError(f"expression {self.op!r} has invalid fields")

    def to_document(self) -> dict[str, JsonValue]:
        if self.op == "const":
            assert self.value is not None
            return {"op": "const", "value": self.value}
        if self.op == "var":
            assert self.name is not None
            return {"op": "var", "name": self.name}
        return {"op": self.op, "arguments": [item.to_document() for item in self.arguments]}

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> "Expression":
        if not isinstance(value, dict) or not isinstance(value.get("op"), str):
            raise CollectionLanguageError("expression must be an object with an op")
        op = value["op"]
        if op == "const":
            if set(value) != {"op", "value"}:
                raise CollectionLanguageError("constant expression has invalid fields")
            return cls("const", value=_checked_i64(value["value"], "constant"))
        if op == "var":
            if set(value) != {"op", "name"} or not isinstance(value["name"], str):
                raise CollectionLanguageError("variable expression has invalid fields")
            return cls("var", name=value["name"])
        if set(value) != {"op", "arguments"} or not isinstance(value["arguments"], list):
            raise CollectionLanguageError(f"expression {op!r} has invalid fields")
        arguments = value["arguments"]
        if not all(isinstance(item, dict) for item in arguments):
            raise CollectionLanguageError("expression arguments must be objects")
        return cls(op, tuple(cls.from_document(item) for item in arguments))


@dataclass(frozen=True)
class RecordField:
    name: str
    field_type: str

    def __post_init__(self) -> None:
        if not _valid_identifier(self.name) or self.field_type not in {I64, BOOL, VECTOR_I64}:
            raise CollectionLanguageError("record field is invalid")

    def to_document(self) -> dict[str, JsonValue]:
        return {"name": self.name, "type": self.field_type}


@dataclass(frozen=True)
class ReturnType:
    kind: str
    name: str | None = None
    fields: tuple[RecordField, ...] = ()

    def __post_init__(self) -> None:
        if self.kind == "vector":
            if self.name is not None or self.fields:
                raise CollectionLanguageError("vector return type has invalid fields")
            return
        if self.kind != "record" or not _valid_identifier(self.name):
            raise CollectionLanguageError("collection return type is invalid")
        if not 2 <= len(self.fields) <= MAX_RECORD_FIELDS:
            raise CollectionLanguageError("record field count is invalid")
        names = tuple(field.name for field in self.fields)
        if len(set(names)) != len(names):
            raise CollectionLanguageError("record field names must be unique")
        if sum(field.field_type == VECTOR_I64 for field in self.fields) != 1:
            raise CollectionLanguageError("record must contain exactly one vector field")

    def to_document(self) -> dict[str, JsonValue]:
        if self.kind == "vector":
            return {"kind": "vector", "element_type": I64}
        assert self.name is not None
        return {
            "kind": "record",
            "name": self.name,
            "fields": [field.to_document() for field in self.fields],
        }

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> "ReturnType":
        if not isinstance(value, dict) or not isinstance(value.get("kind"), str):
            raise CollectionLanguageError("return type must be an object")
        if value["kind"] == "vector":
            if value != {"kind": "vector", "element_type": I64}:
                raise CollectionLanguageError("vector return type is invalid")
            return cls("vector")
        if set(value) != {"kind", "name", "fields"} or value["kind"] != "record":
            raise CollectionLanguageError("record return type has invalid fields")
        fields = value["fields"]
        if not isinstance(value["name"], str) or not isinstance(fields, list) or not all(
            isinstance(item, dict) and set(item) == {"name", "type"}
            and isinstance(item["name"], str) and isinstance(item["type"], str)
            for item in fields
        ):
            raise CollectionLanguageError("record return fields are invalid")
        return cls(
            "record",
            value["name"],
            tuple(RecordField(item["name"], item["type"]) for item in fields),
        )


VECTOR_RETURN = ReturnType("vector")


@dataclass(frozen=True)
class Let:
    name: str
    value: Expression


@dataclass(frozen=True)
class Assign:
    name: str
    value: Expression


@dataclass(frozen=True)
class OwnVector:
    name: str
    capacity: Expression


@dataclass(frozen=True)
class ForRange:
    index: str
    start: Expression
    stop: Expression
    body: tuple["Statement", ...]


@dataclass(frozen=True)
class If:
    condition: Expression
    then_body: tuple["Statement", ...]
    else_body: tuple["Statement", ...]


@dataclass(frozen=True)
class Push:
    vector: str
    value: Expression


@dataclass(frozen=True)
class Intrinsic:
    entry_id: str
    arguments: tuple[Expression, ...]


@dataclass(frozen=True)
class Return:
    fields: tuple[tuple[str, Expression], ...]


Statement: TypeAlias = Let | Assign | OwnVector | ForRange | If | Push | Intrinsic | Return


def statement_to_document(statement: Statement) -> dict[str, JsonValue]:
    if isinstance(statement, (Let, Assign)):
        return {
            "op": "let" if isinstance(statement, Let) else "assign",
            "name": statement.name,
            "value": statement.value.to_document(),
        }
    if isinstance(statement, OwnVector):
        return {"op": "own_vector", "name": statement.name, "capacity": statement.capacity.to_document()}
    if isinstance(statement, ForRange):
        return {
            "op": "for_range",
            "index": statement.index,
            "start": statement.start.to_document(),
            "stop": statement.stop.to_document(),
            "body": [statement_to_document(item) for item in statement.body],
        }
    if isinstance(statement, If):
        return {
            "op": "if",
            "condition": statement.condition.to_document(),
            "then": [statement_to_document(item) for item in statement.then_body],
            "else": [statement_to_document(item) for item in statement.else_body],
        }
    if isinstance(statement, Push):
        return {"op": "push", "vector": statement.vector, "value": statement.value.to_document()}
    if isinstance(statement, Intrinsic):
        return {
            "op": "intrinsic",
            "entry_id": statement.entry_id,
            "arguments": [item.to_document() for item in statement.arguments],
        }
    if isinstance(statement, Return):
        return {
            "op": "return",
            "fields": [
                {"name": name, "value": value.to_document()} for name, value in statement.fields
            ],
        }
    raise AssertionError("unknown collection statement")


def statement_from_document(value: Mapping[str, object]) -> Statement:
    if not isinstance(value, dict) or not isinstance(value.get("op"), str):
        raise CollectionLanguageError("statement must be an object with an op")
    op = value["op"]

    def expression(field: str) -> Expression:
        item = value.get(field)
        if not isinstance(item, dict):
            raise CollectionLanguageError(f"statement {op!r} omits {field}")
        return Expression.from_document(item)

    def block(field: str) -> tuple[Statement, ...]:
        item = value.get(field)
        if not isinstance(item, list) or not all(isinstance(row, dict) for row in item):
            raise CollectionLanguageError(f"statement {op!r} has an invalid {field} block")
        return tuple(statement_from_document(row) for row in item)

    if op in {"let", "assign"}:
        if set(value) != {"op", "name", "value"} or not isinstance(value["name"], str):
            raise CollectionLanguageError(f"statement {op!r} has invalid fields")
        return (Let if op == "let" else Assign)(value["name"], expression("value"))
    if op == "own_vector":
        if set(value) != {"op", "name", "capacity"} or not isinstance(value["name"], str):
            raise CollectionLanguageError("own_vector statement has invalid fields")
        return OwnVector(value["name"], expression("capacity"))
    if op == "for_range":
        if set(value) != {"op", "index", "start", "stop", "body"} or not isinstance(value["index"], str):
            raise CollectionLanguageError("for_range statement has invalid fields")
        return ForRange(value["index"], expression("start"), expression("stop"), block("body"))
    if op == "if":
        if set(value) != {"op", "condition", "then", "else"}:
            raise CollectionLanguageError("if statement has invalid fields")
        return If(expression("condition"), block("then"), block("else"))
    if op == "push":
        if set(value) != {"op", "vector", "value"} or not isinstance(value["vector"], str):
            raise CollectionLanguageError("push statement has invalid fields")
        return Push(value["vector"], expression("value"))
    if op == "intrinsic":
        arguments = value.get("arguments")
        if set(value) != {"op", "entry_id", "arguments"} or not isinstance(value["entry_id"], str) or not isinstance(arguments, list) or not all(isinstance(item, dict) for item in arguments):
            raise CollectionLanguageError("intrinsic statement has invalid fields")
        return Intrinsic(value["entry_id"], tuple(Expression.from_document(item) for item in arguments))
    if op == "return":
        fields = value.get("fields")
        if set(value) != {"op", "fields"} or not isinstance(fields, list) or not all(
            isinstance(item, dict) and set(item) == {"name", "value"}
            and isinstance(item["name"], str) and isinstance(item["value"], dict)
            for item in fields
        ):
            raise CollectionLanguageError("return statement has invalid fields")
        return Return(tuple((item["name"], Expression.from_document(item["value"])) for item in fields))
    raise CollectionLanguageError(f"unknown collection statement operation {op!r}")


@dataclass(frozen=True)
class CollectionProgram:
    task_id: str
    return_type: ReturnType
    statements: tuple[Statement, ...]

    def __post_init__(self) -> None:
        if not _valid_identifier(self.task_id):
            raise CollectionLanguageError("collection task identity is invalid")
        count = len(tuple(_walk_statements(self.statements)))
        if not self.statements or count > MAX_STATEMENTS:
            raise CollectionLanguageError("collection statement count is invalid")

    def to_document(self, *, encoded: bool = False) -> dict[str, JsonValue]:
        return {
            "schema_version": ENCODED_PROGRAM_SCHEMA_VERSION if encoded else PROGRAM_SCHEMA_VERSION,
            "kernel_version": KERNEL_VERSION,
            "task_id": self.task_id,
            "parameters": [
                {"name": "nums", "type": ARRAY_I64},
                {"name": "target", "type": I64},
            ],
            "return_type": self.return_type.to_document(),
            "effects": ["bounded_local_vector_mutation"],
            "statements": [statement_to_document(item) for item in self.statements],
        }

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> "CollectionProgram":
        expected = {"schema_version", "kernel_version", "task_id", "parameters", "return_type", "effects", "statements"}
        if not isinstance(value, dict) or set(value) != expected:
            raise CollectionLanguageError("collection program has invalid fields")
        if value["schema_version"] not in {PROGRAM_SCHEMA_VERSION, ENCODED_PROGRAM_SCHEMA_VERSION} or value["kernel_version"] != KERNEL_VERSION:
            raise CollectionLanguageError("collection program has an unknown schema or kernel")
        if value["parameters"] != [{"name": "nums", "type": ARRAY_I64}, {"name": "target", "type": I64}] or value["effects"] != ["bounded_local_vector_mutation"]:
            raise CollectionLanguageError("collection program ABI is invalid")
        statements = value["statements"]
        if not isinstance(value["task_id"], str) or not isinstance(value["return_type"], dict) or not isinstance(statements, list) or not all(isinstance(item, dict) for item in statements):
            raise CollectionLanguageError("collection program payload is invalid")
        return cls(value["task_id"], ReturnType.from_document(value["return_type"]), tuple(statement_from_document(item) for item in statements))

    @property
    def program_id(self) -> str:
        return content_id(self.to_document())


def _walk_statements(statements: Sequence[Statement]) -> Iterable[Statement]:
    for statement in statements:
        yield statement
        if isinstance(statement, ForRange):
            yield from _walk_statements(statement.body)
        elif isinstance(statement, If):
            yield from _walk_statements(statement.then_body)
            yield from _walk_statements(statement.else_body)


_LOWERINGS: dict[str, dict[str, JsonValue]] = {
    "push_indexed": {
        "op": "push",
        "vector": {"op": "hole", "index": 0, "type": VECTOR_I64},
        "value": {
            "op": "get",
            "arguments": [
                {"op": "hole", "index": 1, "type": ARRAY_I64},
                {"op": "hole", "index": 2, "type": I64},
            ],
        },
    },
    "append_indexed_if": {
        "op": "if",
        "condition": {"op": "hole", "index": 1, "type": BOOL},
        "then": [
            {
                "op": "push",
                "vector": {"op": "hole", "index": 0, "type": VECTOR_I64},
                "value": {
                    "op": "get",
                    "arguments": [
                        {"op": "hole", "index": 2, "type": ARRAY_I64},
                        {"op": "hole", "index": 3, "type": I64},
                    ],
                },
            }
        ],
        "else": [],
    },
}
_ENTRY_TYPES = {
    "push_indexed": (VECTOR_I64, ARRAY_I64, I64),
    "append_indexed_if": (VECTOR_I64, BOOL, ARRAY_I64, I64),
}
_ENTRY_OPERATOR_COUNTS = {"push_indexed": 2, "append_indexed_if": 3}


@dataclass(frozen=True)
class CollectionVocabularyEntry:
    kind: str
    evidence_catalog_id: str
    parent_vocabulary_id: str
    learned_cycle: int
    training_task_ids: tuple[str, ...]
    occurrences: int
    estimated_dispatch_saving: int
    learner_id: str = LEARNER_VERSION

    def __post_init__(self) -> None:
        if self.kind not in _LOWERINGS:
            raise CollectionLanguageError("collection vocabulary kind is invalid")
        if not _valid_content_id(self.evidence_catalog_id) or not _valid_content_id(self.parent_vocabulary_id):
            raise CollectionLanguageError("collection vocabulary provenance is invalid")
        if isinstance(self.learned_cycle, bool) or self.learned_cycle < 1 or self.training_task_ids != tuple(sorted(set(self.training_task_ids))) or len(self.training_task_ids) < 2 or self.occurrences < 2 or self.estimated_dispatch_saving < 1 or self.learner_id != LEARNER_VERSION:
            raise CollectionLanguageError("collection vocabulary evidence is invalid")

    @property
    def argument_types(self) -> tuple[str, ...]:
        return _ENTRY_TYPES[self.kind]

    @property
    def entry_id(self) -> str:
        return content_id(self.to_document())

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": VOCABULARY_ENTRY_SCHEMA_VERSION,
            "kind": self.kind,
            "argument_types": list(self.argument_types),
            "lowering": _LOWERINGS[self.kind],
            "learner": {"id": self.learner_id, "cycle": self.learned_cycle},
            "provenance": {
                "evidence_catalog_id": self.evidence_catalog_id,
                "parent_vocabulary_id": self.parent_vocabulary_id,
                "training_task_ids": list(self.training_task_ids),
            },
            "evidence": {
                "cross_task_occurrences": self.occurrences,
                "primitive_operator_count": _ENTRY_OPERATOR_COUNTS[self.kind],
                "estimated_dispatch_saving": self.estimated_dispatch_saving,
            },
        }

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> "CollectionVocabularyEntry":
        expected = {"schema_version", "kind", "argument_types", "lowering", "learner", "provenance", "evidence"}
        if not isinstance(value, dict) or set(value) != expected or value["schema_version"] != VOCABULARY_ENTRY_SCHEMA_VERSION or not isinstance(value["kind"], str):
            raise CollectionLanguageError("collection vocabulary entry is invalid")
        kind = value["kind"]
        if kind not in _LOWERINGS or value["argument_types"] != list(_ENTRY_TYPES[kind]) or value["lowering"] != _LOWERINGS[kind]:
            raise CollectionLanguageError("collection vocabulary lowering differs")
        learner, provenance, evidence = value["learner"], value["provenance"], value["evidence"]
        if not isinstance(learner, dict) or set(learner) != {"id", "cycle"} or not isinstance(provenance, dict) or set(provenance) != {"evidence_catalog_id", "parent_vocabulary_id", "training_task_ids"} or not isinstance(evidence, dict) or set(evidence) != {"cross_task_occurrences", "primitive_operator_count", "estimated_dispatch_saving"}:
            raise CollectionLanguageError("collection vocabulary entry evidence is malformed")
        tasks = provenance["training_task_ids"]
        if not isinstance(tasks, list) or not all(isinstance(item, str) for item in tasks) or evidence["primitive_operator_count"] != _ENTRY_OPERATOR_COUNTS[kind]:
            raise CollectionLanguageError("collection vocabulary entry evidence differs")
        return cls(kind, provenance["evidence_catalog_id"], provenance["parent_vocabulary_id"], learner["cycle"], tuple(tasks), evidence["cross_task_occurrences"], evidence["estimated_dispatch_saving"], learner["id"])


@dataclass(frozen=True)
class CollectionVocabulary:
    parent_vocabulary_id: str | None
    entries: tuple[CollectionVocabularyEntry, ...]

    def __post_init__(self) -> None:
        if self.parent_vocabulary_id is not None and not _valid_content_id(self.parent_vocabulary_id):
            raise CollectionLanguageError("collection vocabulary parent is invalid")
        if len(self.entries) > MAX_VOCABULARY_ENTRIES or self.entries != tuple(sorted(self.entries, key=lambda item: item.entry_id)):
            raise CollectionLanguageError("collection vocabulary entries are invalid")
        if len({item.entry_id for item in self.entries}) != len(self.entries) or len({item.kind for item in self.entries}) != len(self.entries):
            raise CollectionLanguageError("collection vocabulary entries must be unique")

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": VOCABULARY_SCHEMA_VERSION,
            "kernel_version": KERNEL_VERSION,
            "parent_vocabulary_id": self.parent_vocabulary_id,
            "entry_ids": [item.entry_id for item in self.entries],
            "entries": [item.to_document() for item in self.entries],
        }

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> "CollectionVocabulary":
        expected = {"schema_version", "kernel_version", "parent_vocabulary_id", "entry_ids", "entries"}
        if not isinstance(value, dict) or set(value) != expected or value["schema_version"] != VOCABULARY_SCHEMA_VERSION or value["kernel_version"] != KERNEL_VERSION:
            raise CollectionLanguageError("collection vocabulary is invalid")
        parent, entry_ids, entries = value["parent_vocabulary_id"], value["entry_ids"], value["entries"]
        if parent is not None and not isinstance(parent, str) or not isinstance(entry_ids, list) or not isinstance(entries, list) or not all(isinstance(item, dict) for item in entries):
            raise CollectionLanguageError("collection vocabulary payload is invalid")
        parsed = tuple(CollectionVocabularyEntry.from_document(item) for item in entries)
        result = cls(parent, parsed)
        if entry_ids != [item.entry_id for item in parsed]:
            raise CollectionLanguageError("collection vocabulary entry identities differ")
        return result

    @property
    def vocabulary_id(self) -> str:
        return content_id(self.to_document())

    def by_id(self) -> dict[str, CollectionVocabularyEntry]:
        return {item.entry_id: item for item in self.entries}

    def by_kind(self) -> dict[str, CollectionVocabularyEntry]:
        return {item.kind: item for item in self.entries}


EMPTY_COLLECTION_VOCABULARY = CollectionVocabulary(None, ())


def expression_type(expression: Expression, environment: Mapping[str, str], *, depth: int = 0) -> str:
    if depth > MAX_EXPRESSION_DEPTH:
        raise CollectionLanguageError("collection expression is too deeply nested")
    if expression.op == "const":
        return I64
    if expression.op == "var":
        assert expression.name is not None
        try:
            return environment[expression.name]
        except KeyError as error:
            raise CollectionLanguageError(f"collection variable {expression.name!r} is not defined") from error
    argument_types = tuple(expression_type(item, environment, depth=depth + 1) for item in expression.arguments)
    if expression.op == "len" and argument_types[0] in {ARRAY_I64, VECTOR_I64}:
        return I64
    if expression.op == "get" and argument_types[0] in {ARRAY_I64, VECTOR_I64} and argument_types[1] == I64:
        return I64
    if expression.op in _I64_BINARY and argument_types == (I64, I64):
        return I64
    if expression.op in _I64_COMPARISON and argument_types == (I64, I64):
        return BOOL
    raise CollectionLanguageError(f"collection expression {expression.op!r} has incompatible operand types")


def validate_program(program: CollectionProgram, vocabulary: CollectionVocabulary = EMPTY_COLLECTION_VOCABULARY) -> None:
    environment: dict[str, str] = {"nums": ARRAY_I64, "target": I64}

    def block(statements: Sequence[Statement], *, nested: bool) -> None:
        for statement in statements:
            if isinstance(statement, Let):
                if nested or not _valid_identifier(statement.name) or statement.name in environment:
                    raise CollectionLanguageError("scalar declarations are top-level and uniquely named")
                value_type = expression_type(statement.value, environment)
                if value_type not in {I64, BOOL}:
                    raise CollectionLanguageError("scalar declaration type is invalid")
                environment[statement.name] = value_type
            elif isinstance(statement, OwnVector):
                if nested or not _valid_identifier(statement.name) or statement.name in environment or expression_type(statement.capacity, environment) != I64:
                    raise CollectionLanguageError("owned vector declaration is invalid")
                environment[statement.name] = VECTOR_I64
            elif isinstance(statement, Assign):
                if statement.name not in environment or environment[statement.name] not in {I64, BOOL} or expression_type(statement.value, environment) != environment[statement.name]:
                    raise CollectionLanguageError("collection assignment type differs")
            elif isinstance(statement, ForRange):
                if not statement.body or not _valid_identifier(statement.index) or statement.index in environment or expression_type(statement.start, environment) != I64 or expression_type(statement.stop, environment) != I64:
                    raise CollectionLanguageError("collection for_range is invalid")
                environment[statement.index] = I64
                block(statement.body, nested=True)
                del environment[statement.index]
            elif isinstance(statement, If):
                if expression_type(statement.condition, environment) != BOOL:
                    raise CollectionLanguageError("collection if condition must be bool")
                block(statement.then_body, nested=True)
                block(statement.else_body, nested=True)
            elif isinstance(statement, Push):
                if environment.get(statement.vector) != VECTOR_I64 or expression_type(statement.value, environment) != I64:
                    raise CollectionLanguageError("collection push is mistyped")
            elif isinstance(statement, Intrinsic):
                entry = vocabulary.by_id().get(statement.entry_id)
                if entry is None:
                    raise CollectionLanguageError("collection intrinsic is not in the vocabulary")
                actual = tuple(expression_type(item, environment) for item in statement.arguments)
                if actual != entry.argument_types:
                    raise CollectionLanguageError("collection intrinsic arguments are mistyped")
                if statement.arguments[0].op != "var":
                    raise CollectionLanguageError("collection intrinsic vector must be a variable")
            elif isinstance(statement, Return):
                if nested:
                    raise CollectionLanguageError("collection return must be top-level")
                names = tuple(name for name, _ in statement.fields)
                if program.return_type.kind == "vector":
                    expected = (("value", VECTOR_I64),)
                else:
                    expected = tuple((field.name, field.field_type) for field in program.return_type.fields)
                actual = tuple((name, expression_type(value, environment)) for name, value in statement.fields)
                if actual != expected or names != tuple(name for name, _ in expected):
                    raise CollectionLanguageError("collection return fields are mistyped")
            else:
                raise AssertionError("unknown collection statement")

    block(program.statements, nested=False)
    if not isinstance(program.statements[-1], Return) or any(isinstance(item, Return) for item in program.statements[:-1]):
        raise CollectionLanguageError("collection program must end with its only return")


def _motifs(statement: Statement) -> Iterable[str]:
    if isinstance(statement, Push) and statement.value.op == "get":
        yield "push_indexed"
    if isinstance(statement, If) and not statement.else_body and len(statement.then_body) == 1 and isinstance(statement.then_body[0], Push) and statement.then_body[0].value.op == "get":
        yield "append_indexed_if"
    if isinstance(statement, ForRange):
        for item in statement.body:
            yield from _motifs(item)
    elif isinstance(statement, If):
        for item in (*statement.then_body, *statement.else_body):
            yield from _motifs(item)


def learn_collection_intrinsic(programs: Sequence[CollectionProgram], vocabulary: CollectionVocabulary, *, evidence_catalog_id: str, cycle: int) -> CollectionVocabularyEntry:
    if len({program.task_id for program in programs}) < 2:
        raise CollectionLanguageError("collection learner requires at least two tasks")
    counts: dict[str, int] = {}
    tasks: dict[str, set[str]] = {}
    for program in programs:
        validate_program(program)
        for statement in program.statements:
            for kind in _motifs(statement):
                counts[kind] = counts.get(kind, 0) + 1
                tasks.setdefault(kind, set()).add(program.task_id)
    existing = set(vocabulary.by_kind())
    eligible = [kind for kind in counts if kind not in existing and len(tasks[kind]) >= 2]
    if not eligible:
        raise CollectionLanguageError("collection learner found no cross-task statement pattern")
    kind = min(eligible, key=lambda item: (-(_ENTRY_OPERATOR_COUNTS[item] - 1) * counts[item], item))
    return CollectionVocabularyEntry(
        kind,
        evidence_catalog_id,
        vocabulary.vocabulary_id,
        cycle,
        tuple(sorted(tasks[kind])),
        counts[kind],
        (_ENTRY_OPERATOR_COUNTS[kind] - 1) * counts[kind],
    )


def extend_vocabulary(vocabulary: CollectionVocabulary, entry: CollectionVocabularyEntry) -> CollectionVocabulary:
    if entry.parent_vocabulary_id != vocabulary.vocabulary_id:
        raise CollectionLanguageError("collection vocabulary extension parent differs")
    return CollectionVocabulary(vocabulary.vocabulary_id, tuple(sorted((*vocabulary.entries, entry), key=lambda item: item.entry_id)))


def encode_program(program: CollectionProgram, vocabulary: CollectionVocabulary) -> CollectionProgram:
    validate_program(program)
    entries = vocabulary.by_kind()

    def block(statements: Sequence[Statement]) -> tuple[Statement, ...]:
        encoded: list[Statement] = []
        for statement in statements:
            if isinstance(statement, If) and "append_indexed_if" in entries and not statement.else_body and len(statement.then_body) == 1 and isinstance(statement.then_body[0], Push) and statement.then_body[0].value.op == "get":
                push = statement.then_body[0]
                array, index = push.value.arguments
                encoded.append(Intrinsic(entries["append_indexed_if"].entry_id, (Expression("var", name=push.vector), statement.condition, array, index)))
            elif isinstance(statement, Push) and "push_indexed" in entries and statement.value.op == "get":
                array, index = statement.value.arguments
                encoded.append(Intrinsic(entries["push_indexed"].entry_id, (Expression("var", name=statement.vector), array, index)))
            elif isinstance(statement, ForRange):
                encoded.append(ForRange(statement.index, statement.start, statement.stop, block(statement.body)))
            elif isinstance(statement, If):
                encoded.append(If(statement.condition, block(statement.then_body), block(statement.else_body)))
            else:
                encoded.append(statement)
        return tuple(encoded)

    result = CollectionProgram(program.task_id, program.return_type, block(program.statements))
    validate_program(result, vocabulary)
    return result


def intrinsic_uses(program: CollectionProgram) -> tuple[str, ...]:
    return tuple(statement.entry_id for statement in _walk_statements(program.statements) if isinstance(statement, Intrinsic))


class _VectorState:
    def __init__(self, capacity: int) -> None:
        if not 0 <= capacity <= MAX_OWNED_ELEMENTS:
            raise CollectionLanguageError("owned vector capacity is outside the kernel limit")
        self.capacity = capacity
        self.values: list[int] = []

    def push(self, value: int) -> None:
        if len(self.values) >= self.capacity:
            raise CollectionLanguageError("owned vector capacity was exceeded")
        self.values.append(_checked_i64(value, "owned vector element"))


RuntimeValue: TypeAlias = int | bool | tuple[int, ...] | _VectorState
CollectionResultValue: TypeAlias = tuple[int, ...] | Mapping[str, int | bool | tuple[int, ...]]


@dataclass(frozen=True)
class ExecutionResult:
    value: CollectionResultValue
    steps: int
    dispatches: int
    trace: tuple[Mapping[str, JsonValue], ...]
    trace_truncated: bool


class _Runtime:
    def __init__(self, nums: Sequence[int], target: int, vocabulary: CollectionVocabulary, *, trace: bool) -> None:
        if len(nums) > MAX_OWNED_ELEMENTS:
            raise CollectionLanguageError("collection input exceeds the A1 element limit")
        self.environment: dict[str, RuntimeValue] = {
            "nums": tuple(_checked_i64(item, "array element") for item in nums),
            "target": _checked_i64(target, "target"),
        }
        self.vocabulary = vocabulary
        self.steps = 0
        self.dispatches = 0
        self.events: list[Mapping[str, JsonValue]] = []
        self.trace_enabled = trace
        self.trace_truncated = False

    def tick(self, *, dispatch: bool = True) -> None:
        self.steps += 1
        if dispatch:
            self.dispatches += 1
        if self.steps > MAX_RUNTIME_STEPS:
            raise CollectionLanguageError("collection program exceeded its runtime budget")

    def event(self, value: Mapping[str, JsonValue]) -> None:
        if not self.trace_enabled:
            return
        if len(self.events) < MAX_TRACE_EVENTS:
            self.events.append(dict(value))
        else:
            self.trace_truncated = True


def _require_i64(value: RuntimeValue, operation: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CollectionLanguageError(f"{operation} requires i64")
    return value


def _require_bool(value: RuntimeValue, operation: str) -> bool:
    if not isinstance(value, bool):
        raise CollectionLanguageError(f"{operation} requires bool")
    return value


def _eval(expression: Expression, runtime: _Runtime) -> RuntimeValue:
    runtime.tick()
    if expression.op == "const":
        assert expression.value is not None
        return expression.value
    if expression.op == "var":
        assert expression.name is not None
        return runtime.environment[expression.name]
    arguments = tuple(_eval(item, runtime) for item in expression.arguments)
    if expression.op == "len":
        value = arguments[0]
        if isinstance(value, tuple):
            return len(value)
        if isinstance(value, _VectorState):
            return len(value.values)
        raise CollectionLanguageError("len requires an array or vector")
    if expression.op == "get":
        value, index_value = arguments
        index = _require_i64(index_value, "get")
        values = value if isinstance(value, tuple) else value.values if isinstance(value, _VectorState) else None
        if values is None or not 0 <= index < len(values):
            raise CollectionLanguageError("collection index is outside the value")
        return values[index]
    left = _require_i64(arguments[0], expression.op)
    right = _require_i64(arguments[1], expression.op)
    if expression.op == "add":
        return _checked_i64(left + right, "addition result")
    if expression.op == "sub":
        return _checked_i64(left - right, "subtraction result")
    if expression.op == "max":
        return max(left, right)
    return {"eq": left == right, "ne": left != right, "lt": left < right, "le": left <= right, "gt": left > right, "ge": left >= right}[expression.op]


def _run_block(statements: Sequence[Statement], runtime: _Runtime) -> CollectionResultValue | None:
    for statement in statements:
        if isinstance(statement, Let):
            runtime.tick()
            runtime.environment[statement.name] = _eval(statement.value, runtime)
            runtime.event({"event": "let", "name": statement.name})
        elif isinstance(statement, OwnVector):
            runtime.tick()
            capacity = _require_i64(_eval(statement.capacity, runtime), "vector capacity")
            runtime.environment[statement.name] = _VectorState(capacity)
            runtime.event({"event": "own_vector", "name": statement.name, "capacity": capacity})
        elif isinstance(statement, Assign):
            runtime.tick()
            runtime.environment[statement.name] = _eval(statement.value, runtime)
            runtime.event({"event": "assign", "name": statement.name})
        elif isinstance(statement, Push):
            runtime.tick()
            vector = runtime.environment[statement.vector]
            if not isinstance(vector, _VectorState):
                raise CollectionLanguageError("push target is not an owned vector")
            vector.push(_require_i64(_eval(statement.value, runtime), "push"))
            runtime.event({"event": "push", "vector": statement.vector, "length": len(vector.values)})
        elif isinstance(statement, Intrinsic):
            runtime.tick()
            entry = runtime.vocabulary.by_id()[statement.entry_id]
            vector_name = statement.arguments[0].name
            assert vector_name is not None
            vector = runtime.environment[vector_name]
            if not isinstance(vector, _VectorState):
                raise CollectionLanguageError("intrinsic target is not an owned vector")
            if entry.kind == "push_indexed":
                array = _eval(statement.arguments[1], runtime)
                index = _require_i64(_eval(statement.arguments[2], runtime), "push_indexed")
                if not isinstance(array, tuple) or not 0 <= index < len(array):
                    raise CollectionLanguageError("push_indexed is outside the input")
                vector.push(array[index])
            else:
                condition = _require_bool(_eval(statement.arguments[1], runtime), "append_indexed_if")
                if condition:
                    array = _eval(statement.arguments[2], runtime)
                    index = _require_i64(_eval(statement.arguments[3], runtime), "append_indexed_if")
                    if not isinstance(array, tuple) or not 0 <= index < len(array):
                        raise CollectionLanguageError("append_indexed_if is outside the input")
                    vector.push(array[index])
            runtime.event({"event": "intrinsic", "entry_id": statement.entry_id, "kind": entry.kind, "length": len(vector.values)})
        elif isinstance(statement, ForRange):
            runtime.tick()
            start = _require_i64(_eval(statement.start, runtime), "for start")
            stop = _require_i64(_eval(statement.stop, runtime), "for stop")
            for index in range(start, stop):
                runtime.tick(dispatch=False)
                runtime.environment[statement.index] = _checked_i64(index, "loop index")
                result = _run_block(statement.body, runtime)
                if result is not None:
                    return result
            runtime.environment.pop(statement.index, None)
        elif isinstance(statement, If):
            runtime.tick()
            condition = _require_bool(_eval(statement.condition, runtime), "if")
            result = _run_block(statement.then_body if condition else statement.else_body, runtime)
            if result is not None:
                return result
        elif isinstance(statement, Return):
            runtime.tick()
            values: dict[str, int | bool | tuple[int, ...]] = {}
            for name, expression in statement.fields:
                value = _eval(expression, runtime)
                if isinstance(value, _VectorState):
                    values[name] = tuple(value.values)
                elif isinstance(value, (int, bool)):
                    values[name] = value
                else:
                    raise CollectionLanguageError("collection return value is invalid")
            runtime.event({"event": "return", "fields": list(values)})
            if tuple(values) == ("value",):
                result = values["value"]
                assert isinstance(result, tuple)
                return result
            return values
    return None


def execute_program(program: CollectionProgram, nums: Sequence[int], target: int, vocabulary: CollectionVocabulary = EMPTY_COLLECTION_VOCABULARY, *, trace: bool = False) -> ExecutionResult:
    validate_program(program, vocabulary)
    runtime = _Runtime(nums, target, vocabulary, trace=trace)
    value = _run_block(program.statements, runtime)
    if value is None:
        raise CollectionLanguageError("collection program completed without returning")
    return ExecutionResult(value, runtime.steps, runtime.dispatches, tuple(runtime.events), runtime.trace_truncated)


def _render_expression(expression: Expression, vocabulary: CollectionVocabulary) -> str:
    if expression.op == "const":
        return str(expression.value)
    if expression.op == "var":
        assert expression.name is not None
        return expression.name
    arguments = [_render_expression(item, vocabulary) for item in expression.arguments]
    if expression.op == "len":
        return f"len({arguments[0]})"
    if expression.op == "get":
        return f"{arguments[0]}[{arguments[1]}]"
    if expression.op == "max":
        return f"max({arguments[0]}, {arguments[1]})"
    symbols = {"add": "+", "sub": "-", "eq": "==", "ne": "!=", "lt": "<", "le": "<=", "gt": ">", "ge": ">="}
    return f"({arguments[0]} {symbols[expression.op]} {arguments[1]})"


def render_program(program: CollectionProgram, vocabulary: CollectionVocabulary = EMPTY_COLLECTION_VOCABULARY) -> str:
    validate_program(program, vocabulary)
    if program.return_type.kind == "vector":
        return_name = "vector<i64>"
        record = ""
    else:
        assert program.return_type.name is not None
        return_name = program.return_type.name
        record_fields = ", ".join(f"{field.name}: {field.field_type.replace('_', '<', 1) + ('>' if field.field_type == VECTOR_I64 else '')}" for field in program.return_type.fields)
        record = f"record {return_name} {{ {record_fields} }}\n\n"
    def block(statements: Sequence[Statement], indentation: int) -> list[str]:
        prefix = "    " * indentation
        lines: list[str] = []
        for statement in statements:
            if isinstance(statement, Let):
                lines.append(f"{prefix}let {statement.name} = {_render_expression(statement.value, vocabulary)}")
            elif isinstance(statement, OwnVector):
                lines.append(f"{prefix}own {statement.name}: vector<i64> capacity {_render_expression(statement.capacity, vocabulary)}")
            elif isinstance(statement, Assign):
                lines.append(f"{prefix}{statement.name} = {_render_expression(statement.value, vocabulary)}")
            elif isinstance(statement, Push):
                lines.append(f"{prefix}{statement.vector}.push({_render_expression(statement.value, vocabulary)})")
            elif isinstance(statement, Intrinsic):
                entry = vocabulary.by_id()[statement.entry_id]
                args = ", ".join(_render_expression(item, vocabulary) for item in statement.arguments)
                lines.append(f"{prefix}op_{statement.entry_id[7:15]}<{entry.kind}>({args})")
            elif isinstance(statement, ForRange):
                lines.append(f"{prefix}for {statement.index} in {_render_expression(statement.start, vocabulary)}..{_render_expression(statement.stop, vocabulary)} {{")
                lines.extend(block(statement.body, indentation + 1))
                lines.append(f"{prefix}}}")
            elif isinstance(statement, If):
                lines.append(f"{prefix}if {_render_expression(statement.condition, vocabulary)} {{")
                lines.extend(block(statement.then_body, indentation + 1))
                if statement.else_body:
                    lines.append(f"{prefix}}} else {{")
                    lines.extend(block(statement.else_body, indentation + 1))
                lines.append(f"{prefix}}}")
            elif isinstance(statement, Return):
                if program.return_type.kind == "vector":
                    lines.append(f"{prefix}return {_render_expression(statement.fields[0][1], vocabulary)}")
                else:
                    fields = ", ".join(f"{name}: {_render_expression(value, vocabulary)}" for name, value in statement.fields)
                    lines.append(f"{prefix}return {return_name} {{ {fields} }}")
        return lines

    return record + f"algorithm {program.task_id}(nums: array<i64>, target: i64) -> {return_name} {{\n" + "\n".join(block(program.statements, 1)) + "\n}\n"


def _c_i64(value: int) -> str:
    if value == I64_MIN:
        return "INT64_MIN"
    return f"INT64_C({value})"


class _CCompiler:
    def __init__(self, program: CollectionProgram, vocabulary: CollectionVocabulary) -> None:
        self.program = program
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
        arguments = [self.expression(item) for item in value.arguments]
        if value.op == "len":
            argument_type = expression_type(value.arguments[0], self.environment)
            return "((int64_t)nums_len)" if argument_type == ARRAY_I64 else f"lai_vector_len(&{arguments[0]})"
        if value.op == "get":
            argument_type = expression_type(value.arguments[0], self.environment)
            if argument_type == ARRAY_I64:
                return f"lai_input_get({arguments[0]}, nums_len, {arguments[1]}, &ok)"
            return f"lai_vector_get(&{arguments[0]}, {arguments[1]}, &ok)"
        if value.op == "add":
            return f"lai_add({arguments[0]}, {arguments[1]}, &ok)"
        if value.op == "sub":
            return f"lai_sub({arguments[0]}, {arguments[1]}, &ok)"
        if value.op == "max":
            return f"lai_max({arguments[0]}, {arguments[1]})"
        symbols = {"eq": "==", "ne": "!=", "lt": "<", "le": "<=", "gt": ">", "ge": ">="}
        return f"({arguments[0]} {symbols[value.op]} {arguments[1]})"

    def block(self, statements: Sequence[Statement], indentation: int) -> list[str]:
        prefix = "    " * indentation
        lines: list[str] = []
        for statement in statements:
            if isinstance(statement, Let):
                value_type = expression_type(statement.value, self.environment)
                c_type = "bool" if value_type == BOOL else "int64_t"
                lines.append(f"{prefix}{c_type} {statement.name} = {self.expression(statement.value)};")
                lines.append(f"{prefix}if (!ok) return false;")
                self.environment[statement.name] = value_type
            elif isinstance(statement, OwnVector):
                capacity = self.temporary("capacity")
                lines.append(f"{prefix}int64_t {capacity} = {self.expression(statement.capacity)};")
                lines.append(f"{prefix}if (!ok || {capacity} < 0 || {capacity} > LAI_MAX_OWNED) return false;")
                lines.append(f"{prefix}LaiVector {statement.name} = {{.len = 0U, .capacity = (size_t){capacity}}};")
                self.environment[statement.name] = VECTOR_I64
            elif isinstance(statement, Assign):
                lines.append(f"{prefix}{statement.name} = {self.expression(statement.value)};")
                lines.append(f"{prefix}if (!ok) return false;")
            elif isinstance(statement, Push):
                lines.append(f"{prefix}if (!lai_vector_push(&{statement.vector}, {self.expression(statement.value)}, &ok) || !ok) return false;")
            elif isinstance(statement, Intrinsic):
                entry = self.vocabulary.by_id()[statement.entry_id]
                vector = statement.arguments[0].name
                assert vector is not None
                lines.append(f"{prefix}/* learned op_{entry.entry_id[7:15]} lowers to {entry.kind} */")
                if entry.kind == "push_indexed":
                    value = Expression("get", (statement.arguments[1], statement.arguments[2]))
                    lines.append(f"{prefix}if (!lai_vector_push(&{vector}, {self.expression(value)}, &ok) || !ok) return false;")
                else:
                    condition = self.temporary("append_condition")
                    lines.append(f"{prefix}bool {condition} = {self.expression(statement.arguments[1])};")
                    lines.append(f"{prefix}if (!ok) return false;")
                    lines.append(f"{prefix}if ({condition}) {{")
                    value = Expression("get", (statement.arguments[2], statement.arguments[3]))
                    lines.append(f"{prefix}    if (!lai_vector_push(&{vector}, {self.expression(value)}, &ok) || !ok) return false;")
                    lines.append(f"{prefix}}}")
            elif isinstance(statement, ForRange):
                start, stop = self.temporary("start"), self.temporary("stop")
                lines.append(f"{prefix}int64_t {start} = {self.expression(statement.start)};")
                lines.append(f"{prefix}int64_t {stop} = {self.expression(statement.stop)};")
                lines.append(f"{prefix}if (!ok) return false;")
                lines.append(f"{prefix}for (int64_t {statement.index} = {start}; {statement.index} < {stop};) {{")
                lines.append(f"{prefix}    if (++lai_loop_steps > UINT64_C({MAX_RUNTIME_STEPS})) return false;")
                self.environment[statement.index] = I64
                lines.extend(self.block(statement.body, indentation + 1))
                del self.environment[statement.index]
                lines.append(f"{prefix}    if ({statement.index} == INT64_MAX) return false;")
                lines.append(f"{prefix}    ++{statement.index};")
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
                vector_field = next(value for name, value in statement.fields if expression_type(value, self.environment) == VECTOR_I64)
                vector_name = vector_field.name
                assert vector_name is not None
                lines.append(f"{prefix}if (!lai_result_vector(lai_result, &{vector_name})) return false;")
                scalar_fields = [(name, value) for name, value in statement.fields if expression_type(value, self.environment) != VECTOR_I64]
                lines.append(f"{prefix}lai_result->field_count = {len(scalar_fields)}U;")
                for index, (_, value) in enumerate(scalar_fields):
                    rendered = self.expression(value)
                    if expression_type(value, self.environment) == BOOL:
                        rendered = f"(({rendered}) ? INT64_C(1) : INT64_C(0))"
                    lines.append(f"{prefix}lai_result->fields[{index}] = {rendered};")
                    lines.append(f"{prefix}if (!ok) return false;")
                lines.append(f"{prefix}return true;")
        return lines


def _expected_parts(program: CollectionProgram, expected: object) -> tuple[list[int], list[int]]:
    if program.return_type.kind == "vector":
        if not isinstance(expected, list):
            raise CollectionLanguageError("native expected vector is invalid")
        return [_checked_i64(item, "expected vector element") for item in expected], []
    if not isinstance(expected, dict) or set(expected) != {field.name for field in program.return_type.fields}:
        raise CollectionLanguageError("native expected record is invalid")
    values: list[int] = []
    fields: list[int] = []
    for field in program.return_type.fields:
        value = expected[field.name]
        if field.field_type == VECTOR_I64:
            if not isinstance(value, list):
                raise CollectionLanguageError("native expected record vector is invalid")
            values = [_checked_i64(item, "expected record vector element") for item in value]
        elif field.field_type == BOOL:
            if not isinstance(value, bool):
                raise CollectionLanguageError("native expected record bool is invalid")
            fields.append(int(value))
        else:
            fields.append(_checked_i64(value, "expected record scalar"))
    return values, fields


def generate_c_source(program: CollectionProgram, vocabulary: CollectionVocabulary, cases: Sequence[Mapping[str, JsonValue]]) -> str:
    validate_program(program, vocabulary)
    if not cases:
        raise CollectionLanguageError("generated collection C requires cases")
    compiler = _CCompiler(program, vocabulary)
    body = compiler.block(program.statements, 1)
    arrays: list[str] = []
    rows: list[str] = []
    for index, case in enumerate(cases):
        nums, target, expected = case.get("nums"), case.get("target"), case.get("expected")
        if not isinstance(nums, list):
            raise CollectionLanguageError("generated collection input is invalid")
        input_values = [_checked_i64(item, "generated collection input") for item in nums]
        expected_values, expected_fields = _expected_parts(program, expected)
        def declaration(name: str, values: list[int]) -> str:
            payload = ", ".join(_c_i64(item) for item in values) or "INT64_C(0)"
            return f"static const int64_t {name}[{max(1, len(values))}] = {{{payload}}};"
        arrays.extend([
            declaration(f"case_{index:03d}_nums", input_values),
            declaration(f"case_{index:03d}_values", expected_values),
            declaration(f"case_{index:03d}_fields", expected_fields),
        ])
        rows.append(
            "    {"
            f"case_{index:03d}_nums, {len(input_values)}U, {_c_i64(_checked_i64(target, 'generated collection target'))}, "
            f"case_{index:03d}_values, {len(expected_values)}U, case_{index:03d}_fields, {len(expected_fields)}U"
            "},"
        )
    comments = "\n".join(f"/* op_{entry.entry_id[7:15]} lowering={canonical_json_bytes(_LOWERINGS[entry.kind]).decode('utf-8')} */" for entry in vocabulary.entries)
    encoded_id = content_id(program.to_document(encoded=True))
    return f'''/* Generated by LAIcode {KERNEL_VERSION}; do not edit. */
/* task_id={program.task_id} encoded_program_id={encoded_id} vocabulary_id={vocabulary.vocabulary_id} */
#include <inttypes.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#define LAI_MAX_OWNED {MAX_OWNED_ELEMENTS}
#define LAI_MAX_FIELDS {MAX_RECORD_FIELDS}
typedef struct {{ int64_t values[LAI_MAX_OWNED]; size_t len; size_t capacity; }} LaiVector;
typedef struct {{ int64_t values[LAI_MAX_OWNED]; size_t values_len; int64_t fields[LAI_MAX_FIELDS]; size_t field_count; }} LaiResult;
typedef struct {{ const int64_t *nums; size_t nums_len; int64_t target; const int64_t *values; size_t values_len; const int64_t *fields; size_t field_count; }} LaiCase;

static inline int64_t lai_input_get(const int64_t *values, size_t count, int64_t index, bool *ok) {{
    if (index < 0 || (uint64_t)index >= (uint64_t)count) {{ *ok = false; return INT64_C(0); }}
    return values[index];
}}
static inline int64_t lai_vector_get(const LaiVector *vector, int64_t index, bool *ok) {{
    if (index < 0 || (uint64_t)index >= (uint64_t)vector->len) {{ *ok = false; return INT64_C(0); }}
    return vector->values[index];
}}
static inline int64_t lai_vector_len(const LaiVector *vector) {{ return (int64_t)vector->len; }}
static inline bool lai_vector_push(LaiVector *vector, int64_t value, bool *ok) {{
    if (vector->len >= vector->capacity || vector->len >= LAI_MAX_OWNED) {{ *ok = false; return false; }}
    vector->values[vector->len++] = value; return true;
}}
static inline bool lai_result_vector(LaiResult *out, const LaiVector *vector) {{
    if (vector->len > LAI_MAX_OWNED) return false;
    out->values_len = vector->len;
    for (size_t index = 0; index < vector->len; ++index) out->values[index] = vector->values[index];
    return true;
}}
static inline int64_t lai_add(int64_t left, int64_t right, bool *ok) {{
    if ((right > 0 && left > INT64_MAX - right) || (right < 0 && left < INT64_MIN - right)) {{ *ok = false; return INT64_C(0); }}
    return left + right;
}}
static inline int64_t lai_sub(int64_t left, int64_t right, bool *ok) {{
    if ((right > 0 && left < INT64_MIN + right) || (right < 0 && left > INT64_MAX + right)) {{ *ok = false; return INT64_C(0); }}
    return left - right;
}}
static inline int64_t lai_max(int64_t left, int64_t right) {{ return left > right ? left : right; }}

{comments}
static bool lai_run(const int64_t *nums, size_t nums_len, int64_t target, LaiResult *lai_result) {{
    if (nums_len > LAI_MAX_OWNED || nums_len > (size_t)INT64_MAX) return false;
    bool ok = true;
    uint64_t lai_loop_steps = UINT64_C(0);
    (void)nums;
    (void)target;
{chr(10).join(body)}
    return false;
}}

{chr(10).join(arrays)}
static const LaiCase cases[{len(cases)}] = {{
{chr(10).join(rows)}
}};

static uint64_t fold(uint64_t state, int64_t value) {{
    return (state << 7U) ^ (state >> 3U) ^ (uint64_t)value ^ UINT64_C(0x9e3779b97f4a7c15);
}}

int main(void) {{
    uint64_t checksum = UINT64_C(0xbb67ae8584caa73b);
    for (size_t case_index = 0; case_index < {len(cases)}U; ++case_index) {{
        LaiResult actual = {{.values_len = 0U, .field_count = 0U}};
        const LaiCase *expected = &cases[case_index];
        if (!lai_run(expected->nums, expected->nums_len, expected->target, &actual)) return 10;
        if (actual.values_len != expected->values_len || actual.field_count != expected->field_count) return 11;
        checksum = fold(checksum, (int64_t)actual.values_len);
        for (size_t index = 0; index < actual.values_len; ++index) {{
            if (actual.values[index] != expected->values[index]) return 12;
            checksum = fold(checksum, actual.values[index]);
        }}
        for (size_t index = 0; index < actual.field_count; ++index) {{
            if (actual.fields[index] != expected->fields[index]) return 13;
            checksum = fold(checksum, actual.fields[index]);
        }}
    }}
    printf("cases=%zu\\n", (size_t){len(cases)}U);
    printf("checksum=%016" PRIx64 "\\n", checksum);
    return 0;
}}
'''
