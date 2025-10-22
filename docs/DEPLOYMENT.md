Deployment Considerations
=========================

This document highlights operational concerns when deploying the CAM framework.

## 1. Runtime Architecture

```
Client → CAM Ingress → CAM Agent → (LLM models via Ollama / API) → Response Filter → Client
                   ↘︎ Audit Logger ↘︎ Retrieval Store ↘︎ Judge Services
```

- **Ingress**: REST API, gRPC, or messaging queue can wrap the `CAMAgent` class.
- **Stateful components**: Retrieval store (FAISS + JSON metadata) and audit logs.
- **External services**: LLM endpoints (Ollama, Gemini API) and storage (object store for snapshots/backups).

## 2. Environments

### Development
- Run Ollama locally with required models.
- Use SQLite/JSONL for audit logs.
- Trigger pipeline with small question batches.

### Staging
- Mirror production configuration with anonymised queries.
- Enable judge models (medgemma + Gemini) to validate compliance before release.
- Automated nightly pipeline (cron/job scheduler).

### Production
- **Scaling**: Deploy CAM as stateless service (Kubernetes, ECS, etc.) behind load balancer.
- **Secrets management**: Store API keys (Gemini, Ollama auth) in vault/secret manager.
- **Monitoring**: Collect metrics (latency, warning/block rates), traces, and alert when thresholds exceed defined SLAs.
- **Disaster recovery**: Backup `rag_store/` and audit logs regularly; retain digest snapshots for reproducibility.

## 3. Security & Privacy

- **Data retention**: Audit logs may contain sensitive content. Use encryption at rest and access controls.
- **PII handling**: Ensure ingestion pipeline and logs comply with relevant health privacy regulations.
- **Network**: Restrict outbound access to approved LLM providers; enforce TLS.

## 4. Observability

- **Metrics**: Expose action counts (allow/warn/block), judge scores, average latency.
- **Logging**: Stream audit JSONL to central log service (ELK, Cloud Logging) for analytics.
- **Alerting**: Set alerts on block rate spikes, low compliance scores, or pipeline failures.

## 5. Deployment Workflow

1. Build container image (include models or mount them at runtime).
2. Run `cam_pipeline.py --dry-run --refresh-store` in CI to validate artifacts.
3. Deploy to staging; execute full scenario suite.
4. Promote to production after reviewer sign-off.

## 6. Future Enhancements

- Swap JSONL audit logs for managed database (PostgreSQL) to support analytics and access controls.
- Integrate feature flags/config service for rule toggles and threshold adjustments.
- Add streaming support for multi-turn conversations.

Use this document as a checklist when preparing new environments or planning infrastructure upgrades.

