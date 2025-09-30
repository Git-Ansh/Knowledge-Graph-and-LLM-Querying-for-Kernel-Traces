#!/usr/bin/env python3
"""Schema registry and metadata-driven schema selection."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class GraphSchema:
    """Lightweight schema descriptor consumed by the graph builder."""

    name: str
    description: str
    relationship_types_expected: Set[str]
    constraints: List[str]
    indexes: List[str]
    node_labels: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    application_signatures: List[str] = field(default_factory=list)

    @classmethod
    def from_spec(cls, spec: Dict[str, Any]) -> "GraphSchema":
        return cls(
            name=spec["name"],
            description=spec.get("description", spec["name"]),
            relationship_types_expected=set(spec.get("relationship_types_expected", [])),
            constraints=list(spec.get("constraints", [])),
            indexes=list(spec.get("indexes", [])),
            node_labels=dict(spec.get("node_labels", {})),
            application_signatures=[sig.lower() for sig in spec.get("application_signatures", [])],
        )


class SchemaRegistry:
    """Registry that resolves schemas based on metadata or explicit hints."""

    def __init__(self) -> None:
        self._schemas: Dict[str, GraphSchema] = {}
        self._default_schema: Optional[str] = None
        self._registration_order: List[str] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, schema: GraphSchema, *, default: bool = False) -> None:
        logger.debug("Registering schema '%s'", schema.name)
        self._schemas[schema.name] = schema
        self._registration_order.append(schema.name)
        if default or self._default_schema is None:
            self._default_schema = schema.name

    def get(self, name: str) -> GraphSchema:
        return self._schemas[name]

    def default(self) -> GraphSchema:
        if self._default_schema is None:
            raise RuntimeError("No default schema registered")
        return self._schemas[self._default_schema]

    def list(self) -> List[str]:
        return list(self._registration_order)

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect(
        self,
        metadata: Optional[Dict[str, Any]] = None,
        *,
        trace_path: Optional[Path] = None,
    ) -> GraphSchema:
        metadata = metadata or {}
        candidates = self._collect_candidate_strings(metadata, trace_path)

        logger.debug("Schema detection candidates: %s", candidates)

        # Check registered schemas (non-default first)
        for schema_name in self._registration_order:
            schema = self._schemas[schema_name]
            if schema_name == self._default_schema:
                continue
            if self._matches_schema(schema, candidates):
                logger.info(" Schema detection matched '%s'", schema.name)
                return schema

        logger.info(" Schema detection fell back to default '%s'", self._default_schema)
        return self.default()

    def _collect_candidate_strings(
        self, metadata: Dict[str, Any], trace_path: Optional[Path]
    ) -> List[str]:
        candidates: List[str] = []

        for key in ("application", "service", "workload", "target", "session_name"):
            value = metadata.get(key)
            if value:
                candidates.append(str(value).lower())

        tags = metadata.get("tags")
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        if isinstance(tags, Iterable):
            candidates.extend(str(tag).lower() for tag in tags)

        # Include process names if metadata captured them
        processes = metadata.get("processes")
        if isinstance(processes, Iterable):
            candidates.extend(str(proc).lower() for proc in processes)

        if trace_path:
            candidates.append(trace_path.name.lower())
            candidates.extend(part.lower() for part in trace_path.parts)

        # Deduplicate while preserving order
        deduped: List[str] = []
        seen: Set[str] = set()
        for candidate in candidates:
            if candidate not in seen:
                deduped.append(candidate)
                seen.add(candidate)
        return deduped

    @staticmethod
    def _matches_schema(schema: GraphSchema, candidates: Iterable[str]) -> bool:
        if not schema.application_signatures:
            return False
        for candidate in candidates:
            for signature in schema.application_signatures:
                if signature in candidate:
                    return True
        return False

    # ------------------------------------------------------------------
    # Factory helper
    # ------------------------------------------------------------------

    @classmethod
    def create_default_registry(cls) -> "SchemaRegistry":
        registry = cls()

        # Register universal schema first (default)
        registry.register(GraphSchema.from_spec(_UNIVERSAL_SCHEMA_SPEC), default=True)

        # Attempt to load specialised schemas shipped in schemas/*.py modules
        for module_name in ("schemas.redis_schema",):
            try:
                module = import_module(module_name)
                if hasattr(module, "get_schema_spec"):
                    spec = module.get_schema_spec()
                    registry.register(GraphSchema.from_spec(spec))
                    logger.info(" Registered specialised schema '%s'", spec.get("name"))
            except ModuleNotFoundError:
                logger.debug("Optional schema module '%s' not found", module_name)
            except Exception as exc:
                logger.warning(
                    " Failed to load schema module '%s': %s", module_name, exc
                )

        return registry


# ----------------------------------------------------------------------------
# Default universal schema specification
# ----------------------------------------------------------------------------

_UNIVERSAL_SCHEMA_SPEC: Dict[str, Any] = {
    "name": "universal",
    "description": "Universal kernel trace property graph schema",
    "relationship_types_expected": [
        "READ_FROM",
        "WROTE_TO",
        "OPENED",
        "CLOSED",
        "ACCESSED",
        "SCHEDULED_ON",
        "PREEMPTED_FROM",
        "SENT_TO",
        "RECEIVED_FROM",
        "CONNECTED_TO",
        "FORKED",
    ],
    "constraints": [
        "CREATE CONSTRAINT process_pid IF NOT EXISTS FOR (n:Process) REQUIRE n.pid IS UNIQUE",
        "CREATE CONSTRAINT thread_composite IF NOT EXISTS FOR (n:Thread) REQUIRE (n.tid, n.pid) IS UNIQUE",
        "CREATE CONSTRAINT file_path IF NOT EXISTS FOR (n:File) REQUIRE n.path IS UNIQUE",
        "CREATE CONSTRAINT socket_id IF NOT EXISTS FOR (n:Socket) REQUIRE n.socket_id IS UNIQUE",
        "CREATE CONSTRAINT cpu_id IF NOT EXISTS FOR (n:CPU) REQUIRE n.cpu_id IS UNIQUE",
        "CREATE CONSTRAINT memory_region_composite IF NOT EXISTS FOR (n:MemoryRegion) REQUIRE (n.start_address, n.pid) IS UNIQUE",
    ],
    "indexes": [
        "CREATE INDEX process_name IF NOT EXISTS FOR (n:Process) ON (n.name)",
        "CREATE INDEX process_start_time IF NOT EXISTS FOR (n:Process) ON (n.start_time)",
        "CREATE INDEX thread_name IF NOT EXISTS FOR (n:Thread) ON (n.name)",
        "CREATE INDEX file_type IF NOT EXISTS FOR (n:File) ON (n.file_type)",
        "CREATE INDEX socket_family IF NOT EXISTS FOR (n:Socket) ON (n.family)",
        "CREATE INDEX rel_read_timestamp IF NOT EXISTS FOR ()-[r:READ_FROM]-() ON (r.timestamp)",
        "CREATE INDEX rel_write_timestamp IF NOT EXISTS FOR ()-[r:WROTE_TO]-() ON (r.timestamp)",
        "CREATE INDEX rel_opened_timestamp IF NOT EXISTS FOR ()-[r:OPENED]-() ON (r.timestamp)",
        "CREATE INDEX rel_closed_timestamp IF NOT EXISTS FOR ()-[r:CLOSED]-() ON (r.timestamp)",
        "CREATE INDEX rel_scheduled_timestamp IF NOT EXISTS FOR ()-[r:SCHEDULED_ON]-() ON (r.timestamp)",
        "CREATE INDEX rel_preempted_timestamp IF NOT EXISTS FOR ()-[r:PREEMPTED_FROM]-() ON (r.timestamp)",
        "CREATE INDEX rel_sent_timestamp IF NOT EXISTS FOR ()-[r:SENT_TO]-() ON (r.timestamp)",
        "CREATE INDEX rel_received_timestamp IF NOT EXISTS FOR ()-[r:RECEIVED_FROM]-() ON (r.timestamp)",
        "CREATE INDEX rel_connected_timestamp IF NOT EXISTS FOR ()-[r:CONNECTED_TO]-() ON (r.timestamp)",
        "CREATE INDEX rel_forked_timestamp IF NOT EXISTS FOR ()-[r:FORKED]-() ON (r.timestamp)",
    ],
    "node_labels": {
        "Process": {"id_keys": ["pid"], "properties": ["name", "start_time", "end_time"]},
        "Thread": {"id_keys": ["tid", "pid"], "properties": ["name", "start_time"]},
        "File": {"id_keys": ["path"], "properties": ["file_type", "first_accessed"]},
        "Socket": {"id_keys": ["socket_id"], "properties": ["family", "local_address", "remote_address"]},
        "CPU": {"id_keys": ["cpu_id"], "properties": []},
    },
    "application_signatures": [],
}


__all__ = ["GraphSchema", "SchemaRegistry"]
