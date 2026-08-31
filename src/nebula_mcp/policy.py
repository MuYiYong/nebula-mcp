"""Conservative lexical checks for generated and executable GQL."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from nebula_mcp.models import PolicyDecision, PolicyIssue, StatementKind, ValidationEvidence

READ_ONLY_PROCEDURES = frozenset({"show_graphs", "version"})
MUTATION_KEYWORDS = frozenset(
    {
        "ALTER",
        "COPY",
        "CREATE",
        "DELETE",
        "DROP",
        "GRANT",
        "IMPORT",
        "INSERT",
        "LOAD",
        "MERGE",
        "REMOVE",
        "REPLACE",
        "REVOKE",
        "SET",
        "TRUNCATE",
        "UPDATE",
    }
)
READ_QUERY_STARTS = frozenset(
    {"CALL", "EXPLAIN", "FOR", "LET", "MATCH", "OPTIONAL", "PROFILE", "RETURN", "USE"}
)
CATALOG_STARTS = frozenset({"DESCRIBE", "SHOW"})
AGGREGATE_PATTERN = re.compile(r"\b(?:AVG|COLLECT|COUNT|MAX|MIN|SUM)\s*\(", re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*|;")
PROCEDURE_PATTERN = re.compile(r"\bCALL\s+([A-Za-z_][A-Za-z0-9_.]*)\s*\(", re.IGNORECASE)
PLACEHOLDER_PATTERN = re.compile(r"<[A-Za-z_][^>]*>|\{\{[^{}]+\}\}")


DIALECT_RULES: tuple[tuple[str, str, re.Pattern[str], str], ...] = (
    (
        "cypher_with",
        "cypher",
        re.compile(r"\bWITH\b", re.IGNORECASE),
        "Cypher WITH must be rewritten using YueShu GQL composition.",
    ),
    (
        "cypher_unwind",
        "cypher",
        re.compile(r"\bUNWIND\b", re.IGNORECASE),
        "Cypher UNWIND must be rewritten before execution.",
    ),
    (
        "cypher_variable_edge",
        "cypher",
        re.compile(r"\[\s*:[^\]]*\*[^\]]*\]", re.IGNORECASE),
        "Cypher variable-length edge syntax is not YueShu GQL.",
    ),
    (
        "cypher_toset",
        "cypher",
        re.compile(r"\btoSet\s*\(", re.IGNORECASE),
        "Cypher toSet() requires a YueShu-compatible rewrite.",
    ),
    (
        "cypher_list_comprehension",
        "cypher",
        re.compile(r"\[[A-Za-z_]\w*\s+IN\s+.*?\|", re.IGNORECASE | re.DOTALL),
        "Cypher list comprehension requires a YueShu-compatible rewrite.",
    ),
    (
        "neo4j_procedure",
        "cypher",
        re.compile(r"\bCALL\s+(?:apoc|db|dbms|gds)\.", re.IGNORECASE),
        "Neo4j-specific procedures cannot be executed directly.",
    ),
    (
        "ngql_go",
        "ngql",
        re.compile(r"\bGO\s+FROM\b", re.IGNORECASE),
        "nGQL GO must be rewritten as YueShu GQL.",
    ),
    (
        "ngql_fetch",
        "ngql",
        re.compile(r"\bFETCH\s+PROP\b", re.IGNORECASE),
        "nGQL FETCH PROP must be rewritten as YueShu GQL.",
    ),
    (
        "ngql_lookup",
        "ngql",
        re.compile(r"\bLOOKUP\s+ON\b", re.IGNORECASE),
        "nGQL LOOKUP ON must be rewritten as YueShu GQL.",
    ),
)


@dataclass(frozen=True)
class ScannedGQL:
    """Lexical view with quoted/comment content removed."""

    sanitized: str
    tokens: tuple[str, ...]
    semicolon_positions: tuple[int, ...]
    procedures: tuple[str, ...]
    has_call_subquery: bool


def _blank_quoted_and_commented(statement: str) -> str:
    chars = list(statement)
    index = 0
    length = len(chars)
    while index < length:
        char = chars[index]
        following = chars[index + 1] if index + 1 < length else ""
        if char == "/" and following == "*":
            chars[index] = chars[index + 1] = " "
            index += 2
            while index < length:
                if chars[index] == "*" and index + 1 < length and chars[index + 1] == "/":
                    chars[index] = chars[index + 1] = " "
                    index += 2
                    break
                if chars[index] not in "\r\n":
                    chars[index] = " "
                index += 1
            continue
        if (char == "/" and following == "/") or (char == "-" and following == "-"):
            chars[index] = chars[index + 1] = " "
            index += 2
            while index < length and chars[index] not in "\r\n":
                chars[index] = " "
                index += 1
            continue
        if char in {"'", '"', "`"}:
            quote = char
            chars[index] = " "
            index += 1
            while index < length:
                current = chars[index]
                if current == "\\" and index + 1 < length:
                    chars[index] = chars[index + 1] = " "
                    index += 2
                    continue
                chars[index] = " "
                index += 1
                if current == quote:
                    break
            continue
        index += 1
    return "".join(chars)


def scan_gql(statement: str) -> ScannedGQL:
    sanitized = _blank_quoted_and_commented(statement)
    matches = tuple(TOKEN_PATTERN.finditer(sanitized))
    tokens = tuple(match.group(0) for match in matches)
    procedures = tuple(match.group(1).lower() for match in PROCEDURE_PATTERN.finditer(sanitized))
    return ScannedGQL(
        sanitized=sanitized,
        tokens=tokens,
        semicolon_positions=tuple(match.start() for match in matches if match.group(0) == ";"),
        procedures=procedures,
        has_call_subquery=re.search(r"\bCALL\s*\{", sanitized, re.IGNORECASE) is not None,
    )


def _has_multiple_statements(scan: ScannedGQL) -> bool:
    if not scan.semicolon_positions:
        return False
    if len(scan.semicolon_positions) > 1:
        return True
    trailing_position = len(scan.sanitized.rstrip()) - 1
    return scan.semicolon_positions[0] != trailing_position


def _statement_kind(scan: ScannedGQL) -> StatementKind:
    upper_tokens = tuple(token.upper() for token in scan.tokens if token != ";")
    if not upper_tokens:
        return "unknown"
    if any(token in MUTATION_KEYWORDS for token in upper_tokens):
        return "mutation"
    if upper_tokens[0] in CATALOG_STARTS:
        return "catalog"
    if upper_tokens[0] == "CALL" and scan.procedures:
        return "procedure"
    if upper_tokens[0] in READ_QUERY_STARTS:
        return "query"
    return "unknown"


def evaluate_policy(statement: str, allow_mutations: bool) -> PolicyDecision:
    scan = scan_gql(statement)
    kind = _statement_kind(scan)
    reasons: list[str] = []

    if not statement.strip():
        reasons.append("empty_statement")
    if _has_multiple_statements(scan):
        reasons.append("multiple_statements")
    if scan.procedures and any(name not in READ_ONLY_PROCEDURES for name in scan.procedures):
        reasons.append("procedure_not_allowlisted")
    if kind == "unknown":
        reasons.append("unknown_statement_kind")
    if kind == "mutation" and not allow_mutations:
        reasons.append("mutations_disabled")

    read_only = kind in {"catalog", "query", "procedure"} and not reasons
    allowed = not reasons and (read_only or (kind == "mutation" and allow_mutations))
    return PolicyDecision(
        statement_kind=kind,
        allowed=allowed,
        read_only=read_only,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def validate_candidate(statement: str) -> ValidationEvidence:
    scan = scan_gql(statement)
    issues: list[PolicyIssue] = []
    warnings: list[PolicyIssue] = []
    dialects: set[str] = set()

    placeholders = tuple(match.group(0) for match in PLACEHOLDER_PATTERN.finditer(statement))
    if placeholders:
        issues.append(PolicyIssue(code="placeholder", message="Replace all schema placeholders."))

    for code, dialect, pattern, message in DIALECT_RULES:
        if pattern.search(scan.sanitized):
            dialects.add(dialect)
            issues.append(PolicyIssue(code=code, message=message))

    decision = evaluate_policy(statement, allow_mutations=False)
    for reason in decision.reasons:
        if reason in {"empty_statement", "multiple_statements", "procedure_not_allowlisted"}:
            issues.append(PolicyIssue(code=reason, message=reason.replace("_", " ").capitalize()))

    if (
        re.search(r"\bMATCH\b", scan.sanitized, re.IGNORECASE)
        and re.search(r"\bLIMIT\b", scan.sanitized, re.IGNORECASE) is None
        and AGGREGATE_PATTERN.search(scan.sanitized) is None
    ):
        warnings.append(
            PolicyIssue(
                code="missing_limit",
                message="Non-aggregate MATCH has no LIMIT; result and compute cost may be large.",
            )
        )

    detected_dialect: Literal["gql", "cypher", "ngql", "unknown"]
    if "ngql" in dialects:
        detected_dialect = "ngql"
    elif "cypher" in dialects:
        detected_dialect = "cypher"
    elif statement.strip():
        detected_dialect = "gql"
    else:
        detected_dialect = "unknown"

    return ValidationEvidence(
        valid=not issues,
        detected_dialect=detected_dialect,
        statement_kind=decision.statement_kind,
        issues=tuple(issues),
        warnings=tuple(warnings),
        placeholders=placeholders,
    )
