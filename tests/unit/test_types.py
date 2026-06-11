"""Tests for the EventType StrEnum and Session Manifest models."""

from __future__ import annotations

from enum import StrEnum

import pytest

from strands_compose.types import (
    AgentCoreProviderDescriptor,
    AgentDescriptor,
    CustomProviderDescriptor,
    EdgeRef,
    EntryDescriptor,
    EventType,
    FileProviderDescriptor,
    ModelDescriptor,
    NodeRef,
    OrchestrationDescriptor,
    S3ProviderDescriptor,
    SessionManifest,
)


class TestEventTypeEnum:
    """Verify EventType is a proper StrEnum with all expected members."""

    def test_is_str_enum_with_string_values(self):
        """EventType is a StrEnum and all members are strings."""
        assert issubclass(EventType, StrEnum)
        for member in EventType:
            assert isinstance(member, str)
            assert isinstance(member.value, str)

    @pytest.mark.parametrize(
        ("member", "expected_value"),
        [
            ("TOKEN", "token"),
            ("AGENT_START", "agent_start"),
            ("AGENT_COMPLETE", "agent_complete"),
            ("ERROR", "error"),
            ("TOOL_START", "tool_start"),
            ("TOOL_END", "tool_end"),
            ("REASONING", "reasoning"),
            ("INTERRUPT", "interrupt"),
            ("NODE_START", "node_start"),
            ("NODE_STOP", "node_stop"),
            ("HANDOFF", "handoff"),
            ("MULTIAGENT_START", "multiagent_start"),
            ("MULTIAGENT_COMPLETE", "multiagent_complete"),
        ],
    )
    def test_string_comparison_works(self, member, expected_value):
        """StrEnum values compare equal to their plain string counterparts."""
        assert EventType[member] == expected_value

    def test_session_start_event_type_value(self):
        """EventType.SESSION_START has the correct string value."""
        assert EventType.SESSION_START == "session_start"
        assert isinstance(EventType.SESSION_START, str)

    def test_session_end_event_type_value(self):
        """EventType.SESSION_END has the correct string value."""
        assert EventType.SESSION_END == "session_end"
        assert isinstance(EventType.SESSION_END, str)

    def test_all_members_present(self):
        """All expected EventType members are present."""
        expected = {
            "AGENT_START",
            "TOKEN",
            "TOOL_START",
            "TOOL_END",
            "REASONING",
            "INTERRUPT",
            "AGENT_COMPLETE",
            "ERROR",
            "NODE_START",
            "NODE_STOP",
            "HANDOFF",
            "MULTIAGENT_START",
            "MULTIAGENT_COMPLETE",
            "SESSION_START",
            "SESSION_END",
        }
        assert set(EventType.__members__) == expected


class TestNodeRef:
    """Tests for NodeRef Pydantic model."""

    def test_node_ref_fields(self):
        """NodeRef has the correct fields."""
        node = NodeRef(id="node-1", kind="agent")
        assert node.id == "node-1"
        assert node.kind == "agent"

    def test_node_ref_model_dump(self):
        """NodeRef serializes correctly via model_dump."""
        node = NodeRef(id="node-1", kind="orchestration")
        dumped = node.model_dump()
        assert dumped == {"id": "node-1", "kind": "orchestration"}

    def test_node_ref_json_serializable(self):
        """NodeRef is JSON-serializable."""
        import json

        node = NodeRef(id="node-1", kind="agent")
        json_str = json.dumps(node.model_dump())
        assert json_str == '{"id": "node-1", "kind": "agent"}'


class TestEdgeRef:
    """Tests for EdgeRef Pydantic model."""

    def test_edge_ref_fields(self):
        """EdgeRef has the correct fields."""
        edge = EdgeRef(from_id="node-1", to_id="node-2")
        assert edge.from_id == "node-1"
        assert edge.to_id == "node-2"

    def test_edge_ref_model_dump(self):
        """EdgeRef serializes correctly via model_dump."""
        edge = EdgeRef(from_id="a", to_id="b")
        dumped = edge.model_dump()
        assert dumped == {"from_id": "a", "to_id": "b"}

    def test_edge_ref_json_serializable(self):
        """EdgeRef is JSON-serializable."""
        import json

        edge = EdgeRef(from_id="node-1", to_id="node-2")
        json_str = json.dumps(edge.model_dump())
        assert json_str == '{"from_id": "node-1", "to_id": "node-2"}'


class TestModelDescriptor:
    """Tests for ModelDescriptor Pydantic model."""

    def test_model_descriptor_fields(self):
        """ModelDescriptor has the correct fields."""
        model = ModelDescriptor(
            model_id="us.anthropic.claude-sonnet-4-6",
            provider="strands.models.bedrock.BedrockModel",
        )
        assert model.model_id == "us.anthropic.claude-sonnet-4-6"
        assert model.provider == "strands.models.bedrock.BedrockModel"

    def test_model_descriptor_model_id_none(self):
        """ModelDescriptor allows model_id to be None."""
        model = ModelDescriptor(model_id=None, provider="custom.CustomModel")
        assert model.model_id is None
        assert model.provider == "custom.CustomModel"

    def test_model_descriptor_model_dump(self):
        """ModelDescriptor serializes correctly via model_dump."""
        model = ModelDescriptor(model_id="model-123", provider="Provider")
        dumped = model.model_dump()
        assert dumped == {"model_id": "model-123", "provider": "Provider"}

    def test_model_descriptor_json_serializable(self):
        """ModelDescriptor is JSON-serializable."""
        import json

        model = ModelDescriptor(model_id=None, provider="Provider")
        json_str = json.dumps(model.model_dump())
        assert "provider" in json_str


class TestFileProviderDescriptor:
    """Tests for FileProviderDescriptor."""

    def test_file_provider_descriptor_fields(self):
        """FileProviderDescriptor has the correct fields."""
        desc = FileProviderDescriptor(
            provider="file",
            session_id="session-123",
            storage_dir="/tmp/sessions",
        )
        assert desc.provider == "file"
        assert desc.session_id == "session-123"
        assert desc.storage_dir == "/tmp/sessions"

    def test_file_provider_descriptor_model_dump(self):
        """FileProviderDescriptor serializes correctly."""
        desc = FileProviderDescriptor(
            provider="file",
            session_id="s1",
            storage_dir="/path",
        )
        dumped = desc.model_dump()
        assert dumped == {
            "provider": "file",
            "session_id": "s1",
            "storage_dir": "/path",
        }


class TestS3ProviderDescriptor:
    """Tests for S3ProviderDescriptor."""

    def test_s3_provider_descriptor_fields(self):
        """S3ProviderDescriptor has the correct fields."""
        desc = S3ProviderDescriptor(
            provider="s3",
            session_id="session-123",
            bucket="my-bucket",
            prefix="sessions/",
        )
        assert desc.provider == "s3"
        assert desc.session_id == "session-123"
        assert desc.bucket == "my-bucket"
        assert desc.prefix == "sessions/"

    def test_s3_provider_descriptor_empty_prefix(self):
        """S3ProviderDescriptor allows empty prefix."""
        desc = S3ProviderDescriptor(
            provider="s3",
            session_id="s1",
            bucket="bucket",
            prefix="",
        )
        assert desc.prefix == ""


class TestAgentCoreProviderDescriptor:
    """Tests for AgentCoreProviderDescriptor."""

    def test_agentcore_provider_descriptor_fields(self):
        """AgentCoreProviderDescriptor has the correct fields."""
        desc = AgentCoreProviderDescriptor(
            provider="agentcore",
            session_id="session-123",
            memory_id="mem-456",
            actor_id="actor-789",
        )
        assert desc.provider == "agentcore"
        assert desc.session_id == "session-123"
        assert desc.memory_id == "mem-456"
        assert desc.actor_id == "actor-789"


class TestCustomProviderDescriptor:
    """Tests for CustomProviderDescriptor."""

    def test_custom_provider_descriptor_fields(self):
        """CustomProviderDescriptor has the correct fields."""
        desc = CustomProviderDescriptor(
            provider="custom",
            session_id="session-123",
            class_name="my.module.CustomSessionManager",
        )
        assert desc.provider == "custom"
        assert desc.session_id == "session-123"
        assert desc.class_name == "my.module.CustomSessionManager"

    def test_custom_provider_descriptor_session_id_none(self):
        """CustomProviderDescriptor allows session_id to be None."""
        desc = CustomProviderDescriptor(
            provider="custom",
            session_id=None,
            class_name="my.module.CustomSessionManager",
        )
        assert desc.session_id is None


class TestAgentDescriptor:
    """Tests for AgentDescriptor Pydantic model."""

    def test_agent_descriptor_fields(self):
        """AgentDescriptor has the correct fields."""
        model = ModelDescriptor(model_id="m1", provider="Provider")
        agent = AgentDescriptor(
            name="researcher",
            description="Researches topics",
            model=model,
            session_manager=None,
        )
        assert agent.name == "researcher"
        assert agent.description == "Researches topics"
        assert agent.model == model
        assert agent.session_manager is None

    def test_agent_descriptor_description_none(self):
        """AgentDescriptor allows description to be None."""
        model = ModelDescriptor(model_id=None, provider="Provider")
        agent = AgentDescriptor(
            name="agent",
            description=None,
            model=model,
            session_manager=None,
        )
        assert agent.description is None

    def test_agent_descriptor_with_session_manager(self):
        """AgentDescriptor can include a session manager."""
        model = ModelDescriptor(model_id="m1", provider="Provider")
        sm = FileProviderDescriptor(
            provider="file",
            session_id="s1",
            storage_dir="/tmp",
        )
        agent = AgentDescriptor(
            name="agent",
            description="desc",
            model=model,
            session_manager=sm,
        )
        assert agent.session_manager == sm

    def test_agent_descriptor_model_dump(self):
        """AgentDescriptor serializes correctly."""
        model = ModelDescriptor(model_id="m1", provider="Provider")
        agent = AgentDescriptor(
            name="agent",
            description="desc",
            model=model,
            session_manager=None,
        )
        dumped = agent.model_dump()
        assert dumped["name"] == "agent"
        assert dumped["description"] == "desc"
        assert dumped["model"]["model_id"] == "m1"
        assert dumped["session_manager"] is None


class TestOrchestrationDescriptor:
    """Tests for OrchestrationDescriptor Pydantic model."""

    def test_orchestration_descriptor_fields(self):
        """OrchestrationDescriptor has the correct fields."""
        orch = OrchestrationDescriptor(
            name="main",
            kind="swarm",
            session_manager=None,
            nodes=[NodeRef(id="n1", kind="agent")],
            edges=None,
            entry_node_id="n1",
        )
        assert orch.name == "main"
        assert orch.kind == "swarm"
        assert orch.session_manager is None
        assert len(orch.nodes) == 1
        assert orch.edges is None
        assert orch.entry_node_id == "n1"

    def test_orchestration_descriptor_empty_defaults(self):
        """OrchestrationDescriptor has correct default values."""
        orch = OrchestrationDescriptor(
            name="main",
            kind="delegate",
            session_manager=None,
        )
        assert orch.nodes == []
        assert orch.edges is None
        assert orch.entry_node_id is None

    def test_orchestration_descriptor_with_edges(self):
        """OrchestrationDescriptor can include edges."""
        edges = [EdgeRef(from_id="n1", to_id="n2")]
        orch = OrchestrationDescriptor(
            name="graph",
            kind="graph",
            session_manager=None,
            nodes=[NodeRef(id="n1", kind="agent"), NodeRef(id="n2", kind="agent")],
            edges=edges,
            entry_node_id="n1",
        )
        assert orch.edges == edges


class TestEntryDescriptor:
    """Tests for EntryDescriptor Pydantic model."""

    def test_entry_descriptor_fields(self):
        """EntryDescriptor has the correct fields."""
        entry = EntryDescriptor(name="main", kind="orchestration")
        assert entry.name == "main"
        assert entry.kind == "orchestration"

    def test_entry_descriptor_agent_kind(self):
        """EntryDescriptor can have kind='agent'."""
        entry = EntryDescriptor(name="researcher", kind="agent")
        assert entry.kind == "agent"

    def test_entry_descriptor_model_dump(self):
        """EntryDescriptor serializes correctly."""
        entry = EntryDescriptor(name="main", kind="orchestration")
        dumped = entry.model_dump()
        assert dumped == {"name": "main", "kind": "orchestration"}


class TestSessionManifest:
    """Tests for SessionManifest Pydantic model."""

    def test_session_manifest_fields(self):
        """SessionManifest has the correct fields."""
        entry = EntryDescriptor(name="main", kind="agent")
        manifest = SessionManifest(
            agents=[],
            orchestrations=[],
            entry=entry,
        )
        assert manifest.agents == []
        assert manifest.orchestrations == []
        assert manifest.entry == entry

    def test_session_manifest_empty_defaults(self):
        """SessionManifest defaults agents and orchestrations to empty lists."""
        entry = EntryDescriptor(name="main", kind="agent")
        manifest = SessionManifest(entry=entry)
        assert manifest.agents == []
        assert manifest.orchestrations == []

    def test_session_manifest_with_agents(self):
        """SessionManifest can include agents."""
        model = ModelDescriptor(model_id="m1", provider="Provider")
        agent = AgentDescriptor(
            name="researcher",
            description="desc",
            model=model,
            session_manager=None,
        )
        entry = EntryDescriptor(name="researcher", kind="agent")
        manifest = SessionManifest(
            agents=[agent],
            orchestrations=[],
            entry=entry,
        )
        assert len(manifest.agents) == 1
        assert manifest.agents[0].name == "researcher"

    def test_session_manifest_with_orchestrations(self):
        """SessionManifest can include orchestrations."""
        orch = OrchestrationDescriptor(
            name="main",
            kind="swarm",
            session_manager=None,
        )
        entry = EntryDescriptor(name="main", kind="orchestration")
        manifest = SessionManifest(
            agents=[],
            orchestrations=[orch],
            entry=entry,
        )
        assert len(manifest.orchestrations) == 1
        assert manifest.orchestrations[0].name == "main"

    def test_session_manifest_model_dump(self):
        """SessionManifest serializes correctly via model_dump."""
        entry = EntryDescriptor(name="main", kind="agent")
        manifest = SessionManifest(
            agents=[],
            orchestrations=[],
            entry=entry,
        )
        dumped = manifest.model_dump()
        assert dumped["agents"] == []
        assert dumped["orchestrations"] == []
        assert dumped["entry"]["name"] == "main"
        assert dumped["entry"]["kind"] == "agent"

    def test_session_manifest_json_serializable(self):
        """SessionManifest is JSON-serializable."""
        import json

        entry = EntryDescriptor(name="main", kind="agent")
        manifest = SessionManifest(
            agents=[],
            orchestrations=[],
            entry=entry,
        )
        json_str = json.dumps(manifest.model_dump())
        assert "main" in json_str
        assert "agent" in json_str

    def test_session_manifest_complex_example(self):
        """SessionManifest works with a complex multi-agent setup."""
        model1 = ModelDescriptor(model_id="m1", provider="Provider1")
        model2 = ModelDescriptor(model_id="m2", provider="Provider2")

        agent1 = AgentDescriptor(
            name="researcher",
            description="Researches topics",
            model=model1,
            session_manager=FileProviderDescriptor(
                provider="file",
                session_id="s1",
                storage_dir="/tmp",
            ),
        )
        agent2 = AgentDescriptor(
            name="writer",
            description="Writes content",
            model=model2,
            session_manager=None,
        )

        orch = OrchestrationDescriptor(
            name="main",
            kind="swarm",
            session_manager=None,
            nodes=[
                NodeRef(id="researcher", kind="agent"),
                NodeRef(id="writer", kind="agent"),
            ],
            edges=None,
            entry_node_id="researcher",
        )

        entry = EntryDescriptor(name="main", kind="orchestration")

        manifest = SessionManifest(
            agents=[agent1, agent2],
            orchestrations=[orch],
            entry=entry,
        )

        assert len(manifest.agents) == 2
        assert len(manifest.orchestrations) == 1
        assert manifest.entry.name == "main"

        # Verify it's JSON-serializable
        import json

        json_str = json.dumps(manifest.model_dump())
        assert "researcher" in json_str
        assert "writer" in json_str
