# MSSQL MCP Server — README

Overview
- This project provides a small MCP-based bridge to a Microsoft SQL Server database:
  - `server.py` — MCP server exposing tools to list schema and execute SQL.
  - `main_client.py` — CLI client pipeline: NL → SQL (Gemini) → execute → summarise.
  - `api.py` — FastAPI wrapper that keeps a long‑lived MCP ClientSession and exposes endpoints.
  - `stream_app.py` — Streamlit chat UI that converts user questions to SQL, runs queries and summarizes results.

Prerequisites
- Python 3.8+
- ODBC driver for SQL Server and `pyodbc` installed/configured.
- Required Python packages (examples):
  - streamlit, fastapi, uvicorn, python-dotenv, pyodbc, google-generative-ai (genai), mcp
- A `.env` file or environment variables set for DB and API keys.

Required environment variables
- GOOGLE_API_KEY — Gemini/Generative AI API key.
- MSSQL_HOST — SQL Server host (or IP).
- MSSQL_USER — DB username.
- MSSQL_PASSWORD — DB password.
- MSSQL_DATABASE — Database name.
Optional:
- MSSQL_DRIVER (default: "SQL Server")
- TrustServerCertificate (default: "yes")
- Trusted_Connection (default: "no")

Quick start (from the package directory `.../src/mssql_mcp_server`)
1. Install dependencies (example):
   - pip install -r requirements.txt
   - or pip install streamlit fastapi uvicorn python-dotenv pyodbc google-generative-ai mcp

2. Configure environment:
   - Create a `.env` file with the variables above, or export them in your environment.

3. Start the MCP server (in a terminal)
   - python server.py
   - The server exposes MCP tools via stdio (the clients spawn it using `python server.py`).

4. Run the FastAPI server (optional)
   - uvicorn api:app --reload --port 8000
   - Endpoints:
     - GET  /health
     - GET  /schema
     - POST /nl2sql  { "prompt": "..." }
     - POST /execute { "query": "..." }
     - POST /query   { "prompt": "..." }  — full pipeline: NL → SQL → execute → summary

5. Run the Streamlit chat UI
   - streamlit run stream_app.py
   - The Streamlit app will spawn a short‑lived MCP client that launches `server.py` if needed. Ensure `server.py` is reachable from the working directory.

Notes and tips
- The project uses Gemini (Google Generative AI). Ensure `GOOGLE_API_KEY` is set and has the required quota/permissions.
- ODBC drivers: On Windows use the Microsoft ODBC Driver for SQL Server. On Linux, install the appropriate unixODBC and Microsoft driver packages.
- Connection errors:
  - Verify the ODBC connection string values in `.env`.
  - Check driver name — adjust `MSSQL_DRIVER` if needed.
- Security: Never commit `.env` with credentials. Use secret managers for production.

Troubleshooting
- If the API reports "MCP ClientSession not ready", check server logs and ensure `server.py` can connect to the DB.
- If Gemini calls fail, verify network access and API key.
- For pyodbc issues, try running a simple pyodbc connect script to validate ODBC driver and credentials.

References (key files)
- server.py — MCP Server: exposes `get_schema` and `execute_sql`.
- main_client.py — NL→SQL and summarise helpers using Gemini; also a CLI pipeline.
- api.py — FastAPI wrapper creating a persistent MCP ClientSession and HTTP endpoints.
- stream_app.py — Streamlit chat interface that leverages the pipeline.

License / attribution
- This repository contains integration glue and example code. Ensure third‑party libraries (e.g., Gemini/genai) are used according to their terms.

