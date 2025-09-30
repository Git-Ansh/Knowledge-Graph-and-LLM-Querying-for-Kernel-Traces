#!/usr/bin/env python3
"""
 LTTng Kernel Trace Analysis Pipeline
======================================
Complete orchestrator for LTTng kernel trace capture, processing, and analysis.

Features:
- Automated trace processing pipeline
- Knowledge graph construction  
- Advanced analytics and reporting
- Benchmark trace capture utilities

Author: Knowledge Graph and LLM Querying for Kernel Traces Project
Date: September 29, 2025
"""

import os
import sys
import subprocess
import argparse
import time
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class LTTngPipelineOrchestrator:
    """Main orchestrator for the complete LTTng analysis pipeline."""
    
    def __init__(self, project_root=None):
        self.project_root = Path(project_root) if project_root else Path(__file__).parent
        self.src_dir = self.project_root / "src"
        self.schema_dir = self.project_root / "schema_outputs"
        self.observations_dir = self.project_root / "observations"
        self.traces_dir = self.project_root / "traces"
        self.benchmarks_dir = self.project_root / "benchmarks"
        
        # Core pipeline components
        self.preprocessor = self.src_dir / "lttng_data_preprocessor.py"
        self.graph_builder = self.src_dir / "universal_graph_builder.py"
        self.analyzer = self.src_dir / "universal_trace_analyzer.py"
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure all required directories exist."""
        for directory in [self.src_dir, self.schema_dir, self.observations_dir, 
                         self.traces_dir, self.benchmarks_dir]:
            directory.mkdir(exist_ok=True)
            logger.info(f" Directory ready: {directory}")
    
    def _run_command(self, command, description, cwd=None):
        """Execute a command and handle results."""
        logger.info(f" {description}")
        logger.info(f" Command: {' '.join(command)}")
        
        try:
            start_time = time.time()
            result = subprocess.run(
                command,
                cwd=cwd or self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            
            duration = time.time() - start_time
            logger.info(f" {description} completed successfully in {duration:.2f}s")
            
            if result.stdout:
                print(result.stdout)
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f" {description} failed with exit code {e.returncode}")
            if e.stdout:
                logger.error(f"STDOUT:\n{e.stdout}")
            if e.stderr:
                logger.error(f"STDERR:\n{e.stderr}")
            return False
        except Exception as e:
            logger.error(f" {description} failed with exception: {e}")
            return False
    
    def run_preprocessing(self):
        """Step 1: Process raw LTTng trace data."""
        logger.info("=" * 60)
        logger.info(" STEP 1: LTTng Trace Data Preprocessing")
        logger.info("=" * 60)
        
        if not self.preprocessor.exists():
            logger.error(f" Preprocessor not found: {self.preprocessor}")
            return False
        
        return self._run_command(
            ["python3", str(self.preprocessor)],
            "Processing LTTng trace data and extracting entities"
        )
    
    def run_graph_building(self, schema="universal_kernel", clear_db=True):
        """Step 2: Build knowledge graph from processed entities."""
        logger.info("=" * 60)
        logger.info("  STEP 2: Knowledge Graph Construction")
        logger.info("=" * 60)
        
        if not self.graph_builder.exists():
            logger.error(f" Graph builder not found: {self.graph_builder}")
            return False
        
        command = ["python3", str(self.graph_builder), "--schema", schema, "--entities-dir", str(self.schema_dir / "processed_entities")]
        if clear_db:
            command.append("--clear")
        
        return self._run_command(
            command,
            f"Building knowledge graph with schema '{schema}'"
        )
    
    def run_analysis(self):
        """Step 3: Perform advanced analytics on the knowledge graph."""
        logger.info("=" * 60)
        logger.info(" STEP 3: Advanced Analytics and Reporting")
        logger.info("=" * 60)
        
        if not self.analyzer.exists():
            logger.error(f" Analyzer not found: {self.analyzer}")
            return False
        
        success = self._run_command(
            ["python3", str(self.analyzer)],
            "Running comprehensive trace analysis"
        )
        
        # Move analysis results to observations
        analysis_file = self.project_root / "analysis_summary.json"
        if analysis_file.exists():
            target = self.observations_dir / "analysis_summary.json"
            analysis_file.rename(target)
            logger.info(f" Analysis results moved to: {target}")
        
        return success
    
    def run_complete_pipeline(self, schema="universal_kernel"):
        """Execute the complete analysis pipeline."""
        logger.info("" * 30)
        logger.info(" COMPLETE LTTNG ANALYSIS PIPELINE")
        logger.info("" * 30)
        
        start_time = time.time()
        
        # Step 1: Preprocessing
        if not self.run_preprocessing():
            logger.error(" Pipeline failed at preprocessing step")
            return False
        
        # Step 2: Graph Building
        if not self.run_graph_building(schema):
            logger.error(" Pipeline failed at graph building step")
            return False
        
        # Step 3: Analysis
        if not self.run_analysis():
            logger.error(" Pipeline failed at analysis step")
            return False
        
        total_time = time.time() - start_time
        
        logger.info("" * 30)
        logger.info(f" PIPELINE COMPLETED SUCCESSFULLY in {total_time:.2f}s")
        logger.info("" * 30)
        
        return True
    
    def move_schema_outputs(self):
        """Move schema-related outputs to schema_outputs directory."""
        logger.info(" Moving schema outputs...")
        
        schema_files = ["processed_entities", "*.cypher"]
        for pattern in schema_files:
            for file in self.project_root.glob(pattern):
                if file.is_file() or file.is_dir():
                    target = self.schema_dir / file.name
                    if target.exists():
                        if target.is_dir():
                            import shutil
                            shutil.rmtree(target)
                        else:
                            target.unlink()
                    file.rename(target)
                    logger.info(f" Moved {file.name} to schema_outputs/")


def main():
    """Main entry point for the LTTng analysis pipeline."""
    parser = argparse.ArgumentParser(
        description="LTTng Kernel Trace Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 main.py                           # Run complete pipeline
  python3 main.py --step preprocess         # Run only preprocessing
  python3 main.py --step graph              # Run only graph building
  python3 main.py --step analyze            # Run only analysis
  python3 main.py --schema custom_kernel    # Use custom schema
        """
    )
    
    parser.add_argument(
        "--step",
        choices=["preprocess", "graph", "analyze", "complete"],
        default="complete",
        help="Pipeline step to execute (default: complete)"
    )
    
    parser.add_argument(
        "--schema",
        default="universal_kernel",
        help="Graph schema to use (default: universal_kernel)"
    )
    
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Don't clear database before graph building"
    )
    
    parser.add_argument(
        "--project-root",
        help="Project root directory (default: current directory)"
    )
    
    args = parser.parse_args()
    
    # Initialize orchestrator
    orchestrator = LTTngPipelineOrchestrator(args.project_root)
    
    # Execute requested step(s)
    success = False
    
    if args.step == "preprocess":
        success = orchestrator.run_preprocessing()
    elif args.step == "graph":
        success = orchestrator.run_graph_building(args.schema, not args.no_clear)
    elif args.step == "analyze":
        success = orchestrator.run_analysis()
    elif args.step == "complete":
        success = orchestrator.run_complete_pipeline(args.schema)
    
    # Move outputs to appropriate directories
    orchestrator.move_schema_outputs()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()