#!/usr/bin/env python3
"""
Universal LTTng Kernel Trace Schema
Property graph schema designed specifically for LTTng kernel traces from any application.
Supports hybrid model with both statistical aggregation and temporal event sequences.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Any
from enum import Enum
import json

class NodeType(Enum):
    """Universal node types for kernel trace analysis"""
    PROCESS = "Process"
    THREAD = "Thread"
    FILE = "File"
    SOCKET = "Socket"
    CPU = "CPU"
    MEMORY_REGION = "MemoryRegion"
    SYSCALL_EVENT = "SyscallEvent"
    SYSCALL_TYPE = "SyscallType"
    TIMER = "Timer"
    IRQ = "IRQ"

class RelationshipType(Enum):
    """Universal relationship types for kernel traces"""
    # Process/Thread relationships
    SPAWNED = "SPAWNED"
    CONTAINS = "CONTAINS"
    
    # Scheduling relationships
    SCHEDULED_ON = "SCHEDULED_ON"
    PREEMPTED_BY = "PREEMPTED_BY"
    WOKE_UP = "WOKE_UP"
    
    # Syscall execution
    EXECUTED = "EXECUTED"
    INSTANTIATED = "INSTANTIATED"
    
    # File operations
    OPENED = "OPENED"
    READ_FROM = "READ_FROM"
    WROTE_TO = "WROTE_TO"
    CLOSED = "CLOSED"
    
    # Network operations
    CONNECTED_TO = "CONNECTED_TO"
    SENT_TO = "SENT_TO"
    RECEIVED_FROM = "RECEIVED_FROM"
    
    # Memory operations
    ALLOCATED = "ALLOCATED"
    ACCESSED = "ACCESSED"
    FREED = "FREED"
    
    # Temporal relationships
    FOLLOWED_BY = "FOLLOWED_BY"
    CAUSED_BY = "CAUSED_BY"
    
    # Synchronization
    WAITED_ON = "WAITED_ON"
    SIGNALED = "SIGNALED"

@dataclass
class NodeSchema:
    """Schema definition for a node type"""
    node_type: NodeType
    description: str
    required_properties: Dict[str, str]  # property_name -> data_type
    optional_properties: Dict[str, str]
    indexes: List[str]  # Properties to index
    constraints: List[str]  # Unique constraints

@dataclass
class RelationshipSchema:
    """Schema definition for a relationship type"""
    rel_type: RelationshipType
    source_node: NodeType
    target_node: NodeType
    description: str
    required_properties: Dict[str, str]
    optional_properties: Dict[str, str]

class UniversalKernelTraceSchema:
    """Complete universal schema for LTTng kernel traces"""
    
    def __init__(self):
        self.nodes = self._define_node_schemas()
        self.relationships = self._define_relationship_schemas()
    
    def _define_node_schemas(self) -> Dict[NodeType, NodeSchema]:
        """Define all universal node schemas"""
        return {
            NodeType.PROCESS: NodeSchema(
                node_type=NodeType.PROCESS,
                description="Running process with complete lifecycle information",
                required_properties={
                    "pid": "integer",
                    "name": "string",
                    "start_time": "datetime",
                    "ppid": "integer"
                },
                optional_properties={
                    "end_time": "datetime",
                    "exit_code": "integer",
                    "command_line": "string",
                    "uid": "integer",
                    "gid": "integer",
                    "cpu_time_user": "integer",  # microseconds
                    "cpu_time_kernel": "integer",
                    "memory_peak": "integer",  # bytes
                    "thread_count": "integer",
                    "file_descriptors_max": "integer",
                    "priority": "integer",
                    "nice_value": "integer",
                    "working_directory": "string"
                },
                indexes=["pid", "name", "start_time", "ppid"],
                constraints=["pid"]
            ),
            
            NodeType.THREAD: NodeSchema(
                node_type=NodeType.THREAD,
                description="Thread execution context with scheduling details",
                required_properties={
                    "tid": "integer",
                    "pid": "integer",
                    "name": "string",
                    "start_time": "datetime"
                },
                optional_properties={
                    "end_time": "datetime",
                    "priority": "integer",
                    "nice_value": "integer",
                    "cpu_affinity": "string",  # CPU mask
                    "stack_size": "integer",
                    "cpu_time": "integer",  # microseconds
                    "context_switches": "integer",
                    "voluntary_switches": "integer",
                    "involuntary_switches": "integer",
                    "state": "string",  # RUNNING, SLEEPING, WAITING, etc.
                    "policy": "string"  # SCHED_NORMAL, SCHED_FIFO, etc.
                },
                indexes=["tid", "pid", "name", "start_time"],
                constraints=["tid", "pid"]
            ),
            
            NodeType.FILE: NodeSchema(
                node_type=NodeType.FILE,
                description="File system entity with detailed metadata",
                required_properties={
                    "path": "string",
                    "inode": "integer",
                    "device_id": "string"
                },
                optional_properties={
                    "file_type": "string",  # regular, directory, socket, pipe, etc.
                    "permissions": "string",
                    "size": "integer",
                    "owner_uid": "integer",
                    "owner_gid": "integer",
                    "access_time": "datetime",
                    "modify_time": "datetime",
                    "change_time": "datetime",
                    "link_count": "integer",
                    "block_size": "integer",
                    "blocks": "integer",
                    "flags": "string"
                },
                indexes=["path", "inode", "device_id"],
                constraints=["inode", "device_id"]
            ),
            
            NodeType.SOCKET: NodeSchema(
                node_type=NodeType.SOCKET,
                description="Network socket with connection details",
                required_properties={
                    "socket_id": "string",  # Unique identifier
                    "family": "string",  # AF_INET, AF_INET6, AF_UNIX
                    "type": "string",  # SOCK_STREAM, SOCK_DGRAM
                    "protocol": "string"  # TCP, UDP, etc.
                },
                optional_properties={
                    "local_address": "string",
                    "local_port": "integer",
                    "remote_address": "string",
                    "remote_port": "integer",
                    "state": "string",  # LISTEN, ESTABLISHED, CLOSED, etc.
                    "send_buffer_size": "integer",
                    "receive_buffer_size": "integer",
                    "bytes_sent": "integer",
                    "bytes_received": "integer",
                    "packets_sent": "integer",
                    "packets_received": "integer",
                    "connection_time": "datetime",
                    "close_time": "datetime"
                },
                indexes=["socket_id", "family", "local_address", "remote_address"],
                constraints=["socket_id"]
            ),
            
            NodeType.CPU: NodeSchema(
                node_type=NodeType.CPU,
                description="CPU core with performance metrics",
                required_properties={
                    "cpu_id": "integer",
                    "model": "string"
                },
                optional_properties={
                    "frequency": "integer",  # Hz
                    "cache_size_l1": "integer",
                    "cache_size_l2": "integer",
                    "cache_size_l3": "integer",
                    "utilization": "float",  # 0.0-1.0
                    "temperature": "float",
                    "power_consumption": "float",
                    "idle_time": "integer",  # microseconds
                    "user_time": "integer",
                    "system_time": "integer",
                    "iowait_time": "integer",
                    "irq_time": "integer",
                    "softirq_time": "integer"
                },
                indexes=["cpu_id"],
                constraints=["cpu_id"]
            ),
            
            NodeType.MEMORY_REGION: NodeSchema(
                node_type=NodeType.MEMORY_REGION,
                description="Memory allocation with detailed attributes",
                required_properties={
                    "start_address": "string",  # Hex address
                    "size": "integer",
                    "pid": "integer"
                },
                optional_properties={
                    "end_address": "string",
                    "permissions": "string",  # rwx
                    "region_type": "string",  # heap, stack, mmap, shared
                    "backing_file": "string",
                    "offset": "integer",
                    "flags": "string",
                    "allocation_time": "datetime",
                    "free_time": "datetime",
                    "access_count": "integer",
                    "page_faults": "integer",
                    "resident_pages": "integer",
                    "shared_pages": "integer"
                },
                indexes=["start_address", "pid", "region_type"],
                constraints=["start_address", "pid"]
            ),
            
            NodeType.SYSCALL_EVENT: NodeSchema(
                node_type=NodeType.SYSCALL_EVENT,
                description="Individual system call execution with full context",
                required_properties={
                    "event_id": "string",  # Unique event identifier
                    "syscall_name": "string",
                    "timestamp": "datetime",
                    "event_type": "string",  # entry, exit
                    "tid": "integer",
                    "cpu_id": "integer"
                },
                optional_properties={
                    "duration": "integer",  # microseconds (for paired entry/exit)
                    "return_value": "string",
                    "error_code": "string",
                    "parameters": "string",  # JSON encoded
                    "stack_trace": "string",
                    "instruction_pointer": "string",
                    "cpu_cycles": "integer",
                    "cache_misses": "integer",
                    "context_switches": "integer",
                    "preemption_count": "integer",
                    "priority": "integer",
                    "memory_usage": "integer"
                },
                indexes=["event_id", "syscall_name", "timestamp", "tid", "cpu_id"],
                constraints=["event_id"]
            ),
            
            NodeType.SYSCALL_TYPE: NodeSchema(
                node_type=NodeType.SYSCALL_TYPE,
                description="System call type with aggregated statistics",
                required_properties={
                    "name": "string",
                    "category": "string"  # file_io, network, memory, process, etc.
                },
                optional_properties={
                    "frequency": "integer",
                    "total_duration": "integer",  # microseconds
                    "avg_duration": "float",
                    "min_duration": "integer",
                    "max_duration": "integer",
                    "std_dev_duration": "float",
                    "success_rate": "float",  # 0.0-1.0
                    "error_rate": "float",
                    "cpu_cycles_avg": "integer",
                    "cache_miss_rate": "float",
                    "description": "string",
                    "signature": "string"  # Parameter types
                },
                indexes=["name", "category"],
                constraints=["name"]
            ),
            
            NodeType.TIMER: NodeSchema(
                node_type=NodeType.TIMER,
                description="Kernel timer with timing information",
                required_properties={
                    "timer_id": "string",
                    "function_name": "string",
                    "expires_at": "datetime"
                },
                optional_properties={
                    "created_at": "datetime",
                    "interval": "integer",  # microseconds
                    "flags": "string",
                    "cpu_id": "integer",
                    "callback_duration": "integer",
                    "jiffies": "integer",
                    "precision": "string"  # high_res, low_res
                },
                indexes=["timer_id", "function_name", "expires_at"],
                constraints=["timer_id"]
            ),
            
            NodeType.IRQ: NodeSchema(
                node_type=NodeType.IRQ,
                description="Interrupt request with handling details",
                required_properties={
                    "irq_number": "integer",
                    "timestamp": "datetime"
                },
                optional_properties={
                    "handler_name": "string",
                    "device_name": "string",
                    "cpu_id": "integer",
                    "duration": "integer",  # microseconds
                    "count": "integer",
                    "flags": "string",
                    "priority": "integer",
                    "nested_level": "integer"
                },
                indexes=["irq_number", "timestamp", "cpu_id"],
                constraints=[]  # IRQs can repeat
            )
        }
    
    def _define_relationship_schemas(self) -> Dict[RelationshipType, RelationshipSchema]:
        """Define all universal relationship schemas"""
        return {
            RelationshipType.SPAWNED: RelationshipSchema(
                rel_type=RelationshipType.SPAWNED,
                source_node=NodeType.PROCESS,
                target_node=NodeType.PROCESS,
                description="Parent process creates child process",
                required_properties={
                    "timestamp": "datetime",
                    "method": "string"  # fork, vfork, clone
                },
                optional_properties={
                    "clone_flags": "string",
                    "exit_signal": "integer",
                    "success": "boolean"
                }
            ),
            
            RelationshipType.CONTAINS: RelationshipSchema(
                rel_type=RelationshipType.CONTAINS,
                source_node=NodeType.PROCESS,
                target_node=NodeType.THREAD,
                description="Process contains thread",
                required_properties={
                    "creation_time": "datetime"
                },
                optional_properties={
                    "termination_time": "datetime",
                    "cpu_time_user": "integer",
                    "cpu_time_kernel": "integer"
                }
            ),
            
            RelationshipType.SCHEDULED_ON: RelationshipSchema(
                rel_type=RelationshipType.SCHEDULED_ON,
                source_node=NodeType.THREAD,
                target_node=NodeType.CPU,
                description="Thread scheduled to run on CPU",
                required_properties={
                    "timestamp": "datetime",
                    "duration": "integer"  # microseconds
                },
                optional_properties={
                    "priority": "integer",
                    "preempted": "boolean",
                    "voluntary": "boolean",
                    "prev_thread_tid": "integer",
                    "wait_time": "integer",  # time spent waiting
                    "cpu_utilization": "float"
                }
            ),
            
            RelationshipType.EXECUTED: RelationshipSchema(
                rel_type=RelationshipType.EXECUTED,
                source_node=NodeType.THREAD,
                target_node=NodeType.SYSCALL_EVENT,
                description="Thread executes system call",
                required_properties={
                    "timestamp": "datetime"
                },
                optional_properties={
                    "context_id": "string",
                    "stack_depth": "integer",
                    "cpu_id": "integer"
                }
            ),
            
            RelationshipType.INSTANTIATED: RelationshipSchema(
                rel_type=RelationshipType.INSTANTIATED,
                source_node=NodeType.SYSCALL_EVENT,
                target_node=NodeType.SYSCALL_TYPE,
                description="Syscall event is instance of syscall type",
                required_properties={
                    "timestamp": "datetime"
                },
                optional_properties={
                    "parameters_match": "boolean",
                    "duration_percentile": "float"
                }
            ),
            
            RelationshipType.OPENED: RelationshipSchema(
                rel_type=RelationshipType.OPENED,
                source_node=NodeType.SYSCALL_EVENT,
                target_node=NodeType.FILE,
                description="System call opens file",
                required_properties={
                    "timestamp": "datetime",
                    "flags": "string"
                },
                optional_properties={
                    "mode": "string",
                    "file_descriptor": "integer",
                    "success": "boolean",
                    "latency": "integer"  # microseconds
                }
            ),
            
            RelationshipType.READ_FROM: RelationshipSchema(
                rel_type=RelationshipType.READ_FROM,
                source_node=NodeType.SYSCALL_EVENT,
                target_node=NodeType.FILE,
                description="System call reads from file",
                required_properties={
                    "timestamp": "datetime",
                    "bytes_requested": "integer"
                },
                optional_properties={
                    "bytes_actual": "integer",
                    "offset": "integer",
                    "buffer_address": "string",
                    "latency": "integer",
                    "throughput": "float",  # bytes/second
                    "io_wait_time": "integer"
                }
            ),
            
            RelationshipType.WROTE_TO: RelationshipSchema(
                rel_type=RelationshipType.WROTE_TO,
                source_node=NodeType.SYSCALL_EVENT,
                target_node=NodeType.FILE,
                description="System call writes to file",
                required_properties={
                    "timestamp": "datetime",
                    "bytes_requested": "integer"
                },
                optional_properties={
                    "bytes_actual": "integer",
                    "offset": "integer",
                    "sync_type": "string",  # async, sync, direct
                    "latency": "integer",
                    "throughput": "float",
                    "fsync_required": "boolean"
                }
            ),
            
            RelationshipType.ALLOCATED: RelationshipSchema(
                rel_type=RelationshipType.ALLOCATED,
                source_node=NodeType.SYSCALL_EVENT,
                target_node=NodeType.MEMORY_REGION,
                description="System call allocates memory",
                required_properties={
                    "timestamp": "datetime",
                    "size": "integer"
                },
                optional_properties={
                    "address": "string",
                    "flags": "string",
                    "protection": "string",
                    "success": "boolean",
                    "latency": "integer"
                }
            ),
            
            RelationshipType.FOLLOWED_BY: RelationshipSchema(
                rel_type=RelationshipType.FOLLOWED_BY,
                source_node=NodeType.SYSCALL_EVENT,
                target_node=NodeType.SYSCALL_EVENT,
                description="Temporal sequence between events",
                required_properties={
                    "time_delta": "integer"  # microseconds
                },
                optional_properties={
                    "same_thread": "boolean",
                    "causal_relationship": "string",  # direct, indirect, unrelated
                    "context_switches": "integer"
                }
            ),
            
            RelationshipType.CAUSED_BY: RelationshipSchema(
                rel_type=RelationshipType.CAUSED_BY,
                source_node=NodeType.SYSCALL_EVENT,
                target_node=NodeType.SYSCALL_EVENT,
                description="Causal relationship between events",
                required_properties={
                    "timestamp": "datetime",
                    "causality_type": "string"  # direct, indirect, synchronization
                },
                optional_properties={
                    "confidence": "float",  # 0.0-1.0
                    "evidence": "string"
                }
            )
        }
    
    def generate_neo4j_schema(self) -> str:
        """Generate Neo4j schema creation script"""
        cypher_lines = [
            "// Universal LTTng Kernel Trace Schema",
            "// Generated schema for property graph analysis",
            "",
            "// Drop existing constraints and indexes",
            "CALL db.constraints() YIELD name",
            "CALL apoc.util.map(name, 'DROP CONSTRAINT ' + name + ' IF EXISTS') YIELD value",
            "CALL db.awaitIndexes()",
            "",
            "CALL db.indexes() YIELD name",
            "CALL apoc.util.map(name, 'DROP INDEX ' + name + ' IF EXISTS') YIELD value",
            "CALL db.awaitIndexes()",
            "",
            "// Create constraints for data integrity and performance"
        ]
        
        # Add constraints
        for node_type, schema in self.nodes.items():
            for constraint in schema.constraints:
                if len(schema.constraints) == 1:
                    cypher_lines.append(f"CREATE CONSTRAINT {node_type.value.lower()}_{constraint} IF NOT EXISTS FOR (n:{node_type.value}) REQUIRE n.{constraint} IS UNIQUE;")
                else:
                    props = ", ".join([f"n.{prop}" for prop in schema.constraints])
                    cypher_lines.append(f"CREATE CONSTRAINT {node_type.value.lower()}_composite IF NOT EXISTS FOR (n:{node_type.value}) REQUIRE ({props}) IS UNIQUE;")
        
        cypher_lines.extend([
            "",
            "// Create indexes for query performance"
        ])
        
        # Add indexes
        for node_type, schema in self.nodes.items():
            for index_prop in schema.indexes:
                if index_prop not in schema.constraints:  # Don't duplicate constraint indexes
                    cypher_lines.append(f"CREATE INDEX {node_type.value.lower()}_{index_prop} IF NOT EXISTS FOR (n:{node_type.value}) ON (n.{index_prop});")
        
        cypher_lines.extend([
            "",
            "// Wait for all indexes to come online",
            "CALL db.awaitIndexes();"
        ])
        
        return "\\n".join(cypher_lines)
    
    def get_node_schema(self, node_type: NodeType) -> NodeSchema:
        """Get schema for specific node type"""
        return self.nodes[node_type]
    
    def get_relationship_schema(self, rel_type: RelationshipType) -> RelationshipSchema:
        """Get schema for specific relationship type"""
        return self.relationships[rel_type]
    
    def export_schema(self, filename: str):
        """Export schema as JSON"""
        schema_data = {
            "version": "1.0",
            "description": "Universal LTTng Kernel Trace Schema",
            "nodes": {
                node_type.value: {
                    "description": schema.description,
                    "required_properties": schema.required_properties,
                    "optional_properties": schema.optional_properties,
                    "indexes": schema.indexes,
                    "constraints": schema.constraints
                } for node_type, schema in self.nodes.items()
            },
            "relationships": {
                rel_type.value: {
                    "source_node": schema.source_node.value,
                    "target_node": schema.target_node.value,
                    "description": schema.description,
                    "required_properties": schema.required_properties,
                    "optional_properties": schema.optional_properties
                } for rel_type, schema in self.relationships.items()
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(schema_data, f, indent=2)
        
        print(f"Schema exported to {filename}")

def main():
    """Generate the universal schema"""
    print("Universal LTTng Kernel Trace Schema Generator")
    print("=" * 60)
    
    schema = UniversalKernelTraceSchema()
    
    print(f"Schema created:")
    print(f"   - Node types: {len(schema.nodes)}")
    print(f"   - Relationship types: {len(schema.relationships)}")
    
    # Generate Neo4j schema
    neo4j_schema = schema.generate_neo4j_schema()
    with open('kernel_trace_schema.cypher', 'w') as f:
        f.write(neo4j_schema)
    
    # Export as JSON
    schema.export_schema('kernel_trace_schema.json')
    
    print(f"\nGenerated files:")
    print(f"   - kernel_trace_schema.cypher: Neo4j schema creation")
    print(f"   - kernel_trace_schema.json: Schema definition")
    
    print(f"\nSchema Summary:")
    print(f"   Node Types:")
    for node_type in schema.nodes:
        print(f"     - {node_type.value}: {schema.nodes[node_type].description}")
    
    print(f"\n   Relationship Types:")
    for rel_type in list(schema.relationships.keys())[:5]:  # Show first 5
        rel_schema = schema.relationships[rel_type]
        print(f"     - {rel_type.value}: {rel_schema.source_node.value} → {rel_schema.target_node.value}")
    print(f"     ... and {len(schema.relationships)-5} more")

if __name__ == "__main__":
    main()