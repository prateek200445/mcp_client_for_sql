import asyncio
import os
import google.generativeai as genai
from dotenv import load_dotenv

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

# Load environment variables from .env file
load_dotenv()


# Gemini Setup 

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# function natural language to convert to sql query

async def nl_to_sql(user_prompt: str, schema: str):
    """Convert natural language to MSSQL query using Gemini."""
    system_prompt = f"""
Convert the user's request to a VALID MSSQL SQL query.
Return ONLY the SQL query without any markdown formatting, explanations, or code blocks.

Schema:
{schema}

Rules:
- Use SELECT TOP N instead of LIMIT N
- Do NOT use SHOW TABLES (use SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES instead)
- Return only the raw SQL query
- No markdown code blocks (no ```sql or ```)
- No explanations or comments
"""

    response = genai.GenerativeModel("gemini-2.5-flash").generate_content(
        system_prompt + "\n\nUser request: " + user_prompt
    )
    
    sql = response.text.strip()
    
    # Clean up any markdown code blocks if present
    if sql.startswith("```"):
        lines = sql.split("\n")
        # Remove first line (```sql) and last line (```)
        sql = "\n".join(lines[1:-1]).strip() if len(lines) > 2 else sql
        # Additional cleanup in case of inline ```
        sql = sql.replace("```sql", "").replace("```", "").strip()
    
    return sql


async def summarise(user_prompt: str, sql: str, rows: str):
    """Generate a natural language summary of the query results."""
    prompt = f"""
User asked: {user_prompt}

SQL Executed:
{sql}

Results (first 10 rows):
{rows}

Provide a clear, concise summary for the user. Include:
1. A direct answer to their question
2. Key insights from the data
3. Any notable patterns or findings

Keep it natural and conversational.
"""

    response = genai.GenerativeModel("gemini-2.5-flash").generate_content(prompt)
    return response.text.strip()


async def run_pipeline(session: ClientSession):
    """Main pipeline: NL -> SQL -> Results -> Summary."""
    print("\n🚀 Connected to MCP SQL Server!\n")
    print("💡 Type 'exit', 'quit', or 'q' to close the connection\n")
    print("=" * 60)

    # Get schema once at the start
    print("📋 Fetching database schema...")
    schema_result = await session.call_tool("get_schema", arguments={})
    schema_text = schema_result.content[0].text
    print("✅ Schema retrieved\n")
    print("=" * 60)

    while True:
        try:
            # Get user input
            user_prompt = input("\n💬 Enter your question: ").strip()

            # Check for exit commands
            if user_prompt.lower() in ['exit', 'quit', 'q', '']:
                print("\n👋 Goodbye! Closing connection...\n")
                break

            # 2. Convert NL → SQL using Gemini
            print("\n🤖 Converting to SQL...")
            sql_query = await nl_to_sql(user_prompt, schema_text)
            print(f"\n📝 Generated SQL:\n{sql_query}\n")

            # 3. Execute SQL on MCP server
            print("⚡ Executing query...")
            sql_exec = await session.call_tool("execute_sql", arguments={"query": sql_query})
            sql_output = sql_exec.content[0].text

            # Check for errors
            if sql_output.startswith("Error"):
                print(f"\n❌ {sql_output}")
                continue

            print("✅ Query executed successfully")

            # Get only top 10 rows + header for summary
            lines = sql_output.splitlines()
            rows_text = "\n".join(lines[:11]) if len(lines) > 11 else sql_output

            # 4. Generate final answer from LLM
            print("\n🧠 Generating summary...\n")
            answer = await summarise(user_prompt, sql_query, rows_text)

            print("=" * 60)
            print("🟦 FINAL ANSWER:")
            print("=" * 60)
            print(answer)
            print("=" * 60)
            print(f"\n📊 Total rows returned: {len(lines) - 1}")  # -1 for header
            print("=" * 60)

        except KeyboardInterrupt:
            print("\n\n👋 Interrupted! Closing connection...\n")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            print("Let's try another query!\n")
            continue


async def main():
    """Main entry point."""
    print("=" * 60)
    print("🔌 Starting MCP Client for MSSQL...")
    print("=" * 60)

    # Check for required environment variables
    if not os.getenv("GOOGLE_API_KEY"):
        print("\n❌ Error: GOOGLE_API_KEY not found in environment variables")
        print("Please set it with: $env:GOOGLE_API_KEY='your_key'")
        return

    # Define server parameters
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"]
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the session
                await session.initialize()

                # List available tools (optional, for debugging)
                tools = await session.list_tools()
                print(f"✅ Connected! Available tools: {[tool.name for tool in tools.tools]}")

                # Run the pipeline
                await run_pipeline(session)

    except Exception as e:
        print(f"\n❌ Failed to connect to MCP server: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Make sure server.py is in the same directory")
        print("2. Check that all database environment variables are set:")
        print("   - MSSQL_HOST")
        print("   - MSSQL_USER")
        print("   - MSSQL_PASSWORD")
        print("   - MSSQL_DATABASE")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())