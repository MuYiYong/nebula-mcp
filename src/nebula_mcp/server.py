"""MCP v2 server exposing YueShu workflows over stdio."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, Literal, TypeVar, cast

import anyio
from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, SecretStr, ValidationError

from nebula_mcp import __version__
from nebula_mcp.config import Settings, load_environments, load_settings
from nebula_mcp.database import DatabaseGateway
from nebula_mcp.errors import NebulaMCPError
from nebula_mcp.models import (
    ConnectionOutput,
    EnvironmentsOutput,
    GraphListOutput,
    GraphPresentation,
    GraphSchemaInput,
    GraphSchemaOutput,
    GraphSelectionOutput,
    ListGraphsInput,
    MutationInput,
    MutationOutput,
    QueryInput,
    QueryOutput,
    QueryPresentation,
    ValidateGQLInput,
    ValidationOutput,
)
from nebula_mcp.runtime import RuntimeState
from nebula_mcp.service import NebulaService
from nebula_mcp.ui_resource import UI_RESOURCE_URI, read_query_result_html

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

INSTRUCTIONS = """Use this server when the user says 使用 Nebula MCP，执行 xxx 语句.
On CONFIGURATION_REQUIRED ask for connection settings and call nebula_configure_connection;
never echo passwords. Tool arguments may be recorded by the host; offer local installer
--configure for no-echo password entry. Never invent credentials. Configuration lives in this
MCP process and replaces the old database session only after a successful connection test.
All database operations reuse one session until reconfiguration or process shutdown.
On GRAPH_SELECTION_REQUIRED list graphs with nebula_list_graphs, ask the user to choose a graph,
and pass their answer to nebula_select_graph. It executes SESSION SET GRAPH and resumes the
pending read-only query automatically; present its result without submitting the query again.
Do not assume a graph or retry an unrelated error as a graph error. The user's graph choice
replaces the failed query's graph reference; preserve its other clauses and options.
Call nebula_render_result after a successful query or resumed query: non-empty graph data opens
as an interactive graph; scalar or empty results open as a table. If MCP Apps are unavailable,
show the returned table and available graph/chart specifications directly.
Use this server for YueShu 5.3 graph discovery and execution.
If the user supplies explicit GQL, validate and execute that statement unchanged; do not rewrite
explicit GQL merely to create a graph, and do not create a second visualization query. For a
natural-language scalar request, preserve scalar intent. For other natural-language, Neo4j Cypher,
or nGQL requests, discover the target graph and Schema, then use gql-query-generator in the Codex
client to project Node, Edge, or Path when semantically valid. The server never invokes a model and
never converts another dialect by itself. Auto-execute generated GQL only when the graph is
explicit, no placeholders remain, and read-only validation passes. Queries are read-only by
default; mutations require the server switch and per-call confirmation.
Graph and chart results are portable cytoscape-elements-v1 and vega-lite-v5 specifications; the
graph, analysis, and chart components are independently configurable and default to enabled.
After a successful query, present every enabled result component together: render a graph only
when it contains nodes or edges, render every non-empty vega-lite-v5 chart, and write a
human-readable explanation from explanation_context, table, graph and analysis. Explain the meaning
of returned entities, relationship direction and values, and support insights with specific evidence.
Go beyond row/path counts: identify relevant patterns or contrasts, distinguish observations from
hypotheses, and describe limits from LIMIT, filters, missing data or truncation. Do not claim global
importance, causality or representativeness from a small sample. Offer a concrete next check when
useful. A table does not replace charts or the
explanation. Show GQL from query.display_statement (fall back to query.executed_statement for older results).
Label statements GQL in prose and use untagged code fences. Never use gql or graphql language
tags: the host can interpret these as GraphQL. The MCP App labels statements GQL.
Automatic PROFILE is hidden from displayed/copied GQL; query.executed_statement records the wire
statement and profile contains the plan. Do not run an extra query to obtain PROFILE.
Use nebula_list_environments and nebula_switch_environment only for named environments configured
within this server. They do not switch independent MCP server registrations in the host.
nebula_render_graph is a legacy compatibility tool; prefer nebula_render_result and do not call
both for the same result. Never invent a missing graph, chart, or fact.
"""


def create_server(
    settings: Settings | None = None,
    service: NebulaService | None = None,
) -> MCPServer[RuntimeState]:
    """Create a server without connecting until its lifespan starts."""

    active_state: RuntimeState | None = None
    owned_gateway: DatabaseGateway | None = None
    operation_lock = anyio.Lock()
    environments: dict[str, Settings] = {}
    active_environment: str | None = None

    async def call(operation: Callable[[], Awaitable[OutputModel]]) -> OutputModel:
        # Serialize configuration, graph choice and execution for this stdio session.
        async with operation_lock:
            return await _safe_call(operation)

    @asynccontextmanager
    async def lifespan(_: MCPServer[RuntimeState]) -> AsyncIterator[RuntimeState]:
        nonlocal active_state, owned_gateway, environments, active_environment
        if service is not None:
            active_state = RuntimeState.ready(service)
        else:
            try:
                if settings is None:
                    environments, active_environment = load_environments()
                if environments and active_environment is None:
                    active_state = RuntimeState.connect_failed(NebulaMCPError(
                        category="configuration_error", code="ENVIRONMENT_SELECTION_REQUIRED",
                        message="请选择已配置的环境。",
                        suggestion="Call nebula_list_environments, then nebula_switch_environment",
                    ))
                else:
                    selected = environments.get(active_environment or "") or settings
                    resolved, problem = (selected, None) if selected is not None else load_settings()
                    if problem is not None:
                        active_state = RuntimeState.unconfigured(problem)
                    else:
                        assert resolved is not None
                        if not environments:
                            active_environment = active_environment or "default"
                            environments = {active_environment: resolved}
                        owned_gateway = DatabaseGateway(resolved)
                        await anyio.to_thread.run_sync(owned_gateway.open)
                        initial = NebulaService(resolved, owned_gateway)
                        initial.environment = active_environment
                        active_state = RuntimeState.ready(initial)
            except NebulaMCPError as error:
                if owned_gateway is not None:
                    await anyio.to_thread.run_sync(owned_gateway.close)
                    owned_gateway = None
                active_state = RuntimeState.connect_failed(error)
        try:
            yield active_state
        finally:
            if owned_gateway is not None:
                await anyio.to_thread.run_sync(owned_gateway.close)
                owned_gateway = None
            active_state = None

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
        version=__version__,
        log_level=settings.log_level if settings is not None else "INFO",
        lifespan=lifespan,
    )

    async def replace_connection(
        configured: Settings, state: RuntimeState, name: str | None,
    ) -> ConnectionOutput:
        nonlocal owned_gateway, active_environment
        candidate = DatabaseGateway(configured)
        try:
            await anyio.to_thread.run_sync(candidate.open)
            replacement = NebulaService(configured, candidate)
            replacement.environment = name
            result = await replacement.test_connection()
        except BaseException:
            with anyio.CancelScope(shield=True):
                await anyio.to_thread.run_sync(candidate.close)
            raise
        with anyio.CancelScope(shield=True):
            previous = owned_gateway
            owned_gateway = candidate
            active_environment = name
            state.service, state.error, state.status = replacement, None, "READY"
            if previous is not None:
                await anyio.to_thread.run_sync(previous.close)
        return result

    @server.tool(
        name="nebula_list_environments",
        description="List preconfigured environment names and the active environment; no credentials.",
        annotations=READ_ONLY,
    )
    async def list_environments() -> EnvironmentsOutput:
        async with operation_lock:
            return EnvironmentsOutput(active=active_environment, environments=list(environments))

    @server.tool(
        name="nebula_switch_environment",
        description=(
            "Switch to a preconfigured environment after testing its connection. Failure keeps "
            "the existing session. Success resets selected graph and pending query. "
            "Does not execute pending queries in the new environment or switch host MCP servers."
        ),
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False),
    )
    async def switch_environment(name: str, ctx: Context[RuntimeState, Any]) -> ConnectionOutput:
        async def switch() -> ConnectionOutput:
            if name not in environments:
                raise NebulaMCPError(
                    category="configuration_error", code="UNKNOWN_ENVIRONMENT",
                    message="环境名称不存在，请先调用 nebula_list_environments。",
                )
            return await replace_connection(environments[name], ctx.request_context.lifespan_context, name)
        return await call(switch)

    @server.tool(
        name="nebula_configure_connection",
        description=(
            "Configure the database inside MCP without restarting. Connection settings stay in "
            "this process only; replacing a connection resets its session and graph choice. "
            "Passwords are never returned, but tool arguments may be stored by the host. "
            "Use installer --configure for local no-echo password entry instead if preferred."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=False, idempotent_hint=False,
            open_world_hint=True,
        ),
    )
    async def configure_connection(
        addresses: str,
        username: str,
        password: str,
        ctx: Context[RuntimeState, Any],
        tls_enabled: bool = False,
        connect_timeout_ms: int = 30_000,
        request_timeout_ms: int = 60_000,
        default_schema: str | None = None,
    ) -> ConnectionOutput:
        async def configure() -> ConnectionOutput:
            try:
                if not username.strip() or not password:
                    raise ValueError("Missing credentials")
                configured = Settings.model_validate({
                    "addresses": addresses, "username": username, "password": SecretStr(password),
                    "tls_enabled": tls_enabled, "connect_timeout_ms": connect_timeout_ms,
                    "request_timeout_ms": request_timeout_ms, "default_schema": default_schema,
                })
            except (ValidationError, ValueError):
                raise NebulaMCPError(
                    category="configuration_error", code="INVALID_CONFIGURATION",
                    message="连接配置无效，请检查地址、端口、用户名、密码和超时。",
                ) from None
            return await replace_connection(configured, ctx.request_context.lifespan_context, None)

        return await call(configure)

    @server.tool(
        name="nebula_select_graph",
        description=(
            "Choose the user's graph using SESSION SET GRAPH in the existing database session. "
            "Automatically execute the last read-only query blocked by a missing graph. "
            "Return its result; do not execute that query again."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=False, idempotent_hint=False,
            open_world_hint=True,
        ),
    )
    async def select_graph(graph: str, ctx: Context[RuntimeState, Any]) -> GraphSelectionOutput:
        return await call(lambda: _service(ctx).select_graph(graph))

    @server.tool(
        name="nebula_render_result",
        description=(
            "Display a query result: graph entities open as an interactive graph, otherwise "
            "open the table. Supply an evidence-based explanation of result meaning, specific observations, "
            "insights and limitations, not only counts. Includes charts and actual GQL."
        ),
        annotations=READ_ONLY,
        meta={"ui": {"resourceUri": UI_RESOURCE_URI}},
    )
    async def render_result(result: QueryOutput, explanation: str) -> QueryPresentation:
        return QueryPresentation(result=result, explanation=explanation)

    @server.tool(
        name="nebula_test_connection",
        description="Test the configured YueShu connection and return only redacted settings.",
        annotations=READ_ONLY,
    )
    async def test_connection(ctx: Context[RuntimeState, Any]) -> ConnectionOutput:
        return await call(lambda: _service(ctx).test_connection())

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
        return await call(lambda: _service(ctx).list_graphs(request))

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
        return await call(lambda: _service(ctx).get_graph_schema(request))

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
        return await call(lambda: _service(ctx).validate_gql(request))

    @server.tool(
        name="nebula_execute_query",
        description=(
            "Execute one approved read-only GQL statement. Graph, analysis, and charts are "
            "independently configurable and default to enabled. Present all enabled results "
            "together: render a non-empty cytoscape-elements-v1 graph, render every non-empty "
            "vega-lite-v5 chart, and write a human-readable explanation from "
            "explanation_context. A table does not replace charts or the explanation."
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
        return await call(lambda: _service(ctx).execute_query(request))

    @server.tool(
        name="nebula_render_graph",
        description=(
            "Legacy compatibility entry; prefer nebula_render_result. Render a non-empty query "
            "graph together with its table, charts, explanation, "
            "and exact executed GQL. Explain specific findings, their meaning and limitations; counts alone are insufficient."
        ),
        annotations=READ_ONLY,
        meta={"ui": {"resourceUri": UI_RESOURCE_URI}},
    )
    async def render_graph(result: QueryOutput, explanation: str) -> GraphPresentation:
        return GraphPresentation(result=result, explanation=explanation)

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
        return await call(lambda: _service(ctx).execute_mutation(request))

    @server.resource(
        "nebula://connection",
        name="nebula-connection",
        description="Redacted YueShu connection status and server version.",
        mime_type="application/json",
    )
    async def connection_resource() -> str:
        async with operation_lock:
            return await _resource_json(
                lambda: require_active_state().require_service().test_connection()
            )

    @server.resource(
        UI_RESOURCE_URI,
        name="nebula-query-result-ui",
        description="Interactive graph, table, chart, explanation, and GQL result view.",
        mime_type="text/html;profile=mcp-app",
        meta={"ui": {"prefersBorder": True}},
    )
    async def query_result_ui_resource() -> str:
        return read_query_result_html()

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
        async with operation_lock:
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
