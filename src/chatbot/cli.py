import os, json, sys
from openai import OpenAI, APIConnectionError, APITimeoutError, APIError
from rich.console import Console
from rich.markdown import Markdown
from dotenv import load_dotenv
from src.db import search_contacts, get_deals, get_contact_deals, get_pipeline_summary, semantic_search_contacts
from src.chatbot.tools import TOOLS as TOOL_DEFS

load_dotenv()
console = Console()

BASE_URL = os.getenv("OLLAMA_BASE_URL")
MODEL = os.getenv("OLLAMA_MODEL")

missing = [k for k, v in [("OLLAMA_BASE_URL", BASE_URL), ("OLLAMA_MODEL", MODEL)] if not v]
if missing:
    console.print(f"[red]Missing env vars: {', '.join(missing)}[/red]")
    console.print("[dim]Copy .env.example to .env and fill in values.[/dim]")
    sys.exit(1)

client = OpenAI(base_url=BASE_URL, api_key="ollama")

MAX_HISTORY = 20

SYSTEM = """You are a helpful CRM assistant. You have access to tools that query a
PostgreSQL CRM database containing contacts and deals.

Rules:
- Always use a tool to answer questions about contacts or deals — never guess.
- When you get tool results, summarise them clearly for the user.
- For lists, format them as markdown tables or bullet points.
- If a query returns no results, say so clearly and suggest alternatives.
- If a tool returns an error, explain it to the user and suggest alternatives.
- Deal values are in USD. Stages: prospecting → qualified → proposal → negotiation → closed_won / closed_lost."""

TOOL_MAP = {
    "search_contacts":          search_contacts,
    "get_deals":                get_deals,
    "get_contact_deals":        get_contact_deals,
    "get_pipeline_summary":     get_pipeline_summary,
    "semantic_search_contacts": semantic_search_contacts,
}

def run_tool(name, args):
    fn = TOOL_MAP.get(name)
    if not fn:
        return {"error": f"Unknown tool: {name}"}
    try:
        result = fn(**args)
        return [dict(r) for r in result]
    except Exception as e:
        return {"error": str(e)}

def trim_history(history):
    if len(history) <= MAX_HISTORY + 1:
        return history
    system = history[0]
    rest = history[-MAX_HISTORY:]
    return [system] + rest

def chat(history):
    while True:
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=history,
                tools=TOOL_DEFS,
                tool_choice="auto"
            )
        except (APIConnectionError, APITimeoutError) as e:
            console.print(f"[red]Ollama connection error: {e}[/red]")
            console.print("[dim]Make sure Ollama is running and the model is pulled.[/dim]")
            history.append({"role": "assistant", "content": "Sorry, I couldn't reach the LLM. Please check that Ollama is running."})
            return history
        except APIError as e:
            console.print(f"[red]Ollama API error: {e}[/red]")
            history.append({"role": "assistant", "content": f"LLM error: {e}. Try again."})
            return history

        msg = response.choices[0].message

        if msg.tool_calls:
            history.append(msg)
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError as e:
                    console.print(f"[yellow]Malformed tool arguments: {e}[/yellow]")
                    args = {}
                console.print(f"[dim]  → calling {tc.function.name}({args})[/dim]")
                result = run_tool(tc.function.name, args)
                history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str)
                })
            history = trim_history(history)
        else:
            history.append({"role": "assistant", "content": msg.content})
            console.print(Markdown(msg.content or ""))
            return trim_history(history)

def warmup():
    """Send a tiny request to pre-load the model into GPU/CPU cache.
    
    The first LLM call is always slow because LM Studio needs to:
    1. Load model weights into GPU VRAM (or system RAM for CPU)
    2. Allocate KV-cache memory
    3. Warm up CUDA kernels / Metal shaders
    
    This warmup call triggers all of that upfront so the first real
    user query gets fast response times instead of a 10-30s cold start.
    
    We send a minimal prompt ("Hi") with max_tokens=1 to keep it cheap.
    The response is discarded — we only care about the side effect of
    loading the model into memory.
    """
    console.print("[dim]Warming up model...[/dim]", end=" ")
    try:
        start = __import__("time").time()
        client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1,
        )
        elapsed = __import__("time").time() - start
        console.print(f"[dim]done ({elapsed:.1f}s)[/dim]")
    except Exception:
        console.print("[dim]skip (model already loaded or unavailable)[/dim]")

def main():
    console.print("[bold blue]CRM Chatbot — P1 (Tool Calling)[/bold blue]")
    console.print(f"[dim]Ollama model:[/dim] {MODEL}")
    warmup()
    console.print("[dim]Type 'exit' to quit[/dim]\n")
    history = [{"role": "system", "content": SYSTEM}]
    while True:
        try:
            user_input = console.input("[bold]You:[/bold] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user_input.lower() in ("exit", "quit", "bye"):
            break
        if not user_input:
            continue
        history.append({"role": "user", "content": user_input})
        history = chat(history)
        print()

if __name__ == "__main__":
    main()
