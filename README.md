# Knowledge Graph and LLM Querying for Kernel Traces

## Project Overview  

A layered knowledge graph system for capturing, analyzing, and querying Linux kernel traces using a universal schema that separates kernel reality from application abstraction.

### Core Architecture: Layered Knowledge Graph

This system implements a two-layer graph model:

**1. Kernel Reality Layer** - The ground truth of OS operations
- Nodes: Process, Thread, File, Socket, CPU, EventSequence
- Universal and application-agnostic
- Represents physical kernel operations

**2. Application Abstraction Layer** - Logical application operations
- Nodes: AppEvent, RedisCommand, HttpRequest, SqlQuery
- Application-specific semantic context
- Represents why kernel operations occurred

**Cross-Layer Connection** - FULFILLED_BY relationships link application events to the kernel sequences that implement them.

### Key Features
- **Universal Schema** - Works across any traced application
- **Event Sequence Model** - Groups related syscalls into logical operations
- **Temporal & Causal Preservation** - Complete ordering and relationships
- **Scalable Processing** - Handles large traces efficiently
- **Clean Separation** - Actors (nodes) separate from actions (EventSequence nodes)

### Pipeline Architecture
```
Raw LTTng Trace → Parse Events → Extract Entities → Build Sequences → Construct Graph
                                                                    
   trace_output     KernelEvents    Processes       EventSequence    Neo4j Layered
   .txt file        structured      Threads         action nodes     Knowledge Graph
                    events          Files                            (2 layers)
```

##  Quick Start

### Complete Pipeline Execution
```bash
# Process the latest trace and build knowledge graph
python3 main.py

# Process a specific trace directory
python3 main.py --trace traces/redis_20251003_185958

# Enable verbose logging to see detailed processing steps
python3 main.py --verbose

# Use custom Neo4j credentials
python3 main.py --neo4j-password your_password
```

### Capture New Traces
```bash
# List available benchmark applications
cd benchmarks
python3 benchmark_tracer.py --list

# Capture Redis trace (requires sudo for kernel tracing)
sudo python3 benchmark_tracer.py redis

# The latest trace is automatically symlinked at traces/latest
cd ..
python3 main.py  # Process the latest trace
```

##  Project Structure

```
Knowledge Graph and LLM Querying for Kernel Traces/
├── main.py                         # Pipeline orchestrator
├── src/                            # Core pipeline modules
│   ├── trace_parser.py            # Stage 1: Parse raw LTTng traces
│   ├── entity_extractor.py        # Stage 2: Extract kernel entities
│   ├── event_sequence_builder.py  # Stage 3: Build EventSequence nodes
│   └── graph_builder.py           # Stage 4: Construct Neo4j graph
├── schemas/                        # Schema definitions
│   └── layered_schema.json        # Layered graph schema specification
├── benchmarks/                     # LTTng tracing utilities
│   ├── benchmark_tracer.py        # Automated trace capture
│   └── README.md                  # Tracing documentation
├── traces/                         # Captured LTTng traces
│   ├── latest/                    # Symlink to most recent trace
│   └── {app}_{timestamp}/         # Individual trace sessions
│       ├── trace_output.txt       # Raw LTTng output
│       ├── metadata.json          # Trace metadata
│       └── kernel/                # Binary trace data
├── outputs/                        # Processing outputs
│   ├── processed_entities/        # Extracted entities (JSON)
│   │   ├── processes.json
│   │   ├── threads.json
│   │   ├── files.json
│   │   ├── sockets.json
│   │   ├── cpus.json
│   │   └── event_sequences.json
│   └── graph_stats/               # Graph construction statistics
│       ├── graph_stats.json
│       └── pipeline_summary.json
├── README.md                       # This file
├── SCHEMA.md                       # Detailed schema documentation
└── Project-Log.md                  # Development log
```

##  System Architecture

### 4-Stage Pipeline

**Stage 1: Trace Parsing** (`trace_parser.py`)
- Parse raw LTTng kernel trace output
- Extract individual kernel events with timestamps
- Standardize event format across different trace formats
- Handle syscall entry/exit events

**Stage 2: Entity Extraction** (`entity_extractor.py`)
- Build "actor" nodes: Process, Thread, File, Socket, CPU
- Track entity lifecycles (creation/termination)
- Establish parent-child relationships
- Create kernel reality layer foundation

**Stage 3: Event Sequence Building** (`event_sequence_builder.py`)
- Group related syscalls into logical operations
- Create EventSequence "action" nodes with complete event streams
- Apply schema-defined grouping rules (time gaps, operation types)
- Preserve temporal ordering and causality

**Stage 4: Graph Construction** (`graph_builder.py`)
- Build Neo4j knowledge graph with both layers
- Create kernel reality layer (CONTAINS, PERFORMED, WAS_TARGET_OF)
- Create application abstraction layer (INITIATED, FULFILLED_BY)
- Apply constraints and indexes for query performance

### Layered Graph Model

The knowledge graph separates concerns into two interconnected layers:

**Kernel Reality Layer** (Universal)
```
(Process)-[:CONTAINS]->(Thread)-[:PERFORMED]->(EventSequence)<-[:WAS_TARGET_OF]-(File)
```
- Represents what actually happened at the kernel level
- Works for any traced application
- EventSequence nodes contain complete event streams

**Application Abstraction Layer** (Application-Specific)
```
(Thread)-[:INITIATED]->(AppEvent:RedisCommand)-[:FULFILLED_BY]->(EventSequence)
```
- Represents why operations occurred
- Provides semantic application context
- Links to kernel reality via FULFILLED_BY relationships

### Key Capabilities

- **Complete Event Preservation**: EventSequence nodes store full event streams
- **Multi-Application Support**: Universal kernel layer + pluggable application layers
- **Temporal Analysis**: Preserved timestamps enable time-series queries
- **Causal Tracking**: Relationships capture operation dependencies
- **Scalable Design**: Efficient grouping reduces graph size while preserving detail

##  Prerequisites

### System Requirements
- **OS**: Ubuntu 22.04 LTS or similar Linux distribution
- **Python**: 3.8 or higher
- **Neo4j**: 4.0 or higher (Community or Enterprise)
- **LTTng**: lttng-tools 2.12+ with kernel modules

### Installation

#### 1. Python Dependencies
```bash
pip3 install -r requirements.txt
```

#### 2. LTTng Kernel Tracing
```bash
sudo apt update
sudo apt install lttng-tools lttng-modules-dkms babeltrace2
```

#### 3. Neo4j Database
```bash
# Install Neo4j (see official docs for latest version)
wget -O - https://debian.neo4j.com/neotechnology.gpg.key | sudo apt-key add -
echo 'deb https://debian.neo4j.com stable latest' | sudo tee /etc/apt/sources.list.d/neo4j.list
sudo apt update
sudo apt install neo4j

# Start Neo4j
sudo systemctl enable neo4j
sudo systemctl start neo4j

# Set initial password (default user: neo4j)
# Navigate to http://localhost:7474 and set password
```

#### 4. Configuration
Update Neo4j credentials in main.py or use command-line arguments:
```bash
python3 main.py --neo4j-password your_password
```

##  Complete Workflow Example

### 1. Capture a Trace
```bash
cd benchmarks
sudo python3 benchmark_tracer.py redis
```

This will:
- Start LTTng tracing session
- Launch Redis server
- Execute test workload (SET/GET commands)
- Stop tracing and save output
- Create symlink at `traces/latest`

### 2. Process Trace and Build Graph
```bash
cd ..
python3 main.py --verbose
```

This executes the complete 4-stage pipeline:
- **Stage 1**: Parse 50MB+ trace file
- **Stage 2**: Extract processes, threads, files, sockets
- **Stage 3**: Build EventSequence nodes
- **Stage 4**: Construct Neo4j knowledge graph

### 3. Query the Graph
```bash
# Open Neo4j Browser at http://localhost:7474

# Example queries:

# View all processes and their threads
MATCH (p:Process)-[:CONTAINS]->(t:Thread)
RETURN p.name, count(t) as thread_count
ORDER BY thread_count DESC

# Find expensive operations
MATCH (es:EventSequence)
WHERE es.duration_ms > 10
RETURN es.operation, es.duration_ms, es.count
ORDER BY es.duration_ms DESC
LIMIT 10

# Trace Redis commands to kernel operations
MATCH (rc:RedisCommand)-[:FULFILLED_BY]->(es:EventSequence)
RETURN rc.command, rc.key, es.operation, es.bytes_transferred

# Analyze file access patterns
MATCH (f:File)<-[:WAS_TARGET_OF]-(es:EventSequence)
RETURN f.path, count(es) as access_count, 
       sum(es.bytes_transferred) as total_bytes
ORDER BY access_count DESC
```

##  Output Files

After pipeline execution, check:

- **outputs/processed_entities/** - JSON files with extracted entities
- **outputs/graph_stats/** - Graph construction statistics
- **pipeline.log** - Detailed execution log

Example output structure:
```
outputs/
├── processed_entities/
│   ├── processes.json         # 15 processes extracted
│   ├── threads.json           # 23 threads extracted
│   ├── files.json            # 45 files accessed
│   ├── event_sequences.json  # 234 sequences created
│   └── extraction_summary.json
└── graph_stats/
    ├── graph_stats.json       # Node/relationship counts
    └── pipeline_summary.json  # Timing and performance
```

##  Research Applications

### System Analysis
- **Performance Profiling**: Identify bottlenecks through EventSequence duration analysis
- **Resource Utilization**: Track file/socket access patterns across processes
- **Concurrency Analysis**: Study thread interactions and synchronization patterns
- **I/O Characterization**: Analyze read/write patterns and data transfer volumes

### Application Understanding
- **Behavioral Modeling**: Link high-level operations to kernel implementations
- **Dependency Mapping**: Trace which files/resources applications access
- **Workload Analysis**: Understand application-kernel interaction patterns
- **Performance Tuning**: Identify optimization opportunities through causal analysis

### Cross-Layer Queries
The FULFILLED_BY relationship enables powerful queries bridging application semantics and kernel reality:

```cypher
// How many syscalls does a Redis GET take?
MATCH (rc:RedisCommand {command: 'GET'})-[:FULFILLED_BY]->(es:EventSequence)
RETURN rc.key, sum(es.count) as total_syscalls, 
       sum(es.duration_ms) as total_time_ms

// What files does an HTTP request access?
MATCH (http:HttpRequest)-[:FULFILLED_BY]->(es:EventSequence)
      -[:WAS_TARGET_OF]-(f:File)
RETURN http.uri, collect(DISTINCT f.path) as files_accessed
```

##  Troubleshooting

### Common Issues

**1. Neo4j Connection Failed**
```bash
# Check Neo4j status
sudo systemctl status neo4j

# Restart Neo4j
sudo systemctl restart neo4j

# Verify correct password
python3 main.py --neo4j-password your_actual_password
```

**2. LTTng Permission Denied**
```bash
# Must run tracing with sudo
sudo python3 benchmarks/benchmark_tracer.py redis

# Check lttng-modules are loaded
lsmod | grep lttng
```

**3. Large Trace Files**
Traces can be 50MB-500MB. If parsing is slow:
- Use `--verbose` to monitor progress
- Ensure sufficient disk space in outputs/
- Consider trace filtering in LTTng

**4. Memory Issues**
For very large traces (>1M events):
- Increase Python memory limit
- Process in batches (future enhancement)
- Use streaming mode (future enhancement)

##  Development Notes

### Code Organization
- **No emoji in code or logs** - Professional output only
- **Medium verbosity** - INFO level shows major steps, DEBUG for details
- **Meaningful naming** - Descriptive variable and function names
- **Separation of concerns** - Each module has single responsibility

### Extending the System

**Add New Application Type:**
1. Define schema in `schemas/layered_schema.json`
2. Create parser in `src/myapp_parser.py`
3. Add builder method in `src/graph_builder.py`
4. Update documentation

**Add New Kernel Entity:**
1. Define dataclass in `entity_extractor.py`
2. Add extraction logic for new entity type
3. Update schema with node definition
4. Add graph creation in `graph_builder.py`

##  Project Status

**Current Version**: 2.0 (Layered Architecture)

**Implemented:**
- 4-stage pipeline (parse → extract → sequence → graph)
- Layered knowledge graph architecture
- EventSequence aggregation model
- Universal kernel reality layer
- Redis application layer (basic)
- Complete trace parsing and entity extraction
- Neo4j graph construction
- Command-line orchestrator

**In Progress:**
- Enhanced application layer parsers (Apache, PostgreSQL)
- LLM query interface for natural language queries
- Advanced correlation algorithms for FULFILLED_BY
- Real-time streaming mode

**Roadmap:**
- Query interface with natural language processing
- Machine learning for event correlation
- Multi-trace comparison and diff analysis
- Web-based visualization dashboard
- eBPF trace support in addition to LTTng

##  Contributing

This is an active research project. Contributions welcome in:
- Application-specific parsers
- Query optimization
- Visualization tools
- Documentation improvements

##  License

[Specify your license here]

##  References

See `Project-Log.md` for detailed development history and technical decisions.

See `SCHEMA.md` for complete schema documentation with examples.

---

**Author**: Knowledge Graph and LLM Querying for Kernel Traces Project  
**Last Updated**: October 3, 2025
- **System performance characterization**
- **Trace-driven analysis methodologies**

##  Development

### Project Status
-  **Core Pipeline**: Complete and functional
-  **Graph Construction**: Universal schema implemented
-  **Analytics Engine**: Multi-dimensional analysis ready
-  **Benchmark Tracing**: 5 built-in benchmarks + custom support
-  **LLM Integration**: Natural language querying (in development)

### Contributing
1. Fork the repository
2. Create feature branch: `git checkout -b feature/new-analysis`
3. Commit changes: `git commit -am 'Add new analysis capability'`
4. Push to branch: `git push origin feature/new-analysis`
5. Submit Pull Request

## Documentation

- [ Project Log](Project-Log.md) - Development timeline and milestones
- [ Schema Documentation](SCHEMA.md) - Graph schema specifications  
- [ System Fixes](SYSTEM_FIXES_SUMMARY.md) - Technical implementation details
- [ Benchmarks](benchmarks/README.md) - Tracing utilities documentation

##  Performance Metrics

**Current System Capabilities:**
- **Processing Speed**: 1,000 events in ~0.15s
- **Graph Construction**: 557 nodes + 1,927 relationships in ~1s
- **Analysis Generation**: Complete multi-dimensional analysis in ~0.4s
- **Total Pipeline**: End-to-end processing in ~1.5s

##  Success Metrics

The system successfully transforms minimal trace data into comprehensive diagnostic capabilities:

**Before Enhancement**: 6 nodes, 3 relationships (insufficient for diagnostics)  
**After Enhancement**: 557 nodes, 1,927 relationships (comprehensive system analysis)

This represents a **92x improvement** in diagnostic data extraction from the same kernel traces!

##  License

This project is part of academic research in kernel trace analysis and system performance modeling.