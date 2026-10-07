import json
import logging
import uuid
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger("prodllm.tools")


class FunctionCall(BaseModel):
    name: str
    arguments: str  # JSON formatted string


class ToolCall(BaseModel):
    id: str
    type: str = "function"
    function: FunctionCall


class ToolAdapter:
    """
    Universal Cross-Provider Tool & Function Calling Normalization Engine.
    Seamlessly translates tools and function definitions across OpenAI, Gemini, and Anthropic.
    """

    @staticmethod
    def openai_to_gemini_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        """
        Translates OpenAI tools list to Gemini functionDeclarations format.
        """
        if not tools:
            return None

        function_declarations = []
        for tool in tools:
            if tool.get("type") == "function" and "function" in tool:
                fn = tool["function"]
                decl = {
                    "name": fn.get("name"),
                    "description": fn.get("description", ""),
                }
                if "parameters" in fn:
                    decl["parameters"] = fn["parameters"]
                function_declarations.append(decl)
            elif "name" in tool:
                function_declarations.append(tool)

        if not function_declarations:
            return None

        return [{"functionDeclarations": function_declarations}]

    @staticmethod
    def gemini_response_to_openai_tool_calls(candidate: dict[str, Any]) -> list[ToolCall] | None:
        """
        Translates Gemini candidates functionCall part into OpenAI standard tool_calls.
        """
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        tool_calls = []

        for part in parts:
            if "functionCall" in part:
                fc = part["functionCall"]
                fn_name = fc.get("name", "")
                args = fc.get("args", {})
                args_str = json.dumps(args) if isinstance(args, dict) else str(args)

                tool_calls.append(
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:16]}",
                        type="function",
                        function=FunctionCall(
                            name=fn_name,
                            arguments=args_str,
                        ),
                    )
                )

        return tool_calls if tool_calls else None


tool_adapter = ToolAdapter()
