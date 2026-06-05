import os, json
from openai import OpenAI
from rich.console import Console
from rich.markdown import Markdown
from dotenv import load_dotenv
import db, tools as tool_defs

load_dotenv()
console = Console()

client = OpenAI(
    base_url=os.getenv("OLLAMA_BASE_URL"),
    api_key="ollama"  # required by SDK, ignored by Ollama
)
MODEL = os.getenv("OLLAMA_MODEL")

SYSTEM = """You are a helpful CRM assistant. You have access to tools that query a 
PostgreSQL CRM database containing contacts and deals.

Rules:
- Always use a tool to answer questions about contacts or deals — never guess.
- When you get tool results, summarise them clearly for the user.
- For lists, format them as markdown tables or bullet points.
- If a query returns no results, say so clearly and suggest alternatives.
- Deal values are in USD. Stages: prospecting → qualified → proposal → negotiation → closed_won / closed_lost."""

TOOL_MAP = {
    "search_contacts":    db.search_contacts,
    "get_deals":          db.get_deals,
    "get_contact_deals":  db.get_contact_deals,
    "get_pipeline_summary": db.get_pipeline_summary,
}

def run_tool(name, args):
    fn = TOOL_MAP.get(name)
    if not fn:
        return {"error": f"Unknown tool: {name}"}
    result = fn(**args)
    return [dict(r) for r in result]

def chat(history):
    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=history,
            tools=tool_defs.TOOLS,
            tool_choice="auto"
        )
        msg = response.choices[0].message

        if msg.tool_calls:
            history.append(msg)
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                console.print(f"[dim]  → calling {tc.function.name}({args})[/dim]")
                result = run_tool(tc.function.name, args)
                history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str)
                })
        else:
            history.append({"role":"assistant","content":msg.content})
            console.print(Markdown(msg.content or ""))
            return history

def main():
    console.print("[bold blue]CRM Chatbot — P1 (Tool Calling)[/bold blue]")
    console.print("[dim]Ollama model:[/dim]", MODEL)
    console.print("[dim]Type 'exit' to quit[/dim]\n")
    history = [{"role":"system","content":SYSTEM}]
    while True:
        try:
            user_input = console.input("[bold]You:[/bold] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user_input.lower() in ("exit","quit","bye"):
            break
        if not user_input:
            continue
        history.append({"role":"user","content":user_input})
        history = chat(history)
        print()

if __name__ == "__main__":
    main()