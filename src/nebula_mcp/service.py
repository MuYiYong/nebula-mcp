"""Application workflows exposed by the nebula-mcp tools."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Protocol

from nebula_mcp.analysis import analyze_rows
from nebula_mcp.config import Settings
from nebula_mcp.database import ResultLike
from nebula_mcp.errors import NebulaMCPError
from nebula_mcp.models import (
    ConnectionOutput,
    ExplanationContext,
    GraphListOutput,
    GraphSchemaEntity,
    GraphSchemaInput,
    GraphSchemaOutput,
    GraphSummary,
    ListGraphsInput,
    MutationInput,
    MutationOutput,
    ParsedResult,
    QueryInput,
    QueryMetadata,
    QueryOutput,
    ResultLimits,
    ValidateGQLInput,
    ValidationEvidence,
    ValidationOutput,
)
from nebula_mcp.policy import evaluate_policy, scan_gql, validate_candidate
from nebula_mcp.result_parser import parse_result
from nebula_mcp.serialization import JsonValue
from nebula_mcp.specs import build_cytoscape_graph, build_vega_lite_specs

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Gateway(Protocol):
    async def execute(self, statement: str) -> ResultLike: ...

    async def version(self) -> str: ...


class NebulaService:
    """Coordinates policy, database access, parsing, and portable artifacts."""

    def __init__(self, settings: Settings, gateway: Gateway) -> None:
        self.settings = settings
        self.gateway = gateway

    async def test_connection(self) -> ConnectionOutput:
        return ConnectionOutput(
            connected=True,
            version=await self.gateway.version(),
            config=self.settings.public_view(),
        )

    async def list_graphs(self, request: ListGraphsInput) -> GraphListOutput:
        if request.schema_name is not None:
            _require_identifier(request.schema_name, field="schema")
        statement = f"CALL show_graphs() RETURN * OFFSET {request.offset} LIMIT {request.limit}"
        parsed = parse_result(
            await self.gateway.execute(statement),
            graph=None,
            limits=self._limits(rows=request.limit),
        )
        graphs: list[GraphSummary] = []
        for row in parsed.table.rows:
            schema_name = _optional_string(row.get("schema"))
            if schema_name is not None:
                schema_name = schema_name.removeprefix("/")
            if request.schema_name is not None and schema_name != request.schema_name:
                continue
            name = _optional_string(row.get("name"))
            if name is None:
                continue
            graphs.append(
                GraphSummary(
                    schema=schema_name,
                    name=name,
                    graph_type=_optional_string(row.get("graph_type")),
                    owner=_optional_string(row.get("owner")),
                    extra=row.get("extra"),
                )
            )
        return GraphListOutput(
            status=parsed.status,
            graphs=graphs,
            limit=request.limit,
            offset=request.offset,
            returned_count=len(graphs),
        )

    async def get_graph_schema(self, request: GraphSchemaInput) -> GraphSchemaOutput:
        _require_identifier(request.schema_name, field="schema")
        _require_identifier(request.graph_type, field="graph_type")
        reference = f"/{request.schema_name}/{request.graph_type}"
        parsed = parse_result(
            await self.gateway.execute(f"DESCRIBE GRAPH TYPE {reference}"),
            graph=None,
            limits=self._limits(rows=self.settings.max_rows),
        )
        entities = [self._schema_entity(row) for row in parsed.table.rows]
        ddl: str | None = None
        ddl_truncated = False
        if request.include_ddl:
            ddl_result = parse_result(
                await self.gateway.execute(f"SHOW CREATE GRAPH TYPE {reference}"),
                graph=None,
                limits=self._limits(rows=1),
            )
            if ddl_result.table.rows:
                value = ddl_result.table.rows[0].get("create_graph_type_statement")
                if isinstance(value, str):
                    ddl, ddl_truncated = _truncate_utf8(value, request.max_ddl_bytes)
        return GraphSchemaOutput(
            status=parsed.status,
            schema=request.schema_name,
            graph_type=request.graph_type,
            entities=entities,
            ddl=ddl,
            ddl_truncated=ddl_truncated,
        )

    async def validate_gql(self, request: ValidateGQLInput) -> ValidationOutput:
        if request.graph is not None:
            _require_identifier(request.graph, field="graph")
        evidence = validate_candidate(request.statement)
        policy = evaluate_policy(request.statement, allow_mutations=False)
        explain: ParsedResult | None = None
        if request.run_explain:
            if not evidence.valid or not policy.allowed or not policy.read_only:
                raise NebulaMCPError(
                    category="validation_error",
                    message="GQL must pass static read-only validation before EXPLAIN",
                    suggestion="Resolve validation issues and retry",
                )
            explain_statement = f"EXPLAIN {self._apply_graph(request.statement, request.graph)}"
            explain = parse_result(
                await self.gateway.execute(explain_statement),
                graph=self._graph_context(request.statement, request.graph),
                limits=self._limits(rows=self.settings.max_rows),
            )
            evidence = evidence.model_copy(update={"explain_checked": True})
        return ValidationOutput(evidence=evidence, policy=policy, explain=explain)

    async def execute_query(self, request: QueryInput) -> QueryOutput:
        if request.graph is not None:
            _require_identifier(request.graph, field="graph")
        evidence = validate_candidate(request.statement)
        if not evidence.valid:
            raise NebulaMCPError(
                category="validation_error",
                message="GQL contains unresolved dialect or placeholder issues",
                suggestion="Use the gql-query-generator skill to produce YueShu 5.3 GQL",
            )
        policy = evaluate_policy(request.statement, allow_mutations=False)
        if not policy.allowed or not policy.read_only:
            raise NebulaMCPError(
                category="policy_denied",
                message="Only an approved read-only GQL statement can use this tool",
                suggestion="Use the mutation tool only after explicitly enabling mutations",
            )
        executed_statement = self._apply_graph(request.statement, request.graph)
        effective_graph = self._graph_context(request.statement, request.graph)
        row_limit = min(request.max_rows or self.settings.max_rows, self.settings.max_rows)
        parsed = parse_result(
            await self.gateway.execute(executed_statement),
            graph=effective_graph,
            limits=self._limits(rows=row_limit),
        )
        executed_evidence = evidence.model_copy(update={"executed": True})
        analysis = (
            analyze_rows(parsed.table.rows, parsed.truncation.truncated)
            if request.include_analysis or request.include_charts
            else None
        )
        graph_spec = build_cytoscape_graph(parsed) if request.include_graph else None
        charts = (
            build_vega_lite_specs(parsed.table.rows, analysis)
            if request.include_charts and analysis is not None
            else []
        )
        output_analysis = analysis if request.include_analysis else None
        return QueryOutput(
            status=parsed.status,
            query=QueryMetadata(
                statement=request.statement,
                graph=effective_graph,
                validation=executed_evidence,
            ),
            table=parsed.table,
            graph=graph_spec,
            analysis=output_analysis,
            charts=charts,
            explanation_context=self._explanation_context(parsed, executed_evidence),
            truncation=parsed.truncation,
        )

    async def execute_mutation(self, request: MutationInput) -> MutationOutput:
        if not self.settings.allow_mutations:
            raise NebulaMCPError(
                category="policy_denied",
                message="Mutation execution is disabled",
                suggestion="Set NEBULA_ALLOW_MUTATIONS=true only for an appropriate database account",
            )
        if not request.confirm_mutation:
            raise NebulaMCPError(
                category="policy_denied",
                message="Explicit mutation confirmation is required",
                suggestion="Review the statement and set confirm_mutation=true",
            )
        if request.graph is not None:
            _require_identifier(request.graph, field="graph")
        evidence = validate_candidate(request.statement)
        policy = evaluate_policy(request.statement, allow_mutations=True)
        if not evidence.valid or not policy.allowed or policy.statement_kind != "mutation":
            raise NebulaMCPError(
                category="policy_denied",
                message="Statement is not an approved single mutation",
                suggestion="Remove placeholders, dialect residuals, and extra statements",
            )
        parsed = parse_result(
            await self.gateway.execute(self._apply_graph(request.statement, request.graph)),
            graph=self._graph_context(request.statement, request.graph),
            limits=self._limits(rows=1),
        )
        return MutationOutput(
            status=parsed.status,
            affected_nodes=_affected_count(parsed.status.extra_info, "affected_nodes"),
            affected_edges=_affected_count(parsed.status.extra_info, "affected_edges"),
            warnings=("This tool executed a database mutation.",),
        )

    def _limits(self, *, rows: int) -> ResultLimits:
        return ResultLimits(
            rows=rows,
            nodes=self.settings.max_nodes,
            edges=self.settings.max_edges,
            bytes=self.settings.max_bytes,
        )

    def _apply_graph(self, statement: str, graph: str | None) -> str:
        if graph is None:
            return statement
        if re.match(r"^\s*USE\b", scan_gql(statement).sanitized, re.IGNORECASE):
            raise NebulaMCPError(
                category="validation_error",
                message="graph input conflicts with an explicit USE clause",
                suggestion="Specify graph in only one place",
            )
        return f"USE {graph}\n{statement}"

    def _graph_context(self, statement: str, graph: str | None) -> str | None:
        if graph is not None:
            return graph
        match = re.match(
            r"^\s*USE\s+(?P<reference>(?:/[A-Za-z_][A-Za-z0-9_]*)+|#[A-Za-z_][A-Za-z0-9_]*|[A-Za-z_][A-Za-z0-9_]*)",
            scan_gql(statement).sanitized,
            re.IGNORECASE,
        )
        return match.group("reference") if match is not None else self.settings.default_graph

    @staticmethod
    def _schema_entity(row: Mapping[str, JsonValue]) -> GraphSchemaEntity:
        return GraphSchemaEntity(
            entity_type=_optional_string(row.get("entity_type")),
            type_name=_optional_string(row.get("type_name")),
            type_pattern=row.get("type_pattern"),
            labels=row.get("labels"),
            primary_key_or_multiedge_key=row.get("primary_key/multiedge_key")
            or row.get("primary_key_or_multiedge_key")
            or row.get("primary_key")
            or row.get("multiedge_key"),
            properties=row.get("properties"),
        )

    @staticmethod
    def _explanation_context(
        parsed: ParsedResult, validation: ValidationEvidence
    ) -> ExplanationContext:
        facts = [
            f"Returned {parsed.table.returned_row_count} row(s).",
            f"Extracted {len(parsed.graph.nodes)} node(s) and {len(parsed.graph.edges)} edge(s).",
        ]
        caveats = [f"Result was truncated by {reason}." for reason in parsed.truncation.reasons]
        caveats.extend(issue.message for issue in validation.warnings)
        return ExplanationContext(
            facts=facts,
            caveats=caveats,
            empty_result=parsed.table.returned_row_count == 0,
            validation_evidence=validation,
            suggested_focus=list(parsed.table.columns[:5]),
        )


def _require_identifier(value: str, *, field: str) -> None:
    if _IDENTIFIER.fullmatch(value) is None:
        raise NebulaMCPError(
            category="validation_error",
            message=f"Invalid {field} identifier",
            suggestion="Use letters, digits, and underscores, starting with a letter or underscore",
        )


def _optional_string(value: JsonValue | None) -> str | None:
    return value if isinstance(value, str) else None


def _truncate_utf8(value: str, max_bytes: int) -> tuple[str, bool]:
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value, False
    return encoded[:max_bytes].decode("utf-8", errors="ignore"), True


def _affected_count(extra_info: Mapping[str, object], key: str) -> int:
    value = extra_info.get(key, 0)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0
