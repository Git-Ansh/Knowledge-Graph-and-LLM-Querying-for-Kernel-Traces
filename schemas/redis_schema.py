#!/usr/bin/env python3
"""
Redis Schema - Specialized Schema for Redis Server Tracing
=========================================================

This schema defines Redis-specific entities and relationships for kernel trace analysis.
Designed for comprehensive Redis server monitoring and performance analysis.

Redis Architecture Components:
- Redis Server Process & Worker Threads
- Client Connections & Sessions  
- Redis Commands & Operations
- Memory Allocation & Data Structures
- Persistence & Replication
- Network I/O & Protocol Analysis
- Configuration & Key Management

Schema Coverage:
 Core Redis Operations (GET, SET, HGET, LPUSH, etc.)
 Client Connection Management  
 Memory & Persistence Patterns
 Network Protocol Analysis
 Multi-threading & Event Loop
 Configuration File Access
 Logging & Monitoring
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class RedisEntity:
    """Redis-specific entity definition"""
    name: str
    description: str
    properties: List[str]
    indices: List[str] = None

@dataclass
class RedisRelationship:
    """Redis-specific relationship definition"""
    name: str
    source_entity: str
    target_entity: str
    description: str
    properties: List[str] = None
    temporal: bool = True

# Redis Entity Definitions
REDIS_ENTITIES = [
    RedisEntity(
        name="RedisServer",
        description="Redis server process instance",
        properties=[
            "pid", "server_name", "version", "port", "config_file",
            "start_time", "memory_usage", "cpu_usage", "uptime"
        ],
        indices=["pid", "port"]
    ),
    
    RedisEntity(
        name="RedisClient", 
        description="Client connection to Redis server",
        properties=[
            "client_id", "connection_id", "client_addr", "client_port",
            "connect_time", "last_cmd_time", "idle_time", "protocol_version"
        ],
        indices=["client_id", "connection_id"]
    ),
    
    RedisEntity(
        name="RedisCommand",
        description="Redis command execution instance", 
        properties=[
            "command_id", "command_type", "command_args", "execution_time",
            "response_size", "key_accessed", "operation_type", "success"
        ],
        indices=["command_id", "command_type", "key_accessed"]
    ),
    
    RedisEntity(
        name="RedisKey",
        description="Redis data key and associated metadata",
        properties=[
            "key_name", "key_type", "ttl", "memory_size", "encoding",
            "created_time", "last_accessed", "access_count", "value_hash"
        ],
        indices=["key_name", "key_type"]
    ),
    
    RedisEntity(
        name="RedisDatabase", 
        description="Redis logical database (0-15)",
        properties=[
            "database_id", "key_count", "expires_count", "memory_usage",
            "last_save_time", "dirty_keys"
        ],
        indices=["database_id"]
    ),
    
    RedisEntity(
        name="RedisMemory",
        description="Memory allocation and usage tracking",
        properties=[
            "allocation_id", "size", "memory_type", "fragmentation",
            "peak_memory", "used_memory", "overhead"
        ],
        indices=["allocation_id", "memory_type"]
    ),
    
    RedisEntity(
        name="RedisPersistence",
        description="Persistence operations (RDB, AOF)",
        properties=[
            "persistence_id", "persistence_type", "file_path", "size",
            "start_time", "duration", "keys_saved", "success"
        ],
        indices=["persistence_id", "persistence_type"]
    ),
    
    RedisEntity(
        name="RedisReplication",
        description="Master-slave replication activities", 
        properties=[
            "replication_id", "role", "master_host", "master_port",
            "replication_offset", "lag", "connected_slaves"
        ],
        indices=["replication_id", "role"]
    ),
    
    RedisEntity(
        name="RedisModule",
        description="Redis modules and extensions",
        properties=[
            "module_name", "module_version", "loaded_time", "commands_added",
            "memory_usage", "status"
        ],
        indices=["module_name"]
    ),
    
    RedisEntity(
        name="RedisThread",
        description="Redis worker threads and async operations",
        properties=[
            "thread_id", "thread_type", "cpu_affinity", "task_queue_size",
            "processed_operations", "current_task"
        ],
        indices=["thread_id", "thread_type"]
    ),
    
    # Include core system entities for correlation
    RedisEntity(
        name="Process",
        description="System process (includes Redis processes)",
        properties=[
            "pid", "name", "command_line", "start_time", "cpu_time", 
            "memory_usage", "state", "parent_pid"
        ],
        indices=["pid", "name"]
    ),
    
    RedisEntity(
        name="Thread",
        description="System thread (includes Redis threads)",
        properties=[
            "tid", "pid", "name", "state", "cpu_usage", "priority"
        ],
        indices=["tid", "pid"]
    ),
    
    RedisEntity(
        name="File",
        description="File system objects accessed by Redis",
        properties=[
            "file_path", "file_type", "size", "permissions", "modified_time",
            "access_pattern", "redis_usage"
        ],
        indices=["file_path", "file_type"]
    ),
    
    RedisEntity(
        name="Socket",
        description="Network sockets for Redis connections",
        properties=[
            "socket_id", "family", "type", "local_addr", "remote_addr",
            "state", "bytes_sent", "bytes_received"
        ],
        indices=["socket_id", "local_addr"]
    ),
    
    RedisEntity(
        name="CPU", 
        description="CPU cores executing Redis operations",
        properties=[
            "cpu_id", "usage_percent", "frequency", "cache_misses"
        ],
        indices=["cpu_id"]
    )
]

# Redis Relationship Definitions  
REDIS_RELATIONSHIPS = [
    # Core Redis Operations
    RedisRelationship(
        name="EXECUTES_COMMAND",
        source_entity="RedisClient", 
        target_entity="RedisCommand",
        description="Client executes a Redis command",
        properties=["execution_time", "response_time", "queue_time"]
    ),
    
    RedisRelationship(
        name="ACCESSES_KEY", 
        source_entity="RedisCommand",
        target_entity="RedisKey", 
        description="Command accesses a Redis key",
        properties=["access_type", "key_operation", "value_changed"]
    ),
    
    RedisRelationship(
        name="USES_DATABASE",
        source_entity="RedisCommand",
        target_entity="RedisDatabase",
        description="Command operates on specific database",
        properties=["database_id", "operation_type"]
    ),
    
    RedisRelationship(
        name="STORES_IN_DATABASE", 
        source_entity="RedisKey",
        target_entity="RedisDatabase",
        description="Key is stored in Redis database",
        properties=["database_id", "ttl", "memory_usage"]
    ),
    
    # Connection Management
    RedisRelationship(
        name="CONNECTED_TO",
        source_entity="RedisClient",
        target_entity="RedisServer", 
        description="Client maintains connection to Redis server",
        properties=["connection_time", "last_activity", "connection_state"]
    ),
    
    RedisRelationship(
        name="SERVES_CLIENT",
        source_entity="RedisServer", 
        target_entity="RedisClient",
        description="Server serves client requests",
        properties=["total_commands", "total_bytes", "connection_duration"]
    ),
    
    # Memory Management
    RedisRelationship(
        name="ALLOCATES_MEMORY",
        source_entity="RedisServer",
        target_entity="RedisMemory", 
        description="Server allocates memory for operations",
        properties=["allocation_size", "memory_type", "fragmentation"]
    ),
    
    RedisRelationship(
        name="USES_MEMORY",
        source_entity="RedisKey",
        target_entity="RedisMemory",
        description="Key uses allocated memory",
        properties=["memory_size", "encoding", "overhead"]
    ),
    
    # Persistence Operations
    RedisRelationship(
        name="PERSISTS_TO",
        source_entity="RedisServer",
        target_entity="RedisPersistence", 
        description="Server persists data to storage",
        properties=["persistence_type", "trigger_reason", "keys_saved"]
    ),
    
    RedisRelationship(
        name="WRITES_TO_AOF",
        source_entity="RedisCommand", 
        target_entity="RedisPersistence",
        description="Command is logged to AOF file", 
        properties=["aof_offset", "sync_policy"]
    ),
    
    # Replication
    RedisRelationship(
        name="REPLICATES_TO", 
        source_entity="RedisServer",
        target_entity="RedisReplication",
        description="Master replicates to slave",
        properties=["replication_offset", "sync_type", "lag"]
    ),
    
    RedisRelationship(
        name="RECEIVES_FROM",
        source_entity="RedisReplication",
        target_entity="RedisServer", 
        description="Slave receives data from master",
        properties=["received_offset", "apply_time"]
    ),
    
    # Module System
    RedisRelationship(
        name="LOADS_MODULE",
        source_entity="RedisServer",
        target_entity="RedisModule",
        description="Server loads Redis module",
        properties=["load_time", "init_status", "config_params"]
    ),
    
    RedisRelationship(
        name="PROVIDES_COMMAND", 
        source_entity="RedisModule",
        target_entity="RedisCommand",
        description="Module provides custom command", 
        properties=["command_name", "arity", "flags"]
    ),
    
    # Thread Management
    RedisRelationship(
        name="SPAWNS_THREAD",
        source_entity="RedisServer",
        target_entity="RedisThread",
        description="Server spawns worker thread",
        properties=["thread_purpose", "cpu_affinity"]
    ),
    
    RedisRelationship(
        name="PROCESSES_ON",
        source_entity="RedisCommand", 
        target_entity="RedisThread",
        description="Command processed by thread",
        properties=["processing_time", "queue_wait"]
    ),
    
    # System Integration (File I/O)
    RedisRelationship(
        name="READ_FROM",
        source_entity="Process",
        target_entity="File",
        description="Process reads from file",
        properties=["bytes_read", "read_time", "file_offset"]
    ),
    
    RedisRelationship(
        name="WROTE_TO", 
        source_entity="Process",
        target_entity="File",
        description="Process writes to file", 
        properties=["bytes_written", "write_time", "sync_type"]
    ),
    
    RedisRelationship(
        name="OPENED",
        source_entity="Process", 
        target_entity="File",
        description="Process opens file",
        properties=["open_flags", "file_mode", "open_time"]
    ),
    
    RedisRelationship(
        name="CLOSED",
        source_entity="Process",
        target_entity="File", 
        description="Process closes file",
        properties=["close_time", "final_size"]
    ),
    
    RedisRelationship(
        name="ACCESSED",
        source_entity="Process",
        target_entity="File",
        description="Process accesses file metadata", 
        properties=["access_type", "permissions_checked"]
    ),
    
    # Network I/O
    RedisRelationship(
        name="SENT_TO",
        source_entity="Process",
        target_entity="Socket",
        description="Process sends data through socket",
        properties=["bytes_sent", "send_time", "protocol"]
    ),
    
    RedisRelationship(
        name="RECEIVED_FROM",
        source_entity="Process", 
        target_entity="Socket",
        description="Process receives data from socket",
        properties=["bytes_received", "receive_time", "protocol"]
    ),
    
    # Process Lifecycle
    RedisRelationship(
        name="FORKED",
        source_entity="Process",
        target_entity="Process", 
        description="Process forks child process",
        properties=["fork_time", "fork_reason"]
    ),
    
    # CPU Scheduling
    RedisRelationship(
        name="SCHEDULED_ON",
        source_entity="Process",
        target_entity="CPU",
        description="Process scheduled on CPU", 
        properties=["schedule_time", "time_slice", "priority"]
    ),
    
    RedisRelationship(
        name="PREEMPTED_FROM", 
        source_entity="Process",
        target_entity="CPU",
        description="Process preempted from CPU",
        properties=["preempt_time", "preempt_reason", "runtime"]
    )
]

# Redis Schema Configuration
REDIS_SCHEMA = {
    "name": "Redis Schema",
    "version": "1.0.0", 
    "description": "Comprehensive schema for Redis server trace analysis",
    "modules": ["redis-core", "redis-persistence", "redis-replication", "redis-modules"],
    "entities": REDIS_ENTITIES,
    "relationships": REDIS_RELATIONSHIPS,
    "detection_patterns": {
        # Process name patterns that indicate Redis
        "process_names": [
            "redis-server", "redis", "redis-sentinel", "redis-cli"
        ],
        
        # File patterns associated with Redis
        "file_patterns": [ 
            r".*\.rdb$",           # RDB files
            r".*\.aof$",           # AOF files  
            r"redis\.conf$",       # Config files
            r"redis.*\.log$",      # Log files
            r"/var/lib/redis/.*",  # Data directory
            r"/etc/redis/.*",      # Config directory
        ],
        
        # Network patterns for Redis protocol
        "network_patterns": [
            r".*:6379.*",          # Default Redis port
            r".*:16379.*",         # Cluster bus port
            r".*:26379.*",         # Sentinel port
        ],
        
        # Command patterns in trace logs
        "command_patterns": [
            r"redis-server",
            r"RESP protocol",
            r"Redis .*",
            r"COMMAND .*",
            r"CLIENT .*"
        ]
    },
    
    "performance_metrics": [
        "command_throughput",     # Commands per second
        "memory_efficiency",      # Memory usage vs data size
        "persistence_latency",    # RDB/AOF write performance  
        "replication_lag",        # Master-slave sync delay
        "connection_overhead",    # Network connection costs
        "cpu_utilization",        # CPU usage patterns
        "cache_hit_ratio",        # Key access efficiency
    ],
    
    "optimization_hints": {
        "high_memory_usage": "Consider key expiration policies and memory optimization",
        "slow_persistence": "Tune RDB/AOF settings for better I/O performance",
        "replication_lag": "Check network bandwidth and master load",
        "cpu_bottleneck": "Consider Redis clustering or optimization",
        "connection_flooding": "Implement connection pooling and limits"
    }
}

def get_redis_schema() -> Dict[str, Any]:
    """Get the complete Redis schema configuration"""
    return REDIS_SCHEMA

def is_redis_trace(trace_file_path: str) -> bool:
    """
    Detect if trace file contains Redis-related activity
    
    Args:
        trace_file_path: Path to LTTng trace file
        
    Returns:
        True if Redis activity detected, False otherwise
    """
    redis_indicators = 0
    total_lines_checked = 0
    max_lines_to_check = 10000  # Check first 10k lines for performance
    
    try:
        with open(trace_file_path, 'r') as f:
            for line in f:
                total_lines_checked += 1
                if total_lines_checked > max_lines_to_check:
                    break
                
                line_lower = line.lower()
                
                # Check for Redis process names
                if any(name in line_lower for name in REDIS_SCHEMA['detection_patterns']['process_names']):
                    redis_indicators += 5
                
                # Check for Redis file patterns
                import re
                for pattern in REDIS_SCHEMA['detection_patterns']['file_patterns']:
                    if re.search(pattern, line, re.IGNORECASE):
                        redis_indicators += 3
                
                # Check for Redis network patterns
                for pattern in REDIS_SCHEMA['detection_patterns']['network_patterns']:
                    if re.search(pattern, line, re.IGNORECASE):
                        redis_indicators += 2
                
                # Check for Redis command patterns
                for pattern in REDIS_SCHEMA['detection_patterns']['command_patterns']:
                    if re.search(pattern, line, re.IGNORECASE):
                        redis_indicators += 1
                
                # Early termination if strong indicators found
                if redis_indicators >= 10:
                    return True
    
    except Exception as e:
        print(f"Warning: Could not analyze trace file {trace_file_path}: {e}")
        return False
    
    # Determine Redis likelihood based on indicators
    confidence_score = redis_indicators / max(total_lines_checked / 100, 1)
    return confidence_score >= 0.5  # 50% confidence threshold

def get_redis_entities_by_type() -> Dict[str, RedisEntity]:
    """Get Redis entities indexed by type name"""
    return {entity.name: entity for entity in REDIS_ENTITIES}

def get_redis_relationships_by_type() -> Dict[str, RedisRelationship]:
    """Get Redis relationships indexed by type name"""
    return {rel.name: rel for rel in REDIS_RELATIONSHIPS}

def validate_redis_schema() -> bool:
    """Validate Redis schema consistency"""
    
    entity_names = {entity.name for entity in REDIS_ENTITIES}
    
    # Check that all relationship endpoints reference valid entities
    for rel in REDIS_RELATIONSHIPS:
        if rel.source_entity not in entity_names:
            print(f"Error: Relationship {rel.name} references unknown source entity: {rel.source_entity}")
            return False
        if rel.target_entity not in entity_names:
            print(f"Error: Relationship {rel.name} references unknown target entity: {rel.target_entity}")
            return False
    
    # Check for relationship naming consistency
    relationship_names = [rel.name for rel in REDIS_RELATIONSHIPS]
    if len(set(relationship_names)) != len(relationship_names):
        print("Error: Duplicate relationship names found")
        return False
    
    print(f" Redis schema validation passed:")
    print(f"    {len(REDIS_ENTITIES)} entities defined")
    print(f"    {len(REDIS_RELATIONSHIPS)} relationships defined")
    print(f"    All relationship endpoints valid")
    
    return True

if __name__ == "__main__":
    # Schema validation and testing
    print(" REDIS SCHEMA VALIDATION")
    print("=" * 50)
    
    if validate_redis_schema():
        print("\n REDIS SCHEMA SUMMARY")
        print(f"   Schema: {REDIS_SCHEMA['name']} v{REDIS_SCHEMA['version']}")
        print(f"   Entities: {len(REDIS_ENTITIES)}")
        print(f"   Relationships: {len(REDIS_RELATIONSHIPS)}")
        print(f"   Modules: {', '.join(REDIS_SCHEMA['modules'])}")
        
        # Show entity breakdown
        entity_counts = {}
        for entity in REDIS_ENTITIES:
            category = "Redis" if entity.name.startswith("Redis") else "System"
            entity_counts[category] = entity_counts.get(category, 0) + 1
        
        print(f"\n Entity Categories:")
        for category, count in entity_counts.items():
            print(f"   {category}: {count} entities")
        
        # Show relationship breakdown
        rel_types = {}
        for rel in REDIS_RELATIONSHIPS:
            if rel.name.startswith(("EXECUTES", "ACCESSES", "USES", "STORES")):
                category = "Redis Operations"
            elif rel.name.startswith(("CONNECTED", "SERVES")):
                category = "Connection Management" 
            elif rel.name.startswith(("ALLOCATES", "USES_MEMORY")):
                category = "Memory Management"
            elif rel.name.startswith(("PERSISTS", "WRITES", "REPLICATES", "RECEIVES")):
                category = "Persistence & Replication"
            elif rel.name.startswith(("READ", "WROTE", "OPENED", "CLOSED", "ACCESSED")):
                category = "File I/O"
            elif rel.name.startswith(("SENT", "RECEIVED")):
                category = "Network I/O"
            else:
                category = "System Operations"
            
            rel_types[category] = rel_types.get(category, 0) + 1
        
        print(f"\n Relationship Categories:")
        for category, count in sorted(rel_types.items()):
            print(f"   {category}: {count} relationships")
        
        print(f"\n Redis schema ready for universal processor integration!")
    
    else:
        print("\n Redis schema validation failed!")
        exit(1)
