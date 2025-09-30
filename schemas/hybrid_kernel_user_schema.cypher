
// ============================================================================
// HYBRID TWO-TIERED KERNEL/USER TRACE SCHEMA
// ============================================================================
// Optimized for both speed (entity relationships) and depth (temporal story)
// Works with kernel syscalls, user space events, and mixed traces
// ============================================================================

// ============================================================================
// CORE ENTITY NODES (Tier 1: Fast Lookups)
// ============================================================================

// Process Node - Represents running processes
CREATE CONSTRAINT process_pid IF NOT EXISTS FOR (n:Process) REQUIRE n.pid IS UNIQUE;
CREATE INDEX process_name IF NOT EXISTS FOR (n:Process) ON (n.name);
CREATE INDEX process_start_time IF NOT EXISTS FOR (n:Process) ON (n.start_time);
CREATE INDEX process_ppid IF NOT EXISTS FOR (n:Process) ON (n.ppid);
CREATE INDEX process_user IF NOT EXISTS FOR (n:Process) ON (n.uid);

// Thread Node - Represents execution threads
CREATE CONSTRAINT thread_composite IF NOT EXISTS FOR (n:Thread) REQUIRE (n.tid, n.pid) IS UNIQUE;
CREATE INDEX thread_name IF NOT EXISTS FOR (n:Thread) ON (n.name);
CREATE INDEX thread_start_time IF NOT EXISTS FOR (n:Thread) ON (n.start_time);

// File Node - Represents file system entities
CREATE CONSTRAINT file_path IF NOT EXISTS FOR (n:File) REQUIRE n.path IS UNIQUE;
CREATE INDEX file_type IF NOT EXISTS FOR (n:File) ON (n.file_type);
CREATE INDEX file_size IF NOT EXISTS FOR (n:File) ON (n.size);
CREATE INDEX file_owner IF NOT EXISTS FOR (n:File) ON (n.owner_uid);

// Socket Node - Represents network endpoints
CREATE CONSTRAINT socket_id IF NOT EXISTS FOR (n:Socket) REQUIRE n.socket_id IS UNIQUE;
CREATE INDEX socket_family IF NOT EXISTS FOR (n:Socket) ON (n.family);
CREATE INDEX socket_local_addr IF NOT EXISTS FOR (n:Socket) ON (n.local_address);
CREATE INDEX socket_remote_addr IF NOT EXISTS FOR (n:Socket) ON (n.remote_address);
CREATE INDEX socket_port IF NOT EXISTS FOR (n:Socket) ON (n.port);

// CPU Node - Represents processing cores
CREATE CONSTRAINT cpu_id IF NOT EXISTS FOR (n:CPU) REQUIRE n.cpu_id IS UNIQUE;
CREATE INDEX cpu_core IF NOT EXISTS FOR (n:CPU) ON (n.core);
CREATE INDEX cpu_package IF NOT EXISTS FOR (n:CPU) ON (n.package);

// Memory Region Node - Represents memory mappings
CREATE CONSTRAINT memory_region_composite IF NOT EXISTS FOR (n:MemoryRegion) REQUIRE (n.start_address, n.pid) IS UNIQUE;
CREATE INDEX memory_region_type IF NOT EXISTS FOR (n:MemoryRegion) ON (n.region_type);
CREATE INDEX memory_region_size IF NOT EXISTS FOR (n:MemoryRegion) ON (n.size);

// ============================================================================
// TIER 1: DIRECT SUMMARY RELATIONSHIPS (For Speed)
// ============================================================================
// These relationships directly connect entities with rich event properties
// Optimized for fast "who did what to whom" queries

// File System Operations
// Process -> File relationships with complete I/O story
CREATE INDEX rel_read_timestamp IF NOT EXISTS FOR ()-[r:READ_FROM]-() ON (r.timestamp);
CREATE INDEX rel_write_timestamp IF NOT EXISTS FOR ()-[r:WROTE_TO]-() ON (r.timestamp);
CREATE INDEX rel_access_timestamp IF NOT EXISTS FOR ()-[r:ACCESSED]-() ON (r.timestamp);

// Process Lifecycle
CREATE INDEX rel_forked_timestamp IF NOT EXISTS FOR ()-[r:FORKED]-() ON (r.timestamp);
CREATE INDEX rel_exec_timestamp IF NOT EXISTS FOR ()-[r:EXECUTED]-() ON (r.timestamp);

// Network Operations  
CREATE INDEX rel_sent_timestamp IF NOT EXISTS FOR ()-[r:SENT_TO]-() ON (r.timestamp);
CREATE INDEX rel_received_timestamp IF NOT EXISTS FOR ()-[r:RECEIVED_FROM]-() ON (r.timestamp);
CREATE INDEX rel_connected_timestamp IF NOT EXISTS FOR ()-[r:CONNECTED_TO]-() ON (r.timestamp);

// CPU Scheduling
CREATE INDEX rel_scheduled_timestamp IF NOT EXISTS FOR ()-[r:SCHEDULED_ON]-() ON (r.timestamp);
CREATE INDEX rel_preempted_timestamp IF NOT EXISTS FOR ()-[r:PREEMPTED_FROM]-() ON (r.timestamp);

// Memory Operations
CREATE INDEX rel_allocated_timestamp IF NOT EXISTS FOR ()-[r:ALLOCATED]-() ON (r.timestamp);
CREATE INDEX rel_mapped_timestamp IF NOT EXISTS FOR ()-[r:MAPPED]-() ON (r.timestamp);

// Synchronization (both kernel and user space)
CREATE INDEX rel_locked_timestamp IF NOT EXISTS FOR ()-[r:LOCKED]-() ON (r.timestamp);
CREATE INDEX rel_unlocked_timestamp IF NOT EXISTS FOR ()-[r:UNLOCKED]-() ON (r.timestamp);
CREATE INDEX rel_signaled_timestamp IF NOT EXISTS FOR ()-[r:SIGNALED]-() ON (r.timestamp);

// ============================================================================
// TIER 2: TEMPORAL STORY PRESERVATION
// ============================================================================
// All relationships include rich properties that preserve the complete story
// Properties are indexed by timestamp for chronological reconstruction

// Common temporal properties for ALL relationships:
// - timestamp: precise event time (microsecond resolution)
// - duration: operation duration (for performance analysis) 
// - sequence_id: global ordering for exact causality
// - cpu_id: which CPU executed this event
// - context: kernel/user space context
// - success: whether operation succeeded
// - error_code: failure reason if applicable

// File Operation Properties:
// READ_FROM/WROTE_TO: {timestamp, duration, bytes, offset, flags, mode, fd}
// ACCESSED: {timestamp, duration, access_type, flags, mode}

// Process Properties:
// FORKED: {timestamp, child_pid, child_tid, flags}
// EXECUTED: {timestamp, program_path, argv, envp}

// Network Properties:  
// SENT_TO/RECEIVED_FROM: {timestamp, bytes, protocol, local_port, remote_port}
// CONNECTED_TO: {timestamp, protocol, connection_id, flags}

// CPU Properties:
// SCHEDULED_ON: {timestamp, priority, nice_value, time_slice}
// PREEMPTED_FROM: {timestamp, reason, next_pid, next_tid}

// Memory Properties:
// ALLOCATED/MAPPED: {timestamp, size, address, flags, protection}

// ============================================================================
// HYBRID QUERYING PATTERNS
// ============================================================================

// Pattern 1: Fast Overview Queries (Use Direct Relationships)
// "Which processes wrote to /var/log/syslog?"
// MATCH (p:Process)-[:WROTE_TO]->(f:File {path: '/var/log/syslog'}) RETURN p

// Pattern 2: Performance Analysis (Use Relationship Properties)  
// "Which file operations took longer than 100ms?"
// MATCH (p:Process)-[r:READ_FROM|WROTE_TO]-(f:File) 
// WHERE r.duration > 0.1 RETURN p, r, f ORDER BY r.duration DESC

// Pattern 3: Temporal Story Reconstruction (Order by Timestamp)
// "What did process 1234 do in chronological order?"
// MATCH (p:Process {pid: 1234})-[r]->(target)
// RETURN p.name, type(r) as event, target, r.timestamp, r.duration
// ORDER BY r.timestamp

// Pattern 4: Causal Analysis (Find Events Before/After)
// "What happened just before the crash at time T?"
// MATCH (p:Process)-[r]->(target) 
// WHERE r.timestamp BETWEEN (T-5.0) AND T
// RETURN p, r, target ORDER BY r.timestamp DESC

// Pattern 5: Cross-Entity Correlation (Multi-hop relationships)
// "Which processes accessed files that process X was writing to?"
// MATCH (px:Process {pid: X})-[:WROTE_TO]->(f:File)<-[:READ_FROM]-(py:Process)
// WHERE py.pid <> X RETURN py, f

// ============================================================================
// KERNEL vs USER SPACE HANDLING
// ============================================================================

// Context differentiation through relationship properties:
// - context: 'kernel' | 'user' | 'transition'
// - syscall_name: specific system call (for kernel events)
// - function_name: user space function (for user events)  
// - call_stack: stack trace (for debugging)

// Example kernel space READ_FROM:
// (Process)-[:READ_FROM {context: 'kernel', syscall_name: 'read', fd: 3, 
//                       timestamp: 12345.678, bytes: 1024, duration: 0.001}]->(File)

// Example user space READ_FROM:
// (Process)-[:READ_FROM {context: 'user', function_name: 'fread', 
//                       timestamp: 12345.679, bytes: 1024, duration: 0.002}]->(File)

// ============================================================================
// PERFORMANCE OPTIMIZATIONS
// ============================================================================

// 1. Entity-centric indexing (fast entity lookups)
// 2. Timestamp indexing on ALL relationships (fast temporal queries)
// 3. Composite indexes for common query patterns
// 4. No separate event nodes (relationships ARE the events)
// 5. Rich properties eliminate need for multiple hops

