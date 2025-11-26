import asyncio
import sys
import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession

import main_client

logger = logging.getLogger("mssql_mcp_api")
app = FastAPI(title="MSSQL MCP API")


class NLRequest(BaseModel):
    prompt: str


class SQLRequest(BaseModel):
    query: str


@app.on_event("startup")
async def startup():
    """Start MCP stdio client and initialize ClientSession."""
    # Use same server params as main_client's main() (simple and explicit)
    server_params = StdioServerParameters(command=sys.executable, args=["server.py"])

    async def _client_runner():
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    app.state.session = session
                    logger.info("MCP ClientSession ready")
                    # keep running until cancelled
                    await asyncio.Future()
        except asyncio.CancelledError:
            logger.info("MCP client runner cancelled")
        except Exception as e:
            logger.exception("MCP client runner failed: %s", e)
            app.state.session = None
            app.state.startup_error = str(e)

    app.state._client_task = asyncio.create_task(_client_runner())


@app.on_event("shutdown")
async def shutdown():
    task = getattr(app.state, "_client_task", None)
    if task:
        task.cancel()
        try:
            await task
        except Exception:
            pass


def _get_session() -> ClientSession:
    session = getattr(app.state, "session", None)
    if session is None:
        if getattr(app.state, "startup_error", None):
            raise HTTPException(status_code=500, detail=f"MCP startup error: {app.state.startup_error}")
        raise HTTPException(status_code=503, detail="MCP ClientSession not ready")
    return session


@app.get("/health")
async def health() -> Any:
    return {"api": "ok", "mcp_session": bool(getattr(app.state, "session", None)), "startup_error": getattr(app.state, "startup_error", None)}


@app.get("/schema")
async def get_schema() -> Any:
    session = _get_session()
    try:
        res = await session.call_tool("get_schema", arguments={})
        return {"schema": res.content[0].text}
    except Exception as e:
        logger.exception("schema error")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/nl2sql")
async def nl2sql(req: NLRequest) -> Any:
    # provide schema context if available
    session = _get_session()
    try:
        schema_res = await session.call_tool("get_schema", arguments={})
        schema_text = schema_res.content[0].text
    except Exception:
        schema_text = ""

    try:
        sql = await main_client.nl_to_sql(req.prompt, schema_text)
        return {"sql": sql}
    except Exception as e:
        logger.exception("nl2sql failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/execute")
async def execute(req: SQLRequest) -> Any:
    session = _get_session()
    try:
        res = await session.call_tool("execute_sql", arguments={"query": req.query})
        text = res.content[0].text
        return {"text": text}
    except Exception as e:
        logger.exception("execute failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query")
async def query(req: NLRequest) -> Any:
    session = _get_session()
    # get schema
    try:
        schema_res = await session.call_tool("get_schema", arguments={})
        schema_text = schema_res.content[0].text
    except Exception:
        schema_text = ""

    try:
        sql = await main_client.nl_to_sql(req.prompt, schema_text)
    except Exception as e:
        logger.exception("nl_to_sql failed")
        raise HTTPException(status_code=500, detail=str(e))

    try:
        exec_res = await session.call_tool("execute_sql", arguments={"query": sql})
        exec_text = exec_res.content[0].text
    except Exception as e:
        logger.exception("execute failed")
        raise HTTPException(status_code=500, detail=str(e))

    # summarise using main_client.summarise
    try:
        lines = exec_text.splitlines()
        rows_text = "\n".join(lines[:11]) if len(lines) > 11 else exec_text
        summary = await main_client.summarise(req.prompt, sql, rows_text)
    except Exception:
        summary = "(summary failed)"

    return {"sql": sql, "result": exec_text, "summary": summary}
