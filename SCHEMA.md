# Layered Knowledge Graph Schema

> **Version 2.0** - Layered architecture separating kernel reality from application abstraction

## Core Philosophy: Separation of Actors and Actions

This schema implements a fundamental design principle: **separate the actors from the actions**.

- **Actors** (Process, Thread, File, Socket, CPU) are the characters in the system
- **Actions** (EventSequence nodes) are the chapters describing what the characters did
- **Relationships** connect actors to their actions and to each other

This design keeps the main graph clean while preserving complete event detail in EventSequence nodes.

## Two-Layer Architecture

### Layer 1: Kernel Reality (Universal)

The ground truth of OS operations - works for any traced application.

**Nodes:**
- `Process` - Operating system process
- `Thread` - Execution thread within a process  
- `File` - File system resource
- `Socket` - Network socket endpoint
- `CPU` - Processor core
- `EventSequence` - Ordered sequence of kernel events forming a logical operation

**Relationships:**
- `CONTAINS` - Process contains Thread
- `PERFORMED` - Thread performed EventSequence
- `WAS_TARGET_OF` - File/Socket was target of EventSequence
- `FOLLOWS` - Temporal ordering between EventSequences
- `SCHEDULED_ON` - Thread scheduled on CPU

### Layer 2: Application Abstraction (Application-Specific)

Semantic context for why operations occurred - pluggable per application.

**Nodes:**
- `AppEvent` - Generic application event
- `RedisCommand` - Redis database command (extends AppEvent)
- `HttpRequest` - HTTP request event (extends AppEvent)
- `SqlQuery` - SQL database query (extends AppEvent)

**Relationships:**
- `INITIATED` - Thread initiated AppEvent
- `FULFILLED_BY` - AppEvent fulfilled by EventSequence (cross-layer link)

## Design Principles

### 1. **Universal Kernel Foundation**
- Core entities exist in ALL traced applications
- Schema works with any tracing backend (LTTng, eBPF, strace)
- Application-agnostic kernel reality layer

### 2. **Event Sequence Aggregation**
Instead of creating individual nodes for each syscall:
- Group related syscalls into EventSequence nodes
- Store complete event stream as property
- Drastically reduces graph size while preserving all detail
- Example: 16 read() calls → 1 EventSequence node with 16 events in event_stream

### 3. **Pluggable Application Layers**
- Universal kernel layer works standalone
- Add application-specific nodes/relationships as needed
- Use multiple labels for inheritance (e.g., `AppEvent:RedisCommand`)
- Application layers link to kernel via FULFILLED_BY

### 4. **Temporal and Causal Preservation**
- All events maintain precise timestamps
- FOLLOWS relationships preserve ordering
- EventSequence nodes capture operation duration
- Enable time-series and causality analysis

## Node Definitions

### Kernel Reality Layer

#### Process
**Description**: Operating system process  
**Properties**:
- `pid` (required) - Process ID
- `name` (required) - Process name
- `start_time` (required) - Process start timestamp
- `cmdline` (optional) - Command line arguments
- `parent_pid` (optional) - Parent process ID
- `end_time` (optional) - Process termination timestamp
- `thread_count` (optional) - Number of threads

#### Thread  
**Description**: Execution thread within a process  
**Properties**:
- `tid` (required) - Thread ID
- `pid` (required) - Parent process ID
- `start_time` (required) - Thread start timestamp
- `name` (optional) - Thread name
- `end_time` (optional) - Thread termination timestamp
- `priority` (optional) - Thread scheduling priority
- `cpu_affinity` (optional) - CPU affinity mask

#### File
**Description**: File system resource  
**Properties**:
- `path` (required) - File path
- `type` (required) - File type (file, directory, pipe, socket)
- `inode` (optional) - Inode number
- `permissions` (optional) - File permissions
- `first_access` (optional) - First access timestamp
- `last_access` (optional) - Last access timestamp
- `access_count` (optional) - Number of accesses

#### Socket
**Description**: Network socket endpoint  
**Properties**:
- `address` (required) - Local IP address
- `port` (required) - Local port number
- `protocol` (required) - Protocol (TCP, UDP, etc.)
- `family` (optional) - Address family (AF_INET, AF_INET6)
- `type` (optional) - Socket type (SOCK_STREAM, SOCK_DGRAM)
- `remote_address` (optional) - Remote IP address
- `remote_port` (optional) - Remote port number
- `first_access` (optional) - First use timestamp

#### CPU
**Description**: Processor core  
**Properties**:
- `cpu_id` (required) - CPU core ID
- `event_count` (optional) - Number of events on this CPU

#### EventSequence (Critical Node)
**Description**: Ordered sequence of kernel events representing a complete logical operation  
**Purpose**: Aggregates related syscalls into single "action chapter" node  
**Properties**:
- `sequence_id` (required) - Unique sequence identifier
- `operation` (required) - Operation type (read, write, open, socket_send, etc.)
- `start_time` (required) - Sequence start timestamp
- `end_time` (required) - Sequence end timestamp
- `count` (required) - Number of events in sequence
- `event_stream` (required) - JSON array of complete event details
- `entity_target` (optional) - Target entity (file path, socket, etc.)
- `return_value` (optional) - Final return value
- `bytes_transferred` (optional) - Total bytes transferred
- `duration_ms` (optional) - Duration in milliseconds

**Example event_stream structure**:
```json
[
  {
    "timestamp": 12345.678,
    "syscall": "read",
    "duration": 0.002,
    "return_value": 4096,
    "key_params": {"fd": 3, "count": 4096}
  },
  ...
]
```

### Application Abstraction Layer

#### AppEvent
**Description**: Generic application-level event  
**Properties**:
- `event_name` (required) - Human-readable event name
- `start_time` (required) - Event start timestamp
- `end_time` (optional) - Event end timestamp
- `details` (optional) - JSON blob of application-specific data
- `status` (optional) - Event status/result

#### RedisCommand (extends AppEvent)
**Description**: Redis database command  
**Additional Properties**:
- `command` (required) - Redis command (SET, GET, DEL, etc.)
- `key` (required) - Redis key
- `value` (optional) - Value data
- `value_size` (optional) - Size of value in bytes
- `client_ip` (optional) - Client IP address
- `result` (optional) - Command result

#### HttpRequest (extends AppEvent)
**Description**: HTTP request event  
**Additional Properties**:
- `method` (required) - HTTP method (GET, POST, etc.)
- `uri` (required) - Request URI
- `status_code` (optional) - HTTP response status
- `response_size` (optional) - Response size in bytes
- `user_agent` (optional) - Client user agent
- `client_ip` (optional) - Client IP address

#### SqlQuery (extends AppEvent)
**Description**: SQL database query  
**Additional Properties**:
- `query_type` (required) - Query type (SELECT, INSERT, UPDATE, DELETE)
- `query_text` (required) - SQL query text
- `rows_affected` (optional) - Number of rows affected
- `execution_time` (optional) - Query execution time
- `database` (optional) - Database name
- `table` (optional) - Primary table name

## Relationship Definitions

### Kernel Reality Layer

#### CONTAINS
**Source**: Process  
**Target**: Thread  
**Description**: Process contains thread  
**Properties**:
- `creation_time` - Thread creation timestamp

**Example**:
```cypher
(p:Process {pid: 1234})-[:CONTAINS {creation_time: 12345.678}]->(t:Thread {tid: 1235})
```

#### PERFORMED
**Source**: Thread  
**Target**: EventSequence  
**Description**: Thread performed an event sequence  
**Properties**:
- `start_time` - When thread started the sequence
- `end_time` - When thread completed the sequence
- `cpu` - CPU where execution occurred

**Example**:
```cypher
(t:Thread {tid: 1235})-[:PERFORMED {start_time: 12345.678, cpu: 0}]->(es:EventSequence {operation: 'read'})
```

#### WAS_TARGET_OF
**Source**: File or Socket  
**Target**: EventSequence  
**Description**: Resource was the target of an event sequence  
**Properties**:
- `access_type` - Type of access (matches EventSequence operation)

**Example**:
```cypher
(f:File {path: '/var/www/index.html'})-[:WAS_TARGET_OF {access_type: 'read'}]->(es:EventSequence)
```

#### FOLLOWS  
**Source**: EventSequence  
**Target**: EventSequence  
**Description**: Temporal ordering between event sequences  
**Properties**:
- `time_delta` - Time gap between sequences in seconds

**Example**:
```cypher
(es1:EventSequence)-[:FOLLOWS {time_delta: 0.005}]->(es2:EventSequence)
```

#### SCHEDULED_ON
**Source**: Thread  
**Target**: CPU  
**Description**: Thread was scheduled on CPU  
**Properties**:
- `timestamp` - Scheduling event timestamp
- `duration` - Time scheduled on CPU

### Application Abstraction Layer

#### INITIATED
**Source**: Thread  
**Target**: AppEvent (or any subtype)  
**Description**: Thread initiated an application-level event  
**Properties**:
- `timestamp` - When the event was initiated

**Example**:
```cypher
(t:Thread {tid: 1235})-[:INITIATED {timestamp: 12345.678}]->(ae:AppEvent:HttpRequest {method: 'GET'})
```

### Cross-Layer Relationships

#### FULFILLED_BY (Critical Connection)
**Source**: AppEvent (or any subtype)  
**Target**: EventSequence  
**Description**: Application event was fulfilled by kernel event sequence  
**Purpose**: Links application abstraction to kernel reality  
**Properties**:
- `correlation_confidence` - Confidence score for correlation (0.0 to 1.0)

**Example**:
```cypher
(ae:AppEvent:HttpRequest {uri: '/index.html'})
  -[:FULFILLED_BY {correlation_confidence: 0.95}]->
  (es:EventSequence {operation: 'read', entity_target: '/var/www/index.html'})
```

This relationship is the key to answering questions like:
- "How many syscalls did it take to serve this HTTP request?"
- "What files were accessed for this Redis SET command?"
- "Show me the kernel-level implementation of this SQL query"

## Event Grouping Rules

EventSequence nodes are created by grouping related syscalls according to schema-defined rules.

### Read Operations
**Syscalls**: read, pread64, readv, preadv  
**Group by**: Thread ID + File Descriptor  
**Break on**: Time gap > 100ms OR different file descriptor  
**Result**: One EventSequence per continuous read operation burst

### Write Operations  
**Syscalls**: write, pwrite64, writev, pwritev  
**Group by**: Thread ID + File Descriptor  
**Break on**: Time gap > 100ms OR different file descriptor  
**Result**: One EventSequence per continuous write operation burst

### File Open Operations
**Syscalls**: open, openat, openat2  
**Group by**: Thread ID  
**Break on**: Immediate (each open is separate)  
**Result**: One EventSequence per file open

### Socket Send Operations
**Syscalls**: send, sendto, sendmsg, sendmmsg  
**Group by**: Thread ID + Socket FD  
**Break on**: Time gap > 50ms OR different socket  
**Result**: One EventSequence per network transmission burst

### Socket Receive Operations
**Syscalls**: recv, recvfrom, recvmsg, recvmmsg  
**Group by**: Thread ID + Socket FD  
**Break on**: Time gap > 50ms OR different socket  
**Result**: One EventSequence per network reception burst

## Example Graph Structure

### Apache Web Server Example

Here's how an HTTP GET request is represented:

```
// Kernel Reality Layer
(apache:Process {pid: 5500, name: "apache2"})
  -[:CONTAINS]->
  (worker:Thread {tid: 5501})
  -[:PERFORMED]->
  (readSeq:EventSequence {
    operation: "read",
    count: 16,
    bytes_transferred: 65536,
    event_stream: "[...16 read syscalls...]"
  })
  <-[:WAS_TARGET_OF]-
  (index:File {path: "/var/www/html/index.html"})

// Application Abstraction Layer
(worker:Thread)
  -[:INITIATED]->
  (request:AppEvent:HttpRequest {
    method: "GET",
    uri: "/index.html",
    status_code: 200
  })
  -[:FULFILLED_BY]->
  (readSeq:EventSequence)
```

This structure allows queries like:
- "Show me all HTTP requests" → Query Application Layer
- "How was each request implemented?" → Traverse FULFILLED_BY
- "What files were accessed?" → Follow to File nodes
- "Show me exact syscall timing" → Read event_stream property

## Query Examples

### Find all file read operations
```cypher
MATCH (es:EventSequence {operation: 'read'})
RETURN es.entity_target, es.count, es.bytes_transferred
```

### Trace a specific thread's activity
```cypher
MATCH (t:Thread {tid: 5501})-[:PERFORMED]->(es:EventSequence)
RETURN es.operation, es.start_time, es.duration_ms
ORDER BY es.start_time
```

### Find application events and their kernel implementation
```cypher
MATCH (ae:AppEvent)-[:FULFILLED_BY]->(es:EventSequence)
RETURN ae.event_name, es.operation, es.count, es.bytes_transferred
```

### Analyze file access patterns
```cypher
MATCH (f:File)<-[:WAS_TARGET_OF]-(es:EventSequence)
RETURN f.path, count(es) as access_sequences, 
       sum(es.bytes_transferred) as total_bytes
ORDER BY access_sequences DESC
```

### Find expensive operations
```cypher
MATCH (es:EventSequence)
WHERE es.duration_ms > 10
RETURN es.operation, es.duration_ms, es.count
ORDER BY es.duration_ms DESC
LIMIT 10
```

## Extending the Schema

### Adding a New Application Type

To support a new application (e.g., PostgreSQL):

1. **Define Application Node** in `schemas/layered_schema.json`:
```json
"PostgresQuery": {
  "layer": "application_abstraction",
  "extends": "AppEvent",
  "required_properties": ["query_type", "query_text"],
  "optional_properties": ["rows_affected", "execution_time"]
}
```

2. **Create Application Parser** in `src/postgres_parser.py`:
```python
def parse_postgres_logs(log_file):
    # Parse PostgreSQL logs
    # Extract query events
    # Return list of PostgresQuery objects
    pass
```

3. **Add to Graph Builder** in `src/graph_builder.py`:
```python
def _build_postgres_layer(self, entities, metadata):
    # Create PostgresQuery nodes
    # Create INITIATED relationships from threads
    # Create FULFILLED_BY relationships to EventSequences
    pass
```

The universal kernel layer requires no changes - only application-specific extensions.

## Implementation Notes

### Performance Considerations
- EventSequence aggregation reduces graph size by 10-100x
- Indexes on timestamps enable fast temporal queries
- event_stream stored as JSON string for detailed access
- Neo4j relationship properties enable efficient filtering

### Data Integrity
- Unique constraints on Process.pid, Thread.tid, EventSequence.sequence_id
- Indexes on frequently queried properties (operation, start_time)
- Referential integrity maintained through relationship creation order

### Scalability
- Large traces (>1M events) processed in minutes
- Graph size manageable due to event aggregation
- Query performance optimized through strategic indexing
- Streaming processing possible for real-time analysis

The schema supports common patterns found across all applications:

### File I/O Pattern (Universal)
```cypher
MATCH path = (p:Process)-[:EXECUTES]->(open:SyscallEvent {name: 'openat'})
            -[:OPENS]->(f:File)
            <-[:READS]-(read:SyscallEvent)<-[:EXECUTES]-(p)
RETURN path
```

### Network Communication Pattern  
```cypher
MATCH (p:Process)-[:EXECUTES]->(connect:SyscallEvent)
     -[:CONNECTS]->(s:Socket)
     <-[:SENDS]-(send:SyscallEvent)<-[:EXECUTES]-(p)
RETURN p.name, s.remote_addr, count(send) as messages_sent
```

### Process Lifecycle Pattern
```cypher
MATCH (parent:Process)-[:SPAWNED]->(child:Process)
MATCH (child)-[:EXECUTES]->(exit:SyscallEvent {name: 'exit'})
RETURN parent.name, child.name, 
       duration.between(child.start_time, exit.timestamp) as lifetime
```

### Memory Management Pattern
```cypher
MATCH (p:Process)-[:EXECUTES]->(mmap:SyscallEvent {name: 'mmap'})
     -[:MAPS]->(mem:MemoryRegion)
     <-[:UNMAPS]-(munmap:SyscallEvent)<-[:EXECUTES]-(p)
RETURN mem.start_addr, mem.size,
       duration.between(mmap.timestamp, munmap.timestamp) as allocated_time
```

## Schema Extensions Framework

### Application-Specific Extensions

**Database Extension**:
```cypher
(:Query {sql_text, duration, rows_affected, plan_hash})
(:Transaction {xid, isolation_level, start_time, commit_time})
(:Lock {lock_type, resource_id, mode, granted_time})

(:Process)-[:EXECUTES_QUERY]->(:Query)
(:Transaction)-[:CONTAINS]->(:Query)
(:Query)-[:ACQUIRES]->(:Lock)
```

**Container Extension**:
```cypher
(:Container {container_id, image, name, start_time})
(:Namespace {ns_type, ns_id, processes})
(:Cgroup {path, limits, usage})

(:Process)-[:RUNS_IN]->(:Container)
(:Container)-[:USES]->(:Namespace)
(:Process)-[:LIMITED_BY]->(:Cgroup)
```

**GPU Extension**:
```cypher  
(:GPUDevice {device_id, model, memory_total})
(:CUDAKernel {name, grid_size, block_size, duration})
(:GPUMemory {address, size, type})

(:Process)-[:LAUNCHES]->(:CUDAKernel)
(:CUDAKernel)-[:EXECUTES_ON]->(:GPUDevice)
(:Process)-[:ALLOCATES]->(:GPUMemory)
```

## Implementation Status

###  Completed
- **v2.0 Universal Schema**: Core entities and relationships defined
- **Multi-tier Architecture**: Process → Resources → Events → Context
- **Universal Parser Framework**: LTTng, strace, eBPF support
- **Neo4j Schema Generator**: Automated constraint and index creation
- **Extension Framework**: Application-specific additions
- **Redis Implementation**: Real-world validation with 300K+ events

###  Current Version  
- **v2.0** (2025-09-27): Universal schema for cross-application tracing
  - Universal entities: Process, Thread, File, Socket, SyscallEvent, SyscallType
  - Universal relationships: SPAWNED, EXECUTES, OPENS, READS, WRITES, CONNECTS
  - Multi-format parser support (LTTng, strace)
  - Extension framework for application-specific needs
  - Performance optimizations: constraints, indexes, aggregation

###  Usage Examples

**Load Universal Schema**:
```bash
# Generate schema files
python3 universal_schema_designer.py

# Load into Neo4j
cypher-shell < universal_schema.cypher
```

**Parse Any Trace Format**:
```bash
# LTTng traces
python3 universal_trace_parser.py lttng_trace.txt

# Strace traces  
python3 universal_trace_parser.py strace_output.txt

# eBPF traces (with extension)
python3 universal_trace_parser.py ebpf_events.txt
```

**Query Any Application**:
```cypher
-- Works with Redis, Apache, PostgreSQL, etc.
MATCH (p:Process)-[:EXECUTES]->(e:SyscallEvent)-[:OPENS]->(f:File)
WHERE f.path CONTAINS '.log'
RETURN p.name, count(f) as log_files_opened
```

###  Future Development
- **LLM Query Interface**: Natural language to Cypher translation
- **Real-time Streaming**: Live trace ingestion and analysis  
- **Machine Learning**: Anomaly detection and pattern recognition
- **Distributed Tracing**: Multi-node application support
- **Custom Extensions**: Domain-specific schema modules