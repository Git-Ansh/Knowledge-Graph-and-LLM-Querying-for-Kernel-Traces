"""
Entity Extractor Module
=======================
Extracts kernel reality layer entities from parsed trace events.

This module builds the "actors" in the knowledge graph:
- Processes
- Threads
- Files
- Sockets
- CPUs

Author: Knowledge Graph and LLM Querying for Kernel Traces Project
Date: October 3, 2025
"""

import logging
import json
from pathlib import Path
from typing import List, Dict, Set, Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict

from trace_parser import KernelEvent

logger = logging.getLogger(__name__)


@dataclass
class Process:
    """Represents a process in the kernel reality layer."""
    pid: int
    name: str
    start_time: float
    cmdline: Optional[str] = None
    parent_pid: Optional[int] = None
    end_time: Optional[float] = None
    thread_count: int = 0
    
    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Thread:
    """Represents a thread in the kernel reality layer."""
    tid: int
    pid: int
    start_time: float
    name: Optional[str] = None
    end_time: Optional[float] = None
    cpu_affinity: Optional[List[int]] = None
    
    def to_dict(self):
        data = {k: v for k, v in asdict(self).items() if v is not None}
        if self.cpu_affinity:
            data['cpu_affinity'] = self.cpu_affinity
        return data


@dataclass
class File:
    """Represents a file resource in the kernel reality layer."""
    path: str
    file_type: str = "file"
    inode: Optional[int] = None
    first_access: Optional[float] = None
    last_access: Optional[float] = None
    access_count: int = 0
    
    def to_dict(self):
        data = asdict(self)
        data['type'] = data.pop('file_type')
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class Socket:
    """Represents a network socket in the kernel reality layer."""
    socket_id: str  # Unique identifier: socket_<pid>_<timestamp>
    address: str
    port: int
    protocol: str
    family: Optional[str] = None
    socket_type: Optional[str] = None
    remote_address: Optional[str] = None
    remote_port: Optional[int] = None
    first_access: Optional[float] = None
    
    def to_dict(self):
        data = asdict(self)
        if 'socket_type' in data:
            data['type'] = data.pop('socket_type')
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class CPU:
    """Represents a CPU core in the kernel reality layer."""
    cpu_id: int
    event_count: int = 0
    
    def to_dict(self):
        return asdict(self)


class EntityExtractor:
    """Extracts kernel reality layer entities from trace events."""
    
    def __init__(self, events: List[KernelEvent]):
        """
        Initialize entity extractor.
        
        Args:
            events: List of parsed kernel events
        """
        self.events = events
        self.processes: Dict[int, Process] = {}
        self.threads: Dict[int, Thread] = {}
        self.files: Dict[str, File] = {}
        self.sockets: Dict[str, Socket] = {}
        self.cpus: Dict[int, CPU] = {}
        
        # Tracking structures
        self.pid_to_threads: Dict[int, Set[int]] = defaultdict(set)
        self.fd_to_file: Dict[tuple, str] = {}  # (pid, fd) -> file_path
        self.fd_to_socket: Dict[tuple, str] = {}  # (pid, fd) -> socket_key
        
        logger.info(f"Initialized EntityExtractor with {len(events)} events")
    
    def extract_all(self) -> Dict[str, any]:
        """
        Extract all entities from trace events.
        
        Returns:
            Dictionary containing all extracted entities
        """
        logger.info("Starting entity extraction")
        
        # Extract in order of dependency
        self._extract_processes_and_threads()
        self._extract_cpus()
        self._extract_files()
        self._extract_sockets()
        self._link_threads_to_processes()
        
        logger.info(f"Extraction complete:")
        logger.info(f"  Processes: {len(self.processes)}")
        logger.info(f"  Threads: {len(self.threads)}")
        logger.info(f"  Files: {len(self.files)}")
        logger.info(f"  Sockets: {len(self.sockets)}")
        logger.info(f"  CPUs: {len(self.cpus)}")
        
        return {
            'processes': list(self.processes.values()),
            'threads': list(self.threads.values()),
            'files': list(self.files.values()),
            'sockets': list(self.sockets.values()),
            'cpus': list(self.cpus.values())
        }
    
    def _extract_processes_and_threads(self):
        """Extract process and thread entities from events."""
        logger.info("Extracting processes and threads")
        
        for event in self.events:
            # Track process
            if event.pid > 0 and event.pid not in self.processes:
                self.processes[event.pid] = Process(
                    pid=event.pid,
                    name=event.process_name,
                    start_time=event.timestamp
                )
            
            # Update process end time
            if event.pid in self.processes:
                self.processes[event.pid].end_time = event.timestamp
            
            # Track thread
            if event.tid > 0 and event.tid not in self.threads:
                self.threads[event.tid] = Thread(
                    tid=event.tid,
                    pid=event.pid,
                    name=event.process_name,
                    start_time=event.timestamp
                )
                self.pid_to_threads[event.pid].add(event.tid)
            
            # Update thread end time
            if event.tid in self.threads:
                self.threads[event.tid].end_time = event.timestamp
            
            # Handle process creation events
            if 'sched_process_fork' in event.event_type:
                parent_pid = event.event_data.get('parent_pid', event.pid)
                child_pid = event.event_data.get('child_pid')
                if child_pid and child_pid in self.processes:
                    self.processes[child_pid].parent_pid = parent_pid
        
        logger.info(f"Extracted {len(self.processes)} processes and {len(self.threads)} threads")
    
    def _extract_cpus(self):
        """Extract CPU entities from events."""
        logger.info("Extracting CPUs")
        
        for event in self.events:
            if event.cpu_id >= 0:
                if event.cpu_id not in self.cpus:
                    self.cpus[event.cpu_id] = CPU(cpu_id=event.cpu_id)
                self.cpus[event.cpu_id].event_count += 1
        
        logger.info(f"Extracted {len(self.cpus)} CPUs")
    
    def _extract_files(self):
        """Extract file entities from syscall events."""
        logger.info("Extracting files")
        
        for event in self.events:
            # File open syscalls
            if 'syscall_entry_open' in event.event_type or 'syscall_entry_openat' in event.event_type:
                filename = event.event_data.get('filename', event.event_data.get('pathname'))
                if filename and isinstance(filename, str):
                    filename = filename.strip('"').strip("'")
                    
                    if filename not in self.files:
                        self.files[filename] = File(
                            path=filename,
                            file_type='file',
                            first_access=event.timestamp
                        )
                    
                    self.files[filename].last_access = event.timestamp
                    self.files[filename].access_count += 1
            
            # File open exit - track fd to file mapping
            elif 'syscall_exit_open' in event.event_type or 'syscall_exit_openat' in event.event_type:
                ret = event.event_data.get('ret')
                if ret and ret >= 0:
                    # Need to correlate with previous entry event to get filename
                    # This is handled in event sequence processing
                    pass
            
            # Read/write syscalls - track file access
            elif any(sc in event.event_type for sc in ['syscall_entry_read', 'syscall_entry_write', 
                                                         'syscall_entry_pread', 'syscall_entry_pwrite']):
                fd = event.event_data.get('fd')
                if fd is not None and fd >= 0:
                    fd_key = (event.pid, fd)
                    if fd_key in self.fd_to_file:
                        filename = self.fd_to_file[fd_key]
                        if filename in self.files:
                            self.files[filename].last_access = event.timestamp
                            self.files[filename].access_count += 1
        
        logger.info(f"Extracted {len(self.files)} files")
    
    def _extract_sockets(self):
        """Extract socket entities from network syscall events."""
        logger.info("Extracting sockets")
        
        for event in self.events:
            # Socket creation
            if 'syscall_entry_socket' in event.event_type:
                family = event.event_data.get('family', 'unknown')
                sock_type = event.event_data.get('type', 'unknown')
                protocol = event.event_data.get('protocol', 0)
                
                # Create placeholder socket
                socket_key = f"socket_{event.pid}_{event.timestamp}"
                if socket_key not in self.sockets:
                    self.sockets[socket_key] = Socket(
                        socket_id=socket_key,
                        address='0.0.0.0',
                        port=0,
                        protocol=str(protocol),
                        family=str(family),
                        socket_type=str(sock_type),
                        first_access=event.timestamp
                    )
            
            # Socket bind
            elif 'syscall_entry_bind' in event.event_type:
                # Extract address and port if available
                pass
            
            # Socket connect
            elif 'syscall_entry_connect' in event.event_type:
                # Extract remote address and port if available
                pass
        
        logger.info(f"Extracted {len(self.sockets)} sockets")
    
    def _link_threads_to_processes(self):
        """Update process thread counts."""
        for pid, thread_ids in self.pid_to_threads.items():
            if pid in self.processes:
                self.processes[pid].thread_count = len(thread_ids)
    
    def save_entities(self, output_dir: Path):
        """
        Save extracted entities to JSON files.
        
        Args:
            output_dir: Directory to save entity files
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Saving entities to {output_dir}")
        
        # Save each entity type
        entities = {
            'processes': [p.to_dict() for p in self.processes.values()],
            'threads': [t.to_dict() for t in self.threads.values()],
            'files': [f.to_dict() for f in self.files.values()],
            'sockets': [s.to_dict() for s in self.sockets.values()],
            'cpus': [c.to_dict() for c in self.cpus.values()]
        }
        
        for entity_type, entity_list in entities.items():
            output_file = output_dir / f"{entity_type}.json"
            with open(output_file, 'w') as f:
                json.dump(entity_list, f, indent=2)
            logger.info(f"  Saved {len(entity_list)} {entity_type} to {output_file.name}")
        
        # Save summary
        summary = {
            'total_events': len(self.events),
            'entity_counts': {k: len(v) for k, v in entities.items()},
            'extraction_metadata': {
                'time_range': self._get_time_range(),
                'unique_pids': len(self.processes),
                'unique_tids': len(self.threads)
            }
        }
        
        summary_file = output_dir / "extraction_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        logger.info(f"  Saved extraction summary to {summary_file.name}")
    
    def _get_time_range(self) -> Dict[str, float]:
        """Get the time range of events."""
        if not self.events:
            return {'start': 0.0, 'end': 0.0, 'duration': 0.0}
        
        start = self.events[0].timestamp
        end = self.events[-1].timestamp
        return {'start': start, 'end': end, 'duration': end - start}


def main():
    """Test the entity extractor independently."""
    import sys
    from trace_parser import TraceParser
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 2:
        print("Usage: python entity_extractor.py <trace_file>")
        sys.exit(1)
    
    trace_file = Path(sys.argv[1])
    if not trace_file.exists():
        print(f"Error: Trace file not found: {trace_file}")
        sys.exit(1)
    
    # Parse trace
    parser = TraceParser(trace_file)
    events = parser.parse()
    
    # Extract entities
    extractor = EntityExtractor(events)
    entities = extractor.extract_all()
    
    # Save entities
    output_dir = Path("outputs/processed_entities")
    extractor.save_entities(output_dir)
    
    print("\nEntity Extraction Complete:")
    for entity_type, entity_list in entities.items():
        print(f"  {entity_type}: {len(entity_list)}")


if __name__ == "__main__":
    main()
