"""Servidor MCP com as ferramentas de um mundo (spec MCP 2026-07-28, SDK mcp 2.x).

Usa o servidor de baixo nível porque as ferramentas já têm schema JSON: não precisa
recriar funções Python só para o SDK inferir o schema. Transportes:
- stdio (padrão): para clientes como o Claude Desktop ou o Claude Code;
- HTTP sem estado de sessão e com resposta JSON (sem SSE): `--http`.
O mundo vive enquanto o servidor estiver de pé; reiniciar o servidor volta ao estado inicial.
"""

from __future__ import annotations

import json
from typing import Any

from mcp import types
from mcp.server.lowlevel import Server

from toolbr import __version__
from toolbr.worlds import make_world


def build_server(world_name: str) -> Server:
    world = make_world(world_name)

    async def list_tools(ctx: Any, params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(
            tools=[
                types.Tool(name=s.name, description=s.description, input_schema=s.parameters)
                for s in world.tool_specs()
            ]
        )

    async def call_tool(ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        result = world.call(params.name, dict(params.arguments or {}))
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))],
            structured_content=result,
            is_error="erro" in result,
        )

    return Server(
        f"toolbr-{world_name}",
        version=__version__,
        instructions=(
            f"Ferramentas do mundo simulado {world_name} ({world.company}).\n\n{world.policy()}"
        ),
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


def run_stdio(world_name: str) -> None:
    import anyio
    from mcp.server.stdio import stdio_server

    server = build_server(world_name)

    async def main() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    anyio.run(main)


def run_http(world_name: str, host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn

    server = build_server(world_name)
    app = server.streamable_http_app(stateless_http=True, json_response=True, host=host)
    uvicorn.run(app, host=host, port=port)
