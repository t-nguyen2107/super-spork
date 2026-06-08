"""
Benchmark: compare first-query speed WITH vs WITHOUT warmup.
Measures cold-start vs warm-start latency for the LLM.
Run: python scripts/benchmark_warmup.py
"""
import os, sys, time, json

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = os.getenv("OLLAMA_BASE_URL")
MODEL = os.getenv("OLLAMA_MODEL")
client = OpenAI(base_url=BASE_URL, api_key="ollama")

def timed_call(label, messages, max_tokens=50):
    """Time a single LLM call and return elapsed seconds."""
    print(f"  {label}...", end=" ", flush=True)
    start = time.time()
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=max_tokens,
        )
        elapsed = time.time() - start
        tokens = resp.usage.total_tokens if resp.usage else "?"
        print(f"{elapsed:.2f}s ({tokens} tokens)")
        return elapsed
    except Exception as e:
        elapsed = time.time() - start
        print(f"ERROR {elapsed:.2f}s — {e}")
        return elapsed

def run_benchmark():
    # Unload model by waiting (LM Studio unloads after idle timeout)
    # We can't force unload, so we simulate by running a "cold" test first
    # then immediately a "warm" test

    print("=" * 60)
    print("WARMUP BENCHMARK")
    print(f"Model: {MODEL}")
    print(f"API:   {BASE_URL}")
    print("=" * 60)

    test_messages = [
        {"role": "system", "content": "You are a CRM assistant. Be brief."},
        {"role": "user", "content": "Hello"},
    ]

    results = {}

    # ── Phase 1: Simulate cold start (first call) ──
    print("\n--- Phase 1: Cold start (first LLM call in session) ---")
    cold_time = timed_call("Cold call", test_messages, max_tokens=5)
    results["cold_start"] = round(cold_time, 2)

    # ── Phase 2: Immediately after (warm) ──
    print("\n--- Phase 2: Warm (immediately after cold call) ---")
    warm_time = timed_call("Warm call", test_messages, max_tokens=5)
    results["warm_after_cold"] = round(warm_time, 2)

    # ── Phase 3: With explicit warmup first ──
    print("\n--- Phase 3: With explicit warmup (max_tokens=1) then real query ---")
    print("  Warmup call...", end=" ", flush=True)
    warmup_start = time.time()
    client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Hi"}],
        max_tokens=1,
    )
    warmup_time = time.time() - warmup_start
    print(f"{warmup_time:.2f}s")

    post_warmup_time = timed_call("Post-warmup call", test_messages, max_tokens=5)
    results["warmup_overhead"] = round(warmup_time, 2)
    results["post_warmup"] = round(post_warmup_time, 2)
    results["total_with_warmup"] = round(warmup_time + post_warmup_time, 2)

    # ── Phase 4: 5 consecutive queries to measure steady-state ──
    print("\n--- Phase 4: 5 consecutive real queries (steady-state) ---")
    queries = [
        "List 3 contacts",
        "What deals are in negotiation?",
        "Show me the pipeline summary",
        "Find Alice",
        "How many active contacts?",
    ]
    steady_times = []
    for q in queries:
        msgs = [
            {"role": "system", "content": "You are a CRM assistant. Be brief."},
            {"role": "user", "content": q},
        ]
        t = timed_call(f"Query: '{q[:30]}...'", msgs, max_tokens=20)
        steady_times.append(t)
    results["steady_avg"] = round(sum(steady_times) / len(steady_times), 2)
    results["steady_min"] = round(min(steady_times), 2)
    results["steady_max"] = round(max(steady_times), 2)

    # ── Summary ──
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Cold start (first call):          {results['cold_start']:>6}s")
    print(f"  Warm (immediately after cold):    {results['warm_after_cold']:>6}s")
    print(f"  Warmup overhead:                  {results['warmup_overhead']:>6}s")
    print(f"  Post-warmup (real query):         {results['post_warmup']:>6}s")
    print(f"  Total with warmup:                {results['total_with_warmup']:>6}s")
    print(f"  Steady-state avg (5 queries):     {results['steady_avg']:>6}s")
    print(f"  Steady-state range:               {results['steady_min']}s — {results['steady_max']}s")

    speedup = results["cold_start"] / results["warm_after_cold"] if results["warm_after_cold"] > 0 else 0
    print(f"  Cold vs Warm speedup:             {speedup:.1f}x")

    _script_dir = os.path.dirname(os.path.abspath(__file__))
    _out = os.path.join(_script_dir, "benchmark_warmup_results.json")
    with open(_out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to benchmark_warmup_results.json")

if __name__ == "__main__":
    run_benchmark()
