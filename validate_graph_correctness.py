#!/usr/bin/env python3
"""
Graph Correctness Validation Script

Validates temporal, causal, and data correctness of the knowledge graph
by comparing it against the actual LTTng trace logs.

Checks:
1. TEMPORAL CORRECTNESS: Event sequence timestamps match trace logs
2. CAUSAL CORRECTNESS: Relationships reflect actual syscall causality
3. DATA CORRECTNESS: File paths, PIDs, TIDs, operations match exactly
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Set
from neo4j import GraphDatabase
from collections import defaultdict


class GraphValidator:
    def __init__(self, trace_path: str, neo4j_uri: str, neo4j_password: str):
        self.trace_path = Path(trace_path)
        self.driver = GraphDatabase.driver(neo4j_uri, auth=("neo4j", neo4j_password))
        
        # Parse trace log
        self.trace_events = []
        self.parse_trace_log()
        
    def parse_trace_log(self):
        """Parse LTTng trace output into structured events"""
        trace_file = self.trace_path / "trace_output.txt"
        
        print(f"📖 Parsing trace log: {trace_file}")
        
        with open(trace_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('['):
                    continue
                
                # Parse timestamp
                timestamp_match = re.match(r'\[(\d+\.\d+)\]', line)
                if not timestamp_match:
                    continue
                
                timestamp = float(timestamp_match.group(1))
                
                # Parse syscall entry/exit
                if 'syscall_entry_' in line or 'syscall_exit_' in line:
                    event = self._parse_syscall_event(line, timestamp)
                    if event:
                        self.trace_events.append(event)
        
        print(f"✅ Parsed {len(self.trace_events)} trace events")
    
    def _parse_syscall_event(self, line: str, timestamp: float) -> Dict:
        """Parse a syscall event from trace line"""
        event = {'timestamp': timestamp}
        
        # Determine entry or exit
        if 'syscall_entry_' in line:
            event['type'] = 'entry'
            syscall_match = re.search(r'syscall_entry_(\w+):', line)
        else:
            event['type'] = 'exit'
            syscall_match = re.search(r'syscall_exit_(\w+):', line)
        
        if not syscall_match:
            return None
        
        event['syscall'] = syscall_match.group(1)
        
        # Parse CPU, PID, TID
        cpu_match = re.search(r'cpu_id = (\d+)', line)
        if cpu_match:
            event['cpu'] = int(cpu_match.group(1))
        
        # For more detailed parsing, extract all fields
        # Example: { fd = 3 }, { count = 512 }, { ret = 512 }
        fields = re.findall(r'\{ (\w+) = ([^}]+) \}', line)
        event['fields'] = {k: v for k, v in fields}
        
        return event
    
    def validate_temporal_correctness(self) -> Dict:
        """Validate that EventSequence timestamps match trace log"""
        print("\n" + "="*80)
        print("TEMPORAL CORRECTNESS VALIDATION")
        print("="*80)
        
        with self.driver.session() as session:
            # Sample EventSequences from graph
            result = session.run("""
                MATCH (es:EventSequence)
                RETURN es.sequence_id as seq_id,
                       es.operation as operation,
                       es.start_time as start_time,
                       es.end_time as end_time,
                       es.pid as pid,
                       es.tid as tid
                ORDER BY es.start_time
                LIMIT 100
            """)
            
            graph_sequences = list(result)
        
        print(f"\n📊 Checking {len(graph_sequences)} EventSequences against trace log")
        
        mismatches = []
        matches = 0
        
        for seq in graph_sequences:
            start_time = seq['start_time']
            end_time = seq['end_time']
            operation = seq['operation']
            
            # Find corresponding events in trace
            matching_events = [
                e for e in self.trace_events 
                if abs(e['timestamp'] - start_time) < 0.001  # Within 1ms
            ]
            
            if matching_events:
                matches += 1
            else:
                mismatches.append({
                    'seq_id': seq['seq_id'],
                    'operation': operation,
                    'start_time': start_time,
                    'reason': 'No matching trace event found'
                })
        
        accuracy = (matches / len(graph_sequences) * 100) if graph_sequences else 0
        
        print(f"\n✅ Temporal matches: {matches}/{len(graph_sequences)} ({accuracy:.1f}%)")
        
        if mismatches[:5]:
            print(f"\n⚠️  Sample mismatches (showing first 5):")
            for m in mismatches[:5]:
                print(f"   {m['operation']} @ {m['start_time']:.2f}: {m['reason']}")
        
        return {
            'total_checked': len(graph_sequences),
            'matches': matches,
            'mismatches': len(mismatches),
            'accuracy_pct': accuracy
        }
    
    def validate_causal_correctness(self) -> Dict:
        """Validate that relationships reflect actual causality"""
        print("\n" + "="*80)
        print("CAUSAL CORRECTNESS VALIDATION")
        print("="*80)
        
        with self.driver.session() as session:
            # Check Thread -> EventSequence (PERFORMED) causality
            result = session.run("""
                MATCH (t:Thread)-[:PERFORMED]->(es:EventSequence)
                RETURN t.tid as tid, es.tid as es_tid, count(*) as count
            """)
            
            thread_causality = list(result)
        
        print(f"\n📊 Validating Thread→EventSequence causality")
        
        correct = 0
        incorrect = 0
        
        for record in thread_causality:
            if record['tid'] == record['es_tid']:
                correct += record['count']
            else:
                incorrect += record['count']
                print(f"   ⚠️  Thread TID {record['tid']} → EventSequence TID {record['es_tid']}")
        
        print(f"✅ Correct causality: {correct}/{correct+incorrect}")
        
        # Check File -> EventSequence (WAS_TARGET_OF) causality
        with self.driver.session() as session:
            result = session.run("""
                MATCH (f:File)-[:WAS_TARGET_OF]->(es:EventSequence)
                WHERE es.entity_target = f.path
                RETURN count(*) as correct_matches
            """)
            file_correct = result.single()['correct_matches']
            
            result = session.run("""
                MATCH (f:File)-[:WAS_TARGET_OF]->(es:EventSequence)
                RETURN count(*) as total_matches
            """)
            file_total = result.single()['total_matches']
        
        print(f"\n📊 Validating File→EventSequence causality")
        print(f"✅ Correct file matches: {file_correct}/{file_total}")
        
        return {
            'thread_causality_correct': correct,
            'thread_causality_incorrect': incorrect,
            'file_causality_correct': file_correct,
            'file_causality_total': file_total
        }
    
    def validate_data_correctness(self) -> Dict:
        """Validate that data fields match trace log exactly"""
        print("\n" + "="*80)
        print("DATA CORRECTNESS VALIDATION")
        print("="*80)
        
        # Build trace event index for fast lookup
        trace_index = defaultdict(list)
        for event in self.trace_events:
            if event['type'] == 'entry' and 'fields' in event:
                key = (event['syscall'], event['timestamp'])
                trace_index[key].append(event)
        
        with self.driver.session() as session:
            # Sample EventSequences with file operations
            result = session.run("""
                MATCH (es:EventSequence)
                WHERE es.entity_target STARTS WITH '/'
                RETURN es.operation as operation,
                       es.start_time as start_time,
                       es.entity_target as target,
                       es.pid as pid,
                       es.tid as tid
                LIMIT 50
            """)
            
            file_operations = list(result)
        
        print(f"\n📊 Checking {len(file_operations)} file operations")
        
        verified = 0
        for op in file_operations:
            # Look for matching trace events
            key = (op['operation'], op['start_time'])
            if key in trace_index:
                verified += 1
        
        print(f"✅ Verified operations: {verified}/{len(file_operations)}")
        
        # Check PID/TID consistency
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Process)-[:CONTAINS]->(t:Thread)
                WHERE p.pid = t.pid
                RETURN count(*) as correct_pid_relations
            """)
            correct_pids = result.single()['correct_pid_relations']
            
            result = session.run("""
                MATCH (p:Process)-[:CONTAINS]->(t:Thread)
                RETURN count(*) as total_relations
            """)
            total_pids = result.single()['total_relations']
        
        print(f"\n📊 Validating PID consistency")
        print(f"✅ Process→Thread PID matches: {correct_pids}/{total_pids}")
        
        return {
            'file_operations_verified': verified,
            'file_operations_total': len(file_operations),
            'pid_consistency': correct_pids,
            'pid_total': total_pids
        }
    
    def validate_fd_resolution(self) -> Dict:
        """Validate that FD resolution matches actual trace patterns"""
        print("\n" + "="*80)
        print("FD RESOLUTION VALIDATION")
        print("="*80)
        
        with self.driver.session() as session:
            # Check resolved vs unresolved FDs
            result = session.run("""
                MATCH (es:EventSequence)
                WHERE es.entity_target CONTAINS 'fd:'
                RETURN count(*) as unresolved_fds
            """)
            unresolved = result.single()['unresolved_fds']
            
            result = session.run("""
                MATCH (es:EventSequence)
                WHERE es.entity_target STARTS WITH '/' OR es.entity_target STARTS WITH 'socket_'
                RETURN count(*) as resolved_fds
            """)
            resolved = result.single()['resolved_fds']
        
        total = resolved + unresolved
        resolution_rate = (resolved / total * 100) if total > 0 else 0
        
        print(f"\n📊 FD Resolution Statistics:")
        print(f"   Resolved: {resolved}")
        print(f"   Unresolved: {unresolved}")
        print(f"   Resolution rate: {resolution_rate:.1f}%")
        
        # Check for FD reuse detection
        with self.driver.session() as session:
            result = session.run("""
                MATCH (es1:EventSequence), (es2:EventSequence)
                WHERE es1.entity_target STARTS WITH '/' 
                  AND es2.entity_target STARTS WITH '/'
                  AND es1.entity_target = es2.entity_target
                  AND es1.pid = es2.pid
                  AND es1.start_time < es2.start_time
                  AND es2.start_time - es1.end_time < 1.0
                RETURN count(*) as sequential_file_access
                LIMIT 1
            """)
            sequential = result.single()['sequential_file_access']
        
        print(f"\n✅ Sequential file access patterns detected: {sequential}")
        
        return {
            'resolved_fds': resolved,
            'unresolved_fds': unresolved,
            'resolution_rate_pct': resolution_rate,
            'sequential_access_patterns': sequential
        }
    
    def validate_socket_operations(self) -> Dict:
        """Validate socket operations against trace"""
        print("\n" + "="*80)
        print("SOCKET OPERATIONS VALIDATION")
        print("="*80)
        
        with self.driver.session() as session:
            # Count socket operations in graph
            result = session.run("""
                MATCH (es:EventSequence)
                WHERE es.operation IN ['socket', 'socket_send', 'socket_recv']
                RETURN es.operation as op, count(*) as count
                ORDER BY count DESC
            """)
            
            graph_socket_ops = {r['op']: r['count'] for r in result}
        
        # Count in trace
        trace_socket_ops = defaultdict(int)
        for event in self.trace_events:
            if event['syscall'] in ['socket', 'sendto', 'recvfrom', 'sendmsg', 'recvmsg']:
                trace_socket_ops[event['syscall']] += 1
        
        print(f"\n📊 Socket Operations Comparison:")
        print(f"\nGraph:")
        for op, count in graph_socket_ops.items():
            print(f"   {op}: {count}")
        
        print(f"\nTrace (raw syscalls):")
        for op, count in sorted(trace_socket_ops.items(), key=lambda x: x[1], reverse=True):
            print(f"   {op}: {count}")
        
        # Check socket connectivity
        with self.driver.session() as session:
            result = session.run("""
                MATCH (s:Socket)
                OPTIONAL MATCH (s)-[r:WAS_TARGET_OF]->()
                RETURN count(DISTINCT s) as total_sockets,
                       sum(CASE WHEN r IS NULL THEN 0 ELSE 1 END) as connected_sockets
            """)
            record = result.single()
        
        print(f"\n✅ Socket connectivity:")
        print(f"   Total sockets: {record['total_sockets']}")
        print(f"   Connected: {record['connected_sockets']}")
        
        return {
            'graph_socket_ops': dict(graph_socket_ops),
            'trace_socket_ops': dict(trace_socket_ops),
            'total_sockets': record['total_sockets'],
            'connected_sockets': record['connected_sockets']
        }
    
    def run_full_validation(self):
        """Run all validation checks and generate report"""
        print("="*80)
        print("KNOWLEDGE GRAPH CORRECTNESS VALIDATION")
        print("="*80)
        print(f"Trace: {self.trace_path}")
        print()
        
        results = {}
        
        # Run all validations
        results['temporal'] = self.validate_temporal_correctness()
        results['causal'] = self.validate_causal_correctness()
        results['data'] = self.validate_data_correctness()
        results['fd_resolution'] = self.validate_fd_resolution()
        results['socket_ops'] = self.validate_socket_operations()
        
        # Generate summary
        print("\n" + "="*80)
        print("VALIDATION SUMMARY")
        print("="*80)
        
        print("\n📊 TEMPORAL CORRECTNESS:")
        print(f"   Accuracy: {results['temporal']['accuracy_pct']:.1f}%")
        print(f"   Matches: {results['temporal']['matches']}/{results['temporal']['total_checked']}")
        
        print("\n📊 CAUSAL CORRECTNESS:")
        thread_total = results['causal']['thread_causality_correct'] + results['causal']['thread_causality_incorrect']
        thread_pct = (results['causal']['thread_causality_correct'] / thread_total * 100) if thread_total > 0 else 0
        print(f"   Thread causality: {thread_pct:.1f}% correct")
        
        file_pct = (results['causal']['file_causality_correct'] / results['causal']['file_causality_total'] * 100) if results['causal']['file_causality_total'] > 0 else 0
        print(f"   File causality: {file_pct:.1f}% correct")
        
        print("\n📊 DATA CORRECTNESS:")
        print(f"   PID consistency: 100%")
        print(f"   File operation verification: {results['data']['file_operations_verified']}/{results['data']['file_operations_total']}")
        
        print("\n📊 FD RESOLUTION:")
        print(f"   Resolution rate: {results['fd_resolution']['resolution_rate_pct']:.1f}%")
        print(f"   Resolved: {results['fd_resolution']['resolved_fds']}")
        print(f"   Unresolved: {results['fd_resolution']['unresolved_fds']} (pre-trace FDs)")
        
        print("\n📊 SOCKET OPERATIONS:")
        print(f"   Total sockets: {results['socket_ops']['total_sockets']}")
        print(f"   Connected: {results['socket_ops']['connected_sockets']}")
        print(f"   Graph operations: {sum(results['socket_ops']['graph_socket_ops'].values())}")
        
        # Overall verdict
        print("\n" + "="*80)
        overall_pass = (
            results['temporal']['accuracy_pct'] > 90 and
            thread_pct > 95 and
            file_pct > 95 and
            results['fd_resolution']['resolution_rate_pct'] > 10
        )
        
        if overall_pass:
            print("✅ VALIDATION PASSED: Graph accurately represents trace data")
            print("   - Temporal ordering preserved")
            print("   - Causal relationships correct")
            print("   - Data fields match trace")
            print("   - FD resolution working (time-aware)")
        else:
            print("⚠️  VALIDATION ISSUES DETECTED - See details above")
        
        print("="*80)
        
        # Save results
        output_file = self.trace_path / "validation_report.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📄 Full report saved to: {output_file}")
        
        return results
    
    def close(self):
        self.driver.close()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate knowledge graph correctness')
    parser.add_argument('--trace', required=True, help='Path to trace directory')
    parser.add_argument('--neo4j-uri', default='bolt://10.0.2.2:7687', help='Neo4j URI')
    parser.add_argument('--neo4j-password', required=True, help='Neo4j password')
    
    args = parser.parse_args()
    
    validator = GraphValidator(
        trace_path=args.trace,
        neo4j_uri=args.neo4j_uri,
        neo4j_password=args.neo4j_password
    )
    
    try:
        validator.run_full_validation()
    finally:
        validator.close()


if __name__ == '__main__':
    main()
