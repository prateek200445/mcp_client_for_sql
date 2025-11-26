import streamlit as st
import asyncio
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


from main_client import nl_to_sql, summarise

st.set_page_config(page_title="SQL CHAT BOT", page_icon="🗄️")
st.title("SQL Chatbot")
st.write("Ask questions in natural language. The app will convert them to MSSQL, run the query, and summarize the results.")

if "history" not in st.session_state:
    st.session_state["history"] = []  

# input from ui
prompt = st.text_input("Enter your question", key="prompt_input")
col1, col2 = st.columns([1, 1.5])
with col2:
    send = st.button("Send")

async def _run_pipeline_once(user_prompt: str):
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"]
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # 1) Get schema
                schema_resp = await session.call_tool("get_schema", arguments={})
                schema_text = schema_resp.content[0].text

                # 2) NL -> SQL
                sql = await nl_to_sql(user_prompt, schema_text)

                # 3) Execute SQL
                exec_resp = await session.call_tool("execute_sql", arguments={"query": sql})
                output = exec_resp.content[0].text

                # 4) Summarize (use up to first 10 rows + header)
                lines = output.splitlines()
                rows_text = "\n".join(lines[:11]) if len(lines) > 11 else output
                summary = await summarise(user_prompt, sql, rows_text)

                return {"sql": sql, "output": output, "summary": summary}

    except Exception as e:
        return {"error": str(e)}

# trigger pipline on buttton

if send and prompt:
    st.session_state["history"].append({"role": "user", "text": prompt})
    with st.spinner("Processing..."):
        try:
            result = asyncio.run(_run_pipeline_once(prompt))

        except RuntimeError:

            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(_run_pipeline_once(prompt))
            loop.close()

    if result is None:
        st.session_state["history"].append({"role": "assistant", "text": "No response (internal error)."})
    elif "error" in result:
        st.session_state["history"].append({"role": "assistant", "text": f"Error: {result['error']}"})
    else:
        assistant_msg = f"SQL:\n{result['sql']}\n\nResults:\n{result['output']}\n\nSummary:\n{result['summary']}"
        st.session_state["history"].append({"role": "assistant", "text": assistant_msg})

for item in st.session_state["history"]:
    if item["role"] == "user":
        st.markdown(f"You: {item['text']}")
    else:
        st.markdown(f"Assistant:\n\n```\n{item['text']}\n```")
