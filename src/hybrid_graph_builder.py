#!/usr/bin/env python3
"""
Hybrid Two-Tiered Graph Builder
Creates optimized Neo4j graph with entity nodes and e            'CREATE INDEX rel_connected_timestamp IF NOT EXISTS FOR ()-[r:CONNECTED_TO]-() ON (r.timestamp)',
            'CREATE INDEX rel_rcu_timestamp IF NOT EXISTS FOR ()-[r:RCU_SYNC]-() ON (r.timestamp)',
            'CREATE INDEX rel_executed_timestamp IF NOT EXISTS FOR ()-[r:EXECUTED_ON]-() ON (r.timestamp)',
            'CREATE INDEX rel_scheduling_timestamp IF NOT EXISTS FOR ()-[r:SCHEDULING_OPERATION]-() ON (r.timestamp)'ent relationships

Architecture:
- Tier 1: Core entity nodes (Process, Thread, File, Socket, CPU, MemoryRegion)
- Tier 2: Rich event relationships (READ_FROM, WROTE_TO, SCHEDULED_ON, etc.)
- Performance: Fast entity queries + detailed temporal reconstruction
- Context: Handles both kernel and user space traces seamlessly
"""

import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
from schema_registry import GraphSchema, SchemaRegistry

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HybridGraphBuilder:
    """Builds hybrid two-tiered graph optimized for speed and depth"""
    
    def __init__(self, uri: str = "bolt://localhost:7687", user: str = "neo4j", password: str = "sudoroot"):
        self.driver = None
        self.uri = uri
        self.user = user
        self.password = password
        
        # Statistics
        self._reset_stats()
        
        self._connect()
    
    def _reset_stats(self) -> None:
        self.stats = {
            'nodes_created': 0,
            'relationships_created': 0,
            'constraints_created': 0,
            'indexes_created': 0,
            'processing_time': 0.0
        }

    def _connect(self) -> None:
        """Establish Neo4j connection"""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
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
        """Clear existing data"""
        logger.info(" Clearing database...")
        with self.driver.session() as session:
            try:
                session.run("MATCH (n) DETACH DELETE n")
            except Exception as e:
                logger.warning(f"Error clearing database: {e}")
    
    def create_schema(self, schema: GraphSchema) -> None:
        """Create constraints and indexes defined by the provided schema."""
        logger.info(" Creating schema '%s'...", schema.name)

        constraints_created = 0
        indexes_created = 0
        commands = list(schema.constraints) + list(schema.indexes)

        with self.driver.session() as session:
            for command in commands:
                try:
                    session.run(command)
                    if "CONSTRAINT" in command.upper():
                        constraints_created += 1
                    elif "INDEX" in command.upper():
                        indexes_created += 1
                except Exception as e:
                    logger.warning(f"Schema command failed: {command} - {e}")

        self.stats['constraints_created'] += constraints_created
        self.stats['indexes_created'] += indexes_created

        logger.info(
            " Schema '%s' prepared (%d constraints, %d indexes)",
            schema.name,
            constraints_created,
            indexes_created
        )

    def prepare_schema(self, schema: GraphSchema, clear_existing: bool = True) -> None:
        """Clear the database if requested and apply the provided schema."""
        logger.info(" Preparing Neo4j schema using '%s'", schema.name)
        if clear_existing:
            self.clear_database()
        self.create_schema(schema)
    
    def load_entities(self, entities_dir: str) -> Dict[str, List[Dict]]:
        """Load entities from hybrid preprocessor output"""
        logger.info(f" Loading hybrid entities from {entities_dir}")
        
        entities_path = Path(entities_dir)
        entities = {}
        
        entity_files = {
            'processes': 'processes.json',
            'threads': 'threads.json', 
            'files': 'files.json',
            'sockets': 'sockets.json',
            'cpus': 'cpus.json',
            'memory_regions': 'memory_regions.json',
            'event_relationships': 'event_relationships.json'
        }
        
        for entity_type, filename in entity_files.items():
            file_path = entities_path / filename
            if file_path.exists():
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    entities[entity_type] = data
                    logger.info(f"    {entity_type}: {len(data):,} entities")
            else:
                logger.warning(f"    {filename} not found")
                entities[entity_type] = []
        
        return entities
    
    def create_entity_nodes(self, entities: Dict[str, List[Dict]]) -> None:
        """Create all entity nodes (Tier 1)"""
        logger.info(" Creating entity nodes...")
        
        with self.driver.session() as session:
            # Create Process nodes
            if entities['processes']:
                logger.info(f"    Creating {len(entities['processes'])} Process nodes...")
                query = """
                UNWIND $processes as proc
                CREATE (p:Process {
                    pid: proc.pid,
                    ppid: proc.ppid,
                    name: proc.name,
                    command_line: proc.command_line,
                    start_time: proc.start_time,
                    end_time: proc.end_time,
                    uid: proc.uid,
                    gid: proc.gid,
                    state: proc.state
                })
                """
                session.run(query, processes=entities['processes'])
                self.stats['nodes_created'] += len(entities['processes'])
            
            # Create Thread nodes
            if entities['threads']:
                logger.info(f"    Creating {len(entities['threads'])} Thread nodes...")
                query = """
                UNWIND $threads as thread
                CREATE (t:Thread {
                    tid: thread.tid,
                    pid: thread.pid,
                    name: thread.name,
                    start_time: thread.start_time,
                    end_time: thread.end_time,
                    priority: thread.priority
                })
                """
                session.run(query, threads=entities['threads'])
                self.stats['nodes_created'] += len(entities['threads'])
            
            # Create File nodes
            if entities['files']:
                logger.info(f"    Creating {len(entities['files'])} File nodes...")
                query = """
                UNWIND $files as file
                CREATE (f:File {
                    path: file.path,
                    file_type: file.file_type,
                    size: file.size,
                    owner_uid: file.owner_uid,
                    owner_gid: file.owner_gid,
                    permissions: file.permissions,
                    inode: file.inode
                })
                """
                session.run(query, files=entities['files'])
                self.stats['nodes_created'] += len(entities['files'])
            
            # Create Socket nodes
            if entities['sockets']:
                logger.info(f"    Creating {len(entities['sockets'])} Socket nodes...")
                query = """
                UNWIND $sockets as socket
                CREATE (s:Socket {
                    socket_id: socket.socket_id,
                    family: socket.family,
                    socket_type: socket.socket_type,
                    protocol: socket.protocol,
                    local_address: socket.local_address,
                    remote_address: socket.remote_address,
                    port: socket.port,
                    state: socket.state
                })
                """
                session.run(query, sockets=entities['sockets'])
                self.stats['nodes_created'] += len(entities['sockets'])
            
            # Create CPU nodes
            if entities['cpus']:
                logger.info(f"    Creating {len(entities['cpus'])} CPU nodes...")
                query = """
                UNWIND $cpus as cpu
                CREATE (c:CPU {
                    cpu_id: cpu.cpu_id,
                    core: cpu.core,
                    package: cpu.package,
                    frequency: cpu.frequency
                })
                """
                session.run(query, cpus=entities['cpus'])
                self.stats['nodes_created'] += len(entities['cpus'])
            
            # Create Memory Region nodes
            if entities['memory_regions']:
                logger.info(f"    Creating {len(entities['memory_regions'])} MemoryRegion nodes...")
                query = """
                UNWIND $regions as region
                CREATE (m:MemoryRegion {
                    start_address: region.start_address,
                    pid: region.pid,
                    size: region.size,
                    region_type: region.region_type,
                    permissions: region.permissions,
                    file_path: region.file_path
                })
                """
                session.run(query, regions=entities['memory_regions'])
                self.stats['nodes_created'] += len(entities['memory_regions'])
    
    def create_event_relationships(self, relationships: List[Dict]) -> None:
        """Create event relationships (Tier 2) - The core of the hybrid model"""
        logger.info(" Creating event relationships...")
        
        if not relationships:
            logger.warning("No relationships to create")
            return
        
        # Log relationship processing
        logger.info(f" Processing {len(relationships)} relationships total")
        
        # Group relationships by type for efficient batch processing
        relationship_groups = {}
        for rel in relationships:
            rel_type = rel['relationship_type']
            if rel_type not in relationship_groups:
                relationship_groups[rel_type] = []
            relationship_groups[rel_type].append(rel)
        
        with self.driver.session() as session:
            for rel_type, rel_list in relationship_groups.items():
                logger.info(f"    Creating {len(rel_list)} {rel_type} relationships...")
                
                # Build dynamic query based on relationship type with sample
                query = self._build_relationship_query(rel_type, rel_list[0] if rel_list else None)
                
                try:
                    # Process in batches to avoid memory issues
                    batch_size = 1000
                    for i in range(0, len(rel_list), batch_size):
                        batch = rel_list[i:i + batch_size]
                        result = session.run(query, relationships=batch)
                        
                        # Verify the result
                        summary = result.consume()
                        created_count = summary.counters.relationships_created
                        
                        if created_count != len(batch):
                            logger.warning(f"Expected {len(batch)} relationships, but created {created_count}")
                        
                        self.stats['relationships_created'] += created_count
                        
                        if i + batch_size < len(rel_list):
                            logger.info(f"       Processed {i + batch_size}/{len(rel_list)} {rel_type} relationships...")
                            
                except Exception as e:
                    logger.error(f"Error creating {rel_type} relationships: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
    
    def _build_relationship_query(self, rel_type: str, sample_rel: Dict = None) -> str:
        """Build Cypher query for specific relationship type using dynamic detection"""
        
        # If we have sample data, use that to determine source/target types
        if sample_rel:
            source_type = sample_rel.get('source_type', 'Process')
            target_type = sample_rel.get('target_type', 'Process')
        else:
            # Fallback to static mapping
            source_target_mapping = {
                'READ_FROM': ('Process', 'File'),
                'WROTE_TO': ('Process', 'File'),
                'ACCESSED': ('Process', 'File'),
                'OPENED': ('Process', 'File'),
                'CLOSED': ('Process', 'File'),
                'EXECUTED': ('Process', 'File'),
                'SCHEDULED_ON': ('Process', 'CPU'),
                'PREEMPTED_FROM': ('Process', 'CPU'),
                'SYSCALL_OPERATION': ('Process', 'CPU'),
                'SCHEDULING_OPERATION': ('Process', 'CPU'),
                'RCU_SYNC': ('CPU', 'CPU'),
                'EXECUTED_ON': ('Thread', 'CPU'),
                'FORKED': ('Process', 'Process'),
                'MAPPED': ('Process', 'MemoryRegion'),
                'UNMAPPED': ('Process', 'MemoryRegion'),
                'ALLOCATED': ('Process', 'MemoryRegion'),
                'SENT_TO': ('Process', 'Socket'),
                'RECEIVED_FROM': ('Process', 'Socket'),
                'CONNECTED_TO': ('Process', 'Socket'),
                'BOUND_TO': ('Process', 'Socket')
            }
            source_type, target_type = source_target_mapping.get(rel_type, ('Process', 'Process'))
        
        source_label = source_type
        target_label = target_type
        
        # Build match conditions based on source and target types
        if source_label == 'Process' and target_label == 'Process':
            # Process to Process relationships (e.g., FORKED)
            source_match = "MATCH (source:Process {pid: rel.source_id})"
            target_match = "MATCH (target:Process {pid: rel.target_id})"
        elif source_label == 'Thread' and target_label == 'CPU':
            # Thread to CPU relationships (e.g., EXECUTED_ON)
            source_match = "MATCH (source:Thread) WHERE source.tid = rel.source_id"
            target_match = "MATCH (target:CPU {cpu_id: rel.target_id})"
        elif source_label == 'CPU' and target_label == 'CPU':
            # CPU to CPU relationships (e.g., RCU_SYNC)
            source_match = "MATCH (source:CPU {cpu_id: rel.source_id})"
            target_match = "MATCH (target:CPU {cpu_id: rel.target_id})"
        elif source_label == 'Process' and target_label == 'File':
            # Process to File relationships
            source_match = "MATCH (source:Process {pid: rel.source_id})" 
            target_match = "MATCH (target:File {path: rel.target_id})"
        elif source_label == 'Process' and target_label == 'CPU':
            # Process to CPU relationships
            source_match = "MATCH (source:Process {pid: rel.source_id})"
            target_match = "MATCH (target:CPU {cpu_id: rel.target_id})"
        elif source_label == 'Process' and target_label == 'Socket':
            # Process to Socket relationships
            source_match = "MATCH (source:Process {pid: rel.source_id})"
            target_match = "MATCH (target:Socket {socket_id: rel.target_id})"
        elif source_label == 'Process' and target_label == 'MemoryRegion':
            # Process to MemoryRegion relationships
            source_match = "MATCH (source:Process {pid: rel.source_id})"
            target_match = "MATCH (target:MemoryRegion {start_address: rel.target_id, pid: rel.source_id})"
        else:
            # Default fallback
            source_match = "MATCH (source:Process {pid: rel.source_id})"
            target_match = "MATCH (target {id: rel.target_id})"
        
        # Create a simplified query that handles dynamic properties
        query = f"""
        UNWIND $relationships as rel
        {source_match}
        {target_match}
        CREATE (source)-[r:{rel_type}]->(target)
        SET r = rel.properties
        SET r.timestamp = rel.timestamp
        SET r.source_type = rel.source_type
        SET r.target_type = rel.target_type
        """
        
        return query
    
    def _sanitize_integer_values(self, obj):
        """Sanitize integer values to prevent Neo4j overflow"""
        MAX_SAFE_INTEGER = 2**53 - 1  # Neo4j's maximum safe integer
        MIN_SAFE_INTEGER = -(2**53 - 1)
        
        if isinstance(obj, dict):
            sanitized = {}
            for key, value in obj.items():
                sanitized[key] = self._sanitize_integer_values(value)
            return sanitized
        elif isinstance(obj, list):
            return [self._sanitize_integer_values(item) for item in obj]
        elif isinstance(obj, int):
            if obj > MAX_SAFE_INTEGER or obj < MIN_SAFE_INTEGER:
                # Convert to string to preserve the value but avoid overflow
                return str(obj)
            return obj
        else:
            return obj

    def build_hybrid_graph_from_data(self, entities: Dict[str, List], relationships: List) -> Dict[str, Any]:
        """Build hybrid graph from in-memory data structures"""
        start_time = datetime.now()
        self._reset_stats()
        
        logger.info(" Building hybrid two-tiered graph from data...")
        
        try:
            # Convert entities to expected format (dataclass objects to dicts)
            from dataclasses import asdict
            
            def entities_to_dicts(entity_list):
                """Convert list of dataclass entities to list of dicts"""
                return [self._sanitize_integer_values(asdict(entity)) for entity in entity_list]
            
            entities_formatted = {
                'processes': entities_to_dicts(entities.get('Process', [])),
                'threads': entities_to_dicts(entities.get('Thread', [])),
                'files': entities_to_dicts(entities.get('File', [])),
                'sockets': entities_to_dicts(entities.get('Socket', [])),
                'cpus': entities_to_dicts(entities.get('CPU', [])),
                'memory_regions': entities_to_dicts(entities.get('MemoryRegion', [])),
                'event_relationships': relationships
            }
            
            # Create entity nodes (Tier 1)
            self.create_entity_nodes(entities_formatted)
            
            # Create event relationships (Tier 2) - Convert to dicts if needed
            relationships_formatted = []
            for rel in relationships:
                if hasattr(rel, '__dict__'):  # If it's an object
                    rel_dict = self._sanitize_integer_values(asdict(rel))
                    relationships_formatted.append(rel_dict)
                else:  # If it's already a dict
                    relationships_formatted.append(self._sanitize_integer_values(rel))
            
            self.create_event_relationships(relationships_formatted)
            
            # Calculate processing time
            self.stats['processing_time'] = (datetime.now() - start_time).total_seconds()
            
            # Print summary
            self._print_build_summary()
            
            return self.stats
            
        except Exception as e:
            logger.error(f" Hybrid graph building failed: {e}")
            raise

    def build_hybrid_graph(self, entities_dir: str,
                           schema: Optional[GraphSchema] = None,
                           clear_existing: bool = True) -> None:
        """Build complete hybrid graph"""
        start_time = datetime.now()
        self._reset_stats()
        schema = schema or SchemaRegistry.create_default_registry().default()
        
        logger.info(" Building hybrid two-tiered graph...")
        
        try:
            self.prepare_schema(schema, clear_existing=clear_existing)
            
            # Load entities and relationships  
            entities = self.load_entities(entities_dir)
            
            # Create entity nodes (Tier 1)
            self.create_entity_nodes(entities)
            
            # Create event relationships (Tier 2)
            self.create_event_relationships(entities['event_relationships'])
            
            # Calculate processing time
            self.stats['processing_time'] = (datetime.now() - start_time).total_seconds()
            
            # Print summary
            self._print_build_summary()
            
        except Exception as e:
            logger.error(f" Hybrid graph building failed: {e}")
            raise
    
    def _print_build_summary(self) -> None:
        """Print build summary"""
        print("\n" + "="*70)
        print(" Hybrid Two-Tiered Graph Construction Summary")
        print("="*70)
        print(f"  Processing Time: {self.stats['processing_time']:.2f} seconds")
        print(f"  Nodes Created: {self.stats['nodes_created']:,}")
        print(f" Relationships Created: {self.stats['relationships_created']:,}")
        print(f" Constraints Created: {self.stats['constraints_created']:,}")
        print(f" Indexes Created: {self.stats['indexes_created']:,}")
        
        # Query graph statistics
        with self.driver.session() as session:
            # Node distribution
            print(f"\n Node Distribution:")
            for label in ['Process', 'Thread', 'File', 'Socket', 'CPU', 'MemoryRegion']:
                try:
                    result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                    count = result.single()["count"]
                    if count > 0:
                        print(f"   • {label}: {count:,}")
                except:
                    pass
            
            # Relationship distribution
            print(f"\n Relationship Distribution:")
            try:
                result = session.run("""
                    MATCH ()-[r]->()
                    RETURN type(r) as rel_type, count(r) as count
                    ORDER BY count DESC
                    LIMIT 10
                """)
                
                for record in result:
                    print(f"   • {record['rel_type']}: {record['count']:,}")
            except Exception as e:
                logger.warning(f"Could not get relationship statistics: {e}")
        
        print(f"\n Hybrid Model Benefits:")
        print("    Fast Entity Queries: Direct relationships between core entities")
        print("    Rich Temporal Data: Complete event context in relationship properties")
        print("    Efficient Storage: Events as relationships (no separate event nodes)")
        print("    Chronological Reconstruction: Timestamp indexing enables story rebuilding")
        print("    Context Awareness: Kernel and user space events unified")
        print("    LLM Optimized: Fast overviews + detailed diagnostic capabilities")
        
        print(f"\n Hybrid graph construction completed successfully!")
        print(" Ready for two-tiered querying: Fast + Deep")


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Hybrid Two-Tiered Graph Builder")
    parser.add_argument("--entities-dir", "-e", default="hybrid_entities",
                       help="Directory containing hybrid entities (default: hybrid_entities)")
    parser.add_argument("--clear", "-c", action="store_true", default=True,
                       help="Clear existing database (default: True)")
    
    args = parser.parse_args()
    
    print(" Hybrid Two-Tiered Graph Builder")
    print("=" * 60)
    print(" Building optimized graph: Entity nodes + Event relationships")
    print(" Tier 1: Fast entity lookups")
    print(" Tier 2: Rich temporal story reconstruction")
    print()
    
    builder = None
    try:
        # Initialize hybrid graph builder
        builder = HybridGraphBuilder()
        registry = SchemaRegistry.create_default_registry()
        schema = registry.default()
        
        # Build the hybrid graph
        builder.build_hybrid_graph(args.entities_dir, schema=schema, clear_existing=args.clear)
        
        logger.info(" Hybrid graph building completed successfully!")
        
    except Exception as e:
        logger.error(f" Hybrid graph building failed: {e}")
        raise
    finally:
        if builder:
            builder.close()


if __name__ == "__main__":
    main()