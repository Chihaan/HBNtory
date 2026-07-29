"""Client MCP generique en HTTP.

Connexion a un serveur MCP + conversion des tools au format Claude +
execution d'appels. Plusieurs connexions simultanees doivent partager
la meme AsyncExitStack (voir connect()), sinon erreur "cancel scope in
a different task".
"""

from __future__ import annotations

import json
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


class MCPServerConnection:
    """Represente une connexion active a un serveur MCP HTTP."""

    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
        self._session: ClientSession | None = None

    async def connect(self, stack: AsyncExitStack) -> None:
        read, write, _ = await stack.enter_async_context(
            streamablehttp_client(self.url)
        )
        self._session = await stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()

    async def list_tools_anthropic_format(self) -> list[dict]:
        assert self._session is not None, "connect() doit etre appele avant"
        result = await self._session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema,
            }
            for tool in result.tools
        ]

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        assert self._session is not None, "connect() doit etre appele avant"
        result = await self._session.call_tool(tool_name, arguments)
        if result.content and hasattr(result.content[0], "text"):
            return result.content[0].text
        return json.dumps({"success": False, "error": "Reponse vide du serveur MCP."})