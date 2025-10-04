#!/usr/bin/env python3
"""
Main Pipeline Orchestrator
===========================
Orchestrates the complete trace-to-graph pipeline for the layered knowledge graph.

Pipeline stages:
1. Trace Parsing - Convert raw LTTng output to structured events
2. Entity Extraction - Build kernel reality layer actors
3. Sequence Building - Group events into logical operations
4. Graph Construction - Build Neo4j knowledge graph

Author: Knowledge Graph and LLM Querying for Kernel Traces Project
Date: October 3, 2025
"""

import sys
import logging
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from trace_parser import TraceParser
from entity_extractor import EntityExtractor
from event_sequence_builder import EventSequenceBuilder
from graph_builder import GraphBuilder


class PipelineOrchestrator:
    """Orchestrates the complete pipeline from trace to knowledge graph."""
    
    def __init__(self, trace_dir: Path, output_dir: Path, 
                 neo4j_uri: str = "bolt://10.0.2.2:7687",
                 neo4j_user: str = "neo4j",
                 neo4j_password: str = "sudoroot"):
        """
        Initialize pipeline orchestrator.
        
        Args:
            trace_dir: Directory containing trace files
            output_dir: Directory for output files
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
        """
        self.trace_dir = Path(trace_dir)
        self.output_dir = Path(output_dir)
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        
        # Create output directories
        self.entities_dir = self.output_dir / "processed_entities"
        self.stats_dir = self.output_dir / "graph_stats"
        self.entities_dir.mkdir(parents=True, exist_ok=True)
        self.stats_dir.mkdir(parents=True, exist_ok=True)
        
        # Load schema
        self.schema_file = Path(__file__).parent / "schemas" / "layered_schema.json"
        self.schema_config = self._load_schema()
        
        # Pipeline components
        self.parser = None
        self.extractor = None
        self.sequence_builder = None
        self.graph_builder = None
        
        # Metadata
        self.trace_metadata = None
        self.pipeline_stats = {
            'start_time': None,
            'end_time': None,
            'stages': {}
        }
        
        logging.info("=" * 70)
        logging.info("Pipeline Orchestrator Initialized")
        logging.info("=" * 70)
        logging.info(f"Trace directory: {self.trace_dir}")
        logging.info(f"Output directory: {self.output_dir}")
        logging.info(f"Schema: {self.schema_file.name}")
    
    def _load_schema(self) -> Optional[dict]:
        """Load schema configuration."""
        if self.schema_file.exists():
            with open(self.schema_file, 'r') as f:
                schema = json.load(f)
            logging.info(f"Loaded schema version {schema.get('schema_version', 'unknown')}")
            return schema
        else:
            logging.warning(f"Schema file not found: {self.schema_file}")
            return None
    
    def _load_trace_metadata(self) -> Optional[dict]:
        """Load trace metadata if available."""
        metadata_file = self.trace_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            logging.info(f"Loaded trace metadata for application: {metadata.get('application', 'unknown')}")
            return metadata
        else:
            logging.info("No trace metadata found")
            return None
    
    def run_complete_pipeline(self):
        """Execute the complete pipeline from trace to graph."""
        self.pipeline_stats['start_time'] = datetime.now()
        logging.info("\n" + "=" * 70)
        logging.info("STARTING COMPLETE PIPELINE")
        logging.info("=" * 70 + "\n")
        
        try:
            # Stage 1: Parse trace
            self._stage_parse_trace()
            
            # Stage 2: Extract entities
            self._stage_extract_entities()
            
            # Stage 3: Build event sequences
            self._stage_build_sequences()
            
            # Stage 4: Build graph
            self._stage_build_graph()
            
            # Complete
            self._finalize_pipeline()
            
        except Exception as e:
            logging.error(f"Pipeline failed: {e}", exc_info=True)
            raise
    
    def _stage_parse_trace(self):
        """Stage 1: Parse raw trace file."""
        stage_name = "STAGE 1: TRACE PARSING"
        logging.info("\n" + "=" * 70)
        logging.info(stage_name)
        logging.info("=" * 70)
        
        stage_start = datetime.now()
        
        # Find trace output file
        trace_file = self.trace_dir / "trace_output.txt"
        if not trace_file.exists():
            raise FileNotFoundError(f"Trace file not found: {trace_file}")
        
        logging.info(f"Parsing trace file: {trace_file.name}")
        logging.info(f"File size: {trace_file.stat().st_size / 1024 / 1024:.2f} MB")
        
        # Parse
        self.parser = TraceParser(trace_file)
        events = self.parser.parse()
        
        # Log statistics
        stats = self.parser.get_statistics()
        logging.info(f"\nParsing Results:")
        logging.info(f"  Total lines processed: {stats['total_lines']:,}")
        logging.info(f"  Events extracted: {stats['total_events']:,}")
        logging.info(f"  Parse success rate: {stats['success_rate']:.1f}%")
        logging.info(f"  Unique event types: {stats['unique_event_types']}")
        logging.info(f"  Time range: {stats['time_range_seconds']:.2f} seconds")
        
        stage_duration = (datetime.now() - stage_start).total_seconds()
        self.pipeline_stats['stages']['parse'] = {
            'duration_seconds': stage_duration,
            'events_extracted': len(events),
            'parse_rate': len(events) / stage_duration if stage_duration > 0 else 0
        }
        logging.info(f"\nStage completed in {stage_duration:.2f} seconds")
        logging.info(f"Parse rate: {len(events) / stage_duration:.0f} events/second")
    
    def _stage_extract_entities(self):
        """Stage 2: Extract kernel reality layer entities."""
        stage_name = "STAGE 2: ENTITY EXTRACTION"
        logging.info("\n" + "=" * 70)
        logging.info(stage_name)
        logging.info("=" * 70)
        
        stage_start = datetime.now()
        
        # Extract
        self.extractor = EntityExtractor(self.parser.events)
        entities = self.extractor.extract_all()
        
        # Save
        self.extractor.save_entities(self.entities_dir)
        
        stage_duration = (datetime.now() - stage_start).total_seconds()
        self.pipeline_stats['stages']['extract'] = {
            'duration_seconds': stage_duration,
            'entities_extracted': sum(len(v) for v in entities.values())
        }
        logging.info(f"\nStage completed in {stage_duration:.2f} seconds")
    
    def _stage_build_sequences(self):
        """Stage 3: Build event sequences."""
        stage_name = "STAGE 3: EVENT SEQUENCE BUILDING"
        logging.info("\n" + "=" * 70)
        logging.info(stage_name)
        logging.info("=" * 70)
        
        stage_start = datetime.now()
        
        # Build
        self.sequence_builder = EventSequenceBuilder(self.parser.events, self.schema_config)
        sequences = self.sequence_builder.build_sequences()
        
        # Save
        self.sequence_builder.save_sequences(self.entities_dir)
        
        # Log statistics
        logging.info(f"\nSequence Building Results:")
        logging.info(f"  Total sequences created: {len(sequences)}")
        summary = self.sequence_builder._generate_summary()
        logging.info(f"  Operations breakdown:")
        for operation, count in summary['operations'].items():
            avg_duration = summary['average_durations_ms'].get(operation, 0)
            logging.info(f"    {operation}: {count} sequences (avg {avg_duration:.2f}ms)")
        
        stage_duration = (datetime.now() - stage_start).total_seconds()
        self.pipeline_stats['stages']['sequences'] = {
            'duration_seconds': stage_duration,
            'sequences_created': len(sequences)
        }
        logging.info(f"\nStage completed in {stage_duration:.2f} seconds")
    
    def _stage_build_graph(self):
        """Stage 4: Build Neo4j knowledge graph."""
        stage_name = "STAGE 4: GRAPH CONSTRUCTION"
        logging.info("\n" + "=" * 70)
        logging.info(stage_name)
        logging.info("=" * 70)
        
        stage_start = datetime.now()
        
        # Load trace metadata
        self.trace_metadata = self._load_trace_metadata()
        
        # Build graph
        self.graph_builder = GraphBuilder(
            uri=self.neo4j_uri,
            user=self.neo4j_user,
            password=self.neo4j_password
        )
        
        if not self.graph_builder.connect():
            raise ConnectionError("Failed to connect to Neo4j database")
        
        try:
            logging.info("Clearing existing graph data")
            self.graph_builder.clear_database()
            
            logging.info("Creating constraints and indexes")
            self.graph_builder.create_constraints_and_indexes()
            
            logging.info("Building layered knowledge graph")
            self.graph_builder.build_graph(self.entities_dir, self.trace_metadata)
            
            # Save statistics
            self.graph_builder.save_statistics(self.stats_dir)
            
        finally:
            self.graph_builder.close()
        
        stage_duration = (datetime.now() - stage_start).total_seconds()
        self.pipeline_stats['stages']['graph'] = {
            'duration_seconds': stage_duration,
            'nodes_created': self.graph_builder.stats.nodes_created,
            'relationships_created': self.graph_builder.stats.relationships_created
        }
        logging.info(f"\nStage completed in {stage_duration:.2f} seconds")
    
    def _finalize_pipeline(self):
        """Finalize pipeline and save summary."""
        self.pipeline_stats['end_time'] = datetime.now()
        total_duration = (self.pipeline_stats['end_time'] - 
                         self.pipeline_stats['start_time']).total_seconds()
        
        logging.info("\n" + "=" * 70)
        logging.info("PIPELINE COMPLETE")
        logging.info("=" * 70)
        logging.info(f"\nTotal execution time: {total_duration:.2f} seconds")
        logging.info("\nStage Breakdown:")
        for stage, stats in self.pipeline_stats['stages'].items():
            duration = stats['duration_seconds']
            percentage = (duration / total_duration * 100) if total_duration > 0 else 0
            logging.info(f"  {stage.upper()}: {duration:.2f}s ({percentage:.1f}%)")
        
        # Save pipeline summary
        summary_file = self.output_dir / "pipeline_summary.json"
        with open(summary_file, 'w') as f:
            json.dump({
                'start_time': self.pipeline_stats['start_time'].isoformat(),
                'end_time': self.pipeline_stats['end_time'].isoformat(),
                'total_duration_seconds': total_duration,
                'stages': self.pipeline_stats['stages'],
                'trace_metadata': self.trace_metadata
            }, f, indent=2)
        logging.info(f"\nPipeline summary saved to: {summary_file}")


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('pipeline.log', mode='w')
        ]
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Knowledge Graph Pipeline - Trace to Graph Conversion',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process the latest trace
  python3 main.py
  
  # Process a specific trace
  python3 main.py --trace traces/redis_20251003_185958
  
  # Use custom Neo4j credentials
  python3 main.py --neo4j-password mypassword
  
  # Enable verbose logging
  python3 main.py --verbose
        """
    )
    
    parser.add_argument(
        '--trace',
        type=Path,
        default=Path('traces/latest'),
        help='Path to trace directory (default: traces/latest)'
    )
    
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('outputs'),
        help='Output directory for processed data (default: outputs)'
    )
    
    parser.add_argument(
        '--neo4j-uri',
        default='bolt://10.0.2.2:7687',
        help='Neo4j connection URI (default: bolt://10.0.2.2:7687)'
    )
    
    parser.add_argument(
        '--neo4j-user',
        default='neo4j',
        help='Neo4j username (default: neo4j)'
    )
    
    parser.add_argument(
        '--neo4j-password',
        default='password',
        help='Neo4j password (default: password)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Validate trace directory
    if not args.trace.exists():
        logging.error(f"Trace directory not found: {args.trace}")
        sys.exit(1)
    
    # Check for trace_output.txt
    trace_file = args.trace / "trace_output.txt"
    if not trace_file.exists():
        logging.error(f"trace_output.txt not found in {args.trace}")
        sys.exit(1)
    
    # Run pipeline
    try:
        orchestrator = PipelineOrchestrator(
            trace_dir=args.trace,
            output_dir=args.output,
            neo4j_uri=args.neo4j_uri,
            neo4j_user=args.neo4j_user,
            neo4j_password=args.neo4j_password
        )
        
        orchestrator.run_complete_pipeline()
        
        logging.info("\nPipeline execution successful!")
        sys.exit(0)
        
    except KeyboardInterrupt:
        logging.warning("\nPipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"\nPipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
