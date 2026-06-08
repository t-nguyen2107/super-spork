TOOLS = [
  {
    "type": "function",
    "function": {
      "name": "search_contacts",
      "description": "Search CRM contacts by name, company, city, or status. Use this when the user asks to find, list, or look up contacts or people.",
      "parameters": {
        "type": "object",
        "properties": {
          "name":    {"type":"string","description":"Partial name match (case-insensitive)"},
          "company": {"type":"string","description":"Partial company name match"},
          "city":    {"type":"string","description":"City name"},
          "status":  {"type":"string","enum":["active","inactive","lead"],"description":"Contact status"},
          "limit":   {"type":"integer","description":"Max results, default 10","default":10}
        }
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "get_deals",
      "description": "Retrieve deals from the CRM, optionally filtered by stage, owner, or value range. Use when asked about deals, pipeline, opportunities, or revenue.",
      "parameters": {
        "type": "object",
        "properties": {
          "stage":     {"type":"string","enum":["prospecting","qualified","proposal","negotiation","closed_won","closed_lost"]},
          "owner":     {"type":"string","description":"Sales owner username, e.g. sales_alice"},
          "min_value": {"type":"number","description":"Minimum deal value in USD"},
          "max_value": {"type":"number","description":"Maximum deal value in USD"},
          "limit":     {"type":"integer","default":10}
        }
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "get_contact_deals",
      "description": "Get all deals for a specific contact by their numeric ID.",
      "parameters": {
        "type": "object",
        "properties": {
          "contact_id": {"type":"integer","description":"The contact's ID from search_contacts results"}
        },
        "required": ["contact_id"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "get_pipeline_summary",
      "description": "Get a summary of the entire sales pipeline grouped by stage with deal counts and total values. Use for high-level pipeline or revenue questions."
    }
  },
  {
    "type": "function",
    "function": {
      "name": "semantic_search_contacts",
      "description": "Search contacts using semantic similarity. Use this when the user asks for contacts 'similar to', 'like', or describes a concept rather than an exact value — e.g. 'fintech companies in APAC', 'contacts who mentioned budget approval', 'anyone like our Singapore clients'. Do NOT use for exact lookups (name, email) — use search_contacts for those.",
      "parameters": {
        "type": "object",
        "required": ["query"],
        "properties": {
          "query":     {"type":"string","description":"Natural language description of what to find. Be descriptive — e.g. 'insurance companies interested in workers compensation renewal'."},
          "country":   {"type":"string","description":"ISO 2-letter country filter (optional)"},
          "industry":  {"type":"string","enum":["insurance","fintech","saas","manufacturing","retail"]},
          "status":    {"type":"string","enum":["active","inactive","lead","churned"]},
          "min_value": {"type":"number","description":"Only contacts with at least one deal above this USD value"},
          "limit":     {"type":"integer","default":10}
        }
      }
    }
  }
]