## Week 1: Sept 17 - Sept 23

### Plan for this Week:
- [DONE] Set up the LTTng tracing environment and all dependencies.

### Activity Log (Running Notes):
- **2025-09-17 4:00 PM - 6:00 PM:** Installed and configured a fresh Ubuntu 22.04 LTS OS in VirtualBox. Performed system updates and configured basic settings.
- **2025-09-17 9:00 PM - 10:00 PM:** Installed all required system dependencies (`build-essential`, `dkms`, `linux-headers`) and the LTTng tools. Successfully compiled the lttng-modules.
- **2025-09-17 10:00 PM - 11:00 PM:** Installed VS Code and Git. Initialized the local and remote Git repositories, and created the initial README.md and PROJECT_LOG.md files.

### Key Findings & Results:
- Successfully set up the complete development environment for the project. The system is now ready for the initial data collection and exploration phase. The VM is configured with all necessary build tools and tracing software.

### Problems & Blockers:
- Initially faced issues with missing build-tools (`gcc-12 not found`) but resolved it by reinstalling the `build-essential` package. Also resolved VM performance and full-screen issues by installing and configuring VirtualBox Guest Additions.
- **LTTng Permission Issue:** Encountered "Can't find valid lttng config" error when using `sudo lttng enable-event` after creating session as regular user. **Solution:** Kernel tracing requires root privileges, so the entire session must be created and managed as root user using `sudo lttng create` followed by `sudo` for all subsequent commands.

### Updated Activity Log:
- **2025-09-21 8:30 PM - 8:45 PM:** Successfully captured first LTTng kernel traces. Resolved initial permission issues with kernel tracing by creating session as root user instead of regular user.

### Plan for Next Week (Week 2):
- [DONE] Capture initial sample traces using LTTng from a simple benchmark (e.g., `ls -l`).
- Begin initial analysis of the raw trace file format to understand its structure.
- Install Neo4j and complete its introductory tutorial.