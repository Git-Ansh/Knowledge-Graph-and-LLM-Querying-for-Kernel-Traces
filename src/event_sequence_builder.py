"""
Event Sequence Builder Module
==============================
Groups individual kernel events into EventSequence nodes.

This module implements the core "action grouping" logic:
- Groups related syscalls into logical operation sequences
- Creates EventSequence nodes with complete event streams
- Maintains temporal and causal ordering
- Applies schema-defined grouping rules

Author: Knowledge Graph and LLM Querying for Kernel Traces Project
Date: October 3, 2025
"""

import logging
import json
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict

from trace_parser import KernelEvent

logger = logging.getLogger(__name__)


@dataclass
class EventSequence:
    """Represents a sequence of related kernel events forming a logical operation."""
    sequence_id: str
    operation: str
    start_time: float
    end_time: float
    count: int
    event_stream: List[Dict[str, any]]
    entity_target: Optional[str] = None
    return_value: Optional[int] = None
    bytes_transferred: Optional[int] = 0
    thread_id: Optional[int] = None
    process_id: Optional[int] = None
    cpu_id: Optional[int] = None
    
    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000
    
    def to_dict(self):
        data = asdict(self)
        data['duration_ms'] = self.duration_ms
        return data


class EventSequenceBuilder:
    """Builds EventSequence nodes by grouping related kernel events."""
    
    # Syscall grouping configuration
    GROUPING_RULES = {
        'read': {
            'syscalls': ['read', 'pread64', 'readv', 'preadv', 'pread'],
            'group_by': ['tid', 'fd'],
            'time_gap_ms': 100
        },
        'write': {
            'syscalls': ['write', 'pwrite64', 'writev', 'pwritev', 'pwrite'],
            'group_by': ['tid', 'fd'],
            'time_gap_ms': 100
        },
        'open': {
            'syscalls': ['open', 'openat', 'openat2'],
            'group_by': ['tid'],
            'time_gap_ms': 10,
            'immediate': True  # Each open is separate
        },
        'socket': {
            'syscalls': ['socket'],
            'group_by': ['tid'],
            'time_gap_ms': 10,
            'immediate': True  # Each socket creation is separate
        },
        'close': {
            'syscalls': ['close'],
            'group_by': ['tid'],
            'time_gap_ms': 10,
            'immediate': True
        },
        'socket_send': {
            'syscalls': ['send', 'sendto', 'sendmsg', 'sendmmsg', 'write'],
            'group_by': ['tid', 'socket_fd'],
            'time_gap_ms': 50
        },
        'socket_recv': {
            'syscalls': ['recv', 'recvfrom', 'recvmsg', 'recvmmsg', 'read'],
            'group_by': ['tid', 'socket_fd'],
            'time_gap_ms': 50
        },
        'mmap': {
            'syscalls': ['mmap', 'mmap2', 'munmap', 'mremap'],
            'group_by': ['tid'],
            'time_gap_ms': 50
        }
    }
    
    def __init__(self, events: List[KernelEvent], schema_config: Optional[Dict] = None, trace_dir: Optional[Path] = None):
        """
        Initialize event sequence builder.
        
        Args:
            events: List of parsed kernel events
            schema_config: Optional schema configuration for grouping rules
            trace_dir: Optional path to trace directory (for loading initial FD state)
        """
        self.events = events
        self.sequences: List[EventSequence] = []
        self.sequence_counter = 0
        
        # Time-aware file descriptor tracking: (pid, fd) -> List[(start_time, end_time, path)]
        # Tracks FD lifecycle with temporal ranges to handle FD reuse correctly
        # end_time=None means FD is still open
        self.fd_map: Dict[tuple, List[tuple]] = {}  # (pid, fd) -> [(start, end, path), ...]
        self.fd_mappings_created = 0
        self.fd_mappings_resolved = 0
        self.fd_mappings_cleaned = 0
        self.fd_mappings_from_lsof = 0
        
        # Load grouping rules from schema if provided
        if schema_config and 'processing_rules' in schema_config:
            self._load_schema_rules(schema_config['processing_rules'])
        
        # Load initial FD state from lsof if available
        if trace_dir:
            self._load_initial_fd_state(trace_dir)
        
        logger.info(f"Initialized EventSequenceBuilder with {len(events)} events")
    
    def _load_schema_rules(self, processing_rules: Dict):
        """Load grouping rules from schema configuration."""
        if 'event_grouping' in processing_rules:
            rules_data = processing_rules['event_grouping'].get('rules', [])
            logger.info(f"Loading {len(rules_data)} grouping rules from schema")
            
            for rule in rules_data:
                operation = rule['operation']
                self.GROUPING_RULES[operation] = {
                    'syscalls': rule['syscalls'],
                    'group_by': rule['group_by'],
                    'time_gap_ms': 100  # Default
                }
    
    def _parse_lsof_output(self, raw_output: str) -> Dict[tuple, str]:
        """
        Parse lsof -Fn output format into FD mappings.
        
        Format:
            p<PID>      - Process ID
            f<FD>       - File descriptor number
            n<NAME>     - File/socket name
        
        Args:
            raw_output: Raw lsof -Fn output
            
        Returns:
            Dict mapping (pid, fd) -> file_path/socket_name
        """
        fd_mappings = {}
        current_pid = None
        current_fd = None
        
        for line in raw_output.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('p'):
                # Process ID
                try:
                    current_pid = int(line[1:])
                except ValueError:
                    logger.debug(f"Could not parse PID from: {line}")
                    current_pid = None
            
            elif line.startswith('f'):
                # File descriptor - only numeric FDs
                fd_str = line[1:]
                try:
                    current_fd = int(fd_str)
                except ValueError:
                    # Skip non-numeric FDs (cwd, txt, mem, rtd, etc.)
                    current_fd = None
            
            elif line.startswith('n') and current_pid is not None and current_fd is not None:
                # File/socket name
                file_path = line[1:]
                
                # Only store real paths or sockets (no special types)
                if file_path and not file_path.startswith('type='):
                    key = (current_pid, current_fd)
                    fd_mappings[key] = file_path
        
        return fd_mappings
    
    def _load_initial_fd_state(self, trace_dir: Path):
        """
        Load initial FD state from lsof snapshot and pre-populate fd_map.
        
        Args:
            trace_dir: Path to trace directory containing initial_fd_state.json
        """
        fd_state_file = trace_dir / 'initial_fd_state.json'
        
        if not fd_state_file.exists():
            logger.info("No initial FD state file found - skipping lsof integration")
            return
        
        try:
            with open(fd_state_file, 'r') as f:
                lsof_data = json.load(f)
            
            # Parse each process's lsof output
            all_fd_mappings = {}
            for pid_str, raw_output in lsof_data.items():
                fd_mappings = self._parse_lsof_output(raw_output)
                all_fd_mappings.update(fd_mappings)
            
            # Pre-populate fd_map with lsof data
            # Use timestamp 0.0 as start (before trace) and None as end (still open)
            for (pid, fd), file_path in all_fd_mappings.items():
                key = (pid, fd)
                if key not in self.fd_map:
                    self.fd_map[key] = []
                
                # Add lsof mapping with timestamp 0.0 (pre-trace)
                # This will be overridden if we see an open() during trace
                self.fd_map[key].append((0.0, None, file_path))
                self.fd_mappings_from_lsof += 1
            
            logger.info(f"Loaded {len(all_fd_mappings)} FD mappings from lsof initial state")
            logger.info(f"Pre-populated fd_map with {self.fd_mappings_from_lsof} entries")
            
        except Exception as e:
            logger.warning(f"Failed to load initial FD state: {e}")
            logger.debug(f"Error details: {e}", exc_info=True)
    
    def build_sequences(self) -> List[EventSequence]:
        """
        Build event sequences from kernel events.
        
        Returns:
            List of EventSequence objects
        """
        logger.info("Building event sequences")
        
        # First pass: Group syscall entry/exit pairs and build fd map
        syscall_pairs = self._pair_syscalls()
        logger.info(f"Paired {len(syscall_pairs)} syscall entry/exit events")
        logger.info(f"FD map built: {len(self.fd_map)} active mappings")
        
        # Second pass: Group pairs into sequences (now fd_map is populated)
        for operation, rule in self.GROUPING_RULES.items():
            operation_sequences = self._group_by_rule(syscall_pairs, operation, rule)
            self.sequences.extend(operation_sequences)
            logger.debug(f"Created {len(operation_sequences)} sequences for operation: {operation}")
        
        # Sort sequences by start time
        self.sequences.sort(key=lambda s: s.start_time)
        
        logger.info(f"Built {len(self.sequences)} event sequences")
        logger.info(f"FD tracking: {self.fd_mappings_from_lsof} from lsof, {self.fd_mappings_created} from trace, {self.fd_mappings_resolved} resolved, {self.fd_mappings_cleaned} closed")
        return self.sequences
    
    def _pair_syscalls(self) -> List[Dict[str, any]]:
        """
        Pair syscall entry and exit events.
        Also updates fd→file mappings from open/close syscalls.
        
        Returns:
            List of paired syscall dictionaries
        """
        pairs = []
        pending_entries = {}  # (tid, syscall_name) -> entry_event
        
        for event in self.events:
            if 'syscall_entry' in event.event_type:
                # Extract syscall name
                syscall_name = event.event_type.replace('syscall_entry_', '')
                key = (event.tid, syscall_name)
                pending_entries[key] = event
                
            elif 'syscall_exit' in event.event_type:
                # Extract syscall name
                syscall_name = event.event_type.replace('syscall_exit_', '')
                key = (event.tid, syscall_name)
                
                if key in pending_entries:
                    entry_event = pending_entries.pop(key)
                    
                    # Create paired syscall
                    pair = {
                        'syscall_name': syscall_name,
                        'tid': event.tid,
                        'pid': event.pid,
                        'process_name': event.process_name,
                        'cpu_id': event.cpu_id,
                        'start_time': entry_event.timestamp,
                        'end_time': event.timestamp,
                        'duration': event.timestamp - entry_event.timestamp,
                        'entry_data': entry_event.event_data,
                        'exit_data': event.event_data,
                        'return_value': event.event_data.get('ret', None)
                    }
                    pairs.append(pair)
                    
                    # Update fd→file mapping for open/close syscalls
                    self._update_fd_mapping(pair)
        
        return pairs
    
    def _group_by_rule(self, syscall_pairs: List[Dict], operation: str, rule: Dict) -> List[EventSequence]:
        """
        Group syscall pairs into sequences based on a rule.
        
        Args:
            syscall_pairs: List of paired syscalls
            operation: Operation name
            rule: Grouping rule configuration
            
        Returns:
            List of EventSequence objects for this operation
        """
        sequences = []
        
        # Filter syscalls matching this operation
        matching_pairs = [
            p for p in syscall_pairs 
            if p['syscall_name'] in rule['syscalls']
        ]
        
        if not matching_pairs:
            return sequences
        
        # Group by key (e.g., tid + fd)
        groups = defaultdict(list)
        for pair in matching_pairs:
            # Build grouping key
            key_parts = []
            for key_field in rule['group_by']:
                if key_field == 'fd':
                    fd = pair['entry_data'].get('fd')
                    key_parts.append(str(fd) if fd is not None else 'no_fd')
                elif key_field == 'socket_fd':
                    fd = pair['entry_data'].get('fd')
                    key_parts.append(str(fd) if fd is not None else 'no_fd')
                else:
                    key_parts.append(str(pair.get(key_field, 'unknown')))
            
            group_key = ':'.join(key_parts)
            groups[group_key].append(pair)
        
        # Create sequences from groups
        time_gap_threshold = rule.get('time_gap_ms', 100) / 1000.0  # Convert to seconds
        immediate = rule.get('immediate', False)
        
        for group_key, group_pairs in groups.items():
            # Sort by time
            group_pairs.sort(key=lambda p: p['start_time'])
            
            if immediate:
                # Each syscall is its own sequence
                for pair in group_pairs:
                    sequence = self._create_sequence_from_pairs([pair], operation)
                    sequences.append(sequence)
            else:
                # Group consecutive syscalls within time gap
                current_batch = [group_pairs[0]]
                
                for pair in group_pairs[1:]:
                    time_gap = pair['start_time'] - current_batch[-1]['end_time']
                    
                    if time_gap <= time_gap_threshold:
                        current_batch.append(pair)
                    else:
                        # Create sequence from current batch
                        sequence = self._create_sequence_from_pairs(current_batch, operation)
                        sequences.append(sequence)
                        
                        # Start new batch
                        current_batch = [pair]
                
                # Create sequence from final batch
                if current_batch:
                    sequence = self._create_sequence_from_pairs(current_batch, operation)
                    sequences.append(sequence)
        
        return sequences
    
    def _create_sequence_from_pairs(self, pairs: List[Dict], operation: str) -> EventSequence:
        """
        Create an EventSequence from a list of syscall pairs.
        
        Args:
            pairs: List of paired syscalls
            operation: Operation name
            
        Returns:
            EventSequence object
        """
        self.sequence_counter += 1
        sequence_id = f"seq_{operation}_{self.sequence_counter}"
        
        # Aggregate data
        start_time = pairs[0]['start_time']
        end_time = pairs[-1]['end_time']
        count = len(pairs)
        
        # Calculate bytes transferred
        bytes_transferred = 0
        for pair in pairs:
            ret_val = pair.get('return_value')
            if ret_val and ret_val > 0:
                bytes_transferred += ret_val
        
        # Determine entity target with fd resolution
        entity_target = None
        if pairs[0]['entry_data'].get('filename'):
            entity_target = pairs[0]['entry_data']['filename']
        elif pairs[0]['entry_data'].get('pathname'):
            entity_target = pairs[0]['entry_data']['pathname']
        elif operation == 'socket':
            # For socket() syscalls, the fd is the return value
            # The entity_target is the socket_id we stored in fd_map
            return_val = pairs[0].get('return_value')
            if return_val is not None and return_val >= 0:
                pid = pairs[0]['pid']
                op_time = pairs[0]['start_time']
                resolved_socket = self._resolve_fd(pid, return_val, op_time)
                if resolved_socket:
                    entity_target = resolved_socket
                    self.fd_mappings_resolved += 1
        elif pairs[0]['entry_data'].get('fd') is not None:
            # Try to resolve fd to file path or socket_id using operation time
            fd = pairs[0]['entry_data']['fd']
            pid = pairs[0]['pid']
            op_time = pairs[0]['start_time']  # Use start time of operation
            resolved_path = self._resolve_fd(pid, fd, op_time)
            if resolved_path:
                entity_target = resolved_path
                self.fd_mappings_resolved += 1
            else:
                entity_target = f"fd:{fd}"
        
        # Build event stream (simplified representation)
        event_stream = []
        for pair in pairs:
            event_obj = {
                'timestamp': pair['start_time'],
                'syscall': pair['syscall_name'],
                'duration': pair['duration'],
                'return_value': pair['return_value'],
                'key_params': {
                    k: v for k, v in pair['entry_data'].items()
                    if k in ['fd', 'count', 'buf', 'flags', 'offset']
                }
            }
            event_stream.append(event_obj)
        
        return EventSequence(
            sequence_id=sequence_id,
            operation=operation,
            start_time=start_time,
            end_time=end_time,
            count=count,
            event_stream=event_stream,
            entity_target=entity_target,
            return_value=pairs[-1].get('return_value'),
            bytes_transferred=bytes_transferred,
            thread_id=pairs[0]['tid'],
            process_id=pairs[0]['pid'],
            cpu_id=pairs[0]['cpu_id']
        )
    
    def _update_fd_mapping(self, pair: Dict):
        """
        Update fd→file/socket mapping from open/close/socket syscalls.
        
        Args:
            pair: Syscall pair dictionary
        """
        syscall_name = pair['syscall_name']
        pid = pair['pid']
        return_value = pair.get('return_value')
        
        # Handle open/openat syscalls - create fd→file mapping
        if syscall_name in ['open', 'openat', 'openat2']:
            # Return value is the fd (if >= 0)
            if return_value is not None and return_value >= 0:
                fd = return_value
                # Get filename from entry parameters
                filename = pair['entry_data'].get('filename')
                if filename:
                    # Clean up filename (remove quotes if present)
                    if isinstance(filename, str):
                        filename = filename.strip('"').strip("'")
                    
                    # Store temporal mapping: (start_time, end_time, path)
                    key = (pid, fd)
                    if key not in self.fd_map:
                        self.fd_map[key] = []
                    # Append new mapping with start time, end_time=None (still open)
                    self.fd_map[key].append((pair['start_time'], None, filename))
                    self.fd_mappings_created += 1
        
        # Handle socket syscalls - create fd→socket_id mapping
        elif syscall_name == 'socket':
            # Return value is the socket fd (if >= 0)
            if return_value is not None and return_value >= 0:
                fd = return_value
                # Create socket_id similar to entity_extractor
                # Format: socket_<pid>_<timestamp>
                socket_id = f"socket_{pid}_{pair['start_time']}"
                
                # Store temporal mapping: (start_time, end_time, socket_id)
                key = (pid, fd)
                if key not in self.fd_map:
                    self.fd_map[key] = []
                # Append new mapping with start time, end_time=None (still open)
                self.fd_map[key].append((pair['start_time'], None, socket_id))
                self.fd_mappings_created += 1
        
        # Handle close syscalls - mark the active mapping as closed
        elif syscall_name == 'close':
            fd = pair['entry_data'].get('fd')
            return_value = pair.get('return_value')
            # Only mark closed if close succeeded (return value 0)
            if fd is not None and return_value == 0:
                key = (pid, fd)
                if key in self.fd_map and self.fd_map[key]:
                    # Find the most recent open mapping (end_time=None)
                    for i in range(len(self.fd_map[key]) - 1, -1, -1):
                        start, end, path = self.fd_map[key][i]
                        if end is None:  # This mapping is still open
                            # Update it with close time
                            self.fd_map[key][i] = (start, pair['end_time'], path)
                            self.fd_mappings_cleaned += 1
                            break
    
    def _resolve_fd(self, pid: int, fd: int, op_time: float) -> Optional[str]:
        """
        Resolve a file descriptor to its file path or socket_id at a specific time.
        Uses temporal FD tracking to handle FD reuse correctly.
        
        Resolution order:
        1. Check runtime-captured open/socket syscalls (most accurate)
        2. Fall back to lsof initial state (for pre-trace FDs)
        
        Args:
            pid: Process ID
            fd: File descriptor number
            op_time: Timestamp of the operation using this FD
            
        Returns:
            File path or socket_id valid at op_time, None if not found
        """
        key = (pid, fd)
        if key not in self.fd_map:
            return None
        
        # Find mapping where: start_time <= op_time <= end_time (or end_time is None)
        # The list is ordered, with lsof entries (start_time=0.0) first,
        # then runtime entries in chronological order
        for start_time, end_time, path in self.fd_map[key]:
            if start_time <= op_time:
                if end_time is None or op_time <= end_time:
                    return path
        
        return None
    
    def save_sequences(self, output_dir: Path):
        """
        Save event sequences to JSON file.
        
        Args:
            output_dir: Directory to save sequences
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / "event_sequences.json"
        sequences_data = [seq.to_dict() for seq in self.sequences]
        
        with open(output_file, 'w') as f:
            json.dump(sequences_data, f, indent=2)
        
        logger.info(f"Saved {len(self.sequences)} event sequences to {output_file.name}")
        
        # Save summary statistics
        summary = self._generate_summary()
        summary_file = output_dir / "sequence_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Saved sequence summary to {summary_file.name}")
    
    def _generate_summary(self) -> Dict[str, any]:
        """Generate summary statistics for sequences."""
        operation_counts = defaultdict(int)
        operation_durations = defaultdict(list)
        total_bytes = 0
        
        for seq in self.sequences:
            operation_counts[seq.operation] += 1
            operation_durations[seq.operation].append(seq.duration_ms)
            total_bytes += seq.bytes_transferred or 0
        
        return {
            'total_sequences': len(self.sequences),
            'operations': dict(operation_counts),
            'total_bytes_transferred': total_bytes,
            'average_durations_ms': {
                op: sum(durations) / len(durations) if durations else 0
                for op, durations in operation_durations.items()
            }
        }
    
    def get_sequences_by_operation(self, operation: str) -> List[EventSequence]:
        """Get all sequences for a specific operation."""
        return [seq for seq in self.sequences if seq.operation == operation]
    
    def get_sequences_by_thread(self, tid: int) -> List[EventSequence]:
        """Get all sequences for a specific thread."""
        return [seq for seq in self.sequences if seq.thread_id == tid]


def main():
    """Test the event sequence builder independently."""
    import sys
    from trace_parser import TraceParser
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 2:
        print("Usage: python event_sequence_builder.py <trace_file>")
        sys.exit(1)
    
    trace_file = Path(sys.argv[1])
    if not trace_file.exists():
        print(f"Error: Trace file not found: {trace_file}")
        sys.exit(1)
    
    # Load schema
    schema_file = Path("schemas/layered_schema.json")
    schema_config = None
    if schema_file.exists():
        with open(schema_file, 'r') as f:
            schema_config = json.load(f)
    
    # Parse trace
    parser = TraceParser(trace_file)
    events = parser.parse()
    
    # Build sequences
    builder = EventSequenceBuilder(events, schema_config)
    sequences = builder.build_sequences()
    
    # Save sequences
    output_dir = Path("outputs/processed_entities")
    builder.save_sequences(output_dir)
    
    print(f"\nEvent Sequence Building Complete:")
    print(f"  Total sequences: {len(sequences)}")
    summary = builder._generate_summary()
    print(f"  Operations:")
    for op, count in summary['operations'].items():
        print(f"    {op}: {count}")


if __name__ == "__main__":
    main()
