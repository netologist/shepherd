# Architecture Stack: Python, LangGraph and Standard SRE Telemetry MCPs

We decided to build the automated incident investigation system using Python 3.12+ and LangGraph with PostgreSQL checkpointing, targeting standard cloud-native telemetry (Kubernetes API, Prometheus PromQL, OpenTelemetry/Jaeger). LangGraph provides native support for dynamic parallel fan-out (`Send()`), deterministic conditional routing without LLM-driven control flow, and persistent state restoration for post-investigation chat.
