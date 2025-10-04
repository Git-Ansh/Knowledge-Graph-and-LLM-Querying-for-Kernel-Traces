"""
Graph Builder Module
====================
Constructs the layered knowledge graph in Neo4j.

This module builds both layers:
- Kernel Reality Layer (processes, threads, files, EventSequences)
- Application Abstraction Layer (application-specific events)
- Cross-layer connections (FULFILLED_BY relationships)

Author: Knowledge Graph and LLM Querying for Kernel Traces Project
Date: October 3, 2025
"""

import logging
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

logger = logging.getLogger(__name__)


@dataclass
class GraphStats:
    """Statistics about the constructed graph."""
    nodes_created: int = 0
    relationships_created: int = 0
    node_counts: Dict[str, int] = None
    relationship_counts: Dict[str, int] = None
    
    def __post_init__(self):
        if self.node_counts is None:
            self.node_counts = {}
        if self.relationship_counts is None:
            self.relationship_counts = {}


class GraphBuilder:
    """Builds layered knowledge graph in Neo4j."""
    
    def __init__(self, uri: str = "bolt://10.0.2.2:7687", 
                 user: str = "neo4j", 
                 password: str = "sudoroot"):
        """
        Initialize graph builder.
        
        Args:
            uri: Neo4j connection URI
            user: Neo4j username
            password: Neo4j password
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
        self.stats = GraphStats()
        
        logger.info(f"Initialized GraphBuilder for {uri}")
    
    def connect(self):
        """Establish connection to Neo4j database."""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            # Test connection
            with self.driver.session() as session:
                result = session.run("RETURN 1")
                result.single()
            logger.info("Successfully connected to Neo4j database")
            return True
        except AuthError:
            logger.error("Authentication failed. Check Neo4j credentials.")
            return False
        except ServiceUnavailable:
            logger.error("Neo4j service unavailable. Ensure Neo4j is running.")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            return False
    
    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
            logger.info("Closed Neo4j connection")
    
    def clear_database(self):
        """Clear all nodes and relationships from database."""
        logger.warning("Clearing entire Neo4j database")
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        logger.info("Database cleared")
    
    def create_constraints_and_indexes(self):
        """Create uniqueness constraints and indexes for performance."""
        logger.info("Creating constraints and indexes")
        
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Process) REQUIRE p.pid IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Thread) REQUIRE t.tid IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:CPU) REQUIRE c.cpu_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (es:EventSequence) REQUIRE es.sequence_id IS UNIQUE"
        ]
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (p:Process) ON (p.name)",
            "CREATE INDEX IF NOT EXISTS FOR (t:Thread) ON (t.start_time)",
            "CREATE INDEX IF NOT EXISTS FOR (es:EventSequence) ON (es.operation)",
            "CREATE INDEX IF NOT EXISTS FOR (es:EventSequence) ON (es.start_time)",
            "CREATE INDEX IF NOT EXISTS FOR (ae:AppEvent) ON (ae.event_name)"
        ]
        
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                    logger.debug(f"Created constraint: {constraint[:50]}...")
                except Exception as e:
                    logger.warning(f"Constraint creation warning: {e}")
            
            for index in indexes:
                try:
                    session.run(index)
                    logger.debug(f"Created index: {index[:50]}...")
                except Exception as e:
                    logger.warning(f"Index creation warning: {e}")
        
        logger.info("Constraints and indexes created")
    
    def build_graph(self, entities_dir: Path, metadata: Optional[Dict] = None):
        """
        Build complete knowledge graph from extracted entities.
        
        Args:
            entities_dir: Directory containing entity JSON files
            metadata: Optional metadata about the trace
        """
        logger.info("Building knowledge graph")
        
        # Load entities
        entities = self._load_entities(entities_dir)
        
        # Build kernel reality layer
        self._build_kernel_layer(entities)
        
        # Build application abstraction layer (if metadata indicates specific app)
        if metadata and 'application' in metadata:
            self._build_application_layer(entities, metadata)
        
        # Log final statistics
        logger.info("Graph construction complete")
        logger.info(f"  Total nodes: {self.stats.nodes_created}")
        logger.info(f"  Total relationships: {self.stats.relationships_created}")
        for label, count in self.stats.node_counts.items():
            logger.info(f"    {label}: {count}")
    
    def _load_entities(self, entities_dir: Path) -> Dict[str, List]:
        """Load all entity JSON files."""
        logger.info(f"Loading entities from {entities_dir}")
        
        entities = {}
        entity_files = ['processes', 'threads', 'files', 'sockets', 'cpus', 'event_sequences']
        
        for entity_type in entity_files:
            file_path = entities_dir / f"{entity_type}.json"
            if file_path.exists():
                with open(file_path, 'r') as f:
                    entities[entity_type] = json.load(f)
                logger.info(f"  Loaded {len(entities[entity_type])} {entity_type}")
            else:
                entities[entity_type] = []
                logger.warning(f"  File not found: {file_path.name}")
        
        return entities
    
    def _build_kernel_layer(self, entities: Dict[str, List]):
        """Build the kernel reality layer of the graph."""
        logger.info("Building kernel reality layer")
        
        with self.driver.session() as session:
            # Create Process nodes
            logger.info("  Creating Process nodes")
            for process in entities.get('processes', []):
                # Ensure all expected fields exist, use None for missing values
                process_data = {
                    'pid': process.get('pid'),
                    'name': process.get('name'),
                    'start_time': process.get('start_time'),
                    'end_time': process.get('end_time'),
                    'thread_count': process.get('thread_count', 0),
                    'parent_pid': process.get('parent_pid')
                }
                session.run(
                    """
                    CREATE (p:Process {
                        pid: $pid,
                        name: $name,
                        start_time: $start_time,
                        end_time: $end_time,
                        thread_count: $thread_count,
                        parent_pid: $parent_pid
                    })
                    """,
                    **process_data
                )
                self.stats.nodes_created += 1
                self.stats.node_counts['Process'] = self.stats.node_counts.get('Process', 0) + 1
            
            # Create Thread nodes
            logger.info("  Creating Thread nodes")
            for thread in entities.get('threads', []):
                thread_data = {
                    'tid': thread.get('tid'),
                    'pid': thread.get('pid'),
                    'name': thread.get('name'),
                    'start_time': thread.get('start_time'),
                    'end_time': thread.get('end_time')
                }
                session.run(
                    """
                    CREATE (t:Thread {
                        tid: $tid,
                        pid: $pid,
                        name: $name,
                        start_time: $start_time,
                        end_time: $end_time
                    })
                    """,
                    **thread_data
                )
                self.stats.nodes_created += 1
                self.stats.node_counts['Thread'] = self.stats.node_counts.get('Thread', 0) + 1
            
            # Create CONTAINS relationships (Process -> Thread)
            logger.info("  Creating CONTAINS relationships")
            result = session.run(
                """
                MATCH (p:Process), (t:Thread)
                WHERE p.pid = t.pid
                CREATE (p)-[:CONTAINS {creation_time: t.start_time}]->(t)
                RETURN count(*) as count
                """
            )
            count = result.single()['count']
            self.stats.relationships_created += count
            self.stats.relationship_counts['CONTAINS'] = count
            logger.info(f"    Created {count} CONTAINS relationships")
            
            # Create File nodes - only for files referenced in EventSequences
            logger.info("  Creating File nodes")
            
            # First, collect all file paths referenced in EventSequences
            referenced_files = set()
            for sequence in entities.get('event_sequences', []):
                entity_target = sequence.get('entity_target')
                if entity_target and not entity_target.startswith('fd:'):
                    referenced_files.add(entity_target)
            
            logger.info(f"    Found {len(referenced_files)} files referenced in EventSequences")
            
            # Only create File nodes for referenced files
            created_count = 0
            for file in entities.get('files', []):
                file_path = file.get('path')
                if file_path in referenced_files:
                    file_data = {
                        'path': file_path,
                        'type': file.get('type'),
                        'first_access': file.get('first_access'),
                        'last_access': file.get('last_access'),
                        'access_count': file.get('access_count', 0)
                    }
                    session.run(
                        """
                        CREATE (f:File {
                            path: $path,
                            type: $type,
                            first_access: $first_access,
                            last_access: $last_access,
                            access_count: $access_count
                        })
                        """,
                        **file_data
                    )
                    self.stats.nodes_created += 1
                    self.stats.node_counts['File'] = self.stats.node_counts.get('File', 0) + 1
                    created_count += 1
            
            logger.info(f"    Created {created_count} File nodes (skipped {len(entities.get('files', [])) - created_count} unreferenced)")
            
            # Create Socket nodes
            logger.info("  Creating Socket nodes")
            for socket in entities.get('sockets', []):
                socket_data = {
                    'socket_id': socket.get('socket_id'),
                    'address': socket.get('address'),
                    'port': socket.get('port'),
                    'protocol': socket.get('protocol'),
                    'family': socket.get('family'),
                    'type': socket.get('type'),
                    'first_access': socket.get('first_access')
                }
                session.run(
                    """
                    CREATE (s:Socket {
                        socket_id: $socket_id,
                        address: $address,
                        port: $port,
                        protocol: $protocol,
                        family: $family,
                        type: $type,
                        first_access: $first_access
                    })
                    """,
                    **socket_data
                )
                self.stats.nodes_created += 1
                self.stats.node_counts['Socket'] = self.stats.node_counts.get('Socket', 0) + 1
            
            # Create CPU nodes
            logger.info("  Creating CPU nodes")
            for cpu in entities.get('cpus', []):
                session.run(
                    """
                    CREATE (c:CPU {
                        cpu_id: $cpu_id,
                        event_count: $event_count
                    })
                    """,
                    **cpu
                )
                self.stats.nodes_created += 1
                self.stats.node_counts['CPU'] = self.stats.node_counts.get('CPU', 0) + 1
            
            # Create EventSequence nodes (the "action chapters")
            logger.info("  Creating EventSequence nodes")
            for sequence in entities.get('event_sequences', []):
                # Convert event_stream to JSON string for storage
                event_stream_json = json.dumps(sequence.get('event_stream', []))
                
                session.run(
                    """
                    CREATE (es:EventSequence {
                        sequence_id: $sequence_id,
                        operation: $operation,
                        start_time: $start_time,
                        end_time: $end_time,
                        count: $count,
                        event_stream: $event_stream,
                        entity_target: $entity_target,
                        return_value: $return_value,
                        bytes_transferred: $bytes_transferred,
                        duration_ms: $duration_ms,
                        cpu_id: $cpu_id
                    })
                    """,
                    sequence_id=sequence['sequence_id'],
                    operation=sequence['operation'],
                    start_time=sequence['start_time'],
                    end_time=sequence['end_time'],
                    count=sequence['count'],
                    event_stream=event_stream_json,
                    entity_target=sequence.get('entity_target'),
                    return_value=sequence.get('return_value'),
                    bytes_transferred=sequence.get('bytes_transferred', 0),
                    duration_ms=sequence.get('duration_ms', 0),
                    cpu_id=sequence.get('cpu_id', -1)
                )
                self.stats.nodes_created += 1
                self.stats.node_counts['EventSequence'] = self.stats.node_counts.get('EventSequence', 0) + 1
            
            # Create PERFORMED relationships (Thread -> EventSequence)
            logger.info("  Creating PERFORMED relationships")
            for sequence in entities.get('event_sequences', []):
                if sequence.get('thread_id'):
                    session.run(
                        """
                        MATCH (t:Thread {tid: $tid}), (es:EventSequence {sequence_id: $seq_id})
                        CREATE (t)-[:PERFORMED {
                            start_time: es.start_time,
                            end_time: es.end_time,
                            cpu: $cpu_id
                        }]->(es)
                        """,
                        tid=sequence['thread_id'],
                        seq_id=sequence['sequence_id'],
                        cpu_id=sequence.get('cpu_id', -1)
                    )
                    self.stats.relationships_created += 1
                    self.stats.relationship_counts['PERFORMED'] = \
                        self.stats.relationship_counts.get('PERFORMED', 0) + 1
            
            # Create SCHEDULED_ON relationships (Thread -> CPU)
            logger.info("  Creating SCHEDULED_ON relationships")
            result = session.run(
                """
                MATCH (t:Thread)-[:PERFORMED]->(es:EventSequence), (c:CPU)
                WHERE es.cpu_id = c.cpu_id
                WITH t, c, count(es) as execution_count
                MERGE (t)-[:SCHEDULED_ON {execution_count: execution_count}]->(c)
                RETURN count(DISTINCT t) as threads_scheduled
                """
            )
            scheduled_count = result.single()['threads_scheduled']
            self.stats.relationships_created += scheduled_count
            self.stats.relationship_counts['SCHEDULED_ON'] = scheduled_count
            logger.info(f"    Created {scheduled_count} SCHEDULED_ON relationships")
            
            # Create WAS_TARGET_OF relationships (File/Socket -> EventSequence)
            logger.info("  Creating WAS_TARGET_OF relationships")
            file_target_count = 0
            socket_target_count = 0
            
            for sequence in entities.get('event_sequences', []):
                entity_target = sequence.get('entity_target')
                operation = sequence.get('operation', '')
                
                if entity_target and not entity_target.startswith('fd:'):
                    # Determine if this is a socket or file operation
                    if operation in ['socket_send', 'socket_recv']:
                        # Try to match with Socket - use socket_id format
                        result = session.run(
                            """
                            MATCH (s:Socket {socket_id: $socket_id}), (es:EventSequence {sequence_id: $seq_id})
                            CREATE (s)-[:WAS_TARGET_OF {access_type: es.operation}]->(es)
                            RETURN count(*) as count
                            """,
                            socket_id=entity_target,
                            seq_id=sequence['sequence_id']
                        )
                        if result.single()['count'] > 0:
                            socket_target_count += 1
                    else:
                        # Try to match with File
                        result = session.run(
                            """
                            MATCH (f:File {path: $path}), (es:EventSequence {sequence_id: $seq_id})
                            CREATE (f)-[:WAS_TARGET_OF {access_type: es.operation}]->(es)
                            RETURN count(*) as count
                            """,
                            path=entity_target,
                            seq_id=sequence['sequence_id']
                        )
                        if result.single()['count'] > 0:
                            file_target_count += 1
            
            self.stats.relationships_created += (file_target_count + socket_target_count)
            self.stats.relationship_counts['WAS_TARGET_OF'] = file_target_count + socket_target_count
            logger.info(f"    Created {file_target_count} File→EventSequence relationships")
            logger.info(f"    Created {socket_target_count} Socket→EventSequence relationships")
            
            logger.info("Kernel reality layer complete")
    
    def _build_application_layer(self, entities: Dict[str, List], metadata: Dict):
        """Build application abstraction layer based on application type."""
        app_type = metadata.get('application', 'unknown')
        logger.info(f"Building application layer for: {app_type}")
        
        # This is a placeholder - specific parsers would be implemented per application
        # For now, we'll create generic AppEvent nodes from metadata
        
        if app_type == 'redis':
            self._build_redis_layer(entities, metadata)
        else:
            logger.info(f"  No specific application layer builder for {app_type}")
    
    def _build_redis_layer(self, entities: Dict[str, List], metadata: Dict):
        """Build Redis-specific application layer."""
        logger.info("  Building Redis application layer")
        
        # Example: Parse Redis commands from test_commands in metadata
        test_commands = metadata.get('test_commands', [])
        
        with self.driver.session() as session:
            for idx, command in enumerate(test_commands):
                # Parse Redis command
                parts = command.replace('redis-cli ', '').split()
                if len(parts) >= 1:
                    cmd_type = parts[0].upper()
                    
                    # Create RedisCommand node (inherits from AppEvent)
                    session.run(
                        """
                        CREATE (rc:AppEvent:RedisCommand {
                            event_name: $event_name,
                            command: $command,
                            key: $key,
                            details: $details,
                            start_time: $start_time
                        })
                        """,
                        event_name=f"Redis {cmd_type}",
                        command=cmd_type,
                        key=parts[1] if len(parts) > 1 else 'unknown',
                        details=json.dumps({'full_command': command}),
                        start_time=0.0  # Would need actual timing from trace
                    )
                    self.stats.nodes_created += 1
                    self.stats.node_counts['RedisCommand'] = \
                        self.stats.node_counts.get('RedisCommand', 0) + 1
        
        logger.info(f"    Created {len(test_commands)} RedisCommand nodes")
    
    def save_statistics(self, output_dir: Path):
        """Save graph construction statistics."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        stats_dict = {
            'nodes_created': self.stats.nodes_created,
            'relationships_created': self.stats.relationships_created,
            'node_counts': self.stats.node_counts,
            'relationship_counts': self.stats.relationship_counts
        }
        
        stats_file = output_dir / "graph_stats.json"
        with open(stats_file, 'w') as f:
            json.dump(stats_dict, f, indent=2)
        
        logger.info(f"Saved graph statistics to {stats_file.name}")


def main():
    """Test the graph builder independently."""
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 2:
        print("Usage: python graph_builder.py <entities_directory>")
        sys.exit(1)
    
    entities_dir = Path(sys.argv[1])
    if not entities_dir.exists():
        print(f"Error: Entities directory not found: {entities_dir}")
        sys.exit(1)
    
    # Initialize and connect
    builder = GraphBuilder()
    if not builder.connect():
        sys.exit(1)
    
    try:
        # Clear database
        builder.clear_database()
        
        # Create constraints
        builder.create_constraints_and_indexes()
        
        # Build graph
        builder.build_graph(entities_dir)
        
        # Save statistics
        output_dir = Path("outputs/graph_stats")
        builder.save_statistics(output_dir)
        
    finally:
        builder.close()


if __name__ == "__main__":
    main()
