## Week 1: Sept 17 - Sept 23

### Plan for this Week:
- [DONE] Set up the LTTng tracing environment and all dependencies.
- [DONE] Understand and apply core LTTng concepts for tracing and filtering.
- [DONE] Successfully capture and save LTTng traces to local directory.
- [DONE] Analyze trace format structure and identify key event patterns.

### Activity Log (Running Notes):
- **2025-09-17 4:00 PM - 6:00 PM:** Installed and configured a fresh Ubuntu 22.04 LTS OS in VirtualBox. Performed system updates and configured basic settings.
- **2025-09-17 9:00 PM - 10:00 PM:** Installed all required system dependencies (`build-essential`, `dkms`, `linux-headers`) and the LTTng tools. Successfully compiled the lttng-modules.
- **2025-09-17 10:00 PM - 11:00 PM:** Installed VS Code and Git. Initialized the local and remote Git repositories, and created the initial README.md and PROJECT_LOG.md files.
- **2025-09-21 8:30 PM - 8:45 PM:** Successfully captured first LTTng kernel traces. Resolved initial permission issues with kernel tracing by creating session as root user instead of regular user.
- **2025-09-22 6:00 PM - 8:00 PM:** Completed an in-depth guided learning session on LTTng fundamentals.
  - Explored the core concepts of tracing, kernel vs. user space, and syscalls.
  - Mastered the basic tracing workflow (`create`, `enable-event`, `start`, `stop`, `view`).
  - Practiced tracing various kernel events, including all syscalls (`--syscall -a`) and specific scheduler events (`sched_switch`).
  - Learned two methods for filtering trace data: post-capture using `| grep` and live filtering with the `--filter` option (e.g., filtering by process name).
  - Understood how to enable pre-defined user-space tracepoints (`--userspace`).
- **2025-09-22 8:50 PM - 9:15 PM:** Conducted comprehensive 5-second kernel trace session capturing 3.38M events.
  - Created dedicated `observations/` directory for structured analysis documentation.
  - Captured high-volume trace data (677K events/second) demonstrating system activity patterns.
  - Performed detailed event frequency analysis identifying top event categories: RCU operations (934K), scheduling stats (450K), cooperative scheduling (372K sched_yield pairs).
  - Documented findings in `observations/trace_analysis_findings.md` with implications for knowledge graph schema design.
  - Identified critical event patterns for graph modeling: process lifecycle, syscall entry/exit pairs, memory management, and inter-process communication.

### Key Findings & Results:
- Successfully set up the complete development environment for the project. The system is now ready for the initial data collection and exploration phase.
- **Expanded LTTng Skillset:** Moved from basic setup to practical application. Now capable of capturing targeted, filtered traces for both kernel and user-space events. This provides a solid foundation for analyzing application performance and behavior.
- **High-Volume Trace Analysis:** Successfully captured and analyzed 3.38M kernel events over 5 seconds, demonstrating system capability to handle intensive tracing workloads.
- **Event Pattern Recognition:** Identified key event categories with RCU operations dominating (28% of events), followed by scheduling statistics (13%) and cooperative scheduling patterns (11%).
- **Graph Schema Foundation:** Documented critical event types and relationships for knowledge graph implementation, including process lifecycle, syscall patterns, memory management, and inter-process communication structures.
- **Analysis Infrastructure:** Established `observations/` directory with structured documentation approach for ongoing trace analysis and findings.

### Problems & Blockers:
- Initially faced issues with missing build-tools (`gcc-12 not found`) but resolved it by reinstalling the `build-essential` package. Also resolved VM performance and full-screen issues by installing and configuring VirtualBox Guest Additions.
- **LTTng Permission Issue:** Encountered "Can't find valid lttng config" error when using `sudo lttng enable-event` after creating session as regular user. **Solution:** Kernel tracing requires root privileges, so the entire session must be created and managed as root user using `sudo lttng create` followed by `sudo` for all subsequent commands.
- **Trace Data Overload:** Realized that a simple trace captures an enormous volume of events, making manual analysis difficult. **Solution:** Developed strategies to manage this complexity, first with `grep` for quick analysis, and then with LTTng's `--filter` capability for efficient, targeted captures.
- **GitHub File Size Limit**: Initial attempt to commit trace files failed due to 100+ MB file size limits. **Solution**: Created comprehensive `.gitignore` to exclude trace files and other generated data from version control, as these are artifacts rather than source code.

### Plan for Next Week (Week 2):
- Install Neo4j and complete its introductory tutorial.
- Begin designing the trace data to graph schema mapping.
- Implement initial trace parser to extract structured data from LTTng output.