"""A2 typed function language with bounded user functions and a static call graph."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence, TypeAlias

from .canonical import JsonValue, canonical_json_bytes, content_id


PROGRAM_SCHEMA_VERSION = "FunctionProgramV2"
ENCODED_PROGRAM_SCHEMA_VERSION = "EncodedFunctionProgramV2"
VOCABULARY_ENTRY_SCHEMA_VERSION = "FunctionVocabularyEntryV2"
VOCABULARY_SCHEMA_VERSION = "FunctionVocabularyV2"
KERNEL_VERSION = "CallGraphFunctionKernelV2"
LEARNER_VERSION = "CrossTaskFunctionAbstractionLearnerV2"
DISCOVERY_LEARNER_VERSION = "AntiUnificationDiscoveryLearnerV3"
_LEARNER_IDS = frozenset({LEARNER_VERSION, DISCOVERY_LEARNER_VERSION})

I64_MIN = -(1 << 63)
I64_MAX = (1 << 63) - 1
MAX_RUNTIME_STEPS = 100_000
MAX_TRACE_EVENTS = 256
MAX_STATEMENTS = 256
MAX_EXPRESSION_DEPTH = 32
MAX_INPUT_ELEMENTS = 256
MAX_FUNCTIONS = 8
MAX_PARAMETERS = 4
MAX_CALL_DEPTH = 4
MAX_VOCABULARY_ENTRIES = 16

I64 = "i64"
BOOL = "bool"
ARRAY_I64 = "array_i64"
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_CONTENT_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_ARITY = {
    "len": 1,
    "get": 2,
    "add": 2,
    "sub": 2,
    "eq": 2,
    "ne": 2,
    "lt": 2,
    "le": 2,
    "gt": 2,
    "ge": 2,
}
_I64_BINARY = {"add", "sub"}
_I64_COMPARISON = {"eq", "ne", "lt", "le", "gt", "ge"}
_PARAMETER_TYPES = {I64, BOOL, ARRAY_I64}
_RETURN_TYPES = {I64, BOOL}


class FunctionLanguageError(ValueError):
    """Raised when an A2 program violates the fixed call-graph kernel."""


def _valid_identifier(value: object) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _valid_content_id(value: object) -> bool:
    return isinstance(value, str) and _CONTENT_ID.fullmatch(value) is not None


def _checked_i64(value: object, description: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FunctionLanguageError(f"{description} must be an integer")
    if not I64_MIN <= value <= I64_MAX:
        raise FunctionLanguageError(f"{description} is outside signed i64")
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
                raise FunctionLanguageError("constant expression has invalid fields")
            return
        if self.op == "var":
            if not _valid_identifier(self.name) or self.arguments or self.value is not None or self.entry_id is not None:
                raise FunctionLanguageError("variable expression has invalid fields")
            return
        if self.op == "call":
            if not _valid_identifier(self.name) or self.value is not None or self.entry_id is not None:
                raise FunctionLanguageError("call expression has invalid fields")
            if not 1 <= len(self.arguments) <= MAX_PARAMETERS:
                raise FunctionLanguageError("call expression argument count is invalid")
            return
        if self.op == "learned_call":
            if not _valid_content_id(self.entry_id) or self.name is not None or self.value is not None:
                raise FunctionLanguageError("learned call expression has invalid fields")
            if not 1 <= len(self.arguments) <= MAX_PARAMETERS:
                raise FunctionLanguageError("learned call argument count is invalid")
            return
        arity = _ARITY.get(self.op)
        if arity is None:
            raise FunctionLanguageError(f"unknown function expression {self.op!r}")
        if len(self.arguments) != arity or self.name is not None or self.value is not None or self.entry_id is not None:
            raise FunctionLanguageError(f"expression {self.op!r} has invalid fields")

    def to_document(self) -> dict[str, JsonValue]:
        if self.op == "const":
            assert self.value is not None
            return {"op": "const", "value": self.value}
        if self.op == "var":
            assert self.name is not None
            return {"op": "var", "name": self.name}
        if self.op == "call":
            assert self.name is not None
            return {
                "op": "call",
                "name": self.name,
                "arguments": [item.to_document() for item in self.arguments],
            }
        if self.op == "learned_call":
            assert self.entry_id is not None
            return {
                "op": "learned_call",
                "entry_id": self.entry_id,
                "arguments": [item.to_document() for item in self.arguments],
            }
        return {"op": self.op, "arguments": [item.to_document() for item in self.arguments]}

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> "Expression":
        if not isinstance(value, dict) or not isinstance(value.get("op"), str):
            raise FunctionLanguageError("expression must be an object with an op")
        op = value["op"]
        if op == "const":
            if set(value) != {"op", "value"}:
                raise FunctionLanguageError("constant expression has invalid fields")
            return cls("const", value=_checked_i64(value["value"], "constant"))
        if op == "var":
            if set(value) != {"op", "name"} or not isinstance(value["name"], str):
                raise FunctionLanguageError("variable expression has invalid fields")
            return cls("var", name=value["name"])
        arguments = value.get("arguments")
        if not isinstance(arguments, list) or not all(isinstance(item, dict) for item in arguments):
            raise FunctionLanguageError(f"expression {op!r} has invalid arguments")
        parsed = tuple(cls.from_document(item) for item in arguments)
        if op == "call":
            if set(value) != {"op", "name", "arguments"} or not isinstance(value["name"], str):
                raise FunctionLanguageError("call expression has invalid fields")
            return cls("call", parsed, name=value["name"])
        if op == "learned_call":
            if set(value) != {"op", "entry_id", "arguments"} or not isinstance(value["entry_id"], str):
                raise FunctionLanguageError("learned call expression has invalid fields")
            return cls("learned_call", parsed, entry_id=value["entry_id"])
        if set(value) != {"op", "arguments"}:
            raise FunctionLanguageError(f"expression {op!r} has invalid fields")
        return cls(op, parsed)


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
class If:
    condition: Expression
    then_body: tuple["Statement", ...]
    else_body: tuple["Statement", ...]


@dataclass(frozen=True)
class Return:
    value: Expression


Statement: TypeAlias = Let | Assign | ForRange | If | Return


def statement_to_document(statement: Statement) -> dict[str, JsonValue]:
    if isinstance(statement, (Let, Assign)):
        return {
            "op": "let" if isinstance(statement, Let) else "assign",
            "name": statement.name,
            "value": statement.value.to_document(),
        }
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
    if isinstance(statement, Return):
        return {"op": "return", "value": statement.value.to_document()}
    raise AssertionError("unknown function statement")


def statement_from_document(value: Mapping[str, object]) -> Statement:
    if not isinstance(value, dict) or not isinstance(value.get("op"), str):
        raise FunctionLanguageError("statement must be an object with an op")
    op = value["op"]

    def expression(field: str) -> Expression:
        item = value.get(field)
        if not isinstance(item, dict):
            raise FunctionLanguageError(f"statement {op!r} omits {field}")
        return Expression.from_document(item)

    def block(field: str) -> tuple[Statement, ...]:
        item = value.get(field)
        if not isinstance(item, list) or not all(isinstance(row, dict) for row in item):
            raise FunctionLanguageError(f"statement {op!r} has an invalid {field} block")
        return tuple(statement_from_document(row) for row in item)

    if op in {"let", "assign"}:
        if set(value) != {"op", "name", "value"} or not isinstance(value["name"], str):
            raise FunctionLanguageError(f"statement {op!r} has invalid fields")
        return (Let if op == "let" else Assign)(value["name"], expression("value"))
    if op == "for_range":
        if set(value) != {"op", "index", "start", "stop", "body"} or not isinstance(value["index"], str):
            raise FunctionLanguageError("for_range statement has invalid fields")
        return ForRange(value["index"], expression("start"), expression("stop"), block("body"))
    if op == "if":
        if set(value) != {"op", "condition", "then", "else"}:
            raise FunctionLanguageError("if statement has invalid fields")
        return If(expression("condition"), block("then"), block("else"))
    if op == "return":
        if set(value) != {"op", "value"}:
            raise FunctionLanguageError("return statement has invalid fields")
        return Return(expression("value"))
    raise FunctionLanguageError(f"unknown function statement operation {op!r}")


@dataclass(frozen=True)
class Parameter:
    name: str
    parameter_type: str

    def __post_init__(self) -> None:
        if not _valid_identifier(self.name) or self.parameter_type not in _PARAMETER_TYPES:
            raise FunctionLanguageError("function parameter is invalid")

    def to_document(self) -> dict[str, JsonValue]:
        return {"name": self.name, "type": self.parameter_type}


ENTRY_PARAMETERS = (Parameter("nums", ARRAY_I64), Parameter("target", I64))


@dataclass(frozen=True)
class FunctionDef:
    name: str
    parameters: tuple[Parameter, ...]
    return_type: str
    body: tuple[Statement, ...]

    def __post_init__(self) -> None:
        if not _valid_identifier(self.name) or self.return_type not in _RETURN_TYPES:
            raise FunctionLanguageError("function definition header is invalid")
        if not 1 <= len(self.parameters) <= MAX_PARAMETERS:
            raise FunctionLanguageError("function parameter count is invalid")
        names = tuple(item.name for item in self.parameters)
        if len(set(names)) != len(names):
            raise FunctionLanguageError("function parameter names must be unique")
        if not self.body:
            raise FunctionLanguageError("function body must not be empty")

    @property
    def parameter_types(self) -> tuple[str, ...]:
        return tuple(item.parameter_type for item in self.parameters)

    @property
    def statement_count(self) -> int:
        return len(tuple(_walk_statements(self.body)))

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "name": self.name,
            "parameters": [item.to_document() for item in self.parameters],
            "return_type": self.return_type,
            "body": [statement_to_document(item) for item in self.body],
        }

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> "FunctionDef":
        expected = {"name", "parameters", "return_type", "body"}
        if not isinstance(value, dict) or set(value) != expected:
            raise FunctionLanguageError("function definition has invalid fields")
        parameters, body = value["parameters"], value["body"]
        if not isinstance(value["name"], str) or not isinstance(value["return_type"], str):
            raise FunctionLanguageError("function definition header is malformed")
        if not isinstance(parameters, list) or not all(
            isinstance(item, dict) and set(item) == {"name", "type"}
            and isinstance(item["name"], str) and isinstance(item["type"], str)
            for item in parameters
        ):
            raise FunctionLanguageError("function parameters are malformed")
        if not isinstance(body, list) or not all(isinstance(item, dict) for item in body):
            raise FunctionLanguageError("function body is malformed")
        return cls(
            value["name"],
            tuple(Parameter(item["name"], item["type"]) for item in parameters),
            value["return_type"],
            tuple(statement_from_document(item) for item in body),
        )


@dataclass(frozen=True)
class FunctionProgram:
    task_id: str
    functions: tuple[FunctionDef, ...]

    def __post_init__(self) -> None:
        if not _valid_identifier(self.task_id):
            raise FunctionLanguageError("function task identity is invalid")
        if not 1 <= len(self.functions) <= MAX_FUNCTIONS:
            raise FunctionLanguageError("function count is outside the kernel limit")
        names = tuple(item.name for item in self.functions)
        if len(set(names)) != len(names):
            raise FunctionLanguageError("function names must be unique")
        if sum(item.statement_count for item in self.functions) > MAX_STATEMENTS:
            raise FunctionLanguageError("function statement count is invalid")

    @property
    def entry(self) -> FunctionDef:
        return self.functions[-1]

    @property
    def helpers(self) -> tuple[FunctionDef, ...]:
        return self.functions[:-1]

    @property
    def definition_statements(self) -> int:
        return sum(item.statement_count for item in self.helpers)

    def to_document(self, *, encoded: bool = False) -> dict[str, JsonValue]:
        return {
            "schema_version": ENCODED_PROGRAM_SCHEMA_VERSION if encoded else PROGRAM_SCHEMA_VERSION,
            "kernel_version": KERNEL_VERSION,
            "task_id": self.task_id,
            "parameters": [item.to_document() for item in ENTRY_PARAMETERS],
            "return_type": I64,
            "effects": ["pure_bounded_call_graph"],
            "functions": [item.to_document() for item in self.functions],
        }

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> "FunctionProgram":
        expected = {"schema_version", "kernel_version", "task_id", "parameters", "return_type", "effects", "functions"}
        if not isinstance(value, dict) or set(value) != expected:
            raise FunctionLanguageError("function program has invalid fields")
        if value["schema_version"] not in {PROGRAM_SCHEMA_VERSION, ENCODED_PROGRAM_SCHEMA_VERSION} or value["kernel_version"] != KERNEL_VERSION:
            raise FunctionLanguageError("function program has an unknown schema or kernel")
        if value["parameters"] != [item.to_document() for item in ENTRY_PARAMETERS] or value["return_type"] != I64 or value["effects"] != ["pure_bounded_call_graph"]:
            raise FunctionLanguageError("function program ABI is invalid")
        functions = value["functions"]
        if not isinstance(value["task_id"], str) or not isinstance(functions, list) or not all(isinstance(item, dict) for item in functions):
            raise FunctionLanguageError("function program payload is invalid")
        return cls(value["task_id"], tuple(FunctionDef.from_document(item) for item in functions))

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


def _statement_expressions(statement: Statement) -> Iterable[Expression]:
    if isinstance(statement, (Let, Assign, Return)):
        yield statement.value
    elif isinstance(statement, ForRange):
        yield statement.start
        yield statement.stop
    elif isinstance(statement, If):
        yield statement.condition


def _walk_expressions(expression: Expression) -> Iterable[Expression]:
    yield expression
    for item in expression.arguments:
        yield from _walk_expressions(item)


def _function_expressions(function: FunctionDef) -> Iterable[Expression]:
    for statement in _walk_statements(function.body):
        for expression in _statement_expressions(statement):
            yield from _walk_expressions(expression)


def _absolute_value_body() -> dict[str, JsonValue]:
    return {
        "name": "abs_value",
        "parameters": [{"name": "x", "type": I64}],
        "return_type": I64,
        "body": [
            {
                "op": "if",
                "condition": {"op": "lt", "arguments": [{"op": "var", "name": "x"}, {"op": "const", "value": 0}]},
                "then": [
                    {
                        "op": "return",
                        "value": {"op": "sub", "arguments": [{"op": "const", "value": 0}, {"op": "var", "name": "x"}]},
                    }
                ],
                "else": [],
            },
            {"op": "return", "value": {"op": "var", "name": "x"}},
        ],
    }


def _maximum_body() -> dict[str, JsonValue]:
    return {
        "name": "max_of",
        "parameters": [{"name": "a", "type": I64}, {"name": "b", "type": I64}],
        "return_type": I64,
        "body": [
            {
                "op": "if",
                "condition": {"op": "lt", "arguments": [{"op": "var", "name": "a"}, {"op": "var", "name": "b"}]},
                "then": [{"op": "return", "value": {"op": "var", "name": "b"}}],
                "else": [],
            },
            {"op": "return", "value": {"op": "var", "name": "a"}},
        ],
    }


_DEFINITIONS: dict[str, dict[str, JsonValue]] = {
    "abs_value": _absolute_value_body(),
    "max_of": _maximum_body(),
}


def learned_definition(kind: str) -> FunctionDef:
    """Return the fixed transparent definition archived for a learned kind."""

    if kind not in _DEFINITIONS:
        raise FunctionLanguageError("function vocabulary kind is invalid")
    return FunctionDef.from_document(_DEFINITIONS[kind])


def check_discovered_definition(definition: FunctionDef) -> None:
    """Validate a definition that no fixed table vouches for.

    A2 shipped with two hand-written definitions and required every entry to
    name one of them, so nothing a learner *discovered* could be represented.
    Discovered entries carry their own definition instead, and earn the same
    transparency guarantee structurally rather than by table lookup: the body
    must type-check standalone, be self-contained, and be non-recursive.
    """

    if definition.name in _DEFINITIONS:
        raise FunctionLanguageError("discovered definition may not shadow a fixed kind")
    if not all(item.parameter_type in {I64, BOOL} for item in definition.parameters):
        raise FunctionLanguageError("discovered definition takes only scalar parameters")
    if definition.statement_count < 2:
        raise FunctionLanguageError("discovered definition must contain multiple statements")
    for expression in _function_expressions(definition):
        if expression.op == "call":
            raise FunctionLanguageError("discovered definition must be self-contained")
        if expression.op == "learned_call":
            raise FunctionLanguageError("discovered definition must not nest learned calls")
    # Type-check the body in isolation: no sibling declarations exist for it.
    _validate_function(definition, {}, EMPTY_FUNCTION_VOCABULARY)


@dataclass(frozen=True)
class FunctionVocabularyEntry:
    kind: str
    evidence_catalog_id: str
    parent_vocabulary_id: str
    learned_cycle: int
    training_task_ids: tuple[str, ...]
    occurrences: int
    estimated_definition_saving: int
    learner_id: str = LEARNER_VERSION
    discovered_definition: FunctionDef | None = None

    def __post_init__(self) -> None:
        if self.discovered_definition is None:
            if self.kind not in _DEFINITIONS:
                raise FunctionLanguageError("function vocabulary kind is invalid")
        else:
            if self.discovered_definition.name != self.kind:
                raise FunctionLanguageError("discovered definition name must match its kind")
            check_discovered_definition(self.discovered_definition)
        if not _valid_content_id(self.evidence_catalog_id) or not _valid_content_id(self.parent_vocabulary_id):
            raise FunctionLanguageError("function vocabulary provenance is invalid")
        if isinstance(self.learned_cycle, bool) or self.learned_cycle < 1 or self.training_task_ids != tuple(sorted(set(self.training_task_ids))) or len(self.training_task_ids) < 2 or self.occurrences < 2 or self.estimated_definition_saving < 1 or self.learner_id not in _LEARNER_IDS:
            raise FunctionLanguageError("function vocabulary evidence is invalid")

    @property
    def definition(self) -> FunctionDef:
        if self.discovered_definition is not None:
            return self.discovered_definition
        return learned_definition(self.kind)

    @property
    def parameter_types(self) -> tuple[str, ...]:
        return self.definition.parameter_types

    @property
    def return_type(self) -> str:
        return self.definition.return_type

    @property
    def entry_id(self) -> str:
        return content_id(self.to_document())

    def to_document(self) -> dict[str, JsonValue]:
        definition = self.definition
        return {
            "schema_version": VOCABULARY_ENTRY_SCHEMA_VERSION,
            "kind": self.kind,
            "parameter_types": list(definition.parameter_types),
            "return_type": definition.return_type,
            "definition": definition.to_document(),
            "learner": {"id": self.learner_id, "cycle": self.learned_cycle},
            "provenance": {
                "evidence_catalog_id": self.evidence_catalog_id,
                "parent_vocabulary_id": self.parent_vocabulary_id,
                "training_task_ids": list(self.training_task_ids),
            },
            "evidence": {
                "cross_task_occurrences": self.occurrences,
                "definition_statement_count": definition.statement_count,
                "estimated_definition_saving": self.estimated_definition_saving,
            },
        }

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> "FunctionVocabularyEntry":
        expected = {"schema_version", "kind", "parameter_types", "return_type", "definition", "learner", "provenance", "evidence"}
        if not isinstance(value, dict) or set(value) != expected or value["schema_version"] != VOCABULARY_ENTRY_SCHEMA_VERSION or not isinstance(value["kind"], str):
            raise FunctionLanguageError("function vocabulary entry is invalid")
        kind, document = value["kind"], value["definition"]
        if not isinstance(document, dict):
            raise FunctionLanguageError("function vocabulary definition is malformed")
        if kind in _DEFINITIONS:
            if document != _DEFINITIONS[kind]:
                raise FunctionLanguageError("function vocabulary definition differs")
            definition = learned_definition(kind)
            discovered = None
        else:
            definition = FunctionDef.from_document(document)
            check_discovered_definition(definition)
            discovered = definition
        if value["parameter_types"] != list(definition.parameter_types) or value["return_type"] != definition.return_type:
            raise FunctionLanguageError("function vocabulary signature differs")
        learner, provenance, evidence = value["learner"], value["provenance"], value["evidence"]
        if not isinstance(learner, dict) or set(learner) != {"id", "cycle"} or not isinstance(provenance, dict) or set(provenance) != {"evidence_catalog_id", "parent_vocabulary_id", "training_task_ids"} or not isinstance(evidence, dict) or set(evidence) != {"cross_task_occurrences", "definition_statement_count", "estimated_definition_saving"}:
            raise FunctionLanguageError("function vocabulary entry evidence is malformed")
        tasks = provenance["training_task_ids"]
        if not isinstance(tasks, list) or not all(isinstance(item, str) for item in tasks) or evidence["definition_statement_count"] != definition.statement_count:
            raise FunctionLanguageError("function vocabulary entry evidence differs")
        return cls(kind, provenance["evidence_catalog_id"], provenance["parent_vocabulary_id"], learner["cycle"], tuple(tasks), evidence["cross_task_occurrences"], evidence["estimated_definition_saving"], learner["id"], discovered)


@dataclass(frozen=True)
class FunctionVocabulary:
    parent_vocabulary_id: str | None
    entries: tuple[FunctionVocabularyEntry, ...]

    def __post_init__(self) -> None:
        if self.parent_vocabulary_id is not None and not _valid_content_id(self.parent_vocabulary_id):
            raise FunctionLanguageError("function vocabulary parent is invalid")
        if len(self.entries) > MAX_VOCABULARY_ENTRIES or self.entries != tuple(sorted(self.entries, key=lambda item: item.entry_id)):
            raise FunctionLanguageError("function vocabulary entries are invalid")
        if len({item.entry_id for item in self.entries}) != len(self.entries) or len({item.kind for item in self.entries}) != len(self.entries):
            raise FunctionLanguageError("function vocabulary entries must be unique")

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": VOCABULARY_SCHEMA_VERSION,
            "kernel_version": KERNEL_VERSION,
            "parent_vocabulary_id": self.parent_vocabulary_id,
            "entry_ids": [item.entry_id for item in self.entries],
            "entries": [item.to_document() for item in self.entries],
        }

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> "FunctionVocabulary":
        expected = {"schema_version", "kernel_version", "parent_vocabulary_id", "entry_ids", "entries"}
        if not isinstance(value, dict) or set(value) != expected or value["schema_version"] != VOCABULARY_SCHEMA_VERSION or value["kernel_version"] != KERNEL_VERSION:
            raise FunctionLanguageError("function vocabulary is invalid")
        parent, entry_ids, entries = value["parent_vocabulary_id"], value["entry_ids"], value["entries"]
        if parent is not None and not isinstance(parent, str) or not isinstance(entry_ids, list) or not isinstance(entries, list) or not all(isinstance(item, dict) for item in entries):
            raise FunctionLanguageError("function vocabulary payload is invalid")
        parsed = tuple(FunctionVocabularyEntry.from_document(item) for item in entries)
        result = cls(parent, parsed)
        if entry_ids != [item.entry_id for item in parsed]:
            raise FunctionLanguageError("function vocabulary entry identities differ")
        return result

    @property
    def vocabulary_id(self) -> str:
        return content_id(self.to_document())

    def by_id(self) -> dict[str, FunctionVocabularyEntry]:
        return {item.entry_id: item for item in self.entries}

    def by_kind(self) -> dict[str, FunctionVocabularyEntry]:
        return {item.kind: item for item in self.entries}


EMPTY_FUNCTION_VOCABULARY = FunctionVocabulary(None, ())

Signature: TypeAlias = tuple[tuple[str, ...], str]


def expression_type(
    expression: Expression,
    environment: Mapping[str, str],
    signatures: Mapping[str, Signature] | None = None,
    vocabulary: FunctionVocabulary = EMPTY_FUNCTION_VOCABULARY,
    *,
    depth: int = 0,
) -> str:
    if depth > MAX_EXPRESSION_DEPTH:
        raise FunctionLanguageError("function expression is too deeply nested")
    resolved = signatures if signatures is not None else {}
    if expression.op == "const":
        return I64
    if expression.op == "var":
        assert expression.name is not None
        try:
            return environment[expression.name]
        except KeyError as error:
            raise FunctionLanguageError(f"function variable {expression.name!r} is not defined") from error
    argument_types = tuple(
        expression_type(item, environment, resolved, vocabulary, depth=depth + 1)
        for item in expression.arguments
    )
    if expression.op == "call":
        assert expression.name is not None
        signature = resolved.get(expression.name)
        if signature is None:
            raise FunctionLanguageError(f"function {expression.name!r} is not callable here")
        if argument_types != signature[0]:
            raise FunctionLanguageError(f"call to {expression.name!r} is mistyped")
        return signature[1]
    if expression.op == "learned_call":
        assert expression.entry_id is not None
        entry = vocabulary.by_id().get(expression.entry_id)
        if entry is None:
            raise FunctionLanguageError("learned call is not in the vocabulary")
        if argument_types != entry.parameter_types:
            raise FunctionLanguageError("learned call arguments are mistyped")
        return entry.return_type
    if expression.op == "len" and argument_types[0] == ARRAY_I64:
        return I64
    if expression.op == "get" and argument_types == (ARRAY_I64, I64):
        return I64
    if expression.op in _I64_BINARY and argument_types == (I64, I64):
        return I64
    if expression.op in _I64_COMPARISON and argument_types == (I64, I64):
        return BOOL
    raise FunctionLanguageError(f"function expression {expression.op!r} has incompatible operand types")


def _validate_function(
    function: FunctionDef,
    signatures: Mapping[str, Signature],
    vocabulary: FunctionVocabulary,
) -> None:
    environment: dict[str, str] = {item.name: item.parameter_type for item in function.parameters}

    def block(statements: Sequence[Statement], *, nested: bool) -> None:
        for statement in statements:
            if isinstance(statement, Let):
                if nested or not _valid_identifier(statement.name) or statement.name in environment:
                    raise FunctionLanguageError("scalar declarations are top-level and uniquely named")
                value_type = expression_type(statement.value, environment, signatures, vocabulary)
                if value_type not in {I64, BOOL}:
                    raise FunctionLanguageError("scalar declaration type is invalid")
                environment[statement.name] = value_type
            elif isinstance(statement, Assign):
                if statement.name not in environment or environment[statement.name] not in {I64, BOOL} or expression_type(statement.value, environment, signatures, vocabulary) != environment[statement.name]:
                    raise FunctionLanguageError("function assignment type differs")
            elif isinstance(statement, ForRange):
                if not statement.body or not _valid_identifier(statement.index) or statement.index in environment or expression_type(statement.start, environment, signatures, vocabulary) != I64 or expression_type(statement.stop, environment, signatures, vocabulary) != I64:
                    raise FunctionLanguageError("function for_range is invalid")
                environment[statement.index] = I64
                block(statement.body, nested=True)
                del environment[statement.index]
            elif isinstance(statement, If):
                if expression_type(statement.condition, environment, signatures, vocabulary) != BOOL:
                    raise FunctionLanguageError("function if condition must be bool")
                block(statement.then_body, nested=True)
                block(statement.else_body, nested=True)
            elif isinstance(statement, Return):
                if expression_type(statement.value, environment, signatures, vocabulary) != function.return_type:
                    raise FunctionLanguageError(f"function {function.name!r} returns the wrong type")
            else:
                raise AssertionError("unknown function statement")

    block(function.body, nested=False)
    if not isinstance(function.body[-1], Return):
        raise FunctionLanguageError(f"function {function.name!r} must end with a return")
    if any(isinstance(item, Return) for item in function.body[:-1]):
        raise FunctionLanguageError(f"function {function.name!r} has unreachable statements")
    if any(isinstance(item, ForRange) and any(isinstance(row, Return) for row in _walk_statements(item.body)) for item in _walk_statements(function.body)):
        raise FunctionLanguageError(f"function {function.name!r} must not return from a loop")


def call_graph(program: FunctionProgram) -> dict[str, tuple[str, ...]]:
    """Return each declared function's directly called local functions."""

    graph: dict[str, tuple[str, ...]] = {}
    for function in program.functions:
        called = sorted({
            expression.name
            for expression in _function_expressions(function)
            if expression.op == "call" and expression.name is not None
        })
        graph[function.name] = tuple(called)
    return graph


def _learned_calls(function: FunctionDef) -> tuple[str, ...]:
    return tuple(sorted({
        expression.entry_id
        for expression in _function_expressions(function)
        if expression.op == "learned_call" and expression.entry_id is not None
    }))


def _entry_depth(entry: FunctionVocabularyEntry, vocabulary: FunctionVocabulary) -> int:
    definition = entry.definition
    resolved = vocabulary.by_id()
    nested: list[int] = []
    for entry_id in _learned_calls(definition):
        if entry_id not in resolved:
            raise FunctionLanguageError("learned call is not in the vocabulary")
        nested.append(_entry_depth(resolved[entry_id], vocabulary))
    return 1 + max(nested, default=0)


def call_depth(program: FunctionProgram, vocabulary: FunctionVocabulary = EMPTY_FUNCTION_VOCABULARY) -> int:
    """Return the statically resolved maximum call depth including the entry.

    Learned calls count toward the same budget the runtime enforces, so an
    encoded program reports the depth its core program already had.
    """

    graph = call_graph(program)
    resolved = vocabulary.by_id()
    depths: dict[str, int] = {}
    for function in program.functions:
        callees = graph[function.name]
        unknown = [item for item in callees if item not in depths]
        if unknown:
            raise FunctionLanguageError(f"function {function.name!r} calls an undeclared or later function")
        reachable = [depths[item] for item in callees]
        for entry_id in _learned_calls(function):
            if entry_id not in resolved:
                raise FunctionLanguageError("learned call is not in the vocabulary")
            reachable.append(_entry_depth(resolved[entry_id], vocabulary))
        depths[function.name] = 1 + max(reachable, default=0)
    return depths[program.entry.name]


def validate_program(program: FunctionProgram, vocabulary: FunctionVocabulary = EMPTY_FUNCTION_VOCABULARY) -> None:
    entry = program.entry
    if entry.name != program.task_id or entry.parameters != ENTRY_PARAMETERS or entry.return_type != I64:
        raise FunctionLanguageError("function entry point signature is invalid")
    signatures: dict[str, Signature] = {}
    for function in program.functions:
        _validate_function(function, signatures, vocabulary)
        signatures[function.name] = (function.parameter_types, function.return_type)
    depth = call_depth(program, vocabulary)
    if depth > MAX_CALL_DEPTH:
        raise FunctionLanguageError("function call depth exceeds the kernel limit")
    graph = call_graph(program)
    reachable = {entry.name}
    pending = [entry.name]
    while pending:
        for name in graph[pending.pop()]:
            if name not in reachable:
                reachable.add(name)
                pending.append(name)
    unreachable = sorted({function.name for function in program.functions} - reachable)
    if unreachable:
        raise FunctionLanguageError(f"function {unreachable[0]!r} is never called from the entry point")


def learned_uses(program: FunctionProgram) -> tuple[str, ...]:
    return tuple(
        expression.entry_id
        for function in program.functions
        for expression in _function_expressions(function)
        if expression.op == "learned_call" and expression.entry_id is not None
    )


def learn_function_abstraction(
    programs: Sequence[FunctionProgram],
    vocabulary: FunctionVocabulary,
    *,
    evidence_catalog_id: str,
    cycle: int,
) -> FunctionVocabularyEntry:
    if len({program.task_id for program in programs}) < 2:
        raise FunctionLanguageError("function learner requires at least two tasks")
    documents: dict[str, JsonValue] = {}
    tasks: dict[str, set[str]] = {}
    conflicting: set[str] = set()
    for program in programs:
        validate_program(program)
        for function in program.helpers:
            document = function.to_document()
            if function.name in documents and documents[function.name] != document:
                conflicting.add(function.name)
            documents[function.name] = document
            tasks.setdefault(function.name, set()).add(program.task_id)
    existing = set(vocabulary.by_kind())
    eligible = [
        name
        for name in documents
        if name not in existing
        and name not in conflicting
        and len(tasks[name]) >= 2
        and name in _DEFINITIONS
        and documents[name] == _DEFINITIONS[name]
        and learned_definition(name).statement_count >= 2
    ]
    if not eligible:
        raise FunctionLanguageError("function learner found no cross-task abstraction")
    savings = {name: learned_definition(name).statement_count * len(tasks[name]) for name in eligible}
    kind = min(eligible, key=lambda item: (-savings[item], item))
    return FunctionVocabularyEntry(
        kind,
        evidence_catalog_id,
        vocabulary.vocabulary_id,
        cycle,
        tuple(sorted(tasks[kind])),
        len(tasks[kind]),
        savings[kind],
    )


def extend_vocabulary(vocabulary: FunctionVocabulary, entry: FunctionVocabularyEntry) -> FunctionVocabulary:
    if entry.parent_vocabulary_id != vocabulary.vocabulary_id:
        raise FunctionLanguageError("function vocabulary extension parent differs")
    return FunctionVocabulary(vocabulary.vocabulary_id, tuple(sorted((*vocabulary.entries, entry), key=lambda item: item.entry_id)))


def _rewrite_expression(expression: Expression, replacements: Mapping[str, str]) -> Expression:
    arguments = tuple(_rewrite_expression(item, replacements) for item in expression.arguments)
    if expression.op == "call" and expression.name in replacements:
        return Expression("learned_call", arguments, entry_id=replacements[expression.name])
    if expression.op == "call":
        return Expression("call", arguments, name=expression.name)
    if expression.op == "learned_call":
        return Expression("learned_call", arguments, entry_id=expression.entry_id)
    if expression.op in {"const", "var"}:
        return expression
    return Expression(expression.op, arguments)


def _rewrite_statements(statements: Sequence[Statement], replacements: Mapping[str, str]) -> tuple[Statement, ...]:
    rewritten: list[Statement] = []
    for statement in statements:
        if isinstance(statement, Let):
            rewritten.append(Let(statement.name, _rewrite_expression(statement.value, replacements)))
        elif isinstance(statement, Assign):
            rewritten.append(Assign(statement.name, _rewrite_expression(statement.value, replacements)))
        elif isinstance(statement, Return):
            rewritten.append(Return(_rewrite_expression(statement.value, replacements)))
        elif isinstance(statement, ForRange):
            rewritten.append(
                ForRange(
                    statement.index,
                    _rewrite_expression(statement.start, replacements),
                    _rewrite_expression(statement.stop, replacements),
                    _rewrite_statements(statement.body, replacements),
                )
            )
        elif isinstance(statement, If):
            rewritten.append(
                If(
                    _rewrite_expression(statement.condition, replacements),
                    _rewrite_statements(statement.then_body, replacements),
                    _rewrite_statements(statement.else_body, replacements),
                )
            )
        else:
            raise AssertionError("unknown function statement")
    return tuple(rewritten)


def encode_program(program: FunctionProgram, vocabulary: FunctionVocabulary) -> FunctionProgram:
    validate_program(program)
    entries = vocabulary.by_kind()
    replacements = {
        function.name: entries[function.name].entry_id
        for function in program.helpers
        if function.name in entries and function.to_document() == _DEFINITIONS[function.name]
    }
    functions = tuple(
        FunctionDef(
            function.name,
            function.parameters,
            function.return_type,
            _rewrite_statements(function.body, replacements),
        )
        for function in program.functions
        if function.name not in replacements
    )
    result = FunctionProgram(program.task_id, functions)
    validate_program(result, vocabulary)
    return result


RuntimeValue: TypeAlias = int | bool | tuple[int, ...]


@dataclass(frozen=True)
class ExecutionResult:
    value: int
    steps: int
    dispatches: int
    calls: int
    maximum_depth: int
    trace: tuple[Mapping[str, JsonValue], ...]
    trace_truncated: bool


class _Runtime:
    def __init__(self, program: FunctionProgram, vocabulary: FunctionVocabulary, *, trace: bool) -> None:
        self.functions = {item.name: item for item in program.functions}
        self.vocabulary = vocabulary
        self.steps = 0
        self.dispatches = 0
        self.calls = 0
        self.depth = 0
        self.maximum_depth = 0
        self.events: list[Mapping[str, JsonValue]] = []
        self.trace_enabled = trace
        self.trace_truncated = False

    def tick(self, *, dispatch: bool = True) -> None:
        self.steps += 1
        if dispatch:
            self.dispatches += 1
        if self.steps > MAX_RUNTIME_STEPS:
            raise FunctionLanguageError("function program exceeded its runtime budget")

    def event(self, value: Mapping[str, JsonValue]) -> None:
        if not self.trace_enabled:
            return
        if len(self.events) < MAX_TRACE_EVENTS:
            self.events.append(dict(value))
        else:
            self.trace_truncated = True


def _require_i64(value: RuntimeValue, operation: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FunctionLanguageError(f"{operation} requires i64")
    return value


def _require_bool(value: RuntimeValue, operation: str) -> bool:
    if not isinstance(value, bool):
        raise FunctionLanguageError(f"{operation} requires bool")
    return value


def _eval(expression: Expression, environment: Mapping[str, RuntimeValue], runtime: _Runtime) -> RuntimeValue:
    runtime.tick()
    if expression.op == "const":
        assert expression.value is not None
        return expression.value
    if expression.op == "var":
        assert expression.name is not None
        return environment[expression.name]
    arguments = tuple(_eval(item, environment, runtime) for item in expression.arguments)
    if expression.op == "call":
        assert expression.name is not None
        return _invoke(runtime.functions[expression.name], arguments, runtime, label=expression.name)
    if expression.op == "learned_call":
        assert expression.entry_id is not None
        entry = runtime.vocabulary.by_id()[expression.entry_id]
        return _invoke(entry.definition, arguments, runtime, label=entry.kind, entry_id=expression.entry_id)
    if expression.op == "len":
        value = arguments[0]
        if not isinstance(value, tuple):
            raise FunctionLanguageError("len requires an array")
        return len(value)
    if expression.op == "get":
        value, index_value = arguments
        index = _require_i64(index_value, "get")
        if not isinstance(value, tuple) or not 0 <= index < len(value):
            raise FunctionLanguageError("function index is outside the array")
        return value[index]
    left = _require_i64(arguments[0], expression.op)
    right = _require_i64(arguments[1], expression.op)
    if expression.op == "add":
        return _checked_i64(left + right, "addition result")
    if expression.op == "sub":
        return _checked_i64(left - right, "subtraction result")
    return {"eq": left == right, "ne": left != right, "lt": left < right, "le": left <= right, "gt": left > right, "ge": left >= right}[expression.op]


class _Returned:
    __slots__ = ("value",)

    def __init__(self, value: RuntimeValue) -> None:
        self.value = value


def _run_block(statements: Sequence[Statement], environment: dict[str, RuntimeValue], runtime: _Runtime) -> _Returned | None:
    for statement in statements:
        if isinstance(statement, Let):
            runtime.tick()
            environment[statement.name] = _eval(statement.value, environment, runtime)
            runtime.event({"event": "let", "name": statement.name})
        elif isinstance(statement, Assign):
            runtime.tick()
            environment[statement.name] = _eval(statement.value, environment, runtime)
            runtime.event({"event": "assign", "name": statement.name})
        elif isinstance(statement, ForRange):
            runtime.tick()
            start = _require_i64(_eval(statement.start, environment, runtime), "for start")
            stop = _require_i64(_eval(statement.stop, environment, runtime), "for stop")
            for index in range(start, stop):
                runtime.tick(dispatch=False)
                environment[statement.index] = _checked_i64(index, "loop index")
                result = _run_block(statement.body, environment, runtime)
                if result is not None:
                    return result
            environment.pop(statement.index, None)
        elif isinstance(statement, If):
            runtime.tick()
            condition = _require_bool(_eval(statement.condition, environment, runtime), "if")
            result = _run_block(statement.then_body if condition else statement.else_body, environment, runtime)
            if result is not None:
                return result
        elif isinstance(statement, Return):
            runtime.tick()
            return _Returned(_eval(statement.value, environment, runtime))
        else:
            raise AssertionError("unknown function statement")
    return None


def _invoke(function: FunctionDef, arguments: Sequence[RuntimeValue], runtime: _Runtime, *, label: str, entry_id: str | None = None) -> RuntimeValue:
    if runtime.depth >= MAX_CALL_DEPTH:
        raise FunctionLanguageError("function call depth exceeded the kernel limit")
    runtime.depth += 1
    runtime.calls += 1
    runtime.maximum_depth = max(runtime.maximum_depth, runtime.depth)
    event: dict[str, JsonValue] = {"event": "call", "function": label, "depth": runtime.depth}
    if entry_id is not None:
        event["entry_id"] = entry_id
        event["learned"] = True
    runtime.event(event)
    environment: dict[str, RuntimeValue] = {
        parameter.name: value for parameter, value in zip(function.parameters, arguments)
    }
    result = _run_block(function.body, environment, runtime)
    if result is None:
        raise FunctionLanguageError(f"function {label!r} completed without returning")
    runtime.event({"event": "return", "function": label, "depth": runtime.depth})
    runtime.depth -= 1
    return result.value


def execute_program(
    program: FunctionProgram,
    nums: Sequence[int],
    target: int,
    vocabulary: FunctionVocabulary = EMPTY_FUNCTION_VOCABULARY,
    *,
    trace: bool = False,
) -> ExecutionResult:
    validate_program(program, vocabulary)
    if len(nums) > MAX_INPUT_ELEMENTS:
        raise FunctionLanguageError("function input exceeds the A2 element limit")
    runtime = _Runtime(program, vocabulary, trace=trace)
    arguments: tuple[RuntimeValue, ...] = (
        tuple(_checked_i64(item, "array element") for item in nums),
        _checked_i64(target, "target"),
    )
    value = _invoke(program.entry, arguments, runtime, label=program.entry.name)
    return ExecutionResult(
        _require_i64(value, "entry result"),
        runtime.steps,
        runtime.dispatches,
        runtime.calls,
        runtime.maximum_depth,
        tuple(runtime.events),
        runtime.trace_truncated,
    )


def _learned_label(entry: FunctionVocabularyEntry) -> str:
    return f"op_{entry.entry_id[7:15]}<{entry.kind}>"


def _render_expression(expression: Expression, vocabulary: FunctionVocabulary) -> str:
    if expression.op == "const":
        return str(expression.value)
    if expression.op == "var":
        assert expression.name is not None
        return expression.name
    arguments = [_render_expression(item, vocabulary) for item in expression.arguments]
    if expression.op == "call":
        return f"{expression.name}({', '.join(arguments)})"
    if expression.op == "learned_call":
        assert expression.entry_id is not None
        entry = vocabulary.by_id()[expression.entry_id]
        return f"{_learned_label(entry)}({', '.join(arguments)})"
    if expression.op == "len":
        return f"len({arguments[0]})"
    if expression.op == "get":
        return f"{arguments[0]}[{arguments[1]}]"
    symbols = {"add": "+", "sub": "-", "eq": "==", "ne": "!=", "lt": "<", "le": "<=", "gt": ">", "ge": ">="}
    return f"({arguments[0]} {symbols[expression.op]} {arguments[1]})"


def _render_type(name: str) -> str:
    return "array<i64>" if name == ARRAY_I64 else name


def render_program(program: FunctionProgram, vocabulary: FunctionVocabulary = EMPTY_FUNCTION_VOCABULARY) -> str:
    validate_program(program, vocabulary)

    def block(statements: Sequence[Statement], indentation: int) -> list[str]:
        prefix = "    " * indentation
        lines: list[str] = []
        for statement in statements:
            if isinstance(statement, Let):
                lines.append(f"{prefix}let {statement.name} = {_render_expression(statement.value, vocabulary)}")
            elif isinstance(statement, Assign):
                lines.append(f"{prefix}{statement.name} = {_render_expression(statement.value, vocabulary)}")
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
                lines.append(f"{prefix}return {_render_expression(statement.value, vocabulary)}")
        return lines

    sections: list[str] = []
    for entry in vocabulary.entries:
        if entry.entry_id in set(learned_uses(program)):
            definition = entry.definition
            parameters = ", ".join(f"{item.name}: {_render_type(item.parameter_type)}" for item in definition.parameters)
            body = "\n".join(block(definition.body, 1))
            sections.append(f"use fn {_learned_label(entry)}({parameters}) -> {definition.return_type} {{\n{body}\n}}\n")
    for function in program.functions:
        keyword = "algorithm" if function is program.entry else "fn"
        parameters = ", ".join(f"{item.name}: {_render_type(item.parameter_type)}" for item in function.parameters)
        body = "\n".join(block(function.body, 1))
        sections.append(f"{keyword} {function.name}({parameters}) -> {function.return_type} {{\n{body}\n}}\n")
    return "\n".join(sections)


def _c_i64(value: int) -> str:
    if value == I64_MIN:
        return "INT64_MIN"
    return f"INT64_C({value})"


class _CCompiler:
    def __init__(self, program: FunctionProgram, vocabulary: FunctionVocabulary) -> None:
        self.program = program
        self.vocabulary = vocabulary
        self.signatures: dict[str, Signature] = {}
        self.environment: dict[str, str] = {}
        self.serial = 0

    def temporary(self, prefix: str) -> str:
        self.serial += 1
        return f"lai_{prefix}_{self.serial}"

    def c_name(self, name: str) -> str:
        return "lai_run" if name == self.program.entry.name else f"lai_fn_{name}"

    def learned_name(self, entry: FunctionVocabularyEntry) -> str:
        return f"lai_learned_{entry.entry_id[7:15]}"

    def expression(self, value: Expression) -> str:
        if value.op == "const":
            assert value.value is not None
            return _c_i64(value.value)
        if value.op == "var":
            assert value.name is not None
            return value.name
        arguments = [self.expression(item) for item in value.arguments]
        if value.op == "call":
            assert value.name is not None
            rendered = self.call_arguments(value, arguments)
            return f"{self.c_name(value.name)}({rendered})"
        if value.op == "learned_call":
            assert value.entry_id is not None
            entry = self.vocabulary.by_id()[value.entry_id]
            rendered = self.call_arguments(value, arguments)
            return f"{self.learned_name(entry)}({rendered})"
        if value.op == "len":
            assert value.arguments[0].name is not None
            return f"((int64_t){value.arguments[0].name}_len)"
        if value.op == "get":
            assert value.arguments[0].name is not None
            return f"lai_input_get({arguments[0]}, {value.arguments[0].name}_len, {arguments[1]}, ok)"
        if value.op == "add":
            return f"lai_add({arguments[0]}, {arguments[1]}, ok)"
        if value.op == "sub":
            return f"lai_sub({arguments[0]}, {arguments[1]}, ok)"
        symbols = {"eq": "==", "ne": "!=", "lt": "<", "le": "<=", "gt": ">", "ge": ">="}
        return f"({arguments[0]} {symbols[value.op]} {arguments[1]})"

    def call_arguments(self, value: Expression, arguments: Sequence[str]) -> str:
        if value.op == "call":
            assert value.name is not None
            parameter_types = self.signatures[value.name][0]
        else:
            assert value.entry_id is not None
            parameter_types = self.vocabulary.by_id()[value.entry_id].parameter_types
        rendered: list[str] = []
        for argument, expression, parameter_type in zip(arguments, value.arguments, parameter_types):
            if parameter_type == ARRAY_I64:
                assert expression.name is not None
                rendered.append(f"{argument}, {expression.name}_len")
            else:
                rendered.append(argument)
        rendered.append("ok")
        return ", ".join(rendered)

    def block(self, statements: Sequence[Statement], indentation: int, *, failure: str, entry: bool) -> list[str]:
        prefix = "    " * indentation
        lines: list[str] = []
        for statement in statements:
            if isinstance(statement, Let):
                value_type = expression_type(statement.value, self.environment, self.signatures, self.vocabulary)
                c_type = "bool" if value_type == BOOL else "int64_t"
                lines.append(f"{prefix}{c_type} {statement.name} = {self.expression(statement.value)};")
                lines.append(f"{prefix}if (!*ok) {failure}")
                self.environment[statement.name] = value_type
            elif isinstance(statement, Assign):
                lines.append(f"{prefix}{statement.name} = {self.expression(statement.value)};")
                lines.append(f"{prefix}if (!*ok) {failure}")
            elif isinstance(statement, ForRange):
                start, stop = self.temporary("start"), self.temporary("stop")
                lines.append(f"{prefix}int64_t {start} = {self.expression(statement.start)};")
                lines.append(f"{prefix}int64_t {stop} = {self.expression(statement.stop)};")
                lines.append(f"{prefix}if (!*ok) {failure}")
                lines.append(f"{prefix}for (int64_t {statement.index} = {start}; {statement.index} < {stop};) {{")
                lines.append(f"{prefix}    if (++lai_loop_steps > UINT64_C({MAX_RUNTIME_STEPS})) {{ *ok = false; {failure} }}")
                self.environment[statement.index] = I64
                lines.extend(self.block(statement.body, indentation + 1, failure=failure, entry=entry))
                del self.environment[statement.index]
                lines.append(f"{prefix}    if ({statement.index} == INT64_MAX) {{ *ok = false; {failure} }}")
                lines.append(f"{prefix}    ++{statement.index};")
                lines.append(f"{prefix}}}")
            elif isinstance(statement, If):
                condition = self.temporary("condition")
                lines.append(f"{prefix}bool {condition} = {self.expression(statement.condition)};")
                lines.append(f"{prefix}if (!*ok) {failure}")
                lines.append(f"{prefix}if ({condition}) {{")
                lines.extend(self.block(statement.then_body, indentation + 1, failure=failure, entry=entry))
                if statement.else_body:
                    lines.append(f"{prefix}}} else {{")
                    lines.extend(self.block(statement.else_body, indentation + 1, failure=failure, entry=entry))
                lines.append(f"{prefix}}}")
            elif isinstance(statement, Return):
                result = self.temporary("result")
                value_type = expression_type(statement.value, self.environment, self.signatures, self.vocabulary)
                c_type = "bool" if value_type == BOOL else "int64_t"
                lines.append(f"{prefix}{c_type} {result} = {self.expression(statement.value)};")
                lines.append(f"{prefix}if (!*ok) {failure}")
                if entry:
                    lines.append(f"{prefix}*lai_result = {result};")
                    lines.append(f"{prefix}return true;")
                else:
                    lines.append(f"{prefix}return {result};")
        return lines

    def signature(self, function: FunctionDef, name: str) -> str:
        parameters: list[str] = []
        for parameter in function.parameters:
            if parameter.parameter_type == ARRAY_I64:
                parameters.append(f"const int64_t *{parameter.name}, size_t {parameter.name}_len")
            elif parameter.parameter_type == BOOL:
                parameters.append(f"bool {parameter.name}")
            else:
                parameters.append(f"int64_t {parameter.name}")
        if name == "lai_run":
            parameters.append("int64_t *lai_result")
        parameters.append("bool *ok")
        return_type = "bool" if function.return_type == BOOL else "int64_t"
        if name == "lai_run":
            return_type = "bool"
        return f"static {return_type} {name}({', '.join(parameters)})"

    def function(self, function: FunctionDef, name: str) -> list[str]:
        self.environment = {item.name: item.parameter_type for item in function.parameters}
        entry = name == "lai_run"
        if entry:
            failure = "{ return false; }"
        else:
            zero = "false" if function.return_type == BOOL else "INT64_C(0)"
            failure = f"{{ *ok = false; return {zero}; }}"
        lines = [f"{self.signature(function, name)} {{"]
        for parameter in function.parameters:
            lines.append(f"    (void){parameter.name};")
            if parameter.parameter_type == ARRAY_I64:
                lines.append(f"    (void){parameter.name}_len;")
                lines.append(f"    if ({parameter.name}_len > LAI_MAX_INPUT || {parameter.name}_len > (size_t)INT64_MAX) {{ *ok = false; {failure} }}")
        lines.extend(self.block(function.body, 1, failure=failure, entry=entry))
        lines.append("}")
        return lines


def generate_c_source(
    program: FunctionProgram,
    vocabulary: FunctionVocabulary,
    cases: Sequence[Mapping[str, JsonValue]],
) -> str:
    validate_program(program, vocabulary)
    if not cases:
        raise FunctionLanguageError("generated function C requires cases")
    compiler = _CCompiler(program, vocabulary)
    used = set(learned_uses(program))
    definitions: list[str] = []
    for entry in vocabulary.entries:
        if entry.entry_id not in used:
            continue
        definition = entry.definition
        definitions.append(f"/* learned {entry.kind} entry_id={entry.entry_id} */")
        definitions.append(f"/* definition={canonical_json_bytes(_DEFINITIONS[entry.kind]).decode('utf-8')} */")
        definitions.extend(compiler.function(definition, compiler.learned_name(entry)))
    for function in program.functions:
        name = compiler.c_name(function.name)
        definitions.extend(compiler.function(function, name))
        compiler.signatures[function.name] = (function.parameter_types, function.return_type)

    arrays: list[str] = []
    rows: list[str] = []
    for index, case in enumerate(cases):
        nums, target, expected = case.get("nums"), case.get("target"), case.get("expected")
        if not isinstance(nums, list):
            raise FunctionLanguageError("generated function input is invalid")
        input_values = [_checked_i64(item, "generated function input") for item in nums]
        payload = ", ".join(_c_i64(item) for item in input_values) or "INT64_C(0)"
        arrays.append(f"static const int64_t case_{index:03d}_nums[{max(1, len(input_values))}] = {{{payload}}};")
        rows.append(
            "    {"
            f"case_{index:03d}_nums, {len(input_values)}U, "
            f"{_c_i64(_checked_i64(target, 'generated function target'))}, "
            f"{_c_i64(_checked_i64(expected, 'generated function expectation'))}"
            "},"
        )
    encoded_id = content_id(program.to_document(encoded=True))
    graph = "\n".join(
        f"/* call_graph {name} -> {', '.join(callees) if callees else '(none)'} */"
        for name, callees in sorted(call_graph(program).items())
    )
    return f'''/* Generated by LAIcode {KERNEL_VERSION}; do not edit. */
/* task_id={program.task_id} encoded_program_id={encoded_id} vocabulary_id={vocabulary.vocabulary_id} */
/* static_call_depth={call_depth(program, vocabulary)} declared_functions={len(program.functions)} */
{graph}
#include <inttypes.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#define LAI_MAX_INPUT {MAX_INPUT_ELEMENTS}
typedef struct {{ const int64_t *nums; size_t nums_len; int64_t target; int64_t expected; }} LaiCase;

static uint64_t lai_loop_steps = UINT64_C(0);

static inline int64_t lai_input_get(const int64_t *values, size_t count, int64_t index, bool *ok) {{
    if (index < 0 || (uint64_t)index >= (uint64_t)count) {{ *ok = false; return INT64_C(0); }}
    return values[index];
}}
static inline int64_t lai_add(int64_t left, int64_t right, bool *ok) {{
    if ((right > 0 && left > INT64_MAX - right) || (right < 0 && left < INT64_MIN - right)) {{ *ok = false; return INT64_C(0); }}
    return left + right;
}}
static inline int64_t lai_sub(int64_t left, int64_t right, bool *ok) {{
    if ((right > 0 && left < INT64_MIN + right) || (right < 0 && left > INT64_MAX + right)) {{ *ok = false; return INT64_C(0); }}
    return left - right;
}}

{chr(10).join(definitions)}

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
        const LaiCase *expected = &cases[case_index];
        int64_t actual = INT64_C(0);
        bool status = true;
        lai_loop_steps = UINT64_C(0);
        if (!lai_run(expected->nums, expected->nums_len, expected->target, &actual, &status) || !status) return 10;
        if (actual != expected->expected) return 11;
        checksum = fold(checksum, actual);
    }}
    printf("cases=%zu\\n", (size_t){len(cases)}U);
    printf("checksum=%016" PRIx64 "\\n", checksum);
    return 0;
}}
'''
