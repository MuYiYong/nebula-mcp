from __future__ import annotations

import pytest

from nebula_mcp.policy import evaluate_policy, validate_candidate


def test_keywords_inside_strings_comments_and_backticks_do_not_trigger_mutation() -> None:
    decision = evaluate_policy(
        "MATCH (n) WHERE n.note = 'CREATE' AND n.`DELETE` = 1 /* MERGE */ RETURN n LIMIT 5",
        allow_mutations=False,
    )

    assert decision.allowed is True
    assert decision.read_only is True
    assert decision.statement_kind == "query"


def test_multiple_statements_are_rejected_but_one_trailing_semicolon_is_allowed() -> None:
    rejected = evaluate_policy("RETURN 1; RETURN 2", allow_mutations=False)
    accepted = evaluate_policy("RETURN 1;", allow_mutations=False)

    assert rejected.allowed is False
    assert "multiple_statements" in rejected.reasons
    assert accepted.allowed is True


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT (:Person {name: 'A'})",
        "MATCH (n) DELETE n",
        "CREATE GRAPH demo OF TYPE type_a",
        "DROP GRAPH demo",
    ],
)
def test_mutation_is_denied_when_switch_is_off(statement: str) -> None:
    decision = evaluate_policy(statement, allow_mutations=False)

    assert decision.allowed is False
    assert decision.statement_kind == "mutation"
    assert "mutations_disabled" in decision.reasons


def test_recognized_mutation_is_allowed_only_when_switch_is_on() -> None:
    decision = evaluate_policy("INSERT (:Person {name: 'A'})", allow_mutations=True)

    assert decision.allowed is True
    assert decision.read_only is False


@pytest.mark.parametrize("procedure", ["version", "show_graphs"])
def test_read_only_procedure_allowlist(procedure: str) -> None:
    decision = evaluate_policy(f"CALL {procedure}() RETURN *", allow_mutations=False)

    assert decision.allowed is True
    assert decision.read_only is True


def test_unknown_procedure_is_not_treated_as_read_only() -> None:
    decision = evaluate_policy("CALL custom.proc() RETURN *", allow_mutations=False)

    assert decision.allowed is False
    assert "procedure_not_allowlisted" in decision.reasons


def test_call_subquery_is_allowed_when_body_is_read_only() -> None:
    decision = evaluate_policy(
        "CALL { MATCH (n) RETURN n LIMIT 1 } RETURN n",
        allow_mutations=False,
    )

    assert decision.allowed is True
    assert decision.read_only is True


@pytest.mark.parametrize(
    ("statement", "expected_code"),
    [
        ("MATCH (n) WITH n RETURN n", "cypher_with"),
        ("UNWIND [1, 2] AS x RETURN x", "cypher_unwind"),
        ("MATCH ()-[:KNOWS*1..3]->() RETURN 1", "cypher_variable_edge"),
        ("RETURN toSet([1, 1])", "cypher_toset"),
        ("RETURN [x IN [1, 2] | x + 1]", "cypher_list_comprehension"),
        ("GO FROM 'a' OVER follow", "ngql_go"),
        ("FETCH PROP ON player 'a'", "ngql_fetch"),
        ("LOOKUP ON player YIELD player.name", "ngql_lookup"),
        ("CALL apoc.path.expandConfig({}, {})", "neo4j_procedure"),
        ("USE <graph_name> MATCH (n) RETURN n", "placeholder"),
    ],
)
def test_dialect_residuals_and_placeholders_are_hard_stops(
    statement: str,
    expected_code: str,
) -> None:
    evidence = validate_candidate(statement)

    assert evidence.valid is False
    assert expected_code in {issue.code for issue in evidence.issues}


def test_match_without_limit_warns_but_aggregate_does_not() -> None:
    unbounded = validate_candidate("MATCH (n) RETURN n")
    aggregate = validate_candidate("MATCH (n) RETURN count(n) AS total")

    assert "missing_limit" in {warning.code for warning in unbounded.warnings}
    assert "missing_limit" not in {warning.code for warning in aggregate.warnings}


def test_static_validation_and_execution_policy_are_separate_evidence() -> None:
    evidence = validate_candidate("MATCH (n) RETURN n LIMIT 10")

    assert evidence.valid is True
    assert evidence.explain_checked is False
    assert evidence.executed is False
