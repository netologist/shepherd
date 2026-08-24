# Domain-Scoped MCP Tooling and Two-Phase Specialist Execution

We decided to isolate MCP servers by domain (Metrics, Traces, Kubernetes, Troubleshooting) and execute specialists in two distinct phases: a bounded tool-use loop (max 10-15 steps) followed by a tool-free structured extraction into typed Pydantic models. Monolithic MCP toolsets caused cross-domain confusion and excessive token bloat, while free-form text summaries prevented reliable cross-specialist correlation downstream.
