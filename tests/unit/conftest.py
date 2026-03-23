"""Shared test fixtures for strands-compose."""

import textwrap
import threading
from unittest.mock import MagicMock, patch

import pytest
from strands import Agent as _RealAgent

# -- Mock Agent -------------------------------------------------------- #


@pytest.fixture
def mock_agent():
    """Create a mock strands Agent for testing hooks and wrappers.

    The mock has:
    - agent_id = "test-agent"
    - tool_registry with registry dict
    - hook_registry that records add_hook calls
    - __call__ returns a mock AgentResult
    """
    agent = MagicMock()
    agent.agent_id = "test-agent"
    agent.tool_registry = MagicMock()
    agent.tool_registry.registry = {}
    agent.hook_registry = MagicMock()

    # Mock AgentResult
    result = MagicMock()
    result.message = {"content": [{"text": "Test response"}]}
    agent.return_value = result

    return agent


# -- Mock Model -------------------------------------------------------- #


@pytest.fixture
def mock_model():
    """Create a mock LLM model."""
    model = MagicMock()
    model.__class__.__name__ = "MockModel"
    return model


# -- Temporary Tool Files ---------------------------------------------- #


@pytest.fixture
def tools_dir(tmp_path):
    """Create a temporary directory with sample @tool files.

    Creates:
    - tools_dir/greet.py: @tool function 'greet'
    - tools_dir/calc.py: @tool function 'add_numbers'
    - tools_dir/_helpers.py: non-tool file (should be ignored)
    """
    tools = tmp_path / "tools"
    tools.mkdir()

    greet_file = tools / "greet.py"
    greet_file.write_text(
        textwrap.dedent("""\
        from strands import tool

        @tool
        def greet(name: str) -> str:
            \"\"\"Greet someone by name.\"\"\"
            return f"Hello, {name}!"
    """)
    )

    calc_file = tools / "calc.py"
    calc_file.write_text(
        textwrap.dedent("""\
        from strands import tool

        @tool
        def add_numbers(a: int, b: int) -> int:
            \"\"\"Add two numbers.\"\"\"
            return a + b
    """)
    )

    helper_file = tools / "_helpers.py"
    helper_file.write_text("# This is a helper, should be ignored\nHELPER_CONST = 42\n")

    return tools


@pytest.fixture
def plain_tools_file(tmp_path):
    """Create a .py file with plain (undecorated) public functions.

    Used to verify that only ``@tool``-decorated functions are collected;
    plain functions without the decorator should be ignored.
    """
    f = tmp_path / "plain_tools.py"
    f.write_text(
        textwrap.dedent("""\
        def count_words(text: str) -> int:
            \"\"\"Count the number of words in the given text.\"\"\"
            return len(text.split())


        def count_characters(text: str) -> int:
            \"\"\"Count characters in the given text, excluding spaces.\"\"\"
            return len(text.replace(" ", ""))


        def _private_helper():
            \"\"\"Should NOT be collected.\"\"\"
            pass
    """)
    )
    return f


# -- Sample YAML Configs ---------------------------------------------- #


@pytest.fixture
def simple_config_yaml(tmp_path):
    """Create a simple YAML config file."""
    config = tmp_path / "config.yaml"
    config.write_text(
        textwrap.dedent("""\
        agents:
          assistant:
            system_prompt: "You are a helpful assistant."
            max_tool_calls: 10
        entry: assistant
    """)
    )
    return config


# -- Patch Agent Init ------------------------------------------------- #


def _noop_init(self, **kwargs):
    """No-op Agent init that stores kwargs for test assertions."""
    self._init_kwargs = kwargs


@pytest.fixture
def patch_agent_init():
    """Patch Agent.__init__ with a no-op that stores kwargs.

    Use in tests that need to verify what kwargs were passed to Agent()
    without actually constructing a real Agent (which requires a model provider).

    The patched Agent stores all constructor kwargs in ``agent._init_kwargs``.
    """
    with patch.object(_RealAgent, "__init__", _noop_init):
        yield


@pytest.fixture
def full_config_yaml(tmp_path):
    """Create a full YAML config file with models, MCP, agents."""
    config = tmp_path / "config.yaml"
    config.write_text(
        textwrap.dedent("""\
        vars:
          MODEL_ID: "anthropic.claude-3-sonnet"

        models:
          default:
            provider: bedrock
            model_id: "${MODEL_ID}"

        agents:
          orchestrator:
            model: default
            system_prompt: "You are an orchestrator."
            max_tool_calls: 50

          analyzer:
            model: default
            system_prompt: "You analyze data."

        orchestrations:
          main:
            mode: delegate
            entry_name: orchestrator
            connections:
              - agent: analyzer
                description: "Analyze data"

        entry: main
    """)
    )
    return config


# -- Threading Helpers ------------------------------------------------- #


@pytest.fixture
def stop_event():
    """Create a threading.Event for stop signaling tests."""
    return threading.Event()


# -- Hook Event Factories --------------------------------------------- #


@pytest.fixture
def make_before_tool_event():
    """Factory for creating mock BeforeToolCallEvent objects."""

    def factory(tool_name="test_tool", tool_input=None, invocation_state=None):
        event = MagicMock()
        event.tool_use = {
            "id": f"tool_{tool_name}_123",
            "name": tool_name,
            "input": tool_input or {},
        }
        event.invocation_state = invocation_state or {}
        event.cancel_tool = False
        event.agent = MagicMock()
        event.agent.tool_registry.registry = {
            "test_tool": MagicMock(),
            "query_db": MagicMock(),
            "list_tables": MagicMock(),
        }
        return event

    return factory


@pytest.fixture
def make_after_tool_event():
    """Factory for creating mock AfterToolCallEvent objects."""

    def factory(tool_name="test_tool", result=None, exception=None):
        event = MagicMock()
        event.tool_use = {
            "id": f"tool_{tool_name}_123",
            "name": tool_name,
            "input": {},
        }
        event.result = result or {"content": [{"text": "Tool output"}]}
        event.exception = exception
        return event

    return factory
