# AegisOps AI — 10-Step Customer Onboarding Guide

## 1. Onboarding Philosophy

AegisOps AI is built for frictionless enterprise self-service onboarding. An engineering team can deploy an OpenTelemetry Collector DaemonSet into their Kubernetes cluster or virtual machine fleet, verify the live telemetry probe, configure autonomous safety guardrails, and go live within 10 minutes.

```
┌────────────────────────────────────────────────────────────────────────┐
│                      10-STEP ONBOARDING WORKFLOW                       │
│                                                                        │
│  [Step 1] Organization Profile & Legal Entity                          │
│     ▼                                                                  │
│  [Step 2] Cloud Infrastructure & Target Selection (EKS, GKE, AKS, VM)  │
│     ▼                                                                  │
│  [Step 3] Single-Reveal Ingestion API Key Generation                   │
│     ▼                                                                  │
│  [Step 4] OpenTelemetry Collector DaemonSet Deployment                │
│     ▼                                                                  │
│  [Step 5] Service Discovery & Dynamic Topology Mapping                │
│     ▼                                                                  │
│  [Step 6] Service Level Objectives (SLO) & SLA Target Definition       │
│     ▼                                                                  │
│  [Step 7] Notification Channels & PagerDuty / Slack Routing            │
│     ▼                                                                  │
│  [Step 8] Autonomous Remediation Policy & Guardrail Configuration      │
│     ▼                                                                  │
│  [Step 9] Non-Destructive Synthetic Failure Probe Test                 │
│     ▼                                                                  │
│  [Step 10] Active Production Go-Live Confirmation                      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Step-by-Step Walkthrough

### Step 1: Organization Profile
Register legal corporate entity, administrative contact, data residency region (`us-east-1`, `eu-west-1`, etc.), and SaaS subscription plan (`ENTERPRISE`, `SOVEREIGN_FLEET`).

### Step 2: Target Infrastructure
Select target cloud environment:
- AWS Elastic Kubernetes Service (EKS)
- Google Kubernetes Engine (GKE)
- Managed Kubernetes / Cloud K8s
- Red Hat OpenShift / On-Premises bare metal
- Standalone Linux Virtual Machines (systemd)

### Step 3: Ingestion API Key Generation
Generate a dedicated Ingestion Key (`aegis_live_...`). Save the token immediately; AegisOps stores only a SHA-256 hash.

### Step 4: OTel Collector Deployment
Apply the generated manifest to the target Kubernetes cluster:
```bash
kubectl apply -f https://install.aegisops.ai/v1/agent/k8s-daemonset.yaml
```

### Step 5: Service Discovery & Catalog Mapping
As spans arrive, AegisOps automatically discovers active microservices, API routes, database pools, and Redis caches without manual catalog registration.

### Step 6: Define SLOs & Error Budgets
Configure 30-day rolling availability targets (e.g. 99.95%) and P99 latency bounds (< 150ms) per tier-0 and tier-1 service.

### Step 7: Notification & Alert Routing
Configure Webhook, Slack, PagerDuty, or Microsoft Teams webhooks for P0-P2 incident alerts.

### Step 8: Configure Autonomous Self-Healing Policies
Enable autonomous remediation for `LOW` risk runbooks (`RESET_CONNECTION_POOL`, `CLEAR_CACHE`). Enforce human approval gating for high-risk actions.

### Step 9: Synthetic Non-Destructive Probe Test
AegisOps sends a safe synthetic ping to the OTel collector to confirm bidirectional streaming, trace propagation, and telemetry latency (< 2.5ms).

### Step 10: Active Production Go-Live
Upon receiving live production traces, the platform transitions the tenant status to `ACTIVE` and begins continuous 24/7 autonomous monitoring.
