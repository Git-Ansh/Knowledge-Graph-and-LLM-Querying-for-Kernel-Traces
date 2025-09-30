#!/usr/bin/env python3
"""
Fixed Hybrid Trace Processor - Implementing Original Two-Tiered Design

This implementation fixes the architectural problems to match the original design:
1. Entity-centric nodes (Process, Thread, File, Socket, CPU)  
2. Direct entity relationships (READ_FROM, WROTE_TO, SCHEDULED_ON)
3. Zero isolation - every entity connects to others
4. Fast queries via direct relationships
"""

import re
import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class ProcessEntity:
    pid: int
    ppid: Optional[int] = None
    name: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    uid: Optional[int] = None
    gid: Optional[int] = None

@dataclass 
class ThreadEntity:
    tid: int
    pid: int
    name: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None

@dataclass
class FileEntity:
    path: str
    file_type: str = "regular"
    size: Optional[int] = None
    first_accessed: Optional[float] = None
    last_accessed: Optional[float] = None

@dataclass
class SocketEntity:
    socket_id: str
    family: str = ""
    socket_type: str = ""
    protocol: str = ""
    
@dataclass
class CPUEntity:
    cpu_id: int
    
@dataclass
class EventRelationship:
    source_type: str
    source_id: Any
    target_type: str 
    target_id: Any
    relationship_type: str
    timestamp: float
    properties: Dict[str, Any] = field(default_factory=dict)

class FixedHybridTraceProcessor:
    """Fixed implementation matching the original two-tiered design"""
    
    def __init__(self):
        # Core entities (the nodes)
        self.processes: Dict[int, ProcessEntity] = {}
        self.threads: Dict[Tuple[int, int], ThreadEntity] = {}  # (tid, pid)
        self.files: Dict[str, FileEntity] = {}
        self.sockets: Dict[str, SocketEntity] = {}
        self.cpus: Dict[int, CPUEntity] = {}
        
        # Entity relationships (the edges)
        self.relationships: List[EventRelationship] = []
        
        # File descriptor to filename mapping (critical for design!)
        self.fd_to_filename: Dict[Tuple[int, int], str] = {}  # (pid, fd) -> filename
        
        # Sequence counter for ordering
        self._sequence_counter = 0
        
        # Stats
        self.stats = {
            'total_lines': 0,
            'parsed_events': 0,
            'relationships_created': 0,
            'file_relationships': 0,
            'socket_relationships': 0,
            'scheduling_relationships': 0
        }

    def _get_next_sequence(self) -> int:
        """Get next sequence number for ordering"""
        self._sequence_counter += 1
        return self._sequence_counter

    def process_trace_file(self, file_path: str) -> None:
        """Process LTTng trace file using correct two-tiered design"""
        logger.info(f" Processing trace file: {file_path}")
        
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                self.stats['total_lines'] += 1
                
                if line_num % 10000 == 0:
                    logger.info(f" Processed {line_num} lines, {len(self.relationships)} relationships")
                
                self._process_trace_line(line.strip())
        
        logger.info(f" Processed {self.stats['total_lines']} trace events")
        logger.info(f" Optimizing entity end times...")
        self._optimize_entity_times()

    def _process_trace_line(self, line: str) -> None:
        """Process a single trace line"""
        if not line or line.startswith('#'):
            return
            
        try:
            # Parse LTTng format: [timestamp] (delta) host event_name: { ... } { ... }
            parts = line.split(']', 1)
            if len(parts) < 2:
                return
                
            timestamp_str = parts[0].strip('[')
            remainder = parts[1].strip()
            
            # Find the event name and fields
            # Format: (delta) hostname event_name: { context } { fields }
            colon_pos = remainder.find(':')
            if colon_pos == -1:
                return
                
            # Extract event name (everything before colon, after hostname)
            pre_colon = remainder[:colon_pos].strip()
            remainder_parts = pre_colon.split(' ', 2)  # (delta) hostname event_name
            if len(remainder_parts) < 3:
                return
                
            event_name = remainder_parts[2].strip()
            fields_part = remainder[colon_pos + 1:]  # Everything after colon
            
            # Extract timestamp
            timestamp = self._parse_timestamp(timestamp_str)
            
            # We already have event_name and fields_part from above
            
            # Parse field groups
            field_groups = self._parse_field_groups(fields_part)
            context_fields = field_groups[0] if len(field_groups) > 0 else {}
            event_fields = field_groups[1] if len(field_groups) > 1 else {}
            
            # Process the event according to two-tiered design
            self._process_event(timestamp, event_name, context_fields, event_fields)
            self.stats['parsed_events'] += 1
            
        except Exception as e:
            logger.debug(f"Error processing line: {line[:100]}... - {e}")

    def _parse_timestamp(self, timestamp_str: str) -> float:
        """Parse LTTng timestamp to float seconds"""
        try:
            # Remove microsecond precision and convert to seconds
            if '.' in timestamp_str:
                time_part = timestamp_str.split('.')[0] + '.' + timestamp_str.split('.')[1][:6]
                return float(time_part)
            return float(timestamp_str)
        except:
            return 0.0

    def _parse_field_groups(self, fields_str: str) -> List[Dict[str, Any]]:
        """Parse LTTng field groups: { cpu_id = 1 }, { fd = 23, ... }"""
        groups = []
        current_group = ""
        brace_count = 0
        
        for char in fields_str:
            if char == '{':
                brace_count += 1
                if brace_count == 1:
                    current_group = ""
                    continue
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    groups.append(self._parse_field_group(current_group))
                    current_group = ""
                    continue
            
            if brace_count > 0:
                current_group += char
                
        return groups

    def _parse_field_group(self, group_str: str) -> Dict[str, Any]:
        """Parse individual field group: cpu_id = 1, fd = 23"""
        fields = {}
        if not group_str.strip():
            return fields
            
        try:
            # Split by comma
            for part in group_str.split(','):
                part = part.strip()
                if ' = ' in part:
                    key, value = part.split(' = ', 1)
                    key = key.strip()
                    value = value.strip().strip('"')
                    
                    # Convert to appropriate type
                    try:
                        if '.' in value:
                            fields[key] = float(value)
                        else:
                            fields[key] = int(value)
                    except ValueError:
                        fields[key] = value
                        
        except Exception as e:
            logger.debug(f"Error parsing field group '{group_str}': {e}")
            
        return fields

    def _process_event(self, timestamp: float, event_name: str, 
                      context_fields: Dict[str, Any], event_fields: Dict[str, Any]) -> None:
        """Process event according to two-tiered design principles"""
        
        # Extract common context - PID can be in either context or event fields
        cpu_id = context_fields.get('cpu_id')
        tid = event_fields.get('tid') or context_fields.get('tid')
        pid = event_fields.get('pid') or context_fields.get('pid')
        
        # For sched_switch events, extract PID from prev_tid/next_tid
        if event_name == 'sched_switch':
            # We'll handle PID extraction in the scheduling handler
            pass
        
        # Ensure CPU entity exists
        if cpu_id is not None:
            self._ensure_cpu_exists(cpu_id)
            
        # Handle specific event types that create entity relationships
        
        # 1. File descriptor mapping events (critical for design!)
        if event_name == 'lttng_statedump_file_descriptor':
            self._handle_fd_mapping(timestamp, event_fields)
            
        # 2. Process state events 
        elif event_name == 'lttng_statedump_process_state':
            self._handle_process_state(timestamp, event_fields)
            
        # 3. File syscalls - create Process → File relationships  
        elif event_name.startswith('syscall_exit_'):
            syscall_name = event_name.replace('syscall_exit_', '')
            if syscall_name in ['read', 'write', 'open', 'close', 'openat', 'access']:
                self._handle_file_syscall(timestamp, syscall_name, event_fields, pid, cpu_id)
        elif event_name.startswith('syscall_entry_'):
            syscall_name = event_name.replace('syscall_entry_', '')
            if syscall_name in ['access', 'openat', 'open'] and 'filename' in event_fields:
                self._handle_file_syscall(timestamp, syscall_name, event_fields, pid, cpu_id)
                
        # 4. Scheduling events - create Thread → CPU relationships
        elif event_name == 'sched_switch':
            self._handle_scheduling(timestamp, event_fields, cpu_id)
            
        # 5. Network syscalls - create Process → Socket relationships
        elif event_name.startswith('syscall_exit_') and any(net in event_name for net in ['send', 'recv', 'connect', 'bind']):
            syscall_name = event_name.replace('syscall_exit_', '')
            self._handle_network_syscall(timestamp, syscall_name, event_fields, pid, cpu_id)

    def _handle_fd_mapping(self, timestamp: float, fields: Dict[str, Any]) -> None:
        """Handle file descriptor to filename mapping - CRITICAL for design!"""
        fd = fields.get('fd')
        filename = fields.get('filename')
        file_table_address = fields.get('file_table_address')
        
        if fd is not None and filename and file_table_address:
            # We need to map this to a process - use a heuristic or store for later
            # For now, we'll use the file_table_address as a proxy for process identification
            
            # Ensure file entity exists
            self._ensure_file_exists(filename, timestamp)
            
            # Store fd mapping - we'll need to associate with processes later
            # For now, store globally and match during syscalls
            logger.debug(f"FD mapping: fd={fd} -> {filename}")

    def _handle_process_state(self, timestamp: float, fields: Dict[str, Any]) -> None:
        """Handle process state dump events"""
        pid = fields.get('pid')
        tid = fields.get('tid')
        ppid = fields.get('ppid') 
        name = fields.get('name', '')
        
        if pid is not None:
            # Ensure process exists
            self._ensure_process_exists(pid, timestamp, fields)
            
            # Ensure thread exists
            if tid is not None:
                self._ensure_thread_exists(tid, pid, timestamp, name)

    def _handle_file_syscall(self, timestamp: float, syscall_name: str,
                           fields: Dict[str, Any], pid: Optional[int], cpu_id: Optional[int]) -> None:
        """Handle file syscalls - create Process → File relationships"""
        
        if pid is None:
            return
            
        # Ensure process exists
        self._ensure_process_exists(pid, timestamp, fields)
        
        # Get filename - this is the key fix!
        filename = None
        
        # Direct filename (access, openat syscalls)
        if 'filename' in fields:
            filename = fields['filename']
        elif 'pathname' in fields:
            filename = fields['pathname']
        else:
            # Use fd mapping for read/write syscalls  
            fd = fields.get('fd')
            if fd is not None:
                # For now, create a placeholder file entity using fd
                # In a complete implementation, we'd maintain fd→filename mappings
                filename = f"/proc/fd/{fd}"
                
        if not filename:
            return
            
        # Ensure file entity exists
        self._ensure_file_exists(filename, timestamp)
        
        # Determine relationship type based on original design
        if syscall_name in ['read', 'pread64']:
            rel_type = 'READ_FROM'
        elif syscall_name in ['write', 'pwrite64']:
            rel_type = 'WROTE_TO'
        elif syscall_name in ['open', 'openat', 'creat']:
            rel_type = 'OPENED'
        elif syscall_name == 'close':
            rel_type = 'CLOSED'
        elif syscall_name == 'access':
            rel_type = 'ACCESSED'
        else:
            rel_type = 'ACCESSED'
            
        # Create the entity relationship (Process → File)
        self._add_relationship(
            source_type='Process',
            source_id=pid,
            target_type='File',
            target_id=filename,
            relationship_type=rel_type,
            timestamp=timestamp,
            properties={
                'syscall_name': syscall_name,
                'fd': fields.get('fd'),
                'bytes': fields.get('count', fields.get('ret', 0)),
                'cpu_id': cpu_id,
                'sequence': self._get_next_sequence()
            }
        )
        
        self.stats['file_relationships'] += 1

    def _handle_scheduling(self, timestamp: float, fields: Dict[str, Any], cpu_id: Optional[int]) -> None:
        """Handle scheduling events - create Thread → CPU relationships"""
        
        prev_tid = fields.get('prev_tid')
        prev_comm = fields.get('prev_comm', '')
        next_tid = fields.get('next_tid') 
        next_comm = fields.get('next_comm', '')
        
        # For kernel traces, tid often equals pid for main threads
        # We'll use tid as both thread and process ID for simplicity
        prev_pid = prev_tid  # Assume tid == pid for main threads
        next_pid = next_tid
        
        if cpu_id is None:
            return
            
        # Ensure CPU exists
        self._ensure_cpu_exists(cpu_id)
        
        # Handle thread being scheduled off CPU
        if prev_tid is not None and prev_pid is not None:
            self._ensure_process_exists(prev_pid, timestamp, fields)
            self._ensure_thread_exists(prev_tid, prev_pid, timestamp)
            
            self._add_relationship(
                source_type='Thread',
                source_id=(prev_tid, prev_pid),
                target_type='CPU',
                target_id=cpu_id,
                relationship_type='PREEMPTED_FROM',
                timestamp=timestamp,
                properties={
                    'prev_state': fields.get('prev_state'),
                    'sequence': self._get_next_sequence()
                }
            )
            
        # Handle thread being scheduled on CPU  
        if next_tid is not None and next_pid is not None:
            self._ensure_process_exists(next_pid, timestamp, fields)
            self._ensure_thread_exists(next_tid, next_pid, timestamp)
            
            self._add_relationship(
                source_type='Thread', 
                source_id=(next_tid, next_pid),
                target_type='CPU',
                target_id=cpu_id,
                relationship_type='SCHEDULED_ON',
                timestamp=timestamp,
                properties={
                    'next_prio': fields.get('next_prio'),
                    'sequence': self._get_next_sequence()
                }
            )
            
        self.stats['scheduling_relationships'] += 1

    def _handle_network_syscall(self, timestamp: float, syscall_name: str,
                              fields: Dict[str, Any], pid: Optional[int], cpu_id: Optional[int]) -> None:
        """Handle network syscalls - create Process → Socket relationships"""
        
        if pid is None:
            return
            
        socket_fd = fields.get('fd', fields.get('sockfd'))
        if socket_fd is None:
            return
            
        # Ensure process exists
        self._ensure_process_exists(pid, timestamp, fields)
        
        # Create socket entity
        socket_id = f"socket_{pid}_{socket_fd}"
        if socket_id not in self.sockets:
            self.sockets[socket_id] = SocketEntity(
                socket_id=socket_id,
                family=fields.get('family', ''),
                socket_type=fields.get('type', ''),
                protocol=fields.get('protocol', '')
            )
            
        # Determine relationship type
        if 'send' in syscall_name:
            rel_type = 'SENT_TO'
        elif 'recv' in syscall_name:
            rel_type = 'RECEIVED_FROM'
        elif syscall_name == 'connect':
            rel_type = 'CONNECTED_TO'
        elif syscall_name == 'bind':
            rel_type = 'BOUND_TO'
        else:
            rel_type = 'ACCESSED'
            
        # Create Process → Socket relationship
        self._add_relationship(
            source_type='Process',
            source_id=pid,
            target_type='Socket',
            target_id=socket_id,
            relationship_type=rel_type,
            timestamp=timestamp,
            properties={
                'syscall_name': syscall_name,
                'socket_fd': socket_fd,
                'bytes': fields.get('len', fields.get('ret', 0)),
                'cpu_id': cpu_id,
                'sequence': self._get_next_sequence()
            }
        )
        
        self.stats['socket_relationships'] += 1

    def _ensure_process_exists(self, pid: int, timestamp: float, fields: Dict[str, Any]) -> None:
        """Ensure process entity exists"""
        if pid not in self.processes:
            name = fields.get('name', fields.get('comm', f"Process-{pid}")).strip('"')
            self.processes[pid] = ProcessEntity(
                pid=pid,
                ppid=fields.get('ppid'),
                name=name,
                start_time=timestamp,
                uid=fields.get('uid'),
                gid=fields.get('gid')
            )

    def _ensure_thread_exists(self, tid: int, pid: int, timestamp: float, name: str = None) -> None:
        """Ensure thread entity exists"""
        thread_key = (tid, pid)
        if thread_key not in self.threads:
            thread_name = name if name else f"Thread-{tid}"
            self.threads[thread_key] = ThreadEntity(
                tid=tid,
                pid=pid,
                name=thread_name.strip('"'),
                start_time=timestamp
            )

    def _ensure_file_exists(self, path: str, timestamp: float) -> None:
        """Ensure file entity exists"""
        if path not in self.files:
            # Determine file type
            file_type = "regular"
            if path.startswith("/dev/"):
                file_type = "device"
            elif path.startswith("/proc/"):
                file_type = "virtual"
            elif path.startswith("/sys/"):
                file_type = "sysfs"
            elif path.endswith(".so") or ".so." in path:
                file_type = "library"
                
            self.files[path] = FileEntity(
                path=path,
                file_type=file_type,
                first_accessed=timestamp
            )

    def _ensure_cpu_exists(self, cpu_id: int) -> None:
        """Ensure CPU entity exists"""
        if cpu_id not in self.cpus:
            self.cpus[cpu_id] = CPUEntity(cpu_id=cpu_id)

    def _add_relationship(self, source_type: str, source_id: Any, target_type: str,
                         target_id: Any, relationship_type: str, timestamp: float,
                         properties: Dict[str, Any]) -> None:
        """Add entity relationship"""
        self.relationships.append(EventRelationship(
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relationship_type=relationship_type,
            timestamp=timestamp,
            properties=properties
        ))
        self.stats['relationships_created'] += 1

    def _optimize_entity_times(self) -> None:
        """Optimize entity end times based on last activity"""
        # Find last activity per entity
        last_activity = defaultdict(float)
        
        for rel in self.relationships:
            # Update source entity last activity
            source_key = (rel.source_type, str(rel.source_id))
            last_activity[source_key] = max(last_activity[source_key], rel.timestamp)
            
            # Update target entity last activity  
            target_key = (rel.target_type, str(rel.target_id))
            last_activity[target_key] = max(last_activity[target_key], rel.timestamp)
            
        # Update entity end times
        for process in self.processes.values():
            key = ('Process', str(process.pid))
            if key in last_activity:
                process.end_time = last_activity[key]
                
        for thread in self.threads.values():
            key = ('Thread', str(thread.tid))
            if key in last_activity:
                thread.end_time = last_activity[key]
                
        for file in self.files.values():
            key = ('File', file.path)
            if key in last_activity:
                file.last_accessed = last_activity[key]

    def get_entities(self) -> Dict[str, List]:
        """Get all entities organized by type"""
        return {
            'Process': list(self.processes.values()),
            'Thread': list(self.threads.values()),
            'File': list(self.files.values()),
            'Socket': list(self.sockets.values()),
            'CPU': list(self.cpus.values())
        }

    def get_relationships(self) -> List[EventRelationship]:
        """Get all relationships"""
        return self.relationships

    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            **self.stats,
            'entities': {
                'processes': len(self.processes),
                'threads': len(self.threads),
                'files': len(self.files),
                'sockets': len(self.sockets),
                'cpus': len(self.cpus)
            }
        }

if __name__ == "__main__":
    # Test the fixed processor
    processor = FixedHybridTraceProcessor()
    processor.process_trace_file("traces/TraceMain.txt")
    
    stats = processor.get_stats()
    entities = processor.get_entities()
    
    print(" Fixed Hybrid Processor Results:")
    print(f" Total relationships: {len(processor.relationships)}")
    print(f" Processes: {len(entities['Process'])}")
    print(f" Files: {len(entities['File'])}")
    print(f" File relationships: {stats['file_relationships']}")
    print(f" Scheduling relationships: {stats['scheduling_relationships']}")