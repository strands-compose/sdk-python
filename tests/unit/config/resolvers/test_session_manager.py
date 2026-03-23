"""Tests for core.config.resolvers.session_manager — resolve_session_manager."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from strands_compose.config.resolvers.session_manager import resolve_session_manager
from strands_compose.config.schema import SessionManagerDef

# Module path for patching module-level imports in session_manager resolver
_SM = "strands_compose.config.resolvers.session_manager"
_ACM_CONFIG = "bedrock_agentcore.memory.integrations.strands.config.AgentCoreMemoryConfig"
_ACM_MANAGER = (
    "bedrock_agentcore.memory.integrations.strands.session_manager.AgentCoreMemorySessionManager"
)


class TestResolveSessionManager:
    @patch("strands.session.FileSessionManager")
    def test_file_provider_with_session_id_in_params(self, mock_fs):
        sm_def = SessionManagerDef(
            provider="file", params={"session_id": "abc", "storage_dir": "/data"}
        )
        resolve_session_manager(sm_def)
        mock_fs.assert_called_once()
        call_kwargs = mock_fs.call_args.kwargs
        assert call_kwargs["session_id"] == "abc"
        assert call_kwargs["storage_dir"] == "/data"

    @patch("strands.session.FileSessionManager")
    def test_file_provider_random_session_id_by_default(self, mock_fs):
        """Without session_id in params, a random UUID is generated."""
        sm_def = SessionManagerDef(provider="file")
        resolve_session_manager(sm_def)
        mock_fs.assert_called_once()
        call_kwargs = mock_fs.call_args.kwargs
        # Verify a UUID was generated (36 chars including hyphens)
        assert len(call_kwargs["session_id"]) == 36
        assert "-" in call_kwargs["session_id"]

    @patch("strands.session.FileSessionManager")
    def test_session_id_override_takes_precedence(self, mock_fs):
        """session_id_override parameter wins over params."""
        sm_def = SessionManagerDef(provider="file", params={"session_id": "from-params"})
        resolve_session_manager(sm_def, session_id_override="from-override")
        mock_fs.assert_called_once_with(session_id="from-override")

    @patch("strands.session.S3SessionManager")
    def test_s3_provider(self, mock_s3):
        sm_def = SessionManagerDef(
            provider="s3",
            params={"session_id": "s3-session", "bucket": "my-bucket"},
        )
        resolve_session_manager(sm_def)
        mock_s3.assert_called_once()
        call_kwargs = mock_s3.call_args.kwargs
        assert call_kwargs["session_id"] == "s3-session"
        assert call_kwargs["bucket"] == "my-bucket"

    @patch("strands.session.S3SessionManager")
    def test_s3_provider_random_session_id_by_default(self, mock_s3):
        """Without session_id in params, a random UUID is generated."""
        sm_def = SessionManagerDef(provider="s3")
        resolve_session_manager(sm_def)
        mock_s3.assert_called_once()
        call_kwargs = mock_s3.call_args.kwargs
        # Verify a UUID was generated (36 chars including hyphens)
        assert len(call_kwargs["session_id"]) == 36
        assert "-" in call_kwargs["session_id"]

    def test_unknown_provider_raises(self):
        sm_def = SessionManagerDef(provider="dynamodb")
        with pytest.raises(ValueError, match="Unknown session provider"):
            resolve_session_manager(sm_def)

    @patch("strands.session.FileSessionManager")
    def test_provider_case_insensitive(self, mock_fs):
        sm_def = SessionManagerDef(provider="FILE", params={"session_id": "test"})
        resolve_session_manager(sm_def)
        mock_fs.assert_called_once_with(session_id="test")


class TestAgentcoreProvider:
    @patch(_ACM_MANAGER)
    @patch(_ACM_CONFIG)
    def test_agentcore_provider(self, mock_config_cls, mock_manager_cls):
        sm_def = SessionManagerDef(
            provider="agentcore",
            params={
                "session_id": "sess-1",
                "memory_id": "mem-abc",
                "actor_id": "user-1",
            },
        )
        resolve_session_manager(sm_def)
        mock_config_cls.assert_called_once_with(
            session_id="sess-1",
            memory_id="mem-abc",
            actor_id="user-1",
        )
        mock_manager_cls.assert_called_once_with(
            mock_config_cls.return_value,
        )

    @patch(_ACM_MANAGER)
    @patch(_ACM_CONFIG)
    def test_agentcore_region_extracted_from_params(self, mock_config_cls, mock_manager_cls):
        """region_name goes to the manager constructor, not AgentCoreMemoryConfig."""
        sm_def = SessionManagerDef(
            provider="agentcore",
            params={
                "session_id": "sess-2",
                "memory_id": "mem-xyz",
                "actor_id": "user-2",
                "region_name": "eu-central-1",
            },
        )
        resolve_session_manager(sm_def)
        mock_config_cls.assert_called_once_with(
            session_id="sess-2",
            memory_id="mem-xyz",
            actor_id="user-2",
        )
        mock_manager_cls.assert_called_once_with(
            mock_config_cls.return_value,
            region_name="eu-central-1",
        )

    @patch(_ACM_MANAGER)
    @patch(_ACM_CONFIG)
    def test_agentcore_session_id_override(self, mock_config_cls, mock_manager_cls):
        """HTTP session_id_override wins over params.session_id."""
        sm_def = SessionManagerDef(
            provider="agentcore",
            params={"session_id": "from-params", "memory_id": "m", "actor_id": "a"},
        )
        resolve_session_manager(sm_def, session_id_override="runtime-session")
        config_call = mock_config_cls.call_args.kwargs
        assert config_call["session_id"] == "runtime-session"

    @patch(_ACM_MANAGER)
    @patch(_ACM_CONFIG)
    def test_agentcore_config_fields_separated_from_constructor(
        self, mock_config_cls, mock_manager_cls
    ):
        """AgentCoreMemoryConfig fields and constructor params are split correctly."""
        sm_def = SessionManagerDef(
            provider="agentcore",
            params={
                "session_id": "sess-3",
                "memory_id": "mem-1",
                "actor_id": "user-3",
                "batch_size": 10,
                "context_tag": "ctx",
                "region_name": "us-west-2",
            },
        )
        resolve_session_manager(sm_def)
        # Config fields go to AgentCoreMemoryConfig
        config_kwargs = mock_config_cls.call_args.kwargs
        assert config_kwargs["memory_id"] == "mem-1"
        assert config_kwargs["batch_size"] == 10
        assert config_kwargs["context_tag"] == "ctx"
        assert "region_name" not in config_kwargs
        # Constructor params go to AgentCoreMemorySessionManager
        manager_call_args = mock_manager_cls.call_args
        assert manager_call_args.args[0] is mock_config_cls.return_value
        manager_kwargs = manager_call_args.kwargs
        assert manager_kwargs["region_name"] == "us-west-2"
        assert "memory_id" not in manager_kwargs

    def test_agentcore_missing_actor_id_raises(self):
        """agentcore provider requires actor_id in params."""
        sm_def = SessionManagerDef(
            provider="agentcore",
            params={"memory_id": "mem-1"},
        )
        with pytest.raises(ValueError, match="actor_id"):
            resolve_session_manager(sm_def)

    def test_agentcore_missing_package_raises_friendly_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ImportError for agentcore includes the correct pip install command."""
        _blocked = [
            "bedrock_agentcore",
            "bedrock_agentcore.memory",
            "bedrock_agentcore.memory.integrations",
            "bedrock_agentcore.memory.integrations.strands",
            "bedrock_agentcore.memory.integrations.strands.config",
            "bedrock_agentcore.memory.integrations.strands.session_manager",
        ]
        for mod in _blocked:
            monkeypatch.setitem(sys.modules, mod, None)
        sm_def = SessionManagerDef(
            provider="agentcore",
            params={"memory_id": "mem-1", "actor_id": "user-1"},
        )
        with pytest.raises(ImportError, match=r"pip install strands-compose\[agentcore-memory\]"):
            resolve_session_manager(sm_def)


class TestCustomTypeProvider:
    def test_custom_type_instantiated_with_session_id(self):
        """type: module:Class bypasses provider and instantiates with session_id."""
        from strands.session.session_manager import SessionManager

        mock_instance = MagicMock(spec=SessionManager)
        mock_cls = MagicMock(return_value=mock_instance)

        with patch(f"{_SM}.load_object", return_value=mock_cls):
            sm_def = SessionManagerDef(
                type="my_mod:MySessionManager",
                params={"session_id": "custom-1", "extra_param": "value"},
            )
            result = resolve_session_manager(sm_def)

        mock_cls.assert_called_once_with(session_id="custom-1", extra_param="value")
        assert result is mock_instance

    def test_custom_type_rejects_non_session_manager(self):
        """type: raises TypeError if the class is not a SessionManager subclass."""
        mock_instance = MagicMock()  # not a SessionManager

        with patch(
            f"{_SM}.load_object",
            return_value=MagicMock(return_value=mock_instance),
        ):
            sm_def = SessionManagerDef(type="bad:Class")
            with pytest.raises(TypeError, match="must be a subclass of"):
                resolve_session_manager(sm_def)
