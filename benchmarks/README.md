#  LTTng Application Tracing Utilities

This directory contains tools for automated LTTng kernel tracing of real-world production applications.

##  Quick Start

### List Available Applications
```bash
python3 benchmark_tracer.py --list
```

### Trace Production Applications
```bash
# Redis database server
sudo python3 benchmark_tracer.py redis

# Apache HTTP server  
sudo python3 benchmark_tracer.py apache

# Nginx web server
sudo python3 benchmark_tracer.py nginx

# MySQL database
sudo python3 benchmark_tracer.py mysql

# PostgreSQL database
sudo python3 benchmark_tracer.py postgresql

# Docker container runtime
sudo python3 benchmark_tracer.py docker
```

### Trace Custom Applications
```bash
# Trace any application
sudo python3 benchmark_tracer.py --custom "python3 my_app.py"

# Trace with specific duration
sudo python3 benchmark_tracer.py --custom "node server.js" --duration 60
```

##  Supported Applications

| Application | Description | Workload Tests |
|-------------|-------------|----------------|
| `redis` | In-memory database server | SET/GET operations, PING tests |
| `apache` | HTTP web server | HTTP requests to default pages |
| `nginx` | High-performance web server | HTTP requests and static content |
| `mysql` | SQL database server | Database queries and connections |
| `postgresql` | Advanced SQL database | SQL operations and transactions |
| `docker` | Container runtime | Container management operations |

##  Output Structure

Each benchmark trace creates:
```
traces/
 {benchmark}_{timestamp}/
    kernel/               # Binary LTTng trace files
    trace_output.txt     # Human-readable trace
    metadata.json       # Benchmark metadata
 latest -> {recent_trace} # Symlink to latest trace
```

##  Requirements

- **LTTng Tools**: `sudo apt install lttng-tools lttng-modules-dkms`
- **Root Access**: Kernel tracing requires elevated privileges
- **Babeltrace2**: `sudo apt install babeltrace2` (optional, for better trace export)

##  Usage Tips

1. **Always run with sudo** for kernel tracing
2. **Check trace output** in `traces/latest/trace_output.txt`
3. **Use short benchmarks** for initial testing
4. **Specify duration** for long-running applications
5. **Check metadata.json** for execution details

##  Integration with Main Pipeline

After capturing application traces, process them with the main pipeline:

```bash
# 1. Capture application trace
sudo python3 benchmarks/benchmark_tracer.py redis

# 2. Copy trace to observations for processing
cp traces/latest/trace_output.txt observations/TraceMain.txt

# 3. Run complete analysis pipeline  
python3 main.py
```

##  Application-Specific Features

### Redis Tracing
- Captures database operations (SET/GET/DEL)
- Traces memory management patterns
- Monitors network I/O for client connections

### Web Server Tracing (Apache/Nginx)
- HTTP request processing
- Static file serving
- Connection management
- Process/thread handling

### Database Tracing (MySQL/PostgreSQL)
- SQL query execution
- Transaction processing
- Buffer management
- Lock contention

### Docker Tracing
- Container lifecycle operations
- Image management
- Network namespace creation
- Storage driver interactions

##  Troubleshooting

### Permission Issues
```bash
# Ensure proper LTTng setup
sudo modprobe lttng-ring-buffer-client-discard
sudo modprobe lttng-ring-buffer-client-overwrite
```

### Missing Kernel Modules
```bash
# Rebuild LTTng kernel modules
sudo dkms remove lttng-modules --all
sudo dkms install lttng-modules --all
```

### Trace Export Issues
- Install babeltrace2: `sudo apt install babeltrace2`
- Check trace directory permissions
- Verify LTTng session was created successfully