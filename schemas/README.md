# Schema Definitions

This directory contains the formal schema definitions for the layered knowledge graph.

## Files

### `layered_schema.json`

The complete schema specification for the two-layer knowledge graph architecture.

**Contents:**
- **Schema Metadata** - Version and description
- **Layer Definitions** - Kernel reality and application abstraction layers
- **Node Definitions** - All node types with required/optional properties
- **Relationship Definitions** - All relationship types with properties
- **Processing Rules** - Event grouping and correlation rules

**Structure:**
```json
{
  "schema_version": "2.0",
  "layers": {...},
  "node_definitions": {...},
  "relationship_definitions": {...},
  "processing_rules": {
    "event_grouping": {...},
    "correlation_rules": {...}
  }
}
```

## Schema Layers

### Kernel Reality Layer
Universal nodes and relationships representing OS-level operations:
- **Nodes**: Process, Thread, File, Socket, CPU, EventSequence
- **Relationships**: CONTAINS, PERFORMED, WAS_TARGET_OF, FOLLOWS, SCHEDULED_ON

### Application Abstraction Layer  
Application-specific nodes providing semantic context:
- **Base Node**: AppEvent (generic application event)
- **Extensions**: RedisCommand, HttpRequest, SqlQuery
- **Cross-Layer**: FULFILLED_BY relationship linking to kernel reality

## Usage

The schema is loaded by the pipeline orchestrator and used by:

1. **event_sequence_builder.py** - Uses processing_rules.event_grouping
2. **graph_builder.py** - Uses node_definitions and relationship_definitions
3. **Application parsers** - Reference node_definitions for their specific types

## Extending the Schema

To add support for a new application:

1. Add node definition to `node_definitions`:
```json
"MyAppEvent": {
  "layer": "application_abstraction",
  "extends": "AppEvent",
  "required_properties": ["event_type", "payload"],
  "optional_properties": ["metadata"]
}
```

2. Implement parser in `src/myapp_parser.py`
3. Add builder method in `src/graph_builder.py`

The kernel reality layer remains unchanged.

## Validation

Schema validation is automatically performed when loading:
- Required properties must be present
- Property types are checked where specified
- Layer assignments are validated

## Version History

- **2.0** - Layered architecture with EventSequence aggregation model
- **1.0** - Original flat schema (deprecated)
