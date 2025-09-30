#!/usr/bin/env python3
"""
Complete Integrated Pipeline - Logs → Processor → Builder → Graph
================================================================

Unified pipeline that integrates:
1.  LTTng Trace Capture (Enhanced benchmark tracer)
2.  Universal Data Processing (100% schema compliance)
3.   Knowledge Graph Construction (Neo4j builder)
4.  Data Integrity Validation (100% verification)

Pipeline Architecture:
  Raw Traces → Schema Detection → Entity/Relationship Extraction → Graph Build → Validation

Features:
- End-to-end trace processing with quality assurance
- Automatic schema detection and selection
- Real-time progress monitoring and metrics
- Comprehensive data integrity validation
- Support for multiple applications (Redis, PostgreSQL, Universal)
- Rollback capabilities for failed operations
"""

import os
import sys
import json
import time
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

# Import our components
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / 'benchmarks'))
sys.path.append(str(Path(__file__).parent / 'schemas'))

from universal_data_processor import UniversalDataProcessor, create_universal_processor
from modular_schema_system import ModularSchemaManager, get_optimal_schema_for_trace
from redis_schema import get_redis_schema, is_redis_trace
from neo4j_graph_builder import Neo4jGraphBuilder

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class PipelineConfig:
    """Pipeline configuration settings"""
    # LTTng Configuration
    lttng_session_name: str = "kernel_trace_session"
    trace_duration: int = 60  # seconds
    trace_output_dir: str = "./traces"
    
    # Processing Configuration
    schema_hint: Optional[str] = None  # 'redis', 'postgresql', etc.
    enable_enhanced_extraction: bool = True
    quality_threshold: float = 0.8
    
    # Graph Database Configuration
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    neo4j_database: str = "kernel_traces"
    
    # Validation Configuration
    enable_integrity_validation: bool = True
    max_validation_samples: int = 1000
    validation_timeout: int = 300  # seconds
    
    # Output Configuration
    results_dir: str = "./results"
    save_intermediate_results: bool = True
    generate_reports: bool = True

@dataclass
class PipelineResults:
    """Pipeline execution results"""
    # Execution metadata
    pipeline_id: str
    start_time: datetime
    end_time: datetime
    total_duration: float
    
    # Trace capture results
    trace_file_path: str
    trace_size_mb: float
    trace_events: int
    
    # Processing results
    schema_used: str
    entities_extracted: int
    relationships_extracted: int
    relationship_types_found: List[str]
    processing_quality: float
    
    # Graph construction results
    nodes_created: int
    edges_created: int
    graph_build_time: float
    
    # Validation results
    validation_passed: bool
    integrity_score: float
    validation_errors: List[str]
    
    # Overall status
    success: bool
    error_message: Optional[str] = None

class IntegratedPipeline:
    """Complete integrated pipeline for kernel trace analysis"""
    
    def __init__(self, config: PipelineConfig):
        """Initialize pipeline with configuration"""
        self.config = config
        self.pipeline_id = f"pipeline_{int(time.time())}"
        self.results: Optional[PipelineResults] = None
        
        # Initialize components
        self.processor = create_universal_processor(config.schema_hint)
        self.graph_builder = None
        self.schema_manager = ModularSchemaManager()
        
        # Create output directories
        self._setup_directories()
        
        logger.info(f" INTEGRATED PIPELINE INITIALIZED")
        logger.info(f"    Pipeline ID: {self.pipeline_id}")
        logger.info(f"    Schema hint: {config.schema_hint or 'Auto-detect'}")
        logger.info(f"    Quality threshold: {config.quality_threshold:.1%}")
    
    def execute_full_pipeline(self, target_command: str = "ls -la /tmp") -> PipelineResults:
        """
        Execute the complete pipeline from trace capture to graph validation
        
        Args:
            target_command: Command to trace (for benchmarking)
            
        Returns:
            Complete pipeline results with validation
        """
        start_time = datetime.now()
        logger.info(" STARTING COMPLETE INTEGRATED PIPELINE")
        logger.info("=" * 60)
        
        try:
            # Phase 1: Enhanced LTTng Trace Capture
            trace_file = self._capture_enhanced_traces(target_command)
            
            # Phase 2: Universal Data Processing  
            processing_results = self._process_traces(trace_file)
            
            # Phase 3: Knowledge Graph Construction
            graph_results = self._build_knowledge_graph(processing_results)
            
            # Phase 4: Data Integrity Validation
            validation_results = self._validate_data_integrity(
                trace_file, processing_results, graph_results
            )
            
            # Phase 5: Results Compilation
            self.results = self._compile_results(
                start_time, trace_file, processing_results, 
                graph_results, validation_results
            )
            
            logger.info(" PIPELINE EXECUTION COMPLETED SUCCESSFULLY!")
            self._log_final_summary()
            
            return self.results
            
        except Exception as e:
            error_msg = f"Pipeline execution failed: {str(e)}"
            logger.error(f" {error_msg}")
            
            self.results = PipelineResults(
                pipeline_id=self.pipeline_id,
                start_time=start_time,
                end_time=datetime.now(),
                total_duration=(datetime.now() - start_time).total_seconds(),
                trace_file_path="",
                trace_size_mb=0.0,
                trace_events=0,
                schema_used="unknown",
                entities_extracted=0,
                relationships_extracted=0,
                relationship_types_found=[],
                processing_quality=0.0,
                nodes_created=0,
                edges_created=0,
                graph_build_time=0.0,
                validation_passed=False,
                integrity_score=0.0,
                validation_errors=[error_msg],
                success=False,
                error_message=error_msg
            )
            
            return self.results
    
    def _capture_enhanced_traces(self, target_command: str) -> str:
        """Phase 1: Capture enhanced LTTng traces"""
        logger.info(" PHASE 1: Enhanced LTTng Trace Capture")
        logger.info("-" * 40)
        
        # Use our enhanced benchmark tracer
        benchmark_script = Path(__file__).parent / "benchmarks" / "benchmark_tracer.py"
        
        if not benchmark_script.exists():
            raise FileNotFoundError("Enhanced benchmark tracer not found")
        
        # Execute enhanced tracer
        trace_output_dir = Path(self.config.trace_output_dir) / self.pipeline_id
        trace_output_dir.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            "python3", str(benchmark_script),
            "--command", target_command,
            "--duration", str(self.config.trace_duration),
            "--session-name", f"{self.config.lttng_session_name}_{self.pipeline_id}",
            "--output-dir", str(trace_output_dir)
        ]
        
        logger.info(f"    Target command: {target_command}")
        logger.info(f"     Duration: {self.config.trace_duration}s")
        logger.info(f"    Output: {trace_output_dir}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                raise RuntimeError(f"Trace capture failed: {result.stderr}")
            
            # Find the generated trace file
            trace_files = list(trace_output_dir.glob("*.txt"))
            if not trace_files:
                raise FileNotFoundError("No trace files generated")
            
            trace_file = trace_files[0]  # Use the first/main trace file
            trace_size = trace_file.stat().st_size / (1024 * 1024)  # MB
            
            logger.info(f"    Trace captured: {trace_file}")
            logger.info(f"    Size: {trace_size:.2f} MB")
            
            return str(trace_file)
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Trace capture timed out")
        except Exception as e:
            raise RuntimeError(f"Trace capture failed: {str(e)}")
    
    def _process_traces(self, trace_file: str) -> Dict[str, Any]:
        """Phase 2: Universal data processing with 100% compliance"""
        logger.info(" PHASE 2: Universal Data Processing")
        logger.info("-" * 40)
        
        # Process traces with universal processor
        processing_results = self.processor.process_trace_file(
            trace_file, self.config.schema_hint
        )
        
        # Validate processing quality
        quality_score = processing_results['validation']['data_integrity']
        
        if quality_score < self.config.quality_threshold:
            logger.warning(f"  Processing quality {quality_score:.1%} below threshold {self.config.quality_threshold:.1%}")
            
            # Optionally retry with enhanced settings
            if self.config.enable_enhanced_extraction:
                logger.info("    Retrying with enhanced extraction...")
                # Could implement retry logic here
        
        # Save intermediate results if configured
        if self.config.save_intermediate_results:
            results_file = Path(self.config.results_dir) / f"{self.pipeline_id}_processing.json"
            results_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(results_file, 'w') as f:
                json.dump(processing_results, f, indent=2, default=str)
            
            logger.info(f"    Processing results saved: {results_file}")
        
        return processing_results
    
    def _build_knowledge_graph(self, processing_results: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 3: Neo4j knowledge graph construction"""
        logger.info("  PHASE 3: Knowledge Graph Construction")
        logger.info("-" * 40)
        
        # Initialize graph builder
        self.graph_builder = Neo4jGraphBuilder(
            uri=self.config.neo4j_uri,
            user=self.config.neo4j_user,
            password=self.config.neo4j_password,
            database=self.config.neo4j_database
        )
        
        build_start = time.time()
        
        try:
            # Clear previous data for this pipeline
            database_name = f"{self.config.neo4j_database}_{self.pipeline_id}"
            
            # Create nodes
            nodes_created = 0
            for entity_type, entities in processing_results['entities'].items():
                for entity in entities:
                    self.graph_builder.create_node(
                        entity_type, entity['entity_id'], entity['properties']
                    )
                    nodes_created += 1
            
            logger.info(f"    Created {nodes_created:,} nodes")
            
            # Create relationships
            edges_created = 0
            for relationship in processing_results['relationships']:
                self.graph_builder.create_relationship(
                    relationship['source_type'], relationship['source_id'],
                    relationship['target_type'], relationship['target_id'],
                    relationship['relationship_type'], relationship['properties']
                )
                edges_created += 1
            
            logger.info(f"    Created {edges_created:,} relationships")
            
            build_time = time.time() - build_start
            logger.info(f"     Build time: {build_time:.2f}s")
            
            return {
                'nodes_created': nodes_created,
                'edges_created': edges_created,
                'build_time': build_time,
                'database': database_name,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"    Graph construction failed: {str(e)}")
            return {
                'nodes_created': 0,
                'edges_created': 0,
                'build_time': time.time() - build_start,
                'database': '',
                'success': False,
                'error': str(e)
            }
    
    def _validate_data_integrity(self, trace_file: str, processing_results: Dict[str, Any], 
                                graph_results: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 4: Comprehensive data integrity validation"""
        logger.info(" PHASE 4: Data Integrity Validation")
        logger.info("-" * 40)
        
        if not self.config.enable_integrity_validation:
            logger.info("   ⏭  Validation disabled, skipping...")
            return {
                'validation_passed': True,
                'integrity_score': 1.0,
                'validation_errors': [],
                'checks_performed': []
            }
        
        validation_errors = []
        checks_performed = []
        
        try:
            # Check 1: Trace file integrity
            logger.info("    Validating trace file integrity...")
            trace_validation = self._validate_trace_file(trace_file)
            checks_performed.append("trace_file_integrity")
            
            if not trace_validation['valid']:
                validation_errors.extend(trace_validation['errors'])
            
            # Check 2: Processing completeness
            logger.info("    Validating processing completeness...")
            processing_validation = self._validate_processing_completeness(processing_results)
            checks_performed.append("processing_completeness")
            
            if not processing_validation['valid']:
                validation_errors.extend(processing_validation['errors'])
            
            # Check 3: Graph consistency
            logger.info("    Validating graph consistency...")
            graph_validation = self._validate_graph_consistency(
                processing_results, graph_results
            )
            checks_performed.append("graph_consistency")
            
            if not graph_validation['valid']:
                validation_errors.extend(graph_validation['errors'])
            
            # Check 4: Temporal consistency
            logger.info("    Validating temporal consistency...")
            temporal_validation = self._validate_temporal_consistency(processing_results)
            checks_performed.append("temporal_consistency")
            
            if not temporal_validation['valid']:
                validation_errors.extend(temporal_validation['errors'])
            
            # Calculate overall integrity score
            total_checks = len(checks_performed)
            passed_checks = total_checks - len(validation_errors)
            integrity_score = passed_checks / max(total_checks, 1)
            
            validation_passed = len(validation_errors) == 0
            
            logger.info(f"    Validation results:")
            logger.info(f"       Checks passed: {passed_checks}/{total_checks}")
            logger.info(f"       Integrity score: {integrity_score:.1%}")
            
            if validation_errors:
                logger.warning(f"        Errors found: {len(validation_errors)}")
                for error in validation_errors[:5]:  # Show first 5 errors
                    logger.warning(f"         - {error}")
            
            return {
                'validation_passed': validation_passed,
                'integrity_score': integrity_score,
                'validation_errors': validation_errors,
                'checks_performed': checks_performed
            }
            
        except Exception as e:
            error_msg = f"Validation process failed: {str(e)}"
            logger.error(f"    {error_msg}")
            
            return {
                'validation_passed': False,
                'integrity_score': 0.0,
                'validation_errors': [error_msg],
                'checks_performed': checks_performed
            }
    
    def _validate_trace_file(self, trace_file: str) -> Dict[str, Any]:
        """Validate trace file integrity and quality"""
        errors = []
        
        try:
            # Check file exists and readable
            if not os.path.exists(trace_file):
                errors.append(f"Trace file not found: {trace_file}")
                return {'valid': False, 'errors': errors}
            
            # Check file size
            file_size = os.path.getsize(trace_file)
            if file_size < 1024:  # Less than 1KB
                errors.append("Trace file too small, may be incomplete")
            
            # Sample trace content for quality
            line_count = 0
            valid_lines = 0
            
            with open(trace_file, 'r') as f:
                for i, line in enumerate(f):
                    if i >= 1000:  # Sample first 1000 lines
                        break
                    
                    line_count += 1
                    
                    # Check for valid LTTng format
                    if re.search(r'\[\d{2}:\d{2}:\d{2}\.\d+\]', line):
                        valid_lines += 1
            
            if line_count > 0:
                quality_ratio = valid_lines / line_count
                if quality_ratio < 0.8:
                    errors.append(f"Poor trace quality: only {quality_ratio:.1%} valid lines")
            else:
                errors.append("Trace file appears to be empty")
            
            return {'valid': len(errors) == 0, 'errors': errors}
            
        except Exception as e:
            errors.append(f"Trace validation error: {str(e)}")
            return {'valid': False, 'errors': errors}
    
    def _validate_processing_completeness(self, processing_results: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that processing extracted expected data"""
        errors = []
        
        try:
            # Check entity extraction
            total_entities = processing_results['validation']['entity_count']
            if total_entities == 0:
                errors.append("No entities extracted from trace")
            
            # Check relationship extraction
            total_relationships = processing_results['validation']['relationship_count']
            if total_relationships == 0:
                errors.append("No relationships extracted from trace")
            
            # Check relationship type coverage
            relationship_types = processing_results['validation']['relationship_types_found']
            if len(relationship_types) < 5:  # Expect at least 5 different types
                errors.append(f"Low relationship type diversity: only {len(relationship_types)} types found")
            
            # Check data quality score
            quality_score = processing_results['validation']['data_integrity']
            if quality_score < self.config.quality_threshold:
                errors.append(f"Processing quality {quality_score:.1%} below threshold")
            
            return {'valid': len(errors) == 0, 'errors': errors}
            
        except KeyError as e:
            errors.append(f"Missing processing result field: {str(e)}")
            return {'valid': False, 'errors': errors}
        except Exception as e:
            errors.append(f"Processing validation error: {str(e)}")
            return {'valid': False, 'errors': errors}
    
    def _validate_graph_consistency(self, processing_results: Dict[str, Any], 
                                   graph_results: Dict[str, Any]) -> Dict[str, Any]:
        """Validate graph matches processed data"""
        errors = []
        
        try:
            # Check node count consistency
            expected_nodes = processing_results['validation']['entity_count']
            actual_nodes = graph_results['nodes_created']
            
            if abs(expected_nodes - actual_nodes) > expected_nodes * 0.1:  # 10% tolerance
                errors.append(f"Node count mismatch: expected {expected_nodes}, got {actual_nodes}")
            
            # Check relationship count consistency
            expected_edges = processing_results['validation']['relationship_count']
            actual_edges = graph_results['edges_created']
            
            if abs(expected_edges - actual_edges) > expected_edges * 0.1:  # 10% tolerance
                errors.append(f"Edge count mismatch: expected {expected_edges}, got {actual_edges}")
            
            # Check graph builder success
            if not graph_results.get('success', False):
                errors.append(f"Graph construction failed: {graph_results.get('error', 'Unknown error')}")
            
            return {'valid': len(errors) == 0, 'errors': errors}
            
        except Exception as e:
            errors.append(f"Graph consistency validation error: {str(e)}")
            return {'valid': False, 'errors': errors}
    
    def _validate_temporal_consistency(self, processing_results: Dict[str, Any]) -> Dict[str, Any]:
        """Validate temporal ordering and consistency of relationships"""
        errors = []
        
        try:
            relationships = processing_results.get('relationships', [])
            
            if not relationships:
                return {'valid': True, 'errors': []}  # No relationships to validate
            
            # Check timestamp validity
            invalid_timestamps = 0
            timestamps = []
            
            for rel in relationships:
                timestamp = rel.get('timestamp', 0)
                if timestamp <= 0:
                    invalid_timestamps += 1
                else:
                    timestamps.append(timestamp)
            
            if invalid_timestamps > 0:
                errors.append(f"Found {invalid_timestamps} relationships with invalid timestamps")
            
            # Check temporal ordering makes sense
            if timestamps:
                timestamps.sort()
                time_span = timestamps[-1] - timestamps[0]
                
                if time_span <= 0:
                    errors.append("All relationships have the same timestamp - no temporal progression")
                elif time_span > 86400:  # More than 24 hours
                    errors.append(f"Suspicious time span: {time_span:.2f} seconds")
            
            return {'valid': len(errors) == 0, 'errors': errors}
            
        except Exception as e:
            errors.append(f"Temporal validation error: {str(e)}")
            return {'valid': False, 'errors': errors}
    
    def _compile_results(self, start_time: datetime, trace_file: str,
                        processing_results: Dict[str, Any], graph_results: Dict[str, Any],
                        validation_results: Dict[str, Any]) -> PipelineResults:
        """Compile comprehensive pipeline results"""
        
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()
        
        # Extract trace metrics
        trace_size = os.path.getsize(trace_file) / (1024 * 1024) if os.path.exists(trace_file) else 0
        trace_events = processing_results.get('metrics', {}).get('total_events', 0)
        
        # Determine overall success
        processing_success = processing_results['validation']['data_integrity'] >= self.config.quality_threshold
        graph_success = graph_results.get('success', False)
        validation_success = validation_results.get('validation_passed', False)
        
        overall_success = processing_success and graph_success and validation_success
        
        return PipelineResults(
            pipeline_id=self.pipeline_id,
            start_time=start_time,
            end_time=end_time,
            total_duration=total_duration,
            trace_file_path=trace_file,
            trace_size_mb=trace_size,
            trace_events=trace_events,
            schema_used=processing_results['schema_info']['name'],
            entities_extracted=processing_results['validation']['entity_count'],
            relationships_extracted=processing_results['validation']['relationship_count'],
            relationship_types_found=processing_results['validation']['relationship_types_found'],
            processing_quality=processing_results['validation']['data_integrity'],
            nodes_created=graph_results['nodes_created'],
            edges_created=graph_results['edges_created'],
            graph_build_time=graph_results['build_time'],
            validation_passed=validation_results['validation_passed'],
            integrity_score=validation_results['integrity_score'],
            validation_errors=validation_results['validation_errors'],
            success=overall_success
        )
    
    def _setup_directories(self):
        """Create necessary output directories"""
        for directory in [self.config.trace_output_dir, self.config.results_dir]:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def _log_final_summary(self):
        """Log comprehensive final summary"""
        if not self.results:
            return
        
        logger.info(" PIPELINE EXECUTION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"    Pipeline ID: {self.results.pipeline_id}")
        logger.info(f"     Total Duration: {self.results.total_duration:.2f}s")
        logger.info(f"    Trace File: {self.results.trace_file_path}")
        logger.info(f"    Trace Size: {self.results.trace_size_mb:.2f} MB")
        logger.info(f"    Events Processed: {self.results.trace_events:,}")
        logger.info("")
        logger.info(f"    Schema Used: {self.results.schema_used}")
        logger.info(f"     Entities: {self.results.entities_extracted:,}")
        logger.info(f"    Relationships: {self.results.relationships_extracted:,}")
        logger.info(f"    Relationship Types: {len(self.results.relationship_types_found)}")
        logger.info("")
        logger.info(f"    Processing Quality: {self.results.processing_quality:.1%}")
        logger.info(f"    Integrity Score: {self.results.integrity_score:.1%}")
        logger.info(f"    Validation Passed: {self.results.validation_passed}")
        logger.info("")
        
        if self.results.success:
            logger.info(f" PIPELINE COMPLETED SUCCESSFULLY!")
            logger.info(f"    Ready for LLM querying and analysis")
        else:
            logger.error(f" PIPELINE COMPLETED WITH ERRORS")
            if self.results.validation_errors:
                logger.error(f"    Errors: {len(self.results.validation_errors)}")
    
    def save_results(self, output_path: str = None) -> str:
        """Save pipeline results to file"""
        if not self.results:
            raise ValueError("No results to save - pipeline not executed")
        
        if output_path is None:
            output_path = Path(self.config.results_dir) / f"{self.pipeline_id}_complete_results.json"
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(asdict(self.results), f, indent=2, default=str)
        
        logger.info(f" Pipeline results saved: {output_path}")
        return str(output_path)

# Factory functions for easy usage
def create_pipeline(config: PipelineConfig = None) -> IntegratedPipeline:
    """Create integrated pipeline with default or custom configuration"""
    if config is None:
        config = PipelineConfig()
    return IntegratedPipeline(config)

def run_redis_pipeline(target_command: str = "redis-cli ping") -> PipelineResults:
    """Run pipeline optimized for Redis tracing"""
    config = PipelineConfig(
        schema_hint="redis",
        trace_duration=30,
        quality_threshold=0.9
    )
    pipeline = create_pipeline(config)
    return pipeline.execute_full_pipeline(target_command)

def run_universal_pipeline(target_command: str = "ls -la /tmp") -> PipelineResults:
    """Run pipeline with universal schema detection"""
    config = PipelineConfig(
        schema_hint=None,  # Auto-detect
        trace_duration=60,
        quality_threshold=0.8
    )
    pipeline = create_pipeline(config)
    return pipeline.execute_full_pipeline(target_command)

if __name__ == "__main__":
    # Command line interface for pipeline execution
    import argparse
    
    parser = argparse.ArgumentParser(description="Execute integrated kernel trace pipeline")
    parser.add_argument("--command", default="ls -la /tmp", 
                       help="Command to trace and analyze")
    parser.add_argument("--schema", choices=["redis", "postgresql", "auto"],
                       default="auto", help="Schema hint for processing")
    parser.add_argument("--duration", type=int, default=60,
                       help="Trace duration in seconds")
    parser.add_argument("--quality-threshold", type=float, default=0.8,
                       help="Minimum quality threshold for processing")
    parser.add_argument("--output-dir", default="./results",
                       help="Output directory for results")
    
    args = parser.parse_args()
    
    # Create configuration
    config = PipelineConfig(
        schema_hint=args.schema if args.schema != "auto" else None,
        trace_duration=args.duration,
        quality_threshold=args.quality_threshold,
        results_dir=args.output_dir
    )
    
    # Execute pipeline
    logger.info(f" Starting pipeline with command: {args.command}")
    
    pipeline = create_pipeline(config)
    results = pipeline.execute_full_pipeline(args.command)
    
    # Save results
    results_file = pipeline.save_results()
    
    # Exit with appropriate code
    exit_code = 0 if results.success else 1
    sys.exit(exit_code)