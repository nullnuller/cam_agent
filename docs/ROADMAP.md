CAM Roadmap
===========

This roadmap captures planned enhancements and open questions for the CAM framework.

## Near-Term (0–3 months)

- **Compliance Rules**: Expand rule set with clause-specific checks (APP 6, Privacy Act s 16A, APS Code dual relationships, National Law mandatory notifications).
- **LLM-Assisted Verification**: Integrate a judge-as-guard approach where a specialised model cross-checks citations in real time.
- **UX Integration**: Expose CAM via REST API endpoints with authentication and rate limiting.
- **Analytics Dashboard**: Build lightweight dashboards (Streamlit/Looker) visualising warn/block trends and judge scores.

## Mid-Term (3–6 months)

- **Adaptive Thresholds**: Automatically adjust min similarity and fallback thresholds based on historical performance.
- **Active Learning**: Loop flagged interactions back into retraining datasets for base models.
- **Rule Management UI**: Provide a non-technical interface for compliance teams to edit rule configs and clause mappings.
- **Multi-lingual Support**: Extend RAG corpus and rules to handle additional languages or culturally-specific regulations.

## Long-Term (6+ months)

- **Dynamic Document Updates**: Auto-monitor regulation sources for updates and trigger RAG rebuilds.
- **Fine-Tuning Pipeline**: Automate fine-tuning of specialised models using CAM audit logs with compliance labels.
- **Federated Deployments**: Support on-prem and cross-region deployments with consistent compliance configuration.
- **Certification**: Pursue formal audits/compliance certifications (ISO 27001, HIPAA, Australian privacy standards).

## Open Questions

- How should CAM handle real-time escalations (chat hand-off, duty-of-care triggers)?
- What governance process is needed for rule updates (sign-off, versioning)?
- Should we support multiple store versions concurrently for A/B testing?

Contributors should update this roadmap when priorities change or new initiatives emerge.

