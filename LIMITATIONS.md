# AegisOps AI - Architectural Limitations & Future Scope

## 1. Current Academic Baseline & Scope
In accordance with academic integrity and CPU-native operational constraints:
1. **Model Scope**: Standardized on Scikit-learn Isolation Forest, Statistical Z-Scores, and TF-IDF Cosine Similarity. Deep Transformer neural networks (e.g. BERT/LLaMA) are not loaded in the core loop to guarantee ultra-fast CPU inference (< 10ms).
2. **Persistence**: Configured with SQLite in WAL mode for simple zero-dependency local execution. The database layer uses SQLAlchemy 2.0 async abstractions and can be switched to PostgreSQL by updating `DATABASE_URL` in `.env`.
3. **Simulated Services**: The 4 microservices are independently running HTTP services with realistic network and processing latency. Production Kubernetes/eBPF agent integrations can hook into the same `/api/metrics` and `/api/logs` ingestion endpoints.

---

## 2. Future Extensions
1. **eBPF Kernel Probing**: Low-overhead Linux kernel packet inspection and TCP socket latency monitoring.
2. **Kubernetes CRD & Operator**: Direct integration with Kubernetes Custom Resource Definitions (CRDs) for pod eviction, vertical pod autoscaling, and replica adjustments.
3. **Multi-Region Disaster Recovery**: Cross-datacenter consensus and distributed state synchronization.
