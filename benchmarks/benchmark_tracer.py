#!/usr/bin/env python3
"""
 LTTng Application Tracer
==========================
Automated LTTng kernel tracing for real-world applications.

This utility provides structured tracing for production applications:
- Redis in-memory database
- Apache/Nginx HTTP servers
- MySQL/PostgreSQL databases  
- Docker container runtime
- Custom applications

Features:
- Automated LTTng session management
- Application startup and workload tracing
- Realistic test command execution
- Structured trace storage with metadata
- Production application profiling

Author: Knowledge Graph and LLM Querying for Kernel Traces Project
Date: September 29, 2025
"""

import os
import sys
import subprocess
import argparse
import time
import json
import logging
from pathlib import Path
from datetime import datetime
import tempfile

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class LTTngBenchmarkTracer:
    """Automated LTTng tracing for application benchmarks."""
    
    def __init__(self, project_root=None):
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent
        self.traces_dir = self.project_root / "traces"
        self.benchmarks_dir = self.project_root / "benchmarks"
        
        # Ensure directories exist
        self.traces_dir.mkdir(exist_ok=True)
        self.benchmarks_dir.mkdir(exist_ok=True)
        
        # Application tracing configurations
        self.application_traces = {
            "redis": {
                "name": "Redis Database Server",
                "command": ["redis-server", "--daemonize", "no"],
                "cleanup": ["pkill", "-f", "redis-server"],
                "description": "Trace Redis with comprehensive syscall coverage for 100% relationship extraction",
                "setup": ["sudo", "systemctl", "stop", "redis"],
                "test_commands": [
                    "redis-cli ping",
                    "redis-cli set test_key 'hello_world'",
                    "redis-cli get test_key",
                    "redis-cli del test_key"
                ]
            },
            "apache": {
                "name": "Apache HTTP Server",
                "command": ["apache2", "-D", "FOREGROUND"],
                "cleanup": ["pkill", "-f", "apache2"],
                "description": "Trace Apache HTTP server request handling",
                "setup": ["sudo", "systemctl", "stop", "apache2"],
                "test_commands": [
                    "curl -s http://localhost/",
                    "curl -s http://localhost/index.html"
                ]
            },
            "nginx": {
                "name": "Nginx HTTP Server", 
                "command": ["nginx", "-g", "daemon off;"],
                "cleanup": ["pkill", "-f", "nginx"],
                "description": "Trace Nginx HTTP server operations",
                "setup": ["sudo", "systemctl", "stop", "nginx"],
                "test_commands": [
                    "curl -s http://localhost/",
                    "curl -s http://localhost/index.html"
                ]
            },
            "mysql": {
                "name": "MySQL Database Server",
                "command": ["mysqld", "--console", "--skip-networking"],
                "cleanup": ["pkill", "-f", "mysqld"],
                "description": "Trace MySQL database operations",
                "setup": ["sudo", "systemctl", "stop", "mysql"],
                "test_commands": [
                    "mysql -e 'SHOW DATABASES;'",
                    "mysql -e 'SELECT NOW();'"
                ]
            },
            "postgresql": {
                "name": "PostgreSQL Database Server",
                "command": ["postgres", "-D", "/var/lib/postgresql/data"],
                "cleanup": ["pkill", "-f", "postgres"],
                "description": "Trace PostgreSQL database operations",
                "setup": ["sudo", "systemctl", "stop", "postgresql"],
                "test_commands": [
                    "psql -c 'SELECT version();'",
                    "psql -c 'SELECT NOW();'"
                ]
            },
            "docker": {
                "name": "Docker Container Runtime",
                "command": ["dockerd", "--host=unix:///var/run/docker.sock"],
                "cleanup": ["pkill", "-f", "dockerd"],
                "description": "Trace Docker container operations",
                "setup": ["sudo", "systemctl", "stop", "docker"],
                "test_commands": [
                    "docker ps",
                    "docker images",
                    "docker run --rm hello-world"
                ]
            }
        }
    
    def _run_command(self, command, description, cwd=None, capture=True, check=True):
        """Execute a command with proper logging."""
        logger.info(f" {description}")
        logger.debug(f" Command: {' '.join(command) if isinstance(command, list) else command}")
        
        try:
            if isinstance(command, str):
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=cwd,
                    capture_output=capture,
                    text=True,
                    check=check
                )
            else:
                result = subprocess.run(
                    command,
                    cwd=cwd,
                    capture_output=capture,
                    text=True,
                    check=check
                )
            
            if capture and result.stdout:
                logger.debug(f"Output: {result.stdout.strip()}")
            
            return result
            
        except subprocess.CalledProcessError as e:
            if check:
                logger.error(f" {description} failed with exit code {e.returncode}")
                if e.stderr:
                    logger.error(f"Error: {e.stderr}")
                raise
            return e
        except Exception as e:
            logger.error(f" {description} failed with exception: {e}")
            if check:
                raise
            return None
    
    def check_lttng_availability(self):
        """Check if LTTng tools are available and we have proper permissions."""
        try:
            # Check lttng command availability
            result = self._run_command(["which", "lttng"], "Checking LTTng availability")
            if not result or result.returncode != 0:
                logger.error(" LTTng tools not found. Please install lttng-tools package.")
                return False
            
            # Check if running as root or with proper permissions
            result = self._run_command(["lttng", "list", "-k"], "Checking kernel tracing permissions", check=False)
            if result and result.returncode != 0:
                logger.warning("  Kernel tracing may require root privileges")
                logger.info(" Consider running with: sudo python3 benchmarks/benchmark_tracer.py")
            
            return True
            
        except Exception as e:
            logger.error(f" Error checking LTTng availability: {e}")
            return False
    
    def create_lttng_session(self, session_name, output_dir):
        """Create and configure an LTTng tracing session."""
        logger.info(f"  Creating LTTng session: {session_name}")
        
        try:
            # Create session
            self._run_command(
                ["lttng", "create", session_name, "--output", str(output_dir)],
                f"Creating session {session_name}"
            )
            
            # Create a kernel channel (required before enabling events)
            self._run_command(
                ["lttng", "enable-channel", "-k", "kernel"],
                f"Creating kernel channel for session {session_name}"
            )
            
            # Enable kernel events (most comprehensive set)
            kernel_events = [
                "--all",  # All available kernel events
            ]
            
            for event in kernel_events:
                try:
                    self._run_command(
                        ["lttng", "enable-event", "-k", event, "-c", "kernel"],
                        f"Enabling kernel event: {event}",
                        check=False
                    )
                except:
                    logger.warning(f"  Could not enable kernel event: {event}")
            
            # Enable comprehensive syscalls for 100% relationship type coverage
            logger.info(" Configuring enhanced syscall tracing for maximum relationship extraction...")
            
            # File I/O syscalls (READ_FROM, WROTE_TO, OPENED, CLOSED, ACCESSED)
            file_syscalls = [
                "open,openat,close,closeat",
                "read,pread64,readv,preadv",
                "write,pwrite64,writev,pwritev", 
                "access,faccessat,faccessat2"
            ]
            
            # Network I/O syscalls (SENT_TO, RECEIVED_FROM, CONNECTED_TO)
            network_syscalls = [
                "socket,socketpair",
                "bind,listen,accept,accept4",
                "connect,getsockname,getpeername",
                "send,sendto,sendmsg,sendmmsg",
                "recv,recvfrom,recvmsg,recvmmsg"
            ]
            
            # Process lifecycle syscalls (FORKED)
            process_syscalls = [
                "fork,vfork,clone,clone3",
                "execve,execveat",
                "exit,exit_group"
            ]
            
            # Enable all syscall categories
            all_syscalls = file_syscalls + network_syscalls + process_syscalls
            
            for syscall_group in all_syscalls:
                try:
                    self._run_command(
                        ["lttng", "enable-event", "-k", "--syscall", syscall_group, "-c", "kernel"],
                        f"Enabling syscalls: {syscall_group}",
                        check=False
                    )
                except:
                    logger.warning(f"  Could not enable syscall group: {syscall_group}")
                    
            # Enable scheduling events for SCHEDULED_ON/PREEMPTED_FROM
            try:
                self._run_command(
                    ["lttng", "enable-event", "-k", "sched_switch,sched_wakeup,sched_migrate_task", "-c", "kernel"],
                    "Enabling scheduling events",
                    check=False
                )
            except:
                logger.warning("  Could not enable scheduling events")
                
            # Add comprehensive context for enhanced correlation
            context_info = [
                "pid,tid,ppid",
                "procname,prio", 
                "cpu_id"
            ]
            
            for context in context_info:
                try:
                    self._run_command(
                        ["lttng", "add-context", "-k", "-t", context, "-c", "kernel"],
                        f"Adding context: {context}",
                        check=False
                    )
                except:
                    logger.warning(f"  Could not add context: {context}")
            
            logger.info(" LTTng session configured successfully")
            return True
            
        except Exception as e:
            logger.error(f" Failed to create LTTng session: {e}")
            return False
    
    def start_tracing(self, session_name):
        """Start LTTng tracing."""
        try:
            self._run_command(
                ["lttng", "start", session_name],
                f"Starting tracing for session {session_name}"
            )
            logger.info(" Tracing started successfully")
            return True
        except Exception as e:
            logger.error(f" Failed to start tracing: {e}")
            return False
    
    def stop_tracing(self, session_name):
        """Stop LTTng tracing."""
        try:
            self._run_command(
                ["lttng", "stop", session_name],
                f"Stopping tracing for session {session_name}"
            )
            logger.info(" Tracing stopped successfully")
            return True
        except Exception as e:
            logger.error(f" Failed to stop tracing: {e}")
            return False
    
    def destroy_session(self, session_name):
        """Destroy LTTng session."""
        try:
            self._run_command(
                ["lttng", "destroy", session_name],
                f"Destroying session {session_name}",
                check=False
            )
            logger.info(" Session destroyed successfully")
            return True
        except Exception as e:
            logger.warning(f"  Could not destroy session: {e}")
            return False
    
    def run_application_trace(self, app_info, trace_duration=None):
        """Execute application tracing with realistic workload."""
        logger.info(f" Starting application: {app_info['name']}")
        logger.info(f" Description: {app_info['description']}")
        
        start_time = time.time()
        app_process = None
        
        try:
            # Run setup commands if specified
            if app_info.get("setup"):
                self._run_command(
                    app_info["setup"],
                    f"Running setup for {app_info['name']}",
                    check=False
                )
            
            # Start the application in background
            logger.info(f" Starting {app_info['name']} in background...")
            app_process = subprocess.Popen(
                app_info["command"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Wait for application to start
            time.sleep(2)
            
            # Run test commands to generate realistic workload
            if app_info.get("test_commands"):
                logger.info(f" Running test workload for {app_info['name']}...")
                for i, test_cmd in enumerate(app_info["test_commands"], 1):
                    try:
                        logger.info(f"   Test {i}/{len(app_info['test_commands'])}: {test_cmd}")
                        self._run_command(
                            test_cmd.split(),
                            f"Running test command {i}",
                            check=False
                        )
                        time.sleep(0.5)  # Brief pause between commands
                    except Exception as e:
                        logger.warning(f"  Test command failed: {e}")
            
            # If trace_duration is specified, continue tracing for that duration
            if trace_duration:
                logger.info(f"  Continuing trace for {trace_duration} seconds...")
                
                # Run periodic test commands during trace duration
                end_time = time.time() + trace_duration
                while time.time() < end_time:
                    if app_info.get("test_commands"):
                        for test_cmd in app_info["test_commands"]:
                            if time.time() >= end_time:
                                break
                            try:
                                self._run_command(
                                    test_cmd.split(),
                                    "Running periodic test",
                                    check=False
                                )
                                time.sleep(1)
                            except:
                                pass
                    time.sleep(5)  # Wait between test cycles
            else:
                # Default trace duration for application startup and basic operations
                time.sleep(5)
            
            execution_time = time.time() - start_time
            
            logger.info(f" Application tracing completed in {execution_time:.2f}s")
            return {
                "success": True,
                "execution_time": execution_time,
                "return_code": 0
            }
            
        except Exception as e:
            logger.error(f" Application tracing failed: {e}")
            return {
                "success": False,
                "execution_time": time.time() - start_time,
                "error": str(e)
            }
        finally:
            # Always cleanup the application process
            if app_process and app_process.poll() is None:
                logger.info(f" Stopping {app_info['name']}...")
                app_process.terminate()
                time.sleep(2)
                if app_process.poll() is None:
                    app_process.kill()
            
            # Run cleanup commands
            if app_info.get("cleanup"):
                self._run_command(
                    app_info["cleanup"],
                    f"Running cleanup for {app_info['name']}",
                    check=False
                )
    
    def export_trace_text(self, trace_dir, output_file):
        """Export binary trace to text format using babeltrace2."""
        try:
            logger.info(f" Exporting trace to text format: {output_file}")
            
            # Use babeltrace2 to convert binary trace to text
            try:
                with open(output_file, 'w') as f:
                    result = subprocess.run(
                        ["babeltrace2", str(trace_dir)],
                        stdout=f,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=True
                    )
                logger.info(" Trace exported successfully using babeltrace2")
                return True
            except subprocess.CalledProcessError as e:
                logger.warning(f"  babeltrace2 failed: {e.stderr}")
                
                # Fallback: try babeltrace (version 1)
                try:
                    with open(output_file, 'w') as f:
                        result = subprocess.run(
                            ["babeltrace", str(trace_dir)],
                            stdout=f,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=True
                        )
                    logger.info(" Trace exported using babeltrace v1")
                    return True
                except subprocess.CalledProcessError:
                    logger.warning("  babeltrace v1 also failed")
            
            # Create a minimal trace file with metadata if conversion fails
            with open(output_file, 'w') as f:
                f.write(f"# Trace export failed - binary trace available at: {trace_dir}\n")
                f.write(f"# Use: babeltrace2 {trace_dir} to view trace manually\n")
                f.write(f"# Trace directory contents:\n")
                for item in trace_dir.iterdir():
                    f.write(f"# - {item.name}\n")
            
            logger.warning("  Created placeholder text file - use babeltrace2 manually")
            return True
            
        except Exception as e:
            logger.error(f" Failed to export trace: {e}")
            return False
    
    def _validate_trace_quality(self, trace_file):
        """Validate trace quality for relationship extraction"""
        logger.info(" Validating trace quality for relationship extraction...")
        
        try:
            with open(trace_file, 'r') as f:
                # Sample first 10K lines for analysis
                lines = []
                for i, line in enumerate(f):
                    if i >= 10000:
                        break
                    lines.append(line.strip())
                
            # Count syscalls by type
            syscall_counts = {}
            relationship_syscalls = {
                'file_io': ['open', 'read', 'write', 'close', 'access'],
                'network': ['socket', 'connect', 'send', 'recv', 'accept'],
                'process': ['fork', 'clone', 'execve', 'exit'],
                'scheduling': ['sched_switch', 'sched_wakeup']
            }
            
            total_events = len(lines)
            syscall_events = 0
            
            for line in lines:
                if 'syscall_' in line or 'sched_' in line:
                    syscall_events += 1
                    for category, syscalls in relationship_syscalls.items():
                        for syscall in syscalls:
                            if syscall in line:
                                syscall_counts[syscall] = syscall_counts.get(syscall, 0) + 1
            
            # Report quality metrics
            logger.info(f" Trace Quality Report:")
            logger.info(f"   Total events sampled: {total_events:,}")
            logger.info(f"   Syscall events: {syscall_events:,} ({syscall_events/max(total_events,1)*100:.1f}%)")
            logger.info(f"   Relationship-relevant syscalls detected: {len(syscall_counts)}")
            
            if len(syscall_counts) >= 5:
                logger.info(" GOOD trace quality - multiple relationship types detectable")
                return True
            else:
                logger.warning("  LIMITED trace quality - may have reduced relationship extraction")
                return False
                
        except Exception as e:
            logger.warning(f"Could not validate trace quality: {e}")
            return False
    
    def trace_application(self, app_name, custom_command=None, trace_duration=None):
        """Complete application tracing workflow."""
        logger.info("" * 30)
        logger.info(" LTTNG APPLICATION TRACING")
        logger.info("" * 30)
        
        # Check LTTng availability
        if not self.check_lttng_availability():
            return False
        
        # Get application info
        if custom_command:
            app_info = {
                "name": "Custom Application",
                "command": custom_command.split() if isinstance(custom_command, str) else custom_command,
                "cleanup": [],
                "description": f"Custom application: {custom_command}",
                "setup": [],
                "test_commands": []
            }
        elif app_name in self.application_traces:
            app_info = self.application_traces[app_name]
        else:
            logger.error(f" Unknown application: {app_name}")
            logger.info(f"Available applications: {list(self.application_traces.keys())}")
            return False
        
        # Create unique session name and directories
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_name = f"app_{app_name}_{timestamp}"
        trace_output_dir = self.traces_dir / f"{app_name}_{timestamp}"
        trace_output_dir.mkdir(exist_ok=True)
        
        # Metadata for the trace
        metadata = {
            "application": app_name,
            "session_name": session_name,
            "timestamp": timestamp,
            "command": app_info["command"],
            "description": app_info["description"],
            "trace_duration": trace_duration,
            "start_time": datetime.now().isoformat(),
            "setup_commands": app_info.get("setup", []),
            "test_commands": app_info.get("test_commands", [])
        }
        
        success = False
        
        try:
            # Create and configure LTTng session
            if not self.create_lttng_session(session_name, trace_output_dir):
                return False
            
            # Start tracing
            if not self.start_tracing(session_name):
                return False
            
            # Run application with realistic workload
            app_result = self.run_application_trace(app_info, trace_duration)
            metadata.update(app_result)
            
            # Stop tracing
            self.stop_tracing(session_name)
            
            # Export trace to text format
            text_trace_file = trace_output_dir / "trace_output.txt"
            self.export_trace_text(trace_output_dir, text_trace_file)
            
            # Save metadata
            metadata_file = trace_output_dir / "metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Create symlink to latest trace for easy access
            latest_link = self.traces_dir / "latest"
            if latest_link.exists():
                latest_link.unlink()
            latest_link.symlink_to(trace_output_dir.name)
            
            logger.info("" * 30)
            logger.info(f" APPLICATION TRACING COMPLETED")
            logger.info(f" Trace directory: {trace_output_dir}")
            logger.info(f" Text trace: {text_trace_file}")
            logger.info(f" Metadata: {metadata_file}")
            logger.info("" * 30)
            
            success = True
            
        except Exception as e:
            logger.error(f" Tracing failed: {e}")
            metadata["error"] = str(e)
            
        finally:
            # Always try to destroy the session
            self.destroy_session(session_name)
            
            # Save metadata even if failed
            metadata_file = trace_output_dir / "metadata.json"
            metadata["end_time"] = datetime.now().isoformat()
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        
        return success
    
    def list_applications(self):
        """List available applications for tracing."""
        print(" Available Applications for Tracing:")
        print("=" * 50)
        for name, info in self.application_traces.items():
            print(f" {name}")
            print(f"   Name: {info['name']}")
            print(f"   Description: {info['description']}")
            print(f"   Command: {' '.join(info['command'])}")
            if info.get("test_commands"):
                print(f"   Test Commands: {len(info['test_commands'])} workload tests")
            print()


def main():
    """Main entry point for the application tracer."""
    parser = argparse.ArgumentParser(
        description="LTTng Application Tracer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 benchmark_tracer.py --list                           # List available applications
  python3 benchmark_tracer.py redis                           # Trace Redis database  
  python3 benchmark_tracer.py apache --duration 60           # Trace Apache for 60 seconds
  python3 benchmark_tracer.py --custom "python3 my_app.py"   # Trace custom application
        """
    )
    
    parser.add_argument(
        "application",
        nargs="?",
        help="Application to trace (use --list to see available applications)"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available applications"
    )
    
    parser.add_argument(
        "--custom",
        help="Custom application command to trace"
    )
    
    parser.add_argument(
        "--duration",
        type=int,
        help="Trace duration in seconds (default: application startup + basic operations)"
    )
    
    parser.add_argument(
        "--project-root",
        help="Project root directory"
    )
    
    args = parser.parse_args()
    
    # Initialize tracer
    tracer = LTTngBenchmarkTracer(args.project_root)
    
    # Handle list command
    if args.list:
        tracer.list_applications()
        return
    
    # Validate arguments
    if not args.application and not args.custom:
        logger.error(" Must specify an application name or --custom command")
        parser.print_help()
        sys.exit(1)
    
    # Run tracing
    success = tracer.trace_application(
        args.application,
        custom_command=args.custom,
        trace_duration=args.duration
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()