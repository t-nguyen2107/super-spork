"""
Automated chat scenarios — sends real queries to the LLM and captures responses.
Run: python tests/chat_scenarios.py

This script simulates real user conversations by calling the LLM API directly
with tool definitions, then executing the tool calls the LLM makes, and looping
until the LLM gives a final text response.
"""
import os
import sys
import json
import time

# Add project root to path for src imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Fix Windows terminal encoding for unicode characters
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Load env vars
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from src.chatbot import tools as tool_defs
from src.chatbot import cli as chatbot

# ── Setup OpenAI client (LM Studio) ──
client = OpenAI(
    base_url=os.getenv("OLLAMA_BASE_URL"),
    api_key="lm-studio"
)
MODEL = os.getenv("OLLAMA_MODEL")

SYSTEM_PROMPT = (
    "You are a helpful CRM assistant. You have access to tools for querying "
    "a CRM database (contacts, deals, activities). Always use tools when the "
    "user asks about CRM data. Be concise and specific in your answers. "
    "When showing results, format them clearly."
)


def chat_with_tools(query, max_turns=5):
    """
    Send a query to the LLM, handle tool calls in a loop,
    return the final assistant message and all tool calls made.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query}
    ]

    tool_calls_log = []

    for turn in range(max_turns):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tool_defs.TOOLS,
            tool_choice="auto",
            temperature=0.3,
            max_tokens=500
        )

        msg = response.choices[0].message

        # If no tool calls, we have the final answer
        if not msg.tool_calls:
            return msg.content, tool_calls_log

        # Process each tool call
        messages.append(msg)

        for tc in msg.tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            tool_calls_log.append({
                "tool": fn_name,
                "args": fn_args
            })

            # Execute tool
            result = chatbot.run_tool(fn_name, fn_args)

            # Truncate large results for display
            result_display = result
            if isinstance(result, list) and len(result) > 5:
                result_display = result[:5]
                result_display.append(f"... ({len(result)} total rows)")

            tool_calls_log[-1]["result_preview"] = result_display

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, default=str)
            })

    return "Max turns reached without final answer.", tool_calls_log


# ── Define test scenarios ──
SCENARIOS = [
    {
        "name": "Simple contact search by name",
        "query": "Find contacts named Alice"
    },
    {
        "name": "Search contacts by industry",
        "query": "Show me all SaaS contacts in Vietnam"
    },
    {
        "name": "Deals in negotiation stage",
        "query": "What deals are currently in negotiation?"
    },
    {
        "name": "High-value deals",
        "query": "Show me deals worth more than $50,000"
    },
    {
        "name": "Pipeline summary",
        "query": "Give me a pipeline summary"
    },
    {
        "name": "Contact deals lookup",
        "query": "What deals does the first contact named Alice have?"
    },
    {
        "name": "Multi-filter search",
        "query": "Find active fintech contacts in Australia"
    },
    {
        "name": "Semantic search (natural language)",
        "query": "Find contacts who might be interested in cyber insurance"
    },
    {
        "name": "Complex question",
        "query": "Who are our top VIP enterprise clients and what deals do they have open?"
    },
    {
        "name": "Out of scope question",
        "query": "What's the weather like today?"
    }
]


def main():
    print("=" * 70)
    print("CRM CHATBOT — REAL CHAT SCENARIOS")
    print("=" * 70)
    print(f"Model: {MODEL}")
    print(f"API:   {os.getenv('OLLAMA_BASE_URL')}")
    print("=" * 70)

    results = []

    for i, scenario in enumerate(SCENARIOS, 1):
        print(f"\n{'─' * 70}")
        print(f"SCENARIO {i}/10: {scenario['name']}")
        print(f"Query: \"{scenario['query']}\"")
        print(f"{'─' * 70}")

        start = time.time()
        try:
            answer, tool_log = chat_with_tools(scenario["query"])
            elapsed = time.time() - start

            # Show tool calls
            if tool_log:
                for tc in tool_log:
                    args_str = ", ".join(f"{k}={v}" for k, v in tc["args"].items())
                    print(f"  TOOL → {tc['tool']}({args_str})")
                    if "result_preview" in tc:
                        preview = tc["result_preview"]
                        if isinstance(preview, list) and len(preview) > 0:
                            first = preview[0] if isinstance(preview[0], dict) else preview[0]
                            if isinstance(first, dict):
                                print(f"         ↳ {len(preview)} rows, first: {list(first.keys())}")
                            else:
                                print(f"         ↳ {preview}")
                        else:
                            print(f"         ↳ {preview}")
            else:
                print("  (no tool calls)")

            print(f"\n  ANSWER ({elapsed:.1f}s):")
            # Indent each line of the answer
            for line in answer.split("\n"):
                print(f"    {line}")

            results.append({
                "scenario": scenario["name"],
                "query": scenario["query"],
                "tools_used": [tc["tool"] for tc in tool_log],
                "answer": answer,
                "time": round(elapsed, 1),
                "status": "OK"
            })

        except Exception as e:
            elapsed = time.time() - start
            print(f"  ERROR: {e}")
            results.append({
                "scenario": scenario["name"],
                "query": scenario["query"],
                "tools_used": [],
                "answer": str(e),
                "time": round(elapsed, 1),
                "status": "ERROR"
            })

    # ── Summary ──
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    ok = sum(1 for r in results if r["status"] == "OK")
    err = sum(1 for r in results if r["status"] == "ERROR")
    avg_time = sum(r["time"] for r in results) / len(results) if results else 0
    all_tools = set()
    for r in results:
        all_tools.update(r["tools_used"])

    print(f"  Passed:   {ok}/{len(results)}")
    print(f"  Errors:   {err}/{len(results)}")
    print(f"  Avg time: {avg_time:.1f}s")
    print(f"  Tools used: {', '.join(sorted(all_tools)) if all_tools else 'none'}")

    for r in results:
        status = "OK" if r["status"] == "OK" else "ERR"
        tools = ", ".join(r["tools_used"]) if r["tools_used"] else "-"
        print(f"  [{status}] {r['scenario']:<40} {r['time']:>5.1f}s  tools: {tools}")

    # Save results as JSON for the HTML doc
    _out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_scenario_results.json")
    with open(_out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to chat_scenario_results.json")


if __name__ == "__main__":
    main()
