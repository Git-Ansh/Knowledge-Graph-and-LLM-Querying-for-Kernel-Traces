# Copilot Instructions: Knowledge Graph and LLM Querying for Kernel Traces

## Project Overview
This project implements a system for capturing, analyzing, and querying Linux kernel traces using knowledge graphs and Large Language Models. The core workflow involves:
1. **LTTng Trace Capture** → Raw kernel execution traces  
2. **Data Processing** → Structured trace analysis
3. **Knowledge Graph Construction** → Neo4j graph database representation
4. **LLM Integration** → Natural language querying of kernel behavior

## Development Environment & Prerequisites
- **OS**: Ubuntu 22.04 LTS (typically in VirtualBox VM)
- **Kernel Tracing**: LTTng tools with compiled lttng-modules
- **Database**: Neo4j for knowledge graph storage
- **Build Tools**: `build-essential`, `dkms`, `linux-headers`

## Critical Workflows

### LTTng Kernel Tracing
**Always use root privileges for kernel tracing operations:**
```bash
sudo lttng create session_name
sudo lttng enable-event -k --all
sudo lttng start
# Run target application/benchmark
sudo lttng stop
sudo lttng view > trace_output.txt
sudo lttng destroy
```

**Common Issue**: Permission errors occur when mixing user/root session creation. Always create and manage entire sessions as root.

### Project Structure Patterns
- `Project-Log.md`: Weekly progress tracking with specific date/time entries
- Issue-driven development using GitHub templates for weekly progress tasks
- Documentation-first approach with "Coming soon..." placeholders

## Key Technical Concepts

### Trace Data Flow
1. **Raw LTTng Output** → Binary trace files + text views
2. **Parsing Layer** → Extract kernel events, syscalls, scheduling
3. **Graph Modeling** → Nodes: processes/threads/resources, Edges: relationships/causality
4. **Query Interface** → Natural language → Cypher → Results

### Development Patterns
- **Research-oriented**: Document findings and blockers in detail
- **VM-based**: Handle VirtualBox Guest Additions and performance tuning
- **Root-required operations**: Kernel-level tracing needs elevated privileges
- **Weekly milestones**: Use GitHub issues for progress tracking

## File Naming Conventions
- Use descriptive names with hyphens: `weekly-progress-task.md`
- Maintain chronological logs in `Project-Log.md`
- Preserve case-sensitive project name with spaces in directory structure

## Integration Points
- **LTTng → Processing**: Parse binary trace formats and event timestamps
- **Processing → Neo4j**: Map kernel events to graph nodes/relationships
- **Neo4j → LLM**: Generate Cypher queries from natural language
- **Data Sources**: Kernel syscalls, process scheduling, memory management, I/O operations

## Testing & Debugging
- Use simple benchmarks (`ls -l`) for initial trace capture validation
- Verify trace quality before graph construction
- Test LLM query accuracy against known kernel behaviors

## Documentation Standards
When implementing components, update `README.md` sections:
- Replace "Coming soon..." with actual architecture details
- Document specific LTTng event types being captured
- Explain Neo4j schema design for kernel trace representation