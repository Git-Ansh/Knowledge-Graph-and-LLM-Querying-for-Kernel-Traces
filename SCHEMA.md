# Universal Kernel Trace Schema Design

> **Version 2.0** - Universal schema for kernel/application tracing that works across different applications, workloads, and tracing tools (LTTng, eBPF, strace, etc.)

## Design Principles

### 1. **Application Agnostic**
- Core entities that exist in ALL traced applications
- Extensible framework for application-specific additions
- Language and runtime independent

### 2. **Tool Agnostic** 
- Works with any tracing backend (LTTng, eBPF, strace, DTrace)
- Standardized representation regardless of source format
- Consistent timestamps and event ordering

### 3. **Multi-Scale Analysis**
- **Statistical View**: Aggregated patterns and frequencies
- **Temporal View**: Individual event sequences and timing
- **Hierarchical View**: Process trees and resource relationships

### 4. **Extensible Architecture**
- Core schema + optional extensions
- Domain-specific modules (networking, containers, databases)
- Custom property injection without schema changes

## Core Universal Entities (Nodes)

### **Tier 1: Process Hierarchy**
| Node Label | Description | Universal Properties |
|------------|-------------|---------------------|
| **Process** | Any running process/application | `pid`, `name`, `cmdline`, `start_time`, `parent_pid`, `uid`, `gid` |
| **Thread** | Execution thread within process | `tid`, `pid`, `name`, `start_time`, `stack_size`, `priority` |
| **ProcessGroup** | Group of related processes | `pgid`, `leader_pid`, `session_id`, `creation_time` |

### **Tier 2: System Resources**
| Node Label | Description | Universal Properties |
|------------|-------------|---------------------|
| **File** | Files, directories, pipes, sockets | `path`, `inode`, `type`, `permissions`, `size`, `device` |
| **FileDescriptor** | Open file handle | `fd`, `flags`, `offset`, `process_pid`, `file_path` |
| **Socket** | Network endpoint | `family`, `type`, `protocol`, `local_addr`, `remote_addr`, `state` |
| **MemoryRegion** | Allocated memory area | `start_addr`, `end_addr`, `size`, `permissions`, `type`, `backing_file` |

### **Tier 3: Execution Events**
| Node Label | Description | Universal Properties |
|------------|-------------|---------------------|
| **SyscallEvent** | Individual system call | `name`, `timestamp`, `type` (entry/exit), `cpu`, `duration`, `return_value` |
| **SyscallType** | System call category/template | `name`, `category`, `signature`, `frequency`, `avg_duration` |
| **CPUEvent** | CPU scheduling event | `cpu_id`, `timestamp`, `event_type`, `prev_task`, `next_task` |

### **Tier 4: Time & Context**
| Node Label | Description | Universal Properties |
|------------|-------------|---------------------|
| **TimeWindow** | Temporal aggregation unit | `start_time`, `end_time`, `duration`, `event_count` |
| **TraceSession** | Complete trace collection | `session_id`, `start_time`, `end_time`, `tool`, `target_app`, `events_count` |

## Universal Relationships

### **Process Hierarchy & Lifecycle**
| Relationship | Source → Target | Description | Universal Properties |
|--------------|-----------------|-------------|---------------------|
| **SPAWNED** | Process → Process | Parent creates child | `timestamp`, `method` (fork/exec/clone), `exit_code` |
| **CONTAINS** | Process → Thread | Process owns thread | `creation_time`, `termination_time` |
| **BELONGS_TO** | Thread → Process | Thread ownership | `start_time`, `cpu_affinity` |
| **LEADS** | Process → ProcessGroup | Process group leadership | `timestamp`, `session_change` |

### **Execution & Scheduling**
| Relationship | Source → Target | Description | Universal Properties |
|--------------|-----------------|-------------|---------------------|
| **EXECUTES** | Process/Thread → SyscallEvent | Syscall execution | `entry_time`, `exit_time`, `cpu`, `context` |
| **INSTANTIATES** | SyscallEvent → SyscallType | Event classification | `timestamp`, `parameters` |
| **SCHEDULED_ON** | Thread → CPUEvent | CPU scheduling | `timestamp`, `duration`, `priority`, `preemption` |
| **FOLLOWS** | SyscallEvent → SyscallEvent | Temporal sequence | `time_delta`, `causal_relationship` |

### **Resource Access**
| Relationship | Source → Target | Description | Universal Properties |
|--------------|-----------------|-------------|---------------------|
| **OPENS** | SyscallEvent → File | File opening | `timestamp`, `flags`, `mode`, `fd_assigned` |
| **READS** | SyscallEvent → FileDescriptor | Data reading | `timestamp`, `bytes`, `offset`, `buffer_addr` |
| **WRITES** | SyscallEvent → FileDescriptor | Data writing | `timestamp`, `bytes`, `offset`, `sync_type` |
| **CLOSES** | SyscallEvent → FileDescriptor | Resource cleanup | `timestamp`, `final_offset`, `bytes_total` |
| **MAPS** | SyscallEvent → MemoryRegion | Memory mapping | `timestamp`, `address`, `size`, `protection` |
| **UNMAPS** | SyscallEvent → MemoryRegion | Memory unmapping | `timestamp`, `address`, `size` |

### **Network Communication**
| Relationship | Source → Target | Description | Universal Properties |
|--------------|-----------------|-------------|---------------------|
| **CONNECTS** | SyscallEvent → Socket | Network connection | `timestamp`, `result`, `peer_addr`, `local_addr` |
| **SENDS** | SyscallEvent → Socket | Data transmission | `timestamp`, `bytes`, `flags`, `destination` |
| **RECEIVES** | SyscallEvent → Socket | Data reception | `timestamp`, `bytes`, `flags`, `source` |
| **BINDS** | SyscallEvent → Socket | Address binding | `timestamp`, `address`, `port`, `result` |

### **Synchronization & IPC**
| Relationship | Source → Target | Description | Universal Properties |
|--------------|-----------------|-------------|---------------------|
| **WAITS_ON** | Thread → Thread | Thread synchronization | `timestamp`, `mechanism` (futex/mutex), `timeout` |
| **WAKES** | Thread → Thread | Thread wake-up | `timestamp`, `wake_reason`, `priority_boost` |
| **SIGNALS** | Process → Process | Signal delivery | `timestamp`, `signal_num`, `handler`, `result` |

## Universal Event Patterns

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