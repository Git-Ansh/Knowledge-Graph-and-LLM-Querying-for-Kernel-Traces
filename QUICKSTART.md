# QUICKSTART GUIDE

## Installation and Setup (5 minutes)

### 1. Install Dependencies
```bash
# Python packages
pip3 install neo4j

# LTTng (if not already installed)
sudo apt update
sudo apt install lttng-tools lttng-modules-dkms

# Verify installations
python3 --version    # Should be 3.8+
lttng --version      # Should be 2.12+
```

### 2. Start Neo4j
```bash
# Start Neo4j service
sudo systemctl start neo4j

# Verify it's running
sudo systemctl status neo4j

# Open Neo4j Browser: http://localhost:7474
# Default credentials: neo4j/neo4j
# Set new password when prompted
```

### 3. Configure Pipeline
```bash
# Update Neo4j password in main.py, or use command line:
# python3 main.py --neo4j-password YOUR_PASSWORD
```

## Run Your First Analysis (10 minutes)

### Step 1: Capture a Trace
```bash
cd benchmarks
sudo python3 benchmark_tracer.py redis
```

**What this does:**
- Starts LTTng kernel tracing
- Launches Redis server
- Executes test commands (SET, GET, etc.)
- Captures complete kernel trace
- Saves to `traces/redis_TIMESTAMP/`
- Creates symlink at `traces/latest`

**Expected output:**
```
2025-10-03 19:00:00 - INFO - Creating LTTng session: app_redis_20251003_190000
2025-10-03 19:00:01 - INFO - Starting tracing for session app_redis_20251003_190000
2025-10-03 19:00:02 - INFO - Application started with PID: 12345
...
2025-10-03 19:00:15 - INFO - Trace saved to: traces/redis_20251003_190000
```

### Step 2: Process Trace and Build Graph
```bash
cd ..
python3 main.py --verbose
```

**What this does:**
- **Stage 1**: Parse raw LTTng trace (50MB+ file)
- **Stage 2**: Extract entities (processes, threads, files)
- **Stage 3**: Build EventSequence nodes
- **Stage 4**: Construct Neo4j knowledge graph

**Expected output:**
```
======================================================================
Pipeline Orchestrator Initialized
======================================================================
Trace directory: traces/latest
Output directory: outputs
Schema: layered_schema.json

======================================================================
STAGE 1: TRACE PARSING
======================================================================
Parsing trace file: trace_output.txt
File size: 52.34 MB
...
Parsed 145,234 events in 8.5 seconds
Parse rate: 17,087 events/second

======================================================================
STAGE 2: ENTITY EXTRACTION
======================================================================
Extracting processes and threads
Extracted 15 processes and 23 threads
...
Extraction complete:
  Processes: 15
  Threads: 23
  Files: 45
  Sockets: 8
  CPUs: 4

======================================================================
STAGE 3: EVENT SEQUENCE BUILDING
======================================================================
Building event sequences
Paired 12,456 syscall entry/exit events
...
Built 234 event sequences
  read: 45 sequences
  write: 38 sequences
  socket_send: 12 sequences
  ...

======================================================================
STAGE 4: GRAPH CONSTRUCTION
======================================================================
Successfully connected to Neo4j database
Clearing existing graph data
Creating constraints and indexes
Building layered knowledge graph
  Building kernel reality layer
    Creating Process nodes
    Creating Thread nodes
    Creating CONTAINS relationships
    ...
  Building application layer for: redis
...
Graph construction complete
  Total nodes: 329
  Total relationships: 418

======================================================================
PIPELINE COMPLETE
======================================================================
Total execution time: 24.5 seconds

Stage Breakdown:
  PARSE: 8.5s (34.7%)
  EXTRACT: 2.3s (9.4%)
  SEQUENCES: 3.8s (15.5%)
  GRAPH: 9.9s (40.4%)

Pipeline summary saved to: outputs/pipeline_summary.json
```

### Step 3: Query the Graph
```bash
# Open Neo4j Browser
firefox http://localhost:7474
```

**Try these queries:**

1. **View all processes and threads:**
```cypher
MATCH (p:Process)-[:CONTAINS]->(t:Thread)
RETURN p.name, p.pid, count(t) as threads
ORDER BY threads DESC
```

2. **Find all file read operations:**
```cypher
MATCH (f:File)<-[:WAS_TARGET_OF]-(es:EventSequence {operation: 'read'})
RETURN f.path, es.count, es.bytes_transferred, es.duration_ms
ORDER BY es.bytes_transferred DESC
```

3. **Analyze Redis commands:**
```cypher
MATCH (rc:RedisCommand)
RETURN rc.command, rc.key, rc.event_name
```

4. **Find expensive operations:**
```cypher
MATCH (es:EventSequence)
WHERE es.duration_ms > 5
RETURN es.operation, es.entity_target, es.duration_ms, es.count
ORDER BY es.duration_ms DESC
LIMIT 10
```

## Understanding the Output

### Files Created

**outputs/processed_entities/**
- `processes.json` - All processes found in trace
- `threads.json` - All threads with parent PIDs
- `files.json` - Files accessed with access counts
- `event_sequences.json` - Grouped kernel operations
- `extraction_summary.json` - Statistics

**outputs/graph_stats/**
- `graph_stats.json` - Node/relationship counts
- `pipeline_summary.json` - Execution timing

**Root directory:**
- `pipeline.log` - Detailed execution log

### Graph Structure

Your Neo4j database now contains:

**Kernel Reality Layer:**
- Process nodes (e.g., redis-server, systemd)
- Thread nodes (worker threads)
- File nodes (config files, data files)
- Socket nodes (network connections)
- CPU nodes (cores 0-3)
- EventSequence nodes (grouped syscalls)

**Application Layer:**
- RedisCommand nodes (SET, GET, etc.)

**Relationships:**
- CONTAINS (Process → Thread)
- PERFORMED (Thread → EventSequence)
- WAS_TARGET_OF (File → EventSequence)
- INITIATED (Thread → RedisCommand)
- FULFILLED_BY (RedisCommand → EventSequence)

## Next Steps

### Capture Different Applications
```bash
cd benchmarks
sudo python3 benchmark_tracer.py --list    # See available benchmarks
sudo python3 benchmark_tracer.py apache    # Trace Apache
sudo python3 benchmark_tracer.py nginx     # Trace Nginx
```

### Explore the Schema
```bash
cat SCHEMA.md        # Complete schema documentation
cat schemas/layered_schema.json   # Schema specification
```

### Analyze Output
```bash
# View extracted entities
cat outputs/processed_entities/processes.json | jq
cat outputs/processed_entities/event_sequences.json | jq | head -100

# Check statistics
cat outputs/graph_stats/graph_stats.json | jq
```

### Run Individual Modules
```bash
# Test trace parser
python3 src/trace_parser.py traces/latest/trace_output.txt

# Test entity extractor
python3 src/entity_extractor.py traces/latest/trace_output.txt

# Test sequence builder
python3 src/event_sequence_builder.py traces/latest/trace_output.txt
```

## Troubleshooting

**Problem: Neo4j connection failed**
```bash
sudo systemctl status neo4j
sudo systemctl restart neo4j
# Check password: python3 main.py --neo4j-password YOUR_PASSWORD
```

**Problem: LTTng permission denied**
```bash
# Must use sudo for kernel tracing
sudo python3 benchmarks/benchmark_tracer.py redis
```

**Problem: Trace file not found**
```bash
# Check if trace was captured
ls -lh traces/latest/trace_output.txt
# If missing, re-run trace capture
```

**Problem: Pipeline too slow**
```bash
# Check trace size
du -h traces/latest/trace_output.txt
# Large files (>100MB) take longer
# Monitor progress with --verbose flag
```

## Success Criteria

After following this guide, you should have:
- ✓ Captured a Redis trace
- ✓ Processed it through 4-stage pipeline
- ✓ Created Neo4j knowledge graph with 300+ nodes
- ✓ Executed queries showing processes, threads, and operations
- ✓ Understood the layered architecture

## Getting Help

- **Detailed documentation**: README.md
- **Schema reference**: SCHEMA.md
- **Module documentation**: src/README.md
- **Development log**: Project-Log.md

## Common Commands Reference

```bash
# Capture trace
sudo python3 benchmarks/benchmark_tracer.py redis

# Process with default settings
python3 main.py

# Process with custom Neo4j password
python3 main.py --neo4j-password mypassword

# Process specific trace
python3 main.py --trace traces/redis_20251003_190000

# Enable verbose logging
python3 main.py --verbose

# View logs
tail -f pipeline.log

# Check Neo4j
sudo systemctl status neo4j
```

---

**Estimated Time**: 
- Setup: 5 minutes
- First trace: 2 minutes
- Pipeline execution: 30 seconds - 2 minutes (depending on trace size)
- Query exploration: 5-10 minutes

**Total**: ~15-20 minutes to complete first end-to-end run
