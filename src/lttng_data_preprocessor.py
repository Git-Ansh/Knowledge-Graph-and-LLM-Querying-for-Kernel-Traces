#!/usr/bin/env python3
"""
LTTng Kernel Trace Data Preprocessor

Processes raw LTTng kernel traces and extracts entities according to the universal schema.
Transforms trace events into structured data suitable for property graph construction.

Features:
- Parses LTTng trace text output (lttng view format)
- Extracts processes, threads, files, syscalls, CPU usage
- Handles state transitions and relationships
- Optimized for large trace volumes (300K+ events)
- Exports structured data for graph builder
"""

import re
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Set, Any, Optional, Tuple
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ProcessEntity:
    """Process node representation"""
    pid: int
    ppid: Optional[int] = None
    name: str = ""
    command_line: str = ""
    initialization_timestamp: float = 0.0  # REQUIRED: When process first observed
    exit_timestamp: Optional[float] = None  # When process ends/dies
    start_time: Optional[float] = None  # Legacy compatibility
    end_time: Optional[float] = None    # Legacy compatibility
    state: str = "unknown"  # running, sleeping, stopped, zombie
    last_seen_timestamp: float = 0.0   # REQUIRED: Last activity timestamp
    cpu_time: float = 0.0
    memory_usage: int = 0
    syscall_count: int = 0
    file_count: int = 0
    uid: Optional[int] = None
    gid: Optional[int] = None

@dataclass
class ThreadEntity:
    """Thread node representation"""
    tid: int
    pid: int
    name: str = ""
    initialization_timestamp: float = 0.0  # REQUIRED: When thread first observed
    exit_timestamp: Optional[float] = None  # When thread terminates
    start_time: Optional[float] = None  # Legacy compatibility
    end_time: Optional[float] = None    # Legacy compatibility
    state: str = "unknown"  # running, ready, blocked, terminated
    last_activity_timestamp: float = 0.0  # REQUIRED: Last syscall/scheduling event
    priority: int = 0
    cpu_time: float = 0.0
    context_switches: int = 0
    syscall_count: int = 0
    current_cpu: Optional[int] = None

@dataclass
class FileEntity:
    """File node representation"""
    path: str
    inode: Optional[int] = None
    file_type: str = "regular"  # regular, directory, socket, pipe, device
    permissions: str = ""
    size: int = 0
    access_count: int = 0
    first_access_timestamp: float = 0.0    # REQUIRED: When file first accessed
    last_access_timestamp: float = 0.0     # REQUIRED: Most recent access
    modification_time: Optional[float] = None  # File system modification time
    creation_time: Optional[float] = None      # File system creation time
    owner_uid: Optional[int] = None
    owner_gid: Optional[int] = None

@dataclass
class SyscallEventEntity:
    """Individual syscall event"""
    event_id: str
    timestamp: float
    tid: int
    syscall_name: str
    duration: Optional[float] = None
    return_value: Optional[int] = None
    cpu_id: Optional[int] = None
    arguments: Optional[Dict[str, Any]] = None
    entry_timestamp: Optional[float] = None
    exit_timestamp: Optional[float] = None

@dataclass
class SyscallTypeEntity:
    """Aggregated syscall type statistics"""
    name: str
    total_count: int = 0
    average_duration: float = 0.0
    min_duration: float = float('inf')
    max_duration: float = 0.0
    success_rate: float = 0.0
    first_occurrence_timestamp: float = 0.0    # REQUIRED: When first seen
    last_occurrence_timestamp: float = 0.0     # REQUIRED: Most recent occurrence
    error_codes: Optional[Dict[int, int]] = None

class LTTngDataPreprocessor:
    """LTTng trace preprocessor with universal schema support"""
    
    def __init__(self):
        self.processes: Dict[int, ProcessEntity] = {}
        self.threads: Dict[int, ThreadEntity] = {}
        self.files: Dict[str, FileEntity] = {}
        self.syscall_events: List[SyscallEventEntity] = []
        self.syscall_types: Dict[str, SyscallTypeEntity] = {}
        self.pending_syscalls: Dict[int, Dict[str, Dict]] = defaultdict(dict)  # tid -> {syscall_name -> entry_data}
        
        # Execution context tracking to prevent phantom processes
        self.execution_context: Dict[int, int] = {}  # cpu_id -> current_pid
        self.known_pids: Set[int] = set()  # PIDs confirmed by getpid/set_tid_address
        self.cpu_thread_context: Dict[int, int] = {}  # cpu_id -> current_tid
        
        self.stats = {
            'total_events': 0,
            'processed_events': 0,
            'syscall_entries': 0,
            'syscall_exits': 0,
            'context_switches': 0,
            'file_operations': 0,
            'processes_created': 0,
            'threads_created': 0,
            'files_accessed': 0
        }
        
        # Performance optimization: track first/last timestamps
        self.first_timestamp: Optional[float] = None
        self.last_timestamp: Optional[float] = None
        
        # Event counter for unique syscall event IDs
        self.event_counter = 0

    def parse_lttng_trace_file(self, trace_file: str) -> None:
        """Parse LTTng trace text file"""
        logger.info(f" Processing trace file: {trace_file}")
        
        with open(trace_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    self._process_trace_line(line.strip())
                    self.stats['total_events'] += 1
                    
                    if line_num % 10000 == 0:
                        logger.info(f" Processed {line_num:,} lines, {self.stats['processed_events']:,} events")
                        
                except Exception as e:
                    logger.warning(f"  Error processing line {line_num}: {e}")
                    continue

    def _process_trace_line(self, line: str) -> None:
        """Process individual trace line"""
        if not line or line.startswith('#'):
            return
            
        # Parse LTTng trace format: [timestamp] (+offset) hostname event_name: { cpu_id = X }, { ... }
        try:
            # Extract timestamp
            timestamp_match = re.match(r'^\[(\d{2}:\d{2}:\d{2}\.\d{9})\]', line)
            if not timestamp_match:
                return
                
            timestamp_str = timestamp_match.group(1)
            timestamp = self._parse_timestamp(timestamp_str)
            
            # Extract event name and fields after hostname
            # Format: [timestamp] (+offset) Ubuntu event_name: { cpu_id = X }, { ... }
            event_match = re.search(r'Ubuntu\s+([^:]+):\s*\{([^}]*)\}(?:,\s*\{([^}]*)\})?', line)
            if not event_match:
                return
                
            event_name = event_match.group(1)
            cpu_fields = event_match.group(2)
            event_fields = event_match.group(3) or ""
            
            # Parse fields
            fields = self._parse_fields(cpu_fields + ", " + event_fields)
            
            # Process based on event type
            self._handle_kernel_event(timestamp, event_name, fields)
            self.stats['processed_events'] += 1
            
        except Exception as e:
            logger.debug(f"Failed to parse line: {line[:100]}... Error: {e}")

    def _parse_timestamp(self, timestamp_str: str) -> float:
        """Convert timestamp string to float (seconds since start)"""
        try:
            # Parse HH:MM:SS.nnnnnnnnn format
            time_parts = timestamp_str.split(':')
            hours = int(time_parts[0])
            minutes = int(time_parts[1])
            seconds_parts = time_parts[2].split('.')
            seconds = int(seconds_parts[0])
            nanoseconds = int(seconds_parts[1])
            
            total_seconds = hours * 3600 + minutes * 60 + seconds
            total_seconds += nanoseconds / 1000000000.0
            
            return total_seconds
        except:
            return 0.0

    def _parse_fields(self, fields_str: str) -> Dict[str, Any]:
        """Parse LTTng event fields"""
        fields = {}
        if not fields_str.strip():
            return fields
            
        try:
            # Split by comma, handling nested structures
            field_parts = []
            current_part = ""
            bracket_count = 0
            paren_count = 0
            
            for char in fields_str:
                if char == '{':
                    bracket_count += 1
                elif char == '}':
                    bracket_count -= 1
                elif char == '(':
                    paren_count += 1
                elif char == ')':
                    paren_count -= 1
                elif char == ',' and bracket_count == 0 and paren_count == 0:
                    field_parts.append(current_part.strip())
                    current_part = ""
                    continue
                current_part += char
                
            if current_part.strip():
                field_parts.append(current_part.strip())
            
            # Parse each field
            for part in field_parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Convert value types
                    if value.startswith('"') and value.endswith('"'):
                        fields[key] = value[1:-1]  # String
                    elif value == 'NULL':
                        fields[key] = None
                    elif value.startswith('0x'):
                        try:
                            fields[key] = int(value, 16)  # Hex
                        except:
                            fields[key] = value
                    elif value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
                        fields[key] = int(value)  # Integer
                    elif value.replace('.', '').replace('-', '').isdigit():
                        fields[key] = float(value)  # Float
                    else:
                        fields[key] = value  # Raw string
                        
        except Exception as e:
            logger.debug(f"Failed to parse fields: {fields_str[:50]}... Error: {e}")
            
        return fields

    def _handle_kernel_event(self, timestamp: float, event_name: str, fields: Dict[str, Any]) -> None:
        """Handle specific kernel events with proper execution context tracking"""
        cpu_id = fields.get('cpu_id')
        
        # Extract execution context (calling process/thread) - NOT syscall arguments
        tid, pid = self._extract_execution_context(timestamp, event_name, fields, cpu_id)
        
        # For kernel syscall traces, be more permissive about context
        if tid is None or pid is None:
            # Try to use CPU-based context as fallback for syscalls
            if event_name.startswith('syscall_') and cpu_id is not None:
                # Use a consistent CPU-based mapping that works for entry/exit pairs
                # Cache the CPU-to-PID mapping so entry/exit events get same TID
                if cpu_id not in self.cpu_thread_context:
                    # Create a consistent PID for this CPU
                    fallback_pid = cpu_id + 10000  # High number to avoid real PID conflicts
                    self.cpu_thread_context[cpu_id] = fallback_pid
                    self.execution_context[cpu_id] = fallback_pid
                    logger.debug(f"Created CPU-based mapping: CPU {cpu_id} -> PID {fallback_pid}")
                
                tid = pid = self.cpu_thread_context[cpu_id]
                logger.debug(f"Using CPU-based context: TID/PID {tid} for {event_name} on CPU {cpu_id}")
            else:
                logger.debug(f"Skipping event {event_name} - no valid execution context")
                return
        
        # Create/update process and thread entities
        self._ensure_process_exists(pid, timestamp)
        self._ensure_thread_exists(tid, pid, timestamp)
        
        # Handle specific event types
        if event_name.startswith('syscall_entry_'):
            self._handle_syscall_entry(timestamp, event_name, fields, tid, pid, cpu_id)
        elif event_name.startswith('syscall_exit_'):
            self._handle_syscall_exit(timestamp, event_name, fields, tid, pid, cpu_id)
        elif event_name in ['sched_switch', 'sched_wakeup', 'sched_waking']:
            self._handle_scheduling_event(timestamp, event_name, fields)
        elif any(op in event_name for op in ['open', 'close', 'read', 'write']):
            self._handle_file_operation(timestamp, event_name, fields, tid, pid)

    def _ensure_process_exists(self, pid: int, timestamp: float) -> None:
        """Ensure process entity exists"""
        if pid not in self.processes:
            self.processes[pid] = ProcessEntity(
                pid=pid,
                initialization_timestamp=timestamp,
                last_seen_timestamp=timestamp,
                start_time=timestamp,  # Legacy compatibility
                state="running"
            )
        else:
            # Update last seen timestamp
            self.processes[pid].last_seen_timestamp = timestamp

    def _ensure_thread_exists(self, tid: int, pid: int, timestamp: float) -> None:
        """Ensure thread entity exists"""
        if tid not in self.threads:
            self.threads[tid] = ThreadEntity(
                tid=tid,
                pid=pid,
                initialization_timestamp=timestamp,
                last_activity_timestamp=timestamp,
                start_time=timestamp,  # Legacy compatibility
                state="running"
            )
        else:
            # Update last activity timestamp
            self.threads[tid].last_activity_timestamp = timestamp

    def _extract_execution_context(self, timestamp: float, event_name: str, fields: Dict[str, Any], cpu_id: Optional[int]) -> Tuple[Optional[int], Optional[int]]:
        """Extract the actual executing thread/process, not syscall arguments"""
        
        # Special handling for PID discovery syscalls - these tell us real PIDs
        if event_name in ['syscall_exit_getpid', 'syscall_exit_set_tid_address', 'syscall_exit_vfork']:
            ret_pid = fields.get('ret')
            if ret_pid and ret_pid > 0:
                self.known_pids.add(ret_pid)
                if cpu_id is not None:
                    self.execution_context[cpu_id] = ret_pid
                    self.cpu_thread_context[cpu_id] = ret_pid  # Main thread
                logger.debug(f"Discovered real PID {ret_pid} from {event_name} on CPU {cpu_id}")
                return ret_pid, ret_pid
        
        # For syscalls, use execution context or infer intelligently
        if event_name.startswith('syscall_'):
            if cpu_id is not None and cpu_id in self.execution_context:
                # Use known execution context
                pid = self.execution_context[cpu_id]
                tid = self.cpu_thread_context.get(cpu_id, pid)  # Default tid = pid for main thread
                return tid, pid
            else:
                # More aggressive inference for syscall traces
                # In kernel syscall traces, we can be more permissive
                inferred_pid = self._infer_execution_pid(fields, event_name)
                if inferred_pid and inferred_pid > 0:
                    # Cache this inference for future use
                    if cpu_id is not None:
                        self.execution_context[cpu_id] = inferred_pid
                        self.cpu_thread_context[cpu_id] = inferred_pid
                    return inferred_pid, inferred_pid
                    if cpu_id is not None:
                        self.execution_context[cpu_id] = inferred_pid
                        self.cpu_thread_context[cpu_id] = tid
                    return tid, inferred_pid
        
        # For non-syscall events, use direct field extraction
        tid = fields.get('tid', fields.get('vtid', None))
        pid = fields.get('pid', fields.get('vpid', None))
        
        if pid and pid in self.known_pids:
            return tid or pid, pid
        
        return None, None
    
    def _infer_execution_pid(self, fields: Dict[str, Any], event_name: str) -> Optional[int]:
        """Infer execution PID from context, avoiding syscall arguments"""
        # Avoid 'pid' field in syscalls like prlimit64 where it's an argument
        if 'prlimit64' in event_name or 'kill' in event_name or 'wait' in event_name:
            # These syscalls have 'pid' as argument, not caller PID
            return None
        
        # For kernel syscall traces, we often need to use heuristics
        # Look for established PIDs that we can reasonably associate
        if self.known_pids:
            # Simple heuristic: if there's only one known PID, likely it's the one
            if len(self.known_pids) == 1:
                return list(self.known_pids)[0]
            
            # If multiple PIDs, try to use the most recent one or a reasonable default
            # This is a simplification - real production systems would need better logic
            return max(self.known_pids)  # Use highest PID as heuristic
        
        # Fallback: check if fields contain direct PID info (but be cautious)
        pid = fields.get('vpid') or fields.get('pid')
        return pid if pid and pid > 0 else None

    def _handle_syscall_entry(self, timestamp: float, event_name: str, fields: Dict[str, Any], tid: int, pid: int, cpu_id: Optional[int]) -> None:
        """Handle syscall entry event"""
        syscall_name = event_name.replace('syscall_entry_', '')
        
        # Store pending syscall
        self.pending_syscalls[tid][syscall_name] = {
            'entry_timestamp': timestamp,
            'fields': fields,
            'cpu_id': cpu_id
        }
        
        self.stats['syscall_entries'] += 1
        logger.debug(f"Syscall entry: {syscall_name} for TID {tid} on CPU {cpu_id}")
        
        # Update thread syscall count
        if tid in self.threads:
            self.threads[tid].syscall_count += 1

    def _handle_syscall_exit(self, timestamp: float, event_name: str, fields: Dict[str, Any], tid: int, pid: int, cpu_id: Optional[int]) -> None:
        """Handle syscall exit event"""
        syscall_name = event_name.replace('syscall_exit_', '')
        
        logger.debug(f"Syscall exit: {syscall_name} for TID {tid} on CPU {cpu_id}")
        logger.debug(f"Pending syscalls for TID {tid}: {list(self.pending_syscalls.get(tid, {}).keys())}")
        
        # Find matching entry
        if tid in self.pending_syscalls and syscall_name in self.pending_syscalls[tid]:
            entry_info = self.pending_syscalls[tid].pop(syscall_name)
            entry_timestamp = entry_info['entry_timestamp']
            duration = timestamp - entry_timestamp
            logger.debug(f"Successfully matched {syscall_name} for TID {tid}, duration: {duration:.6f}s")
            
            # Create syscall event
            event_id = f"{tid}_{syscall_name}_{self.event_counter}"
            self.event_counter += 1
            
            syscall_event = SyscallEventEntity(
                event_id=event_id,
                timestamp=timestamp,
                tid=tid,
                syscall_name=syscall_name,
                duration=duration,
                return_value=fields.get('ret', None),
                cpu_id=cpu_id,
                arguments=entry_info['fields'],
                entry_timestamp=entry_timestamp,
                exit_timestamp=timestamp
            )
            
            self.syscall_events.append(syscall_event)
            
            # Extract file information from file-related syscalls
            self._extract_file_operations(syscall_name, entry_info['fields'], fields, timestamp, pid)
            
            # Update syscall type statistics
            self._update_syscall_type_stats(syscall_name, duration, fields.get('ret', 0), timestamp)
            
            self.stats['syscall_exits'] += 1
        else:
            logger.debug(f"No matching entry found for {syscall_name} exit, TID {tid}")
            logger.debug(f"Available TIDs: {list(self.pending_syscalls.keys())}")
            if tid in self.pending_syscalls:
                logger.debug(f"Available syscalls for TID {tid}: {list(self.pending_syscalls[tid].keys())}")

    def _extract_file_operations(self, syscall_name: str, entry_fields: Dict[str, Any], exit_fields: Dict[str, Any], timestamp: float, pid: int) -> None:
        """Extract file entities from file-related syscalls"""
        file_syscalls = {
            'openat': 'filename',
            'open': 'filename', 
            'read': None,  # Uses fd
            'write': None,  # Uses fd
            'close': None,  # Uses fd
            'access': 'filename',
            'stat': 'filename',
            'newfstatat': 'filename',
            'readlink': 'pathname',
            'unlink': 'pathname',
            'mkdir': 'pathname',
            'rmdir': 'pathname'
        }
        
        if syscall_name in file_syscalls:
            self.stats['file_operations'] += 1
            
            filename_field = file_syscalls[syscall_name]
            if filename_field and filename_field in entry_fields:
                filepath = entry_fields[filename_field]
                if filepath and isinstance(filepath, str) and len(filepath) > 0:
                    # Create file entity
                    file_id = f"file_{abs(hash(filepath))}"
                    
                    if file_id not in self.files:
                        file_entity = FileEntity(
                            path=filepath,
                            inode=None,  # Not available in syscall trace
                            file_type="regular",
                            permissions="",
                            size=0,
                            access_count=0,
                            first_access_timestamp=timestamp,
                            last_access_timestamp=timestamp,
                            modification_time=None,
                            creation_time=None,
                            owner_uid=None,
                            owner_gid=None
                        )
                        self.files[file_id] = file_entity
                    
                    # Update access statistics
                    self.files[file_id].access_count += 1
                    self.files[file_id].last_access_timestamp = timestamp

    def _update_syscall_type_stats(self, syscall_name: str, duration: float, return_value: int, timestamp: float) -> None:
        """Update aggregated syscall type statistics"""
        if syscall_name not in self.syscall_types:
            self.syscall_types[syscall_name] = SyscallTypeEntity(
                name=syscall_name,
                first_occurrence_timestamp=timestamp,
                last_occurrence_timestamp=timestamp,
                error_codes={}
            )
        else:
            # Update last occurrence timestamp
            self.syscall_types[syscall_name].last_occurrence_timestamp = timestamp
        
        syscall_type = self.syscall_types[syscall_name]
        syscall_type.total_count += 1
        
        # Update duration statistics
        if duration > 0:
            if syscall_type.total_count == 1:
                syscall_type.average_duration = duration
                syscall_type.min_duration = duration
                syscall_type.max_duration = duration
            else:
                # Running average
                syscall_type.average_duration = (
                    (syscall_type.average_duration * (syscall_type.total_count - 1) + duration) /
                    syscall_type.total_count
                )
                syscall_type.min_duration = min(syscall_type.min_duration, duration)
                syscall_type.max_duration = max(syscall_type.max_duration, duration)
        
        # Track return codes
        if return_value < 0:
            if syscall_type.error_codes is None:
                syscall_type.error_codes = {}
            syscall_type.error_codes[return_value] = syscall_type.error_codes.get(return_value, 0) + 1
        
        # Update success rate
        if syscall_type.error_codes:
            error_count = sum(syscall_type.error_codes.values())
        else:
            error_count = 0
        syscall_type.success_rate = (syscall_type.total_count - error_count) / syscall_type.total_count

    def _handle_scheduling_event(self, timestamp: float, event_name: str, fields: Dict[str, Any]) -> None:
        """Handle process/thread scheduling events"""
        if event_name == 'sched_switch':
            prev_tid = fields.get('prev_tid', 0)
            next_tid = fields.get('next_tid', 0)
            cpu_id = fields.get('cpu_id')
            
            # Update thread states and CPU assignments
            if prev_tid and prev_tid in self.threads:
                self.threads[prev_tid].context_switches += 1
                self.threads[prev_tid].state = fields.get('prev_state', 'ready')
                
            if next_tid and next_tid in self.threads:
                self.threads[next_tid].current_cpu = cpu_id
                self.threads[next_tid].state = 'running'
                
            self.stats['context_switches'] += 1
            
        elif event_name in ['sched_waking', 'sched_wakeup']:
            # Handle wakeup events
            tid = fields.get('tid')
            if tid and tid in self.threads:
                self.threads[tid].state = 'ready'

    def _handle_file_operation(self, timestamp: float, event_name: str, fields: Dict[str, Any], tid: int, pid: int) -> None:
        """Handle file system operations"""
        filename = fields.get('filename', fields.get('pathname', ''))
        
        if filename:
            # Ensure file entity exists
            if filename not in self.files:
                self.files[filename] = FileEntity(
                    path=filename,
                    first_access_timestamp=timestamp,
                    last_access_timestamp=timestamp,
                    creation_time=timestamp  # Legacy compatibility
                )
            else:
                # Update last access timestamp
                self.files[filename].last_access_timestamp = timestamp
            
            # Update file statistics
            file_entity = self.files[filename]
            file_entity.access_count += 1
            file_entity.modification_time = timestamp  # Legacy compatibility
            
            # Update process file count
            if pid in self.processes:
                self.processes[pid].file_count += 1
                
            self.stats['file_operations'] += 1

    def export_entities(self, output_dir: str) -> None:
        """Export all extracted entities to JSON files"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        logger.info(f" Exporting entities to {output_dir}")
        
        # Export processes
        processes_data = [asdict(process) for process in self.processes.values()]
        with open(output_path / 'processes.json', 'w') as f:
            json.dump(processes_data, f, indent=2, default=str)
        
        # Export threads
        threads_data = [asdict(thread) for thread in self.threads.values()]
        with open(output_path / 'threads.json', 'w') as f:
            json.dump(threads_data, f, indent=2, default=str)
        
        # Export files
        files_data = [asdict(file_entity) for file_entity in self.files.values()]
        with open(output_path / 'files.json', 'w') as f:
            json.dump(files_data, f, indent=2, default=str)
        
        # Export syscall events with intelligent sampling
        # Prioritize file-related syscalls to fix isolated File node issue
        file_related_syscalls = ['openat', 'open', 'read', 'write', 'close', 'access', 'stat', 'lstat', 'fstat', 'newfstatat']
        
        # Separate file-related and other syscalls
        file_syscalls = [event for event in self.syscall_events if event.syscall_name in file_related_syscalls]
        other_syscalls = [event for event in self.syscall_events if event.syscall_name not in file_related_syscalls]
        
        # Include all file-related syscalls + sample of others
        max_total = 10000  # Reasonable limit for graph performance
        max_file_syscalls = min(len(file_syscalls), max_total // 2)  # Reserve half for file operations
        max_other_syscalls = max_total - max_file_syscalls
        
        selected_syscalls = (
            file_syscalls[:max_file_syscalls] + 
            other_syscalls[:max_other_syscalls]
        )
        
        # Sort by timestamp to maintain chronological order
        selected_syscalls.sort(key=lambda x: x.timestamp)
        
        syscall_events_data = [asdict(event) for event in selected_syscalls]
        
        logger.info(f" Syscall sampling: {len(file_syscalls)} file-related + {len(other_syscalls)} other = {len(selected_syscalls)} total exported")
        with open(output_path / 'syscall_events.json', 'w') as f:
            json.dump(syscall_events_data, f, indent=2, default=str)
        
        # Export syscall types
        syscall_types_data = []
        for syscall_type in self.syscall_types.values():
            data = asdict(syscall_type)
            # Ensure error_codes is a regular dict
            if data['error_codes'] is None:
                data['error_codes'] = {}
            syscall_types_data.append(data)
        
        with open(output_path / 'syscall_types.json', 'w') as f:
            json.dump(syscall_types_data, f, indent=2, default=str)
        
        # Export statistics
        with open(output_path / 'processing_stats.json', 'w') as f:
            json.dump(self.stats, f, indent=2)
        
        logger.info(f" Entity export completed:")
        logger.info(f"    Processes: {len(self.processes):,}")
        logger.info(f"    Threads: {len(self.threads):,}")
        logger.info(f"    Files: {len(self.files):,}")
        logger.info(f"    Syscall Events: {len(self.syscall_events):,}")
        logger.info(f"    Syscall Types: {len(self.syscall_types):,}")

    def print_summary(self) -> None:
        """Print processing summary"""
        print("\n" + "="*60)
        print(" LTTng Trace Processing Summary")
        print("="*60)
        print(f" Total Events: {self.stats['total_events']:,}")
        print(f" Processed Events: {self.stats['processed_events']:,}")
        print(f" Syscall Entries: {self.stats['syscall_entries']:,}")
        print(f" Syscall Exits: {self.stats['syscall_exits']:,}")
        print(f" Context Switches: {self.stats['context_switches']:,}")
        print(f" File Operations: {self.stats['file_operations']:,}")
        print()
        print(f"  Extracted Entities:")
        print(f"   • Processes: {len(self.processes):,}")
        print(f"   • Threads: {len(self.threads):,}")
        print(f"   • Files: {len(self.files):,}")
        print(f"   • Syscall Events: {len(self.syscall_events):,}")
        print(f"   • Syscall Types: {len(self.syscall_types):,}")
        print()
        
        # Top syscalls
        if self.syscall_types:
            print(" Top 10 System Calls:")
            top_syscalls = sorted(self.syscall_types.values(), 
                                key=lambda x: x.total_count, reverse=True)[:10]
            for i, syscall in enumerate(top_syscalls, 1):
                print(f"   {i:2}. {syscall.name:15} - {syscall.total_count:,} calls "
                      f"(avg: {syscall.average_duration:.6f}s)")


def main():
    """Main execution function"""
    print(" LTTng Kernel Trace Data Preprocessor")
    print("=" * 50)
    
    # Initialize preprocessor
    preprocessor = LTTngDataPreprocessor()
    
    # Process trace file
    trace_file = "traces/TraceMain.txt"
    if not Path(trace_file).exists():
        logger.error(f" Trace file not found: {trace_file}")
        return
    
    try:
        # Process the trace
        preprocessor.parse_lttng_trace_file(trace_file)
        
        # Print summary
        preprocessor.print_summary()
        
        # Export entities
        preprocessor.export_entities("processed_entities")
        
        logger.info(" Processing completed successfully!")
        
    except Exception as e:
        logger.error(f" Processing failed: {e}")
        raise


if __name__ == "__main__":
    main()