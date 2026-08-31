"""MCP v2 server exposing YueShu workflows over stdio."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, Literal, TypeVar, cast

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel

from nebula_mcp.config import Settings, load_settings
from nebula_mcp.database import DatabaseGateway
from nebula_mcp.errors import NebulaMCPError
from nebula_mcp.models import (
    ConnectionOutput,
    GraphListOutput,
    GraphSchemaInput,
    GraphSchemaOutput,
    ListGraphsInput,
    MutationInput,
    MutationOutput,
    QueryInput,
    QueryOutput,
    ValidateGQLInput,
    ValidationOutput,
)
from nebula_mcp.runtime import RuntimeState
from nebula_mcp.service import NebulaService

OutputModel = TypeVar("OutputModel", bound=BaseModel)

READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)
MUTATING = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=True,
    idempotent_hint=False,
    open_world_hint=True,
)

INSTRUCTIONS = """Use this server for YueShu 5.3 graph discovery and execution.
For natural language, Neo4j Cypher, or nGQL requests, conversion happens in the Codex client:
discover schema, use gql-query-generator, validate the candidate, show it for review, then execute.
The server never invokes a model and never converts another dialect by itself.
Queries are read-only by default. Mutations require the server switch and per-call confirmation.
Graph and chart results are portable cytoscape-elements-v1 and vega-lite-v5 specifications;
use explanation_context as evidence for a human-readable explanation.
"""


def create_server(
    settings: Settings | None = None,
    service: NebulaService | None = None,
) -> MCPServer[RuntimeState]:
    """Create a server without connecting until its lifespan starts."""

    active_state: RuntimeState | None = None

    @asynccontextmanager
    async def lifespan(_: MCPServer[RuntimeState]) -> AsyncIterator[RuntimeState]:
        nonlocal active_state
        if service is not None:
            active_state = RuntimeState.ready(service)
            try:
                yield active_state
            finally:
                active_state = None
            return

        resolved_settings, problem = (settings, None) if settings is not None else load_settings()
        if problem is not None:
            active_state = RuntimeState.unconfigured(problem)
            try:
                yield active_state
            finally:
                active_state = None
            return

        assert resolved_settings is not None
        gateway = DatabaseGateway(resolved_settings)
        try:
            gateway.open()
        except NebulaMCPError as error:
            active_state = RuntimeState.connect_failed(error)
            try:
                yield active_state
            finally:
                active_state = None
            return

        active_state = RuntimeState.ready(NebulaService(resolved_settings, gateway))
        try:
            yield active_state
        finally:
            active_state = None
            gateway.close()

    def require_active_state() -> RuntimeState:
        if active_state is None:
            raise NebulaMCPError(
                category="configuration_error",
                message="MCP server lifespan is not active",
                suggestion="Connect through an MCP transport before reading resources",
            )
        return active_state

    server = MCPServer[RuntimeState](
        name="nebula-mcp",
        title="YueShu 5.3 MCP",
        description="Local, spec-first access to a remote YueShu graph database",
        instructions=INSTRUCTIONS,
        version="0.1.3",
        log_level=settings.log_level if settings is not None else "INFO",
        lifespan=lifespan,
    )

    @server.tool(
        name="nebula_test_connection",
        description="Test the configured YueShu connection and return only redacted settings.",
        annotations=READ_ONLY,
    )
    async def test_connection(ctx: Context[RuntimeState, Any]) -> ConnectionOutput:
        return await _safe_call(lambda: _service(ctx).test_connection())

    @server.tool(
        name="nebula_list_graphs",
        description="List persistent graphs before choosing schema and graph context.",
        annotations=READ_ONLY,
    )
    async def list_graphs(
        ctx: Context[RuntimeState, Any],
        schema: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> GraphListOutput:
        request = ListGraphsInput(schema=schema, limit=limit, offset=offset)
        return await _safe_call(lambda: _service(ctx).list_graphs(request))

    @server.tool(
        name="nebula_get_graph_schema",
        description="Read a Graph Type schema; optionally include a UTF-8 byte-bounded DDL string.",
        annotations=READ_ONLY,
    )
    async def get_graph_schema(
        schema: str,
        graph_type: str,
        ctx: Context[RuntimeState, Any],
        include_ddl: bool = False,
        max_ddl_bytes: int = 65_536,
    ) -> GraphSchemaOutput:
        request = GraphSchemaInput(
            schema=schema,
            graph_type=graph_type,
            include_ddl=include_ddl,
            max_ddl_bytes=max_ddl_bytes,
        )
        return await _safe_call(lambda: _service(ctx).get_graph_schema(request))

    @server.tool(
        name="nebula_validate_gql",
        description=(
            "Validate YueShu 5.3 GQL for placeholders, dialect residuals, policy, and optional "
            "EXPLAIN. This never executes the original statement."
        ),
        annotations=READ_ONLY,
    )
    async def validate_gql(
        statement: str,
        ctx: Context[RuntimeState, Any],
        graph: str | None = None,
        run_explain: bool = False,
    ) -> ValidationOutput:
        request = ValidateGQLInput(statement=statement, graph=graph, run_explain=run_explain)
        return await _safe_call(lambda: _service(ctx).validate_gql(request))

    @server.tool(
        name="nebula_execute_query",
        description=(
            "Execute one approved read-only GQL statement and optionally return table, "
            "cytoscape-elements-v1 graph, deterministic analysis, and vega-lite-v5 charts."
        ),
        annotations=READ_ONLY,
    )
    async def execute_query(
        statement: str,
        ctx: Context[RuntimeState, Any],
        graph: str | None = None,
        max_rows: int | None = None,
        include_graph: bool = True,
        include_analysis: bool = True,
        include_charts: bool = True,
        render_mode: Literal["spec"] = "spec",
    ) -> QueryOutput:
        request = QueryInput(
            statement=statement,
            graph=graph,
            max_rows=max_rows,
            include_graph=include_graph,
            include_analysis=include_analysis,
            include_charts=include_charts,
            render_mode=render_mode,
        )
        return await _safe_call(lambda: _service(ctx).execute_query(request))

    @server.tool(
        name="nebula_execute_mutation",
        description=(
            "Execute one mutation only when NEBULA_ALLOW_MUTATIONS=true and "
            "confirm_mutation=true. This tool is destructive and returns no charts."
        ),
        annotations=MUTATING,
    )
    async def execute_mutation(
        statement: str,
        ctx: Context[RuntimeState, Any],
        graph: str | None = None,
        confirm_mutation: bool = False,
    ) -> MutationOutput:
        request = MutationInput(
            statement=statement,
            graph=graph,
            confirm_mutation=confirm_mutation,
        )
        return await _safe_call(lambda: _service(ctx).execute_mutation(request))

    @server.resource(
        "nebula://connection",
        name="nebula-connection",
        description="Redacted YueShu connection status and server version.",
        mime_type="application/json",
    )
    async def connection_resource() -> str:
        return await _resource_json(lambda: require_active_state().require_service().test_connection())

    @server.resource(
        "nebula://schema/{schema}/{graph_type}",
        name="nebula-graph-schema",
        description="Structured YueShu Graph Type schema for client-side GQL generation.",
        mime_type="application/json",
    )
    async def schema_resource(
        schema: str,
        graph_type: str,
    ) -> str:
        request = GraphSchemaInput(
            schema=schema,
            graph_type=graph_type,
            include_ddl=False,
            max_ddl_bytes=65_536,
        )
        return await _resource_json(
            lambda: require_active_state().require_service().get_graph_schema(request)
        )

    return server


def _service(ctx: Context[RuntimeState, Any]) -> NebulaService:
    return ctx.request_context.lifespan_context.require_service()


async def _safe_call(operation: Callable[[], Awaitable[OutputModel]]) -> OutputModel:
    try:
        return await operation()
    except NebulaMCPError as exc:
        payload = exc.as_payload()
        result = CallToolResult(
            content=[TextContent(type="text", text=payload.model_dump_json())],
            structured_content={"error": payload.model_dump(mode="json")},
            is_error=True,
        )
        return cast(OutputModel, result)


async def _resource_json(operation: Callable[[], Awaitable[BaseModel]]) -> str:
    try:
        output = await operation()
        return output.model_dump_json(by_alias=True)
    except NebulaMCPError as exc:
        return exc.as_payload().model_dump_json()
