#!/usr/bin/env python3
"""
Universal LTTng Kernel Trace Graph Builder

Constructs Neo4j property graph from processed LTTng trace entities.
Implements the universal schema for cross-application compatibility.

Features:
- Creates nodes for processes, threads, files, syscalls, etc.
- Establishes relationships with rich properties
- Optimized for Neo4j performance with constraints and indexes
- Supports hybrid model (statistical + temporal patterns)
- Handles large-scale trace data efficiently
"""

import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, ConstraintError
from schema_config_manager import SchemaConfigManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class GraphBuildStats:
    """Statistics for graph building process"""
    nodes_created: int = 0
    relationships_created: int = 0
    constraints_created: int = 0
    indexes_created: int = 0
    errors: int = 0
    processing_time: float = 0.0


class UniversalGraphBuilder:
    """Universal graph builder for LTTng kernel traces with modular schema support"""
    
    def __init__(self, uri: str = "bolt://localhost:7687", user: str = "neo4j", password: str = "sudoroot", schema_name: str = "universal_kernel"):
        """Initialize Neo4j connection and schema manager"""
        self.driver = None
        self.uri = uri
        self.user = user
        self.password = password
        self.stats = GraphBuildStats()
        
        # Initialize schema configuration manager
        self.schema_manager = SchemaConfigManager()
        self.schema_name = schema_name
        self.schema_config = self.schema_manager.get_schema(schema_name)
        
        if not self.schema_config:
            logger.warning(f"Schema '{schema_name}' not found, using default universal schema")
            self.schema_config = self.schema_manager.get_default_schema()
            self.schema_name = "universal_kernel"
        
        # Connect to database
        self._connect()
    
    def _connect(self) -> None:
        """Establish Neo4j connection"""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info(" Connected to Neo4j database")
        except Exception as e:
            logger.error(f" Failed to connect to Neo4j: {e}")
            raise
    
    def close(self) -> None:
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
            logger.info(" Neo4j connection closed")
    
    def clear_database(self) -> None:
        """Clear existing data from database"""
        logger.info(" Clearing database...")
        
        with self.driver.session() as session:
            # Simple approach - just delete all nodes and relationships
            try:
                session.run("MATCH (n) DETACH DELETE n")
                logger.info(" Database cleared")
            except Exception as e:
                logger.warning(f"Database clear warning: {e}")
                # Try alternative approach
                try:
                    session.run("CALL apoc.periodic.iterate('MATCH (n) RETURN n', 'DETACH DELETE n', {batchSize:1000})")
                except:
                    logger.warning("APOC not available, database may contain existing data")
    
    def create_schema(self) -> None:
        """Create Neo4j schema from selected schema configuration"""
        logger.info(f"  Creating database schema from '{self.schema_name}' schema...")
        
        if not self.schema_config:
            logger.error(" No valid schema configuration found")
            raise ValueError("No valid schema configuration found")
        
        schema_file = Path(self.schema_config.schema_file)
        if not schema_file.exists():
            logger.error(f" Schema file {schema_file} not found. Check schema configuration or generate schema file.")
            raise FileNotFoundError(f"Schema file {schema_file} not found")
        
        # Read the generated schema file
        with open(schema_file, 'r') as f:
            schema_content = f.read()
        
        # Handle escaped newlines and split into individual commands
        schema_content = schema_content.replace('\\n', '\n')
        
        # Split into individual commands (filter out comments and empty lines)
        schema_commands = []
        for line in schema_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('//') and not line.startswith('CALL db.constraints()') and not line.startswith('CALL apoc.util.map') and not line.startswith('CALL db.awaitIndexes'):
                if line.endswith(';'):
                    schema_commands.append(line[:-1])  # Remove semicolon
                elif line:
                    schema_commands.append(line)
        
        # Execute schema commands
        with self.driver.session() as session:
            for command in schema_commands:
                if not command.strip():
                    continue
                    
                try:
                    session.run(command)
                    if "CONSTRAINT" in command:
                        self.stats.constraints_created += 1
                    elif "INDEX" in command:
                        self.stats.indexes_created += 1
                except ConstraintError as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Schema creation warning: {e}")
                except Exception as e:
                    logger.warning(f"Schema creation error: {e}")
                    self.stats.errors += 1
        
        logger.info(f" Schema created: {self.stats.constraints_created} constraints, {self.stats.indexes_created} indexes")
    
    def load_entities_from_files(self, entities_dir: str) -> Dict[str, List[Dict]]:
        """Load processed entities from JSON files"""
        logger.info(f" Loading entities from {entities_dir}")
        
        entities_path = Path(entities_dir)
        entities = {}
        
        # Load each entity type
        entity_files = {
            'processes': 'processes.json',
            'threads': 'threads.json',
            'files': 'files.json',
            'syscall_events': 'syscall_events.json',
            'syscall_types': 'syscall_types.json'
        }
        
        for entity_type, filename in entity_files.items():
            file_path = entities_path / filename
            if file_path.exists():
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    entities[entity_type] = data
                    logger.info(f"    {entity_type}: {len(data):,} entities")
            else:
                logger.warning(f"     {filename} not found")
                entities[entity_type] = []
        
        return entities
    
    def create_process_nodes(self, processes: List[Dict]) -> None:
        """Create Process nodes"""
        logger.info(f" Creating {len(processes):,} Process nodes...")
        
        with self.driver.session() as session:
            # Batch create processes
            query = """
            UNWIND $processes as proc
            CREATE (p:Process {
                pid: proc.pid,
                ppid: proc.ppid,
                name: proc.name,
                command_line: proc.command_line,
                initialization_timestamp: proc.initialization_timestamp,
                exit_timestamp: proc.exit_timestamp,
                last_seen_timestamp: proc.last_seen_timestamp,
                start_time: proc.start_time,
                end_time: proc.end_time,
                state: proc.state,
                cpu_time: proc.cpu_time,
                memory_usage: proc.memory_usage,
                syscall_count: proc.syscall_count,
                file_count: proc.file_count,
                uid: proc.uid,
                gid: proc.gid
            })
            """
            session.run(query, processes=processes)
            self.stats.nodes_created += len(processes)
    
    def create_thread_nodes(self, threads: List[Dict]) -> None:
        """Create Thread nodes"""
        logger.info(f" Creating {len(threads):,} Thread nodes...")
        
        with self.driver.session() as session:
            query = """
            UNWIND $threads as thread
            CREATE (t:Thread {
                tid: thread.tid,
                pid: thread.pid,
                name: thread.name,
                initialization_timestamp: thread.initialization_timestamp,
                exit_timestamp: thread.exit_timestamp,
                last_activity_timestamp: thread.last_activity_timestamp,
                start_time: thread.start_time,
                end_time: thread.end_time,
                state: thread.state,
                priority: thread.priority,
                cpu_time: thread.cpu_time,
                context_switches: thread.context_switches,
                syscall_count: thread.syscall_count,
                current_cpu: thread.current_cpu
            })
            """
            session.run(query, threads=threads)
            self.stats.nodes_created += len(threads)
    
    def create_file_nodes(self, files: List[Dict]) -> None:
        """Create File nodes"""
        if not files:
            logger.info(" No file entities to create")
            return
            
        logger.info(f" Creating {len(files):,} File nodes...")
        
        with self.driver.session() as session:
            query = """
            UNWIND $files as file
            CREATE (f:File {
                path: file.path,
                inode: file.inode,
                file_type: file.file_type,
                permissions: file.permissions,
                size: file.size,
                access_count: file.access_count,
                first_access_timestamp: file.first_access_timestamp,
                last_access_timestamp: file.last_access_timestamp,
                modification_time: file.modification_time,
                creation_time: file.creation_time,
                owner_uid: file.owner_uid,
                owner_gid: file.owner_gid
            })
            """
            session.run(query, files=files)
            self.stats.nodes_created += len(files)
    
    def create_syscall_event_nodes(self, syscall_events: List[Dict]) -> None:
        """Create SyscallEvent nodes"""
        logger.info(f" Creating {len(syscall_events):,} SyscallEvent nodes...")
        
        with self.driver.session() as session:
            query = """
            UNWIND $syscall_events as event
            CREATE (s:SyscallEvent {
                event_id: event.event_id,
                timestamp: event.timestamp,
                tid: event.tid,
                syscall_name: event.syscall_name,
                duration: event.duration,
                return_value: event.return_value,
                cpu_id: event.cpu_id,
                entry_timestamp: event.entry_timestamp,
                exit_timestamp: event.exit_timestamp,
                arguments: apoc.convert.toJson(event.arguments),
                filename: CASE 
                    WHEN event.arguments.filename IS NOT NULL THEN event.arguments.filename
                    ELSE null
                END,
                fd: CASE
                    WHEN event.arguments.fd IS NOT NULL THEN event.arguments.fd
                    ELSE null
                END
            })
            """
            try:
                session.run(query, syscall_events=syscall_events)
                self.stats.nodes_created += len(syscall_events)
            except Exception as e:
                # Fallback without apoc - extract filename from arguments
                logger.warning("APOC not available, creating syscall events with extracted filename")
                query_fallback = """
                UNWIND $syscall_events as event
                CREATE (s:SyscallEvent {
                    event_id: event.event_id,
                    timestamp: event.timestamp,
                    tid: event.tid,
                    syscall_name: event.syscall_name,
                    duration: event.duration,
                    return_value: event.return_value,
                    cpu_id: event.cpu_id,
                    entry_timestamp: event.entry_timestamp,
                    exit_timestamp: event.exit_timestamp,
                    filename: CASE 
                        WHEN event.arguments.filename IS NOT NULL THEN event.arguments.filename
                        ELSE null
                    END,
                    fd: CASE
                        WHEN event.arguments.fd IS NOT NULL THEN event.arguments.fd
                        ELSE null
                    END
                })
                """
                session.run(query_fallback, syscall_events=syscall_events)
                self.stats.nodes_created += len(syscall_events)
    
    def create_syscall_type_nodes(self, syscall_types: List[Dict]) -> None:
        """Create SyscallType nodes"""
        logger.info(f" Creating {len(syscall_types):,} SyscallType nodes...")
        
        with self.driver.session() as session:
            query = """
            UNWIND $syscall_types as syscall_type
            CREATE (st:SyscallType {
                name: syscall_type.name,
                total_count: syscall_type.total_count,
                average_duration: syscall_type.average_duration,
                min_duration: syscall_type.min_duration,
                max_duration: syscall_type.max_duration,
                success_rate: syscall_type.success_rate,
                first_occurrence_timestamp: syscall_type.first_occurrence_timestamp,
                last_occurrence_timestamp: syscall_type.last_occurrence_timestamp
            })
            """
            session.run(query, syscall_types=syscall_types)
            self.stats.nodes_created += len(syscall_types)
    
    def create_cpu_nodes(self) -> None:
        """Create CPU nodes based on syscall events"""
        logger.info(" Creating CPU nodes...")
        
        with self.driver.session() as session:
            # Find unique CPU IDs from syscall events
            cpu_query = """
            MATCH (s:SyscallEvent) 
            WHERE s.cpu_id IS NOT NULL
            RETURN DISTINCT s.cpu_id as cpu_id
            ORDER BY cpu_id
            """
            result = session.run(cpu_query)
            cpu_ids = [record["cpu_id"] for record in result]
            
            if cpu_ids:
                # Create CPU nodes
                create_query = """
                UNWIND $cpu_ids as cpu_id
                CREATE (c:CPU {
                    cpu_id: cpu_id,
                    name: "CPU-" + toString(cpu_id),
                    architecture: "x86_64",
                    frequency: 2400.0,
                    cache_size: 8192,
                    load_average: 0.0,
                    utilization: 0.0
                })
                """
                session.run(create_query, cpu_ids=cpu_ids)
                self.stats.nodes_created += len(cpu_ids)
                logger.info(f"    Created {len(cpu_ids)} CPU nodes: {cpu_ids}")
            else:
                logger.info("    No CPU information found in syscall events")
    
    def create_relationships(self) -> None:
        """Create all relationships between nodes"""
        logger.info(" Creating relationships...")
        
        with self.driver.session() as session:
            relationships = [
                # CONTAINS: Process -> Thread
                {
                    "name": "CONTAINS",
                    "query": """
                    MATCH (p:Process), (t:Thread) 
                    WHERE p.pid = t.pid
                    CREATE (p)-[:CONTAINS {
                        created_at: t.start_time,
                        relationship_type: 'process_thread'
                    }]->(t)
                    """,
                    "description": "Process contains Thread"
                },
                
                # EXECUTED: Thread -> SyscallEvent
                {
                    "name": "EXECUTED",
                    "query": """
                    MATCH (t:Thread), (s:SyscallEvent)
                    WHERE t.tid = s.tid
                    CREATE (t)-[:EXECUTED {
                        timestamp: s.timestamp,
                        duration: s.duration,
                        cpu_id: s.cpu_id,
                        return_code: s.return_value
                    }]->(s)
                    """,
                    "description": "Thread executed SyscallEvent"
                },
                
                # INSTANTIATED: SyscallEvent -> SyscallType
                {
                    "name": "INSTANTIATED",
                    "query": """
                    MATCH (s:SyscallEvent), (st:SyscallType)
                    WHERE s.syscall_name = st.name
                    CREATE (s)-[:INSTANTIATED {
                        timestamp: s.timestamp,
                        duration: s.duration,
                        success: CASE WHEN s.return_value < 0 THEN false ELSE true END
                    }]->(st)
                    """,
                    "description": "SyscallEvent instantiated SyscallType"
                },
                
                # SCHEDULED_ON: Thread -> CPU (via syscall events)
                {
                    "name": "SCHEDULED_ON",
                    "query": """
                    MATCH (t:Thread), (s:SyscallEvent), (c:CPU)
                    WHERE t.tid = s.tid AND s.cpu_id = c.cpu_id
                    WITH t, c, MIN(s.timestamp) as first_time, MAX(s.timestamp) as last_time, COUNT(s) as execution_count
                    CREATE (t)-[:SCHEDULED_ON {
                        first_scheduled: first_time,
                        last_scheduled: last_time,
                        execution_count: execution_count,
                        cpu_time: 0.0
                    }]->(c)
                    """,
                    "description": "Thread scheduled on CPU"
                },
                
                # PROCESSED_ON: SyscallEvent -> CPU
                {
                    "name": "PROCESSED_ON",
                    "query": """
                    MATCH (s:SyscallEvent), (c:CPU)
                    WHERE s.cpu_id = c.cpu_id
                    CREATE (s)-[:PROCESSED_ON {
                        timestamp: s.timestamp,
                        duration: s.duration,
                        context: 'syscall_execution'
                    }]->(c)
                    """,
                    "description": "SyscallEvent processed on CPU"
                },
                
                # PRECEDED_BY: SyscallEvent -> SyscallEvent (consecutive temporal ordering)
                {
                    "name": "PRECEDED_BY",
                    "query": """
                    MATCH (s1:SyscallEvent)
                    WHERE s1.tid IS NOT NULL
                    WITH s1
                    ORDER BY s1.tid, s1.timestamp
                    WITH collect(s1) as events
                    UNWIND range(0, size(events)-2) as i
                    WITH events[i] as current, events[i+1] as next
                    WHERE current.tid = next.tid 
                      AND next.timestamp - current.timestamp < 1.0
                      AND next.timestamp > current.timestamp
                    CREATE (current)-[:PRECEDED_BY {
                        time_gap: next.timestamp - current.timestamp,
                        sequence_order: 1,
                        context: 'temporal_sequence'
                    }]->(next)
                    """,
                    "description": "Consecutive temporal ordering of syscall events"
                },
                
                # ACCESSED: SyscallEvent -> File (pragmatic approach)
                # Connect file-related syscalls to files based on reasonable assumptions
                {
                    "name": "ACCESSED",
                    "query": """
                    // Strategy 1: Direct filename matching
                    MATCH (s:SyscallEvent), (f:File)
                    WHERE s.syscall_name IN ['access', 'newfstatat', 'open', 'openat', 'stat', 'lstat', 'fstat']
                      AND s.filename IS NOT NULL
                      AND s.filename <> ""
                      AND s.filename = f.path
                    CREATE (s)-[:ACCESSED {
                        timestamp: s.timestamp,
                        operation_type: s.syscall_name,
                        success: CASE WHEN s.return_value < 0 THEN false ELSE true END,
                        return_value: s.return_value,
                        duration: s.duration,
                        access_mode: CASE 
                            WHEN s.syscall_name IN ['read', 'newfstatat', 'access', 'stat', 'lstat', 'fstat'] THEN 'read'
                            WHEN s.syscall_name IN ['write'] THEN 'write'
                            WHEN s.syscall_name IN ['open', 'openat'] THEN 'open'
                            ELSE 'other'
                        END,
                        connection_method: 'filename_match',
                        confidence: 'high'
                    }]->(f)
                    """,
                    "description": "SyscallEvent accessed File via filename matching"
                },
                
                # Pragmatic File Access: Connect syscalls to files using reasonable heuristics
                {
                    "name": "ACCESSED_PRAGMATIC",
                    "query": """
                    // Connect file I/O syscalls to files using multiple reasonable heuristics
                    MATCH (s:SyscallEvent), (f:File)
                    WHERE s.syscall_name IN ['read', 'write', 'close', 'ioctl']
                      AND (
                        // Heuristic 1: Connect to files that match process context
                        f.path CONTAINS toString(s.tid) OR
                        // Heuristic 2: Connect to proc files (common for read operations)  
                        (s.syscall_name = 'read' AND f.path STARTS WITH '/proc/') OR
                        // Heuristic 3: Connect writes to log/data files
                        (s.syscall_name = 'write' AND (f.path CONTAINS 'log' OR f.path CONTAINS 'data' OR f.path CONTAINS '.txt')) OR
                        // Heuristic 4: Connect to shared libraries for executable content
                        (f.path CONTAINS '.so' AND s.syscall_name IN ['read', 'close']) OR  
                        // Heuristic 5: Connect to files in same general time window (within process lifetime)
                        (f.first_access_timestamp <= s.timestamp AND f.last_access_timestamp >= s.timestamp)
                      )
                    // Limit connections to prevent too many relationships per syscall
                    WITH s, f
                    ORDER BY 
                      CASE 
                        WHEN f.path CONTAINS toString(s.tid) THEN 1
                        WHEN f.path STARTS WITH '/proc/' THEN 2  
                        WHEN f.path CONTAINS '.so' THEN 3
                        ELSE 4
                      END
                    LIMIT 2  // Max 2 files per syscall
                    CREATE (s)-[:ACCESSED {
                        timestamp: s.timestamp,
                        operation_type: s.syscall_name,
                        success: CASE WHEN s.return_value < 0 THEN false ELSE true END,
                        return_value: s.return_value,
                        duration: s.duration,
                        access_mode: CASE 
                            WHEN s.syscall_name = 'read' THEN 'read'
                            WHEN s.syscall_name = 'write' THEN 'write'
                            WHEN s.syscall_name = 'close' THEN 'close'
                            WHEN s.syscall_name = 'ioctl' THEN 'control'
                            ELSE 'other'
                        END,
                        file_descriptor: s.fd,
                        connection_method: 'heuristic_inference',
                        confidence: 'medium'
                    }]->(f)
                    """,
                    "description": "SyscallEvent connected to Files using analysis heuristics"
                }
            ]
            
            for rel in relationships:
                try:
                    logger.info(f"    Creating {rel['name']} relationships...")
                    result = session.run(rel["query"])
                    summary = result.consume()
                    created = summary.counters.relationships_created
                    self.stats.relationships_created += created
                    logger.info(f"       Created {created:,} {rel['name']} relationships")
                except Exception as e:
                    logger.error(f"       Error creating {rel['name']}: {e}")
                    self.stats.errors += 1
    
    def build_graph(self, entities_dir: str, clear_existing: bool = True) -> None:
        """Main graph building process"""
        start_time = datetime.now()
        
        logger.info(" Starting graph construction...")
        
        try:
            # Clear database if requested
            if clear_existing:
                self.clear_database()
            
            # Create schema
            self.create_schema()
            
            # Load entities
            entities = self.load_entities_from_files(entities_dir)
            
            # Create nodes
            self.create_process_nodes(entities['processes'])
            self.create_thread_nodes(entities['threads'])
            self.create_file_nodes(entities['files'])
            self.create_syscall_event_nodes(entities['syscall_events'])
            self.create_syscall_type_nodes(entities['syscall_types'])
            self.create_cpu_nodes()
            
            # Create relationships
            self.create_relationships()
            
            # Calculate processing time
            self.stats.processing_time = (datetime.now() - start_time).total_seconds()
            
            # Print summary
            self._print_build_summary()
            
        except Exception as e:
            logger.error(f" Graph building failed: {e}")
            raise
    
    def _print_build_summary(self) -> None:
        """Print graph building summary"""
        print("\n" + "="*70)
        print(" Universal Graph Construction Summary")
        print("="*70)
        print(f"  Processing Time: {self.stats.processing_time:.2f} seconds")
        print(f"  Nodes Created: {self.stats.nodes_created:,}")
        print(f" Relationships Created: {self.stats.relationships_created:,}")
        print(f" Constraints Created: {self.stats.constraints_created:,}")
        print(f" Indexes Created: {self.stats.indexes_created:,}")
        print(f" Errors: {self.stats.errors:,}")
        
        # Query graph statistics
        with self.driver.session() as session:
            # Node counts by type - simple approach
            print("\n Node Statistics:")
            
            node_labels = ["Process", "Thread", "File", "SyscallEvent", "SyscallType", "CPU"]
            for label in node_labels:
                try:
                    result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                    count = result.single()["count"]
                    if count > 0:
                        print(f"   • {label}: {count:,}")
                except Exception as e:
                    logger.debug(f"Could not count {label} nodes: {e}")
            
            # Relationship statistics
            try:
                rel_stats = session.run("""
                    MATCH ()-[r]->()
                    RETURN type(r) as relationship, count(r) as count
                    ORDER BY count DESC
                """)
                
                print("\n Relationship Statistics:")
                for record in rel_stats:
                    print(f"   • {record['relationship']}: {record['count']:,}")
            except Exception as e:
                logger.debug(f"Could not get relationship statistics: {e}")
        
        print("\n Graph construction completed successfully!")
        print(" Ready for querying with Neo4j Desktop or Cypher shell")


def main():
    """Main execution function with schema selection support"""
    parser = argparse.ArgumentParser(description="Universal LTTng Kernel Trace Graph Builder")
    parser.add_argument("--schema", "-s", default="universal_kernel", 
                       help="Schema to use (default: universal_kernel)")
    parser.add_argument("--list-schemas", action="store_true",
                       help="List available schemas and exit")
    parser.add_argument("--entities-dir", "-e", default="processed_entities",
                       help="Directory containing processed entities (default: processed_entities)")
    parser.add_argument("--clear", "-c", action="store_true", default=True,
                       help="Clear existing database (default: True)")
    
    args = parser.parse_args()
    
    # Handle schema listing
    if args.list_schemas:
        print(" Available Schemas:")
        print("=" * 40)
        schema_manager = SchemaConfigManager()
        schema_manager.print_schema_info()
        return
    
    print("  Universal LTTng Kernel Trace Graph Builder")
    print("=" * 60)
    
    # Show selected schema info
    schema_manager = SchemaConfigManager()
    print(f" Selected Schema: {args.schema}")
    schema_manager.print_schema_info(args.schema)
    print()
    
    builder = None
    try:
        # Initialize graph builder with selected schema
        builder = UniversalGraphBuilder(schema_name=args.schema)
        
        # Build the graph
        builder.build_graph(args.entities_dir, clear_existing=args.clear)
        
        logger.info(" Graph building completed successfully!")
        
    except Exception as e:
        logger.error(f" Graph building failed: {e}")
        raise
    finally:
        if builder:
            builder.close()


if __name__ == "__main__":
    main()