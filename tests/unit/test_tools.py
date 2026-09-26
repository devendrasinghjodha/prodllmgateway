import pytest
from app.providers.tools import ToolAdapter


def test_openai_to_gemini_tool_translation():
    adapter = ToolAdapter()
    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": "get_stock_price",
                "description": "Fetch current stock price",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"}
                    },
                    "required": ["symbol"],
                },
            },
        }
    ]

    gemini_tools = adapter.openai_to_gemini_tools(openai_tools)
    assert gemini_tools is not None
    assert len(gemini_tools) == 1
    assert "functionDeclarations" in gemini_tools[0]
    decl = gemini_tools[0]["functionDeclarations"][0]
    assert decl["name"] == "get_stock_price"
    assert decl["description"] == "Fetch current stock price"
    assert "parameters" in decl


def test_gemini_to_openai_tool_call_translation():
    adapter = ToolAdapter()
    gemini_candidate = {
        "content": {
            "parts": [
                {
                    "functionCall": {
                        "name": "get_stock_price",
                        "args": {"symbol": "GOOGL"},
                    }
                }
            ]
        }
    }

    tool_calls = adapter.gemini_response_to_openai_tool_calls(gemini_candidate)
    assert tool_calls is not None
    assert len(tool_calls) == 1
    assert tool_calls[0].type == "function"
    assert tool_calls[0].function.name == "get_stock_price"
    assert '"symbol": "GOOGL"' in tool_calls[0].function.arguments
