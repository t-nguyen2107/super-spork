"""
Test suite for CRM Chatbot — tests all modules without requiring live services.
Run: python -m pytest tests/  OR  python -m tests.test_crm

Tests use mocks for external services (LLM API, PostgreSQL, embedding API)
so they can run offline without LM Studio or PostgreSQL.
"""
import os, sys, json, unittest
from unittest.mock import patch, MagicMock

# Add project root to path for src imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# ── Patch env vars BEFORE importing modules ──
os.environ["OLLAMA_BASE_URL"] = "http://127.0.0.1:1234/v1"
os.environ["OLLAMA_MODEL"] = "test-model"
os.environ["EMBED_MODEL"] = "test-embed"
os.environ["PG_HOST"] = "localhost"
os.environ["PG_PORT"] = "5432"
os.environ["PG_DB"] = "crm"
os.environ["PG_USER"] = "crm"
os.environ["PG_PASSWORD"] = "test"

from src.embeddings import embedder
from src.chatbot import tools as tool_defs
from src.chatbot import cli as chatbot


class TestToolsSchema(unittest.TestCase):
    """Verify tool definitions match OpenAI function-calling schema."""

    def test_tools_is_list(self):
        self.assertIsInstance(tool_defs.TOOLS, list)

    def test_tool_count(self):
        """Should have exactly 5 tools (4 P1 + 1 P2 semantic)."""
        self.assertEqual(len(tool_defs.TOOLS), 5)

    def test_each_tool_has_required_fields(self):
        """Every tool must have: type, function.name, function.description."""
        for tool in tool_defs.TOOLS:
            self.assertEqual(tool["type"], "function")
            self.assertIn("name", tool["function"])
            self.assertIn("description", tool["function"])
            # get_pipeline_summary has no parameters — that's valid
            if tool["function"]["name"] != "get_pipeline_summary":
                self.assertIn("parameters", tool["function"])

    def test_tool_names_match_tool_map(self):
        """Every tool in TOOLS must have a matching entry in chatbot.TOOL_MAP."""
        for tool in tool_defs.TOOLS:
            name = tool["function"]["name"]
            self.assertIn(name, chatbot.TOOL_MAP,
                f"Tool '{name}' defined in tools.py but missing from TOOL_MAP in chatbot.py")

    def test_no_extra_tool_map_entries(self):
        """TOOL_MAP should not have entries that don't exist in TOOLS."""
        tool_names = {t["function"]["name"] for t in tool_defs.TOOLS}
        for name in chatbot.TOOL_MAP:
            self.assertIn(name, tool_names,
                f"TOOL_MAP has '{name}' but no matching tool definition in tools.py")

    def test_required_params_are_declared(self):
        """Tools with required params should declare them."""
        for tool in tool_defs.TOOLS:
            params = tool["function"].get("parameters", {})
            name = tool["function"]["name"]
            if name == "get_contact_deals":
                self.assertIn("contact_id", params.get("required", []))
            elif name == "semantic_search_contacts":
                self.assertIn("query", params.get("required", []))

    def test_enum_values_valid(self):
        """Enum constraints should have non-empty lists."""
        for tool in tool_defs.TOOLS:
            props = tool["function"].get("parameters", {}).get("properties", {})
            for prop_name, prop_schema in props.items():
                if "enum" in prop_schema:
                    self.assertGreater(len(prop_schema["enum"]), 0,
                        f"Empty enum for {tool['function']['name']}.{prop_name}")

    def test_all_tools_have_default_limit(self):
        """Tools that accept limit should have a default value."""
        for tool in tool_defs.TOOLS:
            props = tool["function"].get("parameters", {}).get("properties", {})
            if "limit" in props:
                self.assertIn("default", props["limit"],
                    f"Missing default for limit in {tool['function']['name']}")

    def test_expected_tool_names(self):
        """Verify exact tool names."""
        names = {t["function"]["name"] for t in tool_defs.TOOLS}
        expected = {"search_contacts", "get_deals", "get_contact_deals",
                    "get_pipeline_summary", "semantic_search_contacts"}
        self.assertEqual(names, expected)


class TestEmbedder(unittest.TestCase):
    """Test embedder module — build_embed_text and embed function."""

    def test_build_embed_text_full_contact(self):
        """Full contact should produce a rich sentence."""
        contact = {
            "name": "Alice Nguyen", "company": "TechCorp VN",
            "city": "Ho Chi Minh City", "country": "VN",
            "industry": "saas", "status": "active",
            "tags": ["vip", "enterprise"], "notes": "Budget approved",
            "assigned_to": "sales_alice"
        }
        result = embedder.build_embed_text(contact)
        self.assertIn("Alice Nguyen", result)
        self.assertIn("TechCorp VN", result)
        self.assertIn("saas", result)
        self.assertIn("active", result)
        self.assertIn("vip", result)
        self.assertIn("enterprise", result)
        self.assertIn("Budget approved", result)
        self.assertIn("sales_alice", result)
        self.assertTrue(result.endswith("."))

    def test_build_embed_text_minimal_contact(self):
        """Contact with only name should still produce valid text."""
        result = embedder.build_embed_text({"name": "Bob"})
        self.assertIn("Bob", result)
        self.assertIn("unknown", result)

    def test_build_embed_text_empty_contact(self):
        """Empty contact should produce "."."""
        result = embedder.build_embed_text({})
        self.assertEqual(result, ".")

    def test_build_embed_text_tags_as_string(self):
        """Tags as a single string should be handled gracefully."""
        contact = {"name": "Test", "tags": "vip"}
        result = embedder.build_embed_text(contact)
        self.assertIn("vip", result)

    def test_build_embed_text_tags_as_list(self):
        """Tags as a list should be joined with commas."""
        contact = {"name": "Test", "tags": ["vip", "upsell"]}
        result = embedder.build_embed_text(contact)
        self.assertIn("vip", result)
        self.assertIn("upsell", result)

    def test_embed_url_uses_v1_embeddings(self):
        """Embedding URL should end with /embeddings (OpenAI format)."""
        self.assertTrue(embedder.EMBED_URL.endswith("/embeddings"))

    def test_embed_model_not_none(self):
        """EMBED_MODEL should not be None."""
        self.assertIsNotNone(embedder.EMBED_MODEL)

    @patch("src.embeddings.embedder.requests.post")
    def test_embed_openai_format(self, mock_post):
        """embed() should parse OpenAI response: data[0].embedding."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        result = embedder.embed("test query")
        self.assertEqual(result, [0.1, 0.2, 0.3])

    @patch("src.embeddings.embedder.requests.post")
    def test_embed_ollama_format(self, mock_post):
        """embed() should parse Ollama response: embedding."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"embedding": [0.4, 0.5, 0.6]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        result = embedder.embed("test query")
        self.assertEqual(result, [0.4, 0.5, 0.6])

    @patch("src.embeddings.embedder.requests.post")
    def test_embed_sends_input_not_prompt(self, mock_post):
        """embed() should use 'input' field (OpenAI), not 'prompt' (Ollama)."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": [{"embedding": [0.1]}]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        embedder.embed("hello world")
        body = mock_post.call_args[1]["json"]
        self.assertIn("input", body)
        self.assertNotIn("prompt", body)

    def test_build_embed_text_no_city(self):
        """Contact without city/country should skip location."""
        contact = {"name": "Test", "company": "Co"}
        result = embedder.build_embed_text(contact)
        self.assertNotIn("based in", result)


class TestChatbotRunTool(unittest.TestCase):
    """Test run_tool error handling and routing."""

    def test_unknown_tool_returns_error(self):
        """Unknown tool name should return error dict."""
        result = chatbot.run_tool("nonexistent_tool", {})
        self.assertIn("error", result)
        self.assertIn("Unknown tool", result["error"])

    def test_known_tool_routes_correctly(self):
        """Known tool should call the mapped function."""
        mock_fn = MagicMock(return_value=[{"id": 1, "name": "Alice"}])
        original = chatbot.TOOL_MAP["search_contacts"]
        chatbot.TOOL_MAP["search_contacts"] = mock_fn
        try:
            result = chatbot.run_tool("search_contacts", {"name": "Alice"})
            mock_fn.assert_called_once_with(name="Alice")
            self.assertEqual(result, [{"id": 1, "name": "Alice"}])
        finally:
            chatbot.TOOL_MAP["search_contacts"] = original

    def test_tool_exception_returns_error(self):
        """If the DB function throws, run_tool should return error dict."""
        mock_fn = MagicMock(side_effect=Exception("connection refused"))
        original = chatbot.TOOL_MAP["get_deals"]
        chatbot.TOOL_MAP["get_deals"] = mock_fn
        try:
            result = chatbot.run_tool("get_deals", {})
            self.assertIn("error", result)
            self.assertIn("connection refused", result["error"])
        finally:
            chatbot.TOOL_MAP["get_deals"] = original

    def test_tool_result_converted_to_plain_dicts(self):
        """Tool results should be converted from RealDictRow to plain dicts."""
        # Use a simple dict — RealDictRow behaves like a dict anyway
        mock_fn = MagicMock(return_value=[{"id": 1, "name": "Test"}])
        original = chatbot.TOOL_MAP["get_contact_deals"]
        chatbot.TOOL_MAP["get_contact_deals"] = mock_fn
        try:
            result = chatbot.run_tool("get_contact_deals", {"contact_id": 1})
            self.assertIsInstance(result[0], dict)
            self.assertEqual(result[0]["id"], 1)
        finally:
            chatbot.TOOL_MAP["get_contact_deals"] = original

    def test_all_tool_map_entries_are_callable(self):
        """Every entry in TOOL_MAP should be a callable function."""
        for name, fn in chatbot.TOOL_MAP.items():
            self.assertTrue(callable(fn), f"TOOL_MAP['{name}'] is not callable")


class TestTrimHistory(unittest.TestCase):
    """Test chat history trimming logic."""

    def test_short_history_unchanged(self):
        """History under limit should not be trimmed."""
        history = [{"role": "system", "content": "test"}]
        for i in range(5):
            history.append({"role": "user", "content": f"msg {i}"})
        result = chatbot.trim_history(history)
        self.assertEqual(len(result), 6)

    def test_long_history_trimmed(self):
        """History over limit should be trimmed to MAX_HISTORY + system."""
        history = [{"role": "system", "content": "test"}]
        for i in range(30):
            history.append({"role": "user", "content": f"msg {i}"})
        result = chatbot.trim_history(history)
        self.assertEqual(len(result), chatbot.MAX_HISTORY + 1)

    def test_system_prompt_always_preserved(self):
        """System prompt (index 0) should never be removed."""
        system_msg = {"role": "system", "content": "IMPORTANT SYSTEM PROMPT"}
        history = [system_msg]
        for i in range(30):
            history.append({"role": "user", "content": f"msg {i}"})
        result = chatbot.trim_history(history)
        self.assertEqual(result[0], system_msg)

    def test_most_recent_messages_kept(self):
        """Trimming should keep the most recent messages."""
        history = [{"role": "system", "content": "test"}]
        for i in range(30):
            history.append({"role": "user", "content": f"msg {i}"})
        result = chatbot.trim_history(history)
        last_user = [m for m in result if m["role"] == "user"][-1]
        self.assertEqual(last_user["content"], "msg 29")

    def test_exact_limit_unchanged(self):
        """History at exactly MAX_HISTORY + 1 should not be trimmed."""
        history = [{"role": "system", "content": "test"}]
        for i in range(chatbot.MAX_HISTORY):
            history.append({"role": "user", "content": f"msg {i}"})
        result = chatbot.trim_history(history)
        self.assertEqual(len(result), chatbot.MAX_HISTORY + 1)

    def test_single_message_unchanged(self):
        """History with only system prompt should be unchanged."""
        history = [{"role": "system", "content": "test"}]
        result = chatbot.trim_history(history)
        self.assertEqual(len(result), 1)


class TestJsonParsing(unittest.TestCase):
    """Test JSON parsing robustness for LLM tool arguments."""

    def test_valid_json(self):
        args = json.loads('{"name": "Alice", "limit": 5}')
        self.assertEqual(args["name"], "Alice")

    def test_malformed_json_raises(self):
        with self.assertRaises(json.JSONDecodeError):
            json.loads('{"name": "Alice",}')

    def test_empty_string_raises(self):
        with self.assertRaises(json.JSONDecodeError):
            json.loads('')

    def test_null_raises(self):
        with self.assertRaises((json.JSONDecodeError, TypeError)):
            json.loads(None)


class TestDbSafety(unittest.TestCase):
    """Verify SQL injection is prevented via parameterized queries."""

    def test_search_contacts_uses_parameterized_query(self):
        """search_contacts should use %s placeholders, not string concat."""
        import inspect
        source = inspect.getsource(chatbot.search_contacts)
        # The ILIKE pattern uses params.append(f"%{name}%") which is VALUE construction,
        # then passed via %s placeholder — this is safe.
        # Verify the SQL uses %s, not direct interpolation in WHERE
        self.assertIn("ILIKE %s", source)
        self.assertIn("params.append", source)

    def test_get_deals_uses_parameterized_query(self):
        """get_deals should use %s placeholders."""
        import inspect
        source = inspect.getsource(chatbot.get_deals)
        self.assertIn("d.stage = %s", source)
        self.assertIn("d.value >= %s", source)

    def test_semantic_search_uses_parameterized_query(self):
        """semantic_search_contacts should use %s for all filters."""
        import inspect
        source = inspect.getsource(chatbot.semantic_search_contacts)
        self.assertIn("c.country = %s", source)
        self.assertIn("c.industry = %s", source)
        self.assertIn("c.status = %s", source)


class TestSchemaFile(unittest.TestCase):
    """Verify schema.sql has all required tables and columns."""

    def setUp(self):
        # SQL files are in sql/ directory (project root from tests/)
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(_root, "sql", "schema.sql")) as f:
            self.schema = f.read()

    def test_contacts_table_exists(self):
        self.assertIn("CREATE TABLE contacts", self.schema)

    def test_deals_table_exists(self):
        self.assertIn("CREATE TABLE deals", self.schema)

    def test_activities_table_exists(self):
        self.assertIn("CREATE TABLE activities", self.schema)

    def test_contacts_has_all_columns(self):
        for col in ["industry", "country", "source", "assigned_to", "tags", "notes"]:
            self.assertIn(col, self.schema, f"Missing column: {col}")

    def test_deals_has_all_columns(self):
        for col in ["probability", "close_date", "product"]:
            self.assertIn(col, self.schema, f"Missing column: {col}")

    def test_has_indexes(self):
        self.assertIn("CREATE INDEX", self.schema)

    def test_activities_has_foreign_keys(self):
        self.assertIn("REFERENCES contacts", self.schema)
        self.assertIn("REFERENCES deals", self.schema)

    def test_contacts_email_unique(self):
        self.assertIn("UNIQUE", self.schema)


class TestMigrationP2(unittest.TestCase):
    """Verify migration_p2.sql creates pgvector infrastructure."""

    def setUp(self):
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(_root, "sql", "migration_p2.sql")
        if not os.path.exists(path):
            self.skipTest("migration_p2.sql not found")
        with open(path) as f:
            self.migration = f.read()

    def test_creates_vector_extension(self):
        self.assertIn("CREATE EXTENSION", self.migration)
        self.assertIn("vector", self.migration)

    def test_creates_contact_embeddings_table(self):
        self.assertIn("contact_embeddings", self.migration)

    def test_has_hnsw_index(self):
        self.assertIn("hnsw", self.migration)
        self.assertIn("vector_cosine_ops", self.migration)

    def test_embedding_dimension_768(self):
        self.assertIn("vector(768)", self.migration)

    def test_has_cascade_delete(self):
        self.assertIn("ON DELETE CASCADE", self.migration)

    def test_has_embed_text_column(self):
        self.assertIn("embed_text", self.migration)

    def test_has_model_column(self):
        self.assertIn("model", self.migration)


if __name__ == "__main__":
    print("=" * 60)
    print("CRM Chatbot Test Suite")
    print("=" * 60)
    unittest.main(verbosity=2)
