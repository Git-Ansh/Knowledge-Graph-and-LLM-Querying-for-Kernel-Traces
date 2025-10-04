"""
Trace Parser Module
===================
Parses raw LTTng trace output into structured kernel events.

This module handles the first stage of the pipeline:
- Reading raw trace files
- Extracting individual kernel events
- Standardizing event format
- Performing initial timestamp normalization

Author: Knowledge Graph and LLM Querying for Kernel Traces Project
Date: October 3, 2025
"""

import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, TextIO
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class KernelEvent:
    """Represents a single kernel event from LTTng trace."""
    timestamp: float
    cpu_id: int
    event_type: str
    process_name: str
    pid: int
    tid: int
    event_data: Dict[str, any] = field(default_factory=dict)
    raw_line: str = ""
    
    def __repr__(self):
        return f"KernelEvent(ts={self.timestamp}, type={self.event_type}, pid={self.pid}, tid={self.tid})"


class TraceParser:
    """Parses raw LTTng kernel trace output into structured events."""
    
    # LTTng trace line format pattern
    # Example: [18:59:58.921449123] (+0.000000234) hostname event_name: { cpu_id = 0 }, { ... }
    TRACE_LINE_PATTERN = re.compile(
        r'\[(\d{2}:\d{2}:\d{2}\.\d+)\]\s+'  # Timestamp
        r'\(\+?(-?\d+\.\d+)\)\s+'           # Delta
        r'(\S+)\s+'                          # Hostname
        r'([^:]+):\s+'                       # Event name
        r'(.+)'                              # Event data
    )
    
    # Pattern to extract fields from event data
    FIELD_PATTERN = re.compile(r'(\w+)\s*=\s*([^,}]+)')
    
    def __init__(self, trace_file: Path):
        """
        Initialize trace parser.
        
        Args:
            trace_file: Path to the raw LTTng trace output file
        """
        self.trace_file = trace_file
        self.events: List[KernelEvent] = []
        self.parse_errors = 0
        self.total_lines = 0
        self.base_timestamp = None
        
        # Context tracking: tid -> (pid, comm)
        # Built from sched_* events to enrich syscalls that lack context
        self.tid_context: Dict[int, tuple] = {}
        self.context_updates = 0
        
        # CPU tracking: cpu_id -> current_tid
        # Tracks which thread is currently running on each CPU
        self.cpu_context: Dict[int, int] = {}
        
        logger.info(f"Initialized TraceParser for file: {trace_file.name}")
    
    def parse(self) -> List[KernelEvent]:
        """
        Parse the entire trace file.
        
        Returns:
            List of parsed KernelEvent objects
        """
        logger.info("Starting trace parsing")
        start_time = datetime.now()
        
        try:
            with open(self.trace_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    self.total_lines += 1
                    
                    if self.total_lines % 10000 == 0:
                        logger.debug(f"Processed {self.total_lines} lines, extracted {len(self.events)} events")
                    
                    event = self._parse_line(line)
                    if event:
                        self.events.append(event)
                    
        except Exception as e:
            logger.error(f"Error reading trace file: {e}")
            raise
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Parsing complete: {len(self.events)} events from {self.total_lines} lines in {duration:.2f}s")
        logger.info(f"Parse success rate: {(1 - self.parse_errors/max(self.total_lines, 1))*100:.1f}%")
        logger.info(f"Context tracking: {len(self.tid_context)} unique threads, {self.context_updates} context updates")
        
        return self.events
    
    def _parse_line(self, line: str) -> Optional[KernelEvent]:
        """
        Parse a single trace line into a KernelEvent.
        
        Args:
            line: Raw trace line
            
        Returns:
            KernelEvent object or None if parsing fails
        """
        line = line.strip()
        if not line or line.startswith('#'):
            return None
        
        match = self.TRACE_LINE_PATTERN.match(line)
        if not match:
            self.parse_errors += 1
            return None
        
        try:
            timestamp_str, delta_str, hostname, event_type, event_data_str = match.groups()
            
            # Parse timestamp
            timestamp = self._parse_timestamp(timestamp_str)
            if self.base_timestamp is None:
                self.base_timestamp = timestamp
            
            # Extract event data fields
            event_data = self._parse_event_data(event_data_str)
            
            # Update context tracking from scheduling events
            self._update_context(event_type, event_data)
            
            # Extract common fields with context enrichment
            cpu_id = int(event_data.get('cpu_id', -1))
            
            # Try to get context from event data first
            pid = event_data.get('pid', event_data.get('vpid', event_data.get('parent_pid', None)))
            tid = event_data.get('tid', event_data.get('vtid', event_data.get('child_tid', None)))
            comm = event_data.get('procname', event_data.get('comm', event_data.get('child_comm', None)))
            
            # If not in event data, look up from context tracking
            if tid is None:
                # For some events, tid might be in different fields
                tid = event_data.get('next_tid', event_data.get('prev_tid', None))
            
            # If still no tid, use CPU context (current thread on this CPU)
            if tid is None and cpu_id >= 0 and cpu_id in self.cpu_context:
                tid = self.cpu_context[cpu_id]
            
            # Look up pid/comm from tid context if we have tid but not pid/comm
            if isinstance(tid, int) and tid in self.tid_context:
                context_pid, context_comm = self.tid_context[tid]
                if pid is None:
                    pid = context_pid
                if comm is None:
                    comm = context_comm
            
            # Convert to proper types with defaults
            pid = int(pid) if pid is not None else -1
            tid = int(tid) if tid is not None else -1
            process_name = str(comm) if comm is not None else 'unknown'
            
            # Clean up process name (remove quotes if present)
            if isinstance(process_name, str):
                process_name = process_name.strip('"').strip("'")
            
            return KernelEvent(
                timestamp=timestamp,
                cpu_id=cpu_id,
                event_type=event_type,
                process_name=process_name,
                pid=pid,
                tid=tid,
                event_data=event_data,
                raw_line=line
            )
            
        except Exception as e:
            self.parse_errors += 1
            logger.debug(f"Failed to parse line: {str(e)[:100]}")
            return None
    
    def _update_context(self, event_type: str, event_data: Dict) -> None:
        """
        Update tid->pid/comm context mapping from scheduling events.
        
        LTTng syscall events don't include pid/tid/comm context, but scheduling
        events do. This method extracts context from sched_* events to build
        a lookup table for enriching syscalls.
        
        Args:
            event_type: Type of kernel event
            event_data: Parsed event data fields
        """
        try:
            # sched_process_fork: child process creation
            if event_type == 'sched_process_fork':
                child_tid = event_data.get('child_tid')
                child_pid = event_data.get('child_pid')
                child_comm = event_data.get('child_comm')
                if child_tid is not None and child_pid is not None and child_comm is not None:
                    self.tid_context[int(child_tid)] = (int(child_pid), str(child_comm).strip('"').strip("'"))
                    self.context_updates += 1
                
                # Also track parent
                parent_tid = event_data.get('parent_tid')
                parent_pid = event_data.get('parent_pid')
                parent_comm = event_data.get('parent_comm')
                if parent_tid is not None and parent_pid is not None and parent_comm is not None:
                    self.tid_context[int(parent_tid)] = (int(parent_pid), str(parent_comm).strip('"').strip("'"))
                    self.context_updates += 1
            
            # sched_switch: context switch between threads
            elif event_type == 'sched_switch':
                # Update CPU context: which thread is now running on this CPU
                cpu_id = event_data.get('cpu_id')
                next_tid = event_data.get('next_tid')
                if cpu_id is not None and next_tid is not None:
                    self.cpu_context[int(cpu_id)] = int(next_tid)
                
                # Track next (incoming) thread
                next_comm = event_data.get('next_comm')
                if next_tid is not None and next_comm is not None:
                    next_tid = int(next_tid)
                    next_comm = str(next_comm).strip('"').strip("'")
                    # If we don't have pid, use tid as pid (common for single-threaded)
                    if next_tid not in self.tid_context:
                        self.tid_context[next_tid] = (next_tid, next_comm)
                        self.context_updates += 1
                    else:
                        # Update comm if changed (exec can change it)
                        old_pid, old_comm = self.tid_context[next_tid]
                        if old_comm != next_comm:
                            self.tid_context[next_tid] = (old_pid, next_comm)
                            self.context_updates += 1
                
                # Track prev (outgoing) thread
                prev_tid = event_data.get('prev_tid')
                prev_comm = event_data.get('prev_comm')
                if prev_tid is not None and prev_comm is not None:
                    prev_tid = int(prev_tid)
                    prev_comm = str(prev_comm).strip('"').strip("'")
                    if prev_tid not in self.tid_context:
                        self.tid_context[prev_tid] = (prev_tid, prev_comm)
                        self.context_updates += 1
            
            # sched_waking, sched_wakeup: thread wakeup events
            elif event_type in ('sched_waking', 'sched_wakeup'):
                tid = event_data.get('tid')
                comm = event_data.get('comm')
                if tid is not None and comm is not None:
                    tid = int(tid)
                    comm = str(comm).strip('"').strip("'")
                    if tid not in self.tid_context:
                        self.tid_context[tid] = (tid, comm)
                        self.context_updates += 1
            
            # sched_stat_runtime, sched_stat_sleep, etc.: thread statistics
            elif event_type.startswith('sched_stat_'):
                tid = event_data.get('tid')
                comm = event_data.get('comm')
                if tid is not None and comm is not None:
                    tid = int(tid)
                    comm = str(comm).strip('"').strip("'")
                    if tid not in self.tid_context:
                        self.tid_context[tid] = (tid, comm)
                        self.context_updates += 1
            
            # sched_process_exec: exec system call changes comm
            elif event_type == 'sched_process_exec':
                tid = event_data.get('tid')
                filename = event_data.get('filename')
                if tid is not None and filename is not None:
                    tid = int(tid)
                    # Extract comm from filename (basename without path)
                    comm = str(filename).split('/')[-1].strip('"').strip("'")
                    # Update with new comm
                    old_context = self.tid_context.get(tid, (tid, comm))
                    self.tid_context[tid] = (old_context[0], comm)
                    self.context_updates += 1
        
        except Exception as e:
            # Don't fail parsing if context update fails
            logger.debug(f"Context update error for {event_type}: {e}")
            pass
    
    def _parse_timestamp(self, timestamp_str: str) -> float:
        """
        Convert timestamp string to float seconds.
        
        Args:
            timestamp_str: Timestamp in format HH:MM:SS.nnnnnnnnn
            
        Returns:
            Timestamp as float seconds since midnight
        """
        parts = timestamp_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        
        return hours * 3600 + minutes * 60 + seconds
    
    def _parse_event_data(self, data_str: str) -> Dict[str, any]:
        """
        Parse event data fields into dictionary.
        
        Args:
            data_str: Event data string containing key=value pairs
            
        Returns:
            Dictionary of parsed fields
        """
        data = {}
        
        # Extract all field=value pairs
        for match in self.FIELD_PATTERN.finditer(data_str):
            key = match.group(1)
            value = match.group(2).strip()
            
            # Try to convert to appropriate type
            try:
                # Try integer
                if value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
                    value = int(value)
                # Try float
                elif '.' in value and value.replace('.', '').replace('-', '').isdigit():
                    value = float(value)
                # Try hex
                elif value.startswith('0x'):
                    value = int(value, 16)
                # Keep as string (remove quotes)
                else:
                    value = value.strip('"').strip("'")
            except:
                pass
            
            data[key] = value
        
        return data
    
    def get_syscall_events(self) -> List[KernelEvent]:
        """Filter events to return only syscall events."""
        return [e for e in self.events if 'syscall_entry' in e.event_type or 'syscall_exit' in e.event_type]
    
    def get_sched_events(self) -> List[KernelEvent]:
        """Filter events to return only scheduling events."""
        return [e for e in self.events if 'sched_' in e.event_type]
    
    def get_events_by_type(self, event_type: str) -> List[KernelEvent]:
        """Filter events by specific type."""
        return [e for e in self.events if event_type in e.event_type]
    
    def get_events_by_pid(self, pid: int) -> List[KernelEvent]:
        """Filter events by process ID."""
        return [e for e in self.events if e.pid == pid]
    
    def get_events_by_tid(self, tid: int) -> List[KernelEvent]:
        """Filter events by thread ID."""
        return [e for e in self.events if e.tid == tid]
    
    def get_time_range(self) -> tuple:
        """Get the time range of parsed events."""
        if not self.events:
            return (0.0, 0.0)
        return (self.events[0].timestamp, self.events[-1].timestamp)
    
    def get_statistics(self) -> Dict[str, any]:
        """Get parsing statistics."""
        event_types = {}
        for event in self.events:
            event_types[event.event_type] = event_types.get(event.event_type, 0) + 1
        
        return {
            'total_lines': self.total_lines,
            'total_events': len(self.events),
            'parse_errors': self.parse_errors,
            'success_rate': (1 - self.parse_errors/max(self.total_lines, 1)) * 100,
            'unique_event_types': len(event_types),
            'event_type_distribution': event_types,
            'time_range_seconds': self.get_time_range()[1] - self.get_time_range()[0] if self.events else 0
        }


def main():
    """Test the trace parser independently."""
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 2:
        print("Usage: python trace_parser.py <trace_file>")
        sys.exit(1)
    
    trace_file = Path(sys.argv[1])
    if not trace_file.exists():
        print(f"Error: Trace file not found: {trace_file}")
        sys.exit(1)
    
    parser = TraceParser(trace_file)
    events = parser.parse()
    
    stats = parser.get_statistics()
    print("\nParsing Statistics:")
    print(f"  Total lines: {stats['total_lines']}")
    print(f"  Total events: {stats['total_events']}")
    print(f"  Parse errors: {stats['parse_errors']}")
    print(f"  Success rate: {stats['success_rate']:.1f}%")
    print(f"  Unique event types: {stats['unique_event_types']}")
    print(f"  Time range: {stats['time_range_seconds']:.2f} seconds")
    
    print("\nTop 10 Event Types:")
    sorted_types = sorted(stats['event_type_distribution'].items(), key=lambda x: x[1], reverse=True)
    for event_type, count in sorted_types[:10]:
        print(f"  {event_type}: {count}")


if __name__ == "__main__":
    main()
