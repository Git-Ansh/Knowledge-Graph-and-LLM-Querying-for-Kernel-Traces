# Source Code Modules

This directory contains the core pipeline modules for the layered knowledge graph system.

## Modules

### `trace_parser.py`
**Stage 1: Trace Parsing**

Parses raw LTTng kernel trace output into structured `KernelEvent` objects.

- Handles LTTng text format with timestamps and event data
- Extracts process/thread IDs, CPU information, and event parameters
- Provides filtering methods for specific event types
- Can be run independently for testing: `python3 trace_parser.py <trace_file>`

**Key Classes:**
- `KernelEvent` - Dataclass representing a single kernel event
- `TraceParser` - Main parser with event filtering capabilities

---

### `entity_extractor.py`
**Stage 2: Entity Extraction**

Builds the "actors" in the kernel reality layer from parsed events.

- Extracts Processes, Threads, Files, Sockets, and CPUs
- Tracks entity lifecycles (creation/termination times)
- Establishes parent-child relationships
- Saves entities as structured JSON files

**Key Classes:**
- `Process`, `Thread`, `File`, `Socket`, `CPU` - Entity dataclasses
- `EntityExtractor` - Main extraction engine

---

### `event_sequence_builder.py`
**Stage 3: Event Sequence Building**

Groups related syscalls into `EventSequence` "action chapter" nodes.

- Pairs syscall entry/exit events
- Groups consecutive operations (reads, writes, sends, etc.)
- Applies schema-defined grouping rules
- Creates EventSequence nodes with complete event streams

**Key Classes:**
- `EventSequence` - Dataclass for event sequence with full event stream
- `EventSequenceBuilder` - Groups events according to rules

**Grouping Rules:**
- Read/write operations: Group by thread+fd, break on 100ms gap
- Network operations: Group by thread+socket, break on 50ms gap
- File open/close: Each operation is separate

---

### `graph_builder.py`
**Stage 4: Graph Construction**

Builds the layered Neo4j knowledge graph from extracted entities.

- Connects to Neo4j database
- Creates both kernel reality and application abstraction layers
- Establishes all relationships (CONTAINS, PERFORMED, WAS_TARGET_OF, etc.)
- Creates indexes and constraints for performance
- Supports pluggable application-specific layers

**Key Classes:**
- `GraphBuilder` - Main Neo4j graph construction engine
- `GraphStats` - Statistics tracking for graph construction

**Layers Created:**
1. Kernel Reality Layer - Universal, application-agnostic
2. Application Abstraction Layer - Application-specific semantic context

---

## Pipeline Flow

```
trace_parser.py
    |
    v (List[KernelEvent])
entity_extractor.py
    |
    v (Entities: processes, threads, files, etc.)
event_sequence_builder.py
    |
    v (List[EventSequence])
graph_builder.py
    |
    v Neo4j Knowledge Graph
```

## Usage

Each module can be run independently for testing:

```bash
# Parse trace
python3 src/trace_parser.py traces/latest/trace_output.txt

# Extract entities
python3 src/entity_extractor.py traces/latest/trace_output.txt

# Build sequences
python3 src/event_sequence_builder.py traces/latest/trace_output.txt

# Build graph (requires entities in outputs/)
python3 src/graph_builder.py outputs/processed_entities
```

Or use the complete pipeline orchestrator:

```bash
python3 main.py --trace traces/latest
```

## Dependencies

- Python 3.8+
- neo4j (Python driver for Neo4j)
- Standard library: logging, json, pathlib, dataclasses, collections

Install dependencies:
```bash
pip3 install neo4j
```

## Logging

All modules use Python's logging framework with the following levels:

- INFO: Major pipeline steps and statistics
- DEBUG: Detailed processing information
- WARNING: Non-fatal issues
- ERROR: Fatal errors requiring attention

Configure logging verbosity in main.py or when running modules directly.
