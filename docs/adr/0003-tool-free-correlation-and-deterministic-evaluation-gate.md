# Tool-Free Correlation and Deterministic Evaluation Gate

We decided that the Correlate and Evaluate nodes must have zero tool access and operate solely on structured specialist findings, enforcing a strict cross-validation rule (corroboration by at least two independent specialists) to prevent false positives. Furthermore, the decision to trigger a Deep Dive versus final Synthesis is implemented as a deterministic Python rule (`confidence == "high" and cross_validated is True`) bounded by a hard cap of 2 deep-dive iterations.
