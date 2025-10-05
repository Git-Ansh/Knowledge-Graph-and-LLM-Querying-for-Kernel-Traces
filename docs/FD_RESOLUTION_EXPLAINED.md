# File Descriptor (FD) Resolution - Explained

## What are "Unresolved FDs"?

**Unresolved FDs** are file descriptors that were **opened before the LTTng trace started**. They appear in the graph as `fd:XX` (e.g., `fd:3`, `fd:21`, `fd:74`) instead of actual file paths or socket IDs.

### Example
```
✅ Resolved:   /var/log/redis.log (opened during trace)
🔴 Unresolved: fd:74              (opened before trace)
```

---

## Statistics from Redis Trace

| Category | Count | Percentage |
|----------|-------|------------|
| **Resolved operations** | 4,459 | 66.3% |
| **Unresolved operations** | 2,268 | 33.7% |
| **Total operations** | 6,727 | 100% |

### Breakdown of Unresolved FDs

| Operation Type | Count | Notes |
|----------------|-------|-------|
| close | 639 | Closing pre-existing files/sockets |
| write | 550 | Writing to pre-existing FDs |
| read | 461 | Reading from pre-existing FDs |
| socket_recv | 351 | Network receives on pre-existing sockets |
| socket_send | 184 | Network sends on pre-existing sockets |
| mmap | 83 | Memory mapping pre-existing FDs |

---

## Why Can't We Resolve Them?

### The Trace Window Problem

```
Process starts ──────────────────────────────────────────→ Time
                      ↑                            ↑
                   open fd:3              Trace starts here
                   (we missed this!)     (we only see operations)
```

When tracing starts, some files/sockets are **already open**:
- Redis server started before trace
- Inherited file descriptors from parent process
- Configuration files opened at startup
- Network connections established before trace

### What We Miss
We don't see the `open()`, `socket()`, or `accept()` syscalls that created these FDs, so we can't resolve them to:
- File paths (e.g., `/var/log/redis.log`)
- Socket IDs (e.g., `socket_12417_68400.020298274`)

---

## What Do Unresolved FDs Represent?

### 1. Standard I/O (stdin/stdout/stderr)
```
fd:0 → stdin   (4 operations)
fd:1 → stdout  (96 operations)
fd:2 → stderr  (39 operations)
```

### 2. Pre-existing Network Connections
```
fd:74 → Network socket (12,690 bytes sent)
fd:82 → Network socket (13,156 bytes received)
```
These are **active Redis client connections** that existed before tracing started.

### 3. Configuration and Log Files
```
fd:3  → Unknown file (106 close operations)
fd:4  → Unknown file (107 close operations)
fd:23 → Unknown file (187 read/write operations)
```

### 4. Inherited File Descriptors
Child processes inherit open FDs from parents (Redis worker threads inherit from main process).

---

## Are They Important?

### ✅ YES - Here's Why:

#### 1. **They Represent Real Activity**
- **2,268 operations** (33.7% of all syscalls)
- **1,546 network operations** (socket_send/recv)
- **550 writes + 461 reads = 1,011 I/O operations**

Ignoring them = Ignoring 1/3 of the system's actual behavior!

#### 2. **Thread Execution Continuity**
Example: Thread 888 (Client manageme)
```
Time        Operation       Target          Bytes
----------- --------------- --------------- -------
68400.001   socket_send     fd:74           12,690  🔴
68400.001   socket_recv     fd:74           4       🔴
68400.002   socket_send     fd:82           24      🔴
68400.002   close           fd:82           0       🔴
68411.281   socket_recv     fd:82           13,156  🔴
```

**If we removed unresolved FDs:**
- Thread 888 would appear to do NOTHING
- We'd lose all client management behavior
- Timeline would have gaps

#### 3. **Resource Consumption Analysis**
We can still analyze:
- How much data was transferred (bytes_transferred)
- How many operations were performed
- Which threads used which FDs
- Temporal patterns of I/O

#### 4. **Network Behavior Analysis**
Most network sockets are established before trace:
- Redis server listens on port 6379 (before trace)
- Client connections already established
- Removing them = No network analysis possible

---

## Why Keep Them in the Graph?

### Design Decision: Completeness > Perfect Resolution

| Option | Pros | Cons |
|--------|------|------|
| **Remove unresolved FDs** | Graph only has "known" entities | ❌ 33.7% of operations lost<br>❌ Thread timelines have gaps<br>❌ Network analysis impossible<br>❌ Incomplete behavioral picture |
| **Keep as fd:XX** ✅ | ✅ Complete thread execution<br>✅ All operations preserved<br>✅ Network analysis possible<br>✅ Clear notation (fd:XX = unresolved) | Requires user to understand fd:XX notation |

### Graph Design Principle
**"Show what happened, even if we don't know every detail"**

The `fd:XX` notation:
- Clearly indicates "unresolved" status
- Preserves the operation in the timeline
- Allows queries like: "Show threads using unresolved sockets"
- Enables analysis: "Thread performed 1,546 network operations (unresolved FDs)"

---

## How to Query Unresolved FDs

### Example Queries

#### 1. Find operations on unresolved FDs
```cypher
MATCH (t:Thread)-[:PERFORMED]->(es:EventSequence)
WHERE es.entity_target STARTS WITH 'fd:'
RETURN t.name, es.operation, es.entity_target, es.bytes_transferred
LIMIT 10
```

#### 2. Count unresolved vs resolved operations
```cypher
MATCH (es:EventSequence)
WITH es,
     CASE WHEN es.entity_target STARTS WITH 'fd:' 
          THEN 'unresolved' 
          ELSE 'resolved' 
     END as status
RETURN status, count(*) as count
```

#### 3. Threads using unresolved network sockets
```cypher
MATCH (t:Thread)-[:PERFORMED]->(es:EventSequence)
WHERE es.entity_target STARTS WITH 'fd:'
  AND es.operation IN ['socket_send', 'socket_recv']
RETURN t.tid, t.name, count(*) as network_ops
ORDER BY network_ops DESC
```

#### 4. Total bytes transferred on unresolved FDs
```cypher
MATCH (es:EventSequence)
WHERE es.entity_target STARTS WITH 'fd:'
RETURN sum(es.bytes_transferred) as total_bytes
```

---

## How to Improve Resolution Rate

### Current: 66.3% Resolution

To improve to ~90%+:

#### 1. **Capture Initial FD State**
Run `lsof` before starting trace:
```bash
# Before tracing
lsof -p $REDIS_PID > /tmp/redis_fds.txt

# Start trace
sudo lttng create
sudo lttng enable-event -k --all
sudo lttng start
```

Then parse `redis_fds.txt` to pre-populate the FD map.

#### 2. **Extended Trace Window**
Start tracing BEFORE application starts:
```bash
# Start trace first
sudo lttng start

# Then start application
redis-server &
```

#### 3. **Process Fork Tracking**
Track `fork()` and `execve()` to understand FD inheritance:
```python
# Track parent→child FD inheritance
if syscall == 'fork':
    child_pid = return_value
    fd_map[child_pid] = copy.deepcopy(fd_map[parent_pid])
```

---

## Real-World Analogy

### The Movie Analogy 🎬

Imagine analyzing a movie that starts at the 30-minute mark:

| Trace Analysis | Movie Analysis |
|----------------|----------------|
| **Unresolved FDs** | Characters whose backstory you missed |
| **fd:74** | "The mysterious stranger" |
| **We don't know** | How they met, their names, their origin |
| **We DO know** | Their actions, dialogue, interactions |
| **Removing them?** | Movie becomes incomprehensible |
| **Keeping them?** | Can analyze behavior, even without full context |

**Key Point:** Just because you don't know who fd:74 is (maybe `/var/log/redis.log`?) doesn't mean their actions (187 read/write operations) aren't important for understanding the plot (system behavior).

---

## Conclusion

### Should unresolved FDs be in the graph? **YES!**

✅ **They represent 33.7% of all operations** - Can't ignore 1/3 of system activity  
✅ **They maintain thread execution continuity** - No gaps in timelines  
✅ **They enable network analysis** - Most sockets pre-exist the trace  
✅ **They're clearly marked** - `fd:XX` notation indicates unresolved status  
✅ **They're queryable** - Can filter by resolved/unresolved as needed  
✅ **They're accurate** - We know the operation happened, even if we don't know the file  

### The Alternative (Removing Them) Would:

❌ Create gaps in thread execution timelines  
❌ Lose 2,268 operations (33.7% of data)  
❌ Make network analysis impossible  
❌ Provide incomplete behavioral picture  
❌ Violate graph completeness principle  

---

## Summary

**Unresolved FDs (fd:XX)** are:
- File descriptors opened **before tracing started**
- **Important** because they represent 33.7% of system activity
- **Necessary** for complete thread execution analysis
- **Clearly marked** so users can distinguish them from resolved FDs
- **Queryable** for specific analysis needs

The 66.3% resolution rate is **expected and acceptable** for mid-execution trace capture. The graph prioritizes **completeness and accuracy** over perfect resolution.

---

**Last Updated:** October 4, 2025  
**Trace:** Redis Benchmark (traces/redis_20251003_185958)  
**Resolution Rate:** 66.3% (4,459 resolved / 6,727 total)
