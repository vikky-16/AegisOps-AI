# AegisOps AI — Frontend Screen & UI Inventory

## 1. Frontend Architecture Summary

- **Framework**: React 18 with TypeScript (`frontend/package.json`)
- **Build Tool**: Vite 8.2 (`vite.config.ts`), Rolldown compiler
- **Styling**: Tailwind CSS with dark-mode SRE visual system
- **State Management**: React Context (`TenantContext`, `WorkspaceContext`), custom hooks (`useWebSocket`)
- **Iconography**: Lucide React
- **Total Distinct Pages**: 14 documented core views

## 2. Comprehensive Screen Inventory

| Screen Name | Tab Identifier | Source File | Status | Primary Backend APIs |
| :--- | :--- | :--- | :--- | :--- |
| Platform Health & Multi-Tenant Operations Dashboard | `dashboard` | [`frontend/src/pages/DashboardPage.tsx`](file:///frontend/src/pages/DashboardPage.tsx) | `FULL_RUNTIME_VERIFIED` | `GET /api/platform-health/status...` |
| Operations Center & Incident Command | `operations` | [`frontend/src/pages/OperationsCenterPage.tsx`](file:///frontend/src/pages/OperationsCenterPage.tsx) | `FULL_RUNTIME_VERIFIED` | `GET /api/incidents...` |
| Incidents Directory & Evidence Timeline | `incidents` | [`frontend/src/pages/IncidentsPage.tsx`](file:///frontend/src/pages/IncidentsPage.tsx) | `FULL_RUNTIME_VERIFIED` | `GET /api/incidents...` |
| Dual-Solution Root Cause Analysis (AI + KB Engine) | `rca` | [`frontend/src/pages/RcaPage.tsx`](file:///frontend/src/pages/RcaPage.tsx) | `FULL_RUNTIME_VERIFIED` | `GET /api/incidents/{id}/dual-solutions...` |
| Recovery Orchestrator & Bounded Refinement | `recovery` | [`frontend/src/pages/RecoveryPage.tsx`](file:///frontend/src/pages/RecoveryPage.tsx) | `FULL_RUNTIME_VERIFIED` | `GET /api/incidents/{id}/recovery-plan...` |
| Replica Lab (Digital Twin & Recovery Sandbox) | `testing-lab` | [`frontend/src/pages/TestingSimulationLabPage.tsx`](file:///frontend/src/pages/TestingSimulationLabPage.tsx) | `FULL_RUNTIME_VERIFIED` | `GET /api/testing-lab/inventory...` |
| Approval Center & Operational Governance | `approvals` | [`frontend/src/pages/ApprovalsPage.tsx`](file:///frontend/src/pages/ApprovalsPage.tsx) | `FULL_RUNTIME_VERIFIED` | `GET /api/approvals...` |
| Autonomous SRE Copilot & Chat Operations | `assistant` | [`frontend/src/pages/AssistantPage.tsx`](file:///frontend/src/pages/AssistantPage.tsx) | `FULL_RUNTIME_VERIFIED` | `POST /api/sre-assistant/chat...` |
| Platform Settings, AI Credentials & Operational Policies | `settings` | [`frontend/src/pages/SettingsPage.tsx`](file:///frontend/src/pages/SettingsPage.tsx) | `FULL_RUNTIME_VERIFIED` | `GET /api/ai-config/status...` |
| Service Topology & Blast Radius Graph | `dependency-map` | [`frontend/src/pages/DependencyMapPage.tsx`](file:///frontend/src/pages/DependencyMapPage.tsx) | `FULL_RUNTIME_VERIFIED` | `GET /api/dependencies/graph...` |
| Real-Time Telemetry & Log Explorer | `live-telemetry` | [`frontend/src/pages/LiveTelemetryPage.tsx`](file:///frontend/src/pages/LiveTelemetryPage.tsx) | `FULL_RUNTIME_VERIFIED` | `GET /api/v1/telemetry/stats...` |
| Tenant Integrations & OpenTelemetry Exporters | `integrations` | [`frontend/src/pages/IntegrationsPage.tsx`](file:///frontend/src/pages/IntegrationsPage.tsx) | `FULL_RUNTIME_VERIFIED` | `GET /api/v1/tenants/{id}/integrations...` |
| Operational Runbooks & Verified Recovery Catalog | `runbooks` | [`frontend/src/pages/RunbooksPage.tsx`](file:///frontend/src/pages/RunbooksPage.tsx) | `FULL_RUNTIME_VERIFIED` | `GET /api/runbooks...` |
| Storage Intelligence & Telemetry Archiving | `storage` | [`frontend/src/pages/StoragePage.tsx`](file:///frontend/src/pages/StoragePage.tsx) | `FULL_RUNTIME_VERIFIED` | `GET /api/storage/status...` |

## 3. Screen-by-Screen Technical Details

### Platform Health & Multi-Tenant Operations Dashboard (`dashboard`)

- **Component File**: [`frontend/src/pages/DashboardPage.tsx`](file:///frontend/src/pages/DashboardPage.tsx)
- **Purpose**: Unified high-level dashboard displaying platform health score, multi-company tenant statuses, active incidents, and system metrics.
- **Data Displayed**: Platform health score (0-100), active incident count, mean time to detect/recover (MTTD/MTTR), tenant overview (ShopSphere, FinCore, CloudDesk), service health gauges.
- **Backend API Connections**: `GET /api/platform-health/status, GET /api/incidents, GET /api/tenants, GET /api/approvals/stats`
- **User Interactions**: Filter by tenant, click incident cards to navigate to RCA or Recovery, toggle between Live Telemetry and Controlled Demo mode, view MTTD trends.
- **Verification Status**: `FULL_RUNTIME_VERIFIED`
- **Known Limitations / Notes**: None observed. WebSocket live updates and polling fallback both operational.

### Operations Center & Incident Command (`operations`)

- **Component File**: [`frontend/src/pages/OperationsCenterPage.tsx`](file:///frontend/src/pages/OperationsCenterPage.tsx)
- **Purpose**: Real-time incident triage, live telemetry stream monitoring, active alerts, and immediate operator mitigation triggers.
- **Data Displayed**: Live incident feed, severity badges (CRITICAL, HIGH, MEDIUM, LOW), affected services, real-time telemetry stream waterfall, incident lifecycle states.
- **Backend API Connections**: `GET /api/incidents, GET /api/v1/telemetry/live-events, POST /api/incidents/clear, SSE /api/v1/telemetry/stream`
- **User Interactions**: Acknowledge incident, filter by severity, trigger immediate diagnostic scan, clear resolved incidents, view blast radius summary.
- **Verification Status**: `FULL_RUNTIME_VERIFIED`
- **Known Limitations / Notes**: None observed.

### Incidents Directory & Evidence Timeline (`incidents`)

- **Component File**: [`frontend/src/pages/IncidentsPage.tsx`](file:///frontend/src/pages/IncidentsPage.tsx)
- **Purpose**: Historical and active incident catalog with rich evidence inspection, root cause category breakdowns, and audit lineage.
- **Data Displayed**: Filterable list of incidents, tenant slugs, primary service, root cause category, confidence percentage, time elapsed, approval status, validation status.
- **Backend API Connections**: `GET /api/incidents, GET /api/incidents/{id}, GET /api/tenants`
- **User Interactions**: Search by keyword, filter by tenant or status (OPEN, INVESTIGATING, MITIGATED, RESOLVED), export incident package, click to open RCA.
- **Verification Status**: `FULL_RUNTIME_VERIFIED`
- **Known Limitations / Notes**: None observed.

### Dual-Solution Root Cause Analysis (AI + KB Engine) (`rca`)

- **Component File**: [`frontend/src/pages/RcaPage.tsx`](file:///frontend/src/pages/RcaPage.tsx)
- **Purpose**: Deep root cause diagnosis comparing Solution A (AI LLM via Gemini 3.8 Flash / OpenAI / Claude) with Solution B (Curated Knowledge Base Runbooks), showing consensus/conflict comparison and evidence packages.
- **Data Displayed**: 15-Question RCA evidence facts, AI-generated solution details, KB-matched article and steps, consensus alignment indicator (CONSENSUS_ALIGNED vs CONFLICT_DETECTED), side-by-side comparison matrix, blast radius graph.
- **Backend API Connections**: `GET /api/incidents/{id}/dual-solutions, POST /api/incidents/{id}/select-solution, GET /api/ai-config/status, GET /api/dependencies/graph`
- **User Interactions**: Select Solution A or Solution B, request approval for execution, inspect 15-question RCA answers, inspect evidence lineage, rerun AI analysis.
- **Verification Status**: `FULL_RUNTIME_VERIFIED`
- **Known Limitations / Notes**: None observed. Configured to display active Gemini 3.8 Flash model badge.

### Recovery Orchestrator & Bounded Refinement (`recovery`)

- **Component File**: [`frontend/src/pages/RecoveryPage.tsx`](file:///frontend/src/pages/RecoveryPage.tsx)
- **Purpose**: Closed-loop recovery execution with step-by-step progress tracking, empirical pre/post validation, rollback capability, and bounded retry/refinement.
- **Data Displayed**: Active recovery plan steps, execution logs, attempt counter (1/max), empirical validation check results (8-point criteria), side-effect alerts, rollback plan, escalation status.
- **Backend API Connections**: `GET /api/incidents/{id}/recovery-plan, POST /api/recovery/{id}/execute-step, POST /api/recovery/{id}/rollback, POST /api/recovery/{id}/validate`
- **User Interactions**: Execute next recovery step, trigger rollback, execute automated end-to-end recovery, view empirical validation metrics, escalate to SRE commander.
- **Verification Status**: `FULL_RUNTIME_VERIFIED`
- **Known Limitations / Notes**: None observed.

### Replica Lab (Digital Twin & Recovery Sandbox) (`testing-lab`)

- **Component File**: [`frontend/src/pages/TestingSimulationLabPage.tsx`](file:///frontend/src/pages/TestingSimulationLabPage.tsx)
- **Purpose**: Digital twin replica testbed executing the 17-step scientific experiment lifecycle: isolates proposed fix in twin, reproduces fault, captures baseline, tests remediation, runs regression checks, and ranks candidates.
- **Data Displayed**: Isolated twin status (Synthetic / Container / Staging), scenario parameters, baseline metrics vs post-intervention metrics, regression check results across 3+ services, candidate comparison ranking matrix, confidence score.
- **Backend API Connections**: `GET /api/testing-lab/inventory, GET /api/testing-lab/scenarios, POST /api/testing-lab/experiment/run, POST /api/testing-lab/experiment/{id}/approve-and-deploy`
- **User Interactions**: Select incident, choose scenario, run isolated experiment, review before-after delta, approve deployment to live target service.
- **Verification Status**: `FULL_RUNTIME_VERIFIED`
- **Known Limitations / Notes**: None observed. Full 17-step lifecycle operational.

### Approval Center & Operational Governance (`approvals`)

- **Component File**: [`frontend/src/pages/ApprovalsPage.tsx`](file:///frontend/src/pages/ApprovalsPage.tsx)
- **Purpose**: Human-in-the-loop governance center for high-risk recovery actions requiring explicit authorization under tenant policies.
- **Data Displayed**: Pending approval cards, risk level badges (LOW, MEDIUM, HIGH, CRITICAL), risk score, proposed action, target service, justification, rollback plan, required role, audit history.
- **Backend API Connections**: `GET /api/approvals, POST /api/approvals/{id}/approve, POST /api/approvals/{id}/reject, POST /api/approvals/{id}/defer, GET /api/approvals/stats`
- **User Interactions**: Approve action (triggers controlled recovery execution), reject action with reason, defer ticket, filter by tenant or risk level.
- **Verification Status**: `FULL_RUNTIME_VERIFIED`
- **Known Limitations / Notes**: Zero orphaned approvals; 100% reconciled.

### Autonomous SRE Copilot & Chat Operations (`assistant`)

- **Component File**: [`frontend/src/pages/AssistantPage.tsx`](file:///frontend/src/pages/AssistantPage.tsx)
- **Purpose**: Conversational incident assistant with live telemetry grounding, session persistence, and multi-turn SRE operations.
- **Data Displayed**: Conversation message thread, user prompts, assistant answers, grounded evidence citations, interaction IDs, telemetry source references.
- **Backend API Connections**: `POST /api/sre-assistant/chat, GET /api/sre-assistant/conversations/{id}, GET /api/sre-assistant/conversations`
- **User Interactions**: Submit questions ('What is the root cause?', 'Show me the traces', 'Did recovery succeed?'), create new session, view past conversation history.
- **Verification Status**: `FULL_RUNTIME_VERIFIED`
- **Known Limitations / Notes**: None observed. Supports Gemini 3.8 Flash, Anthropic, OpenAI, and deterministic rule-based fallback.

### Platform Settings, AI Credentials & Operational Policies (`settings`)

- **Component File**: [`frontend/src/pages/SettingsPage.tsx`](file:///frontend/src/pages/SettingsPage.tsx)
- **Purpose**: Configuration of AI providers (Gemini 3.8 Flash, Claude, GPT-4o), dynamic model discovery, reasoning effort tiers, model pinning, sandbox limits, and alerting channels.
- **Data Displayed**: RCA AI credentials (masked), SRE Assistant credentials, Independent Validation AI credentials, Reasoning effort buttons (Low, Medium, High), Discovered Gemini models list, Max recovery attempts slider, Risk ceiling dropdown, Webhook URL.
- **Backend API Connections**: `GET /api/ai-config/status, POST /api/ai-config/update, POST /api/ai-config/test-connection, GET /api/ai-config/models`
- **User Interactions**: Discover models live, select reasoning effort, toggle model pinning, enter API keys, run Test Connection with real diagnostics, update recovery retry limits.
- **Verification Status**: `FULL_RUNTIME_VERIFIED`
- **Known Limitations / Notes**: None observed.

### Service Topology & Blast Radius Graph (`dependency-map`)

- **Component File**: [`frontend/src/pages/DependencyMapPage.tsx`](file:///frontend/src/pages/DependencyMapPage.tsx)
- **Purpose**: Interactive dependency graph visualization showing service topology, direct and downstream dependents, and blast radius calculation.
- **Data Displayed**: Nodes (services, databases, caches), edges (RPC, HTTP, DB connections), health indicators (HEALTHY, DEGRADED, FAILED), blast radius impact percentage.
- **Backend API Connections**: `GET /api/dependencies/graph, GET /api/dependencies/topology`
- **User Interactions**: Click node to inspect service metrics, view blast radius score, simulate node failure, toggle tenant view.
- **Verification Status**: `FULL_RUNTIME_VERIFIED`
- **Known Limitations / Notes**: None observed.

### Real-Time Telemetry & Log Explorer (`live-telemetry`)

- **Component File**: [`frontend/src/pages/LiveTelemetryPage.tsx`](file:///frontend/src/pages/LiveTelemetryPage.tsx)
- **Purpose**: High-frequency telemetry stream inspector with real-time log ingestion, trace waterfall, and metric charts.
- **Data Displayed**: Live metrics (CPU, Memory, Latency p95, Error rate, Active connections), structured logs with log levels (INFO, WARN, ERROR), trace spans with waterfall view.
- **Backend API Connections**: `GET /api/v1/telemetry/stats, GET /api/v1/telemetry/live-events, SSE /api/v1/telemetry/stream`
- **User Interactions**: Filter by service, search log text, pause/resume streaming, toggle metric graphs, inspect trace spans.
- **Verification Status**: `FULL_RUNTIME_VERIFIED`
- **Known Limitations / Notes**: None observed.

### Tenant Integrations & OpenTelemetry Exporters (`integrations`)

- **Component File**: [`frontend/src/pages/IntegrationsPage.tsx`](file:///frontend/src/pages/IntegrationsPage.tsx)
- **Purpose**: Manage external monitoring connectors, OTel collector configuration, and API keys for tenant ingestion.
- **Data Displayed**: Active integrations list (Prometheus, Datadog agent, OpenTelemetry, Kafka), API key management with prefix masking, generated otel-collector.yaml config.
- **Backend API Connections**: `GET /api/v1/tenants/{id}/integrations, POST /api/v1/tenants/{id}/integrations, GET /api/v1/tenants/{id}/integrations/otel-config`
- **User Interactions**: Create API key, rotate key, download OTel collector configuration, test connector connectivity.
- **Verification Status**: `FULL_RUNTIME_VERIFIED`
- **Known Limitations / Notes**: None observed.

### Operational Runbooks & Verified Recovery Catalog (`runbooks`)

- **Component File**: [`frontend/src/pages/RunbooksPage.tsx`](file:///frontend/src/pages/RunbooksPage.tsx)
- **Purpose**: Curated library of standard operating procedures, verified recovery patterns, and allowlisted remediation actions.
- **Data Displayed**: Runbook ID, title, target service, execution steps, prerequisites, risk category, historical success rate, verified execution count.
- **Backend API Connections**: `GET /api/runbooks, GET /api/incidents/recovery/allowlisted-actions, GET /api/incidents/recovery/verified-patterns`
- **User Interactions**: View runbook details, test runbook in sandbox, filter by service or action type.
- **Verification Status**: `FULL_RUNTIME_VERIFIED`
- **Known Limitations / Notes**: None observed.

### Storage Intelligence & Telemetry Archiving (`storage`)

- **Component File**: [`frontend/src/pages/StoragePage.tsx`](file:///frontend/src/pages/StoragePage.tsx)
- **Purpose**: Disk usage forecasting, telemetry compression, retention management, and automated tiering.
- **Data Displayed**: Total disk capacity, telemetry volume consumed, projected hours until saturation, tiering statistics (Hot, Warm, Cold), compression ratios.
- **Backend API Connections**: `GET /api/storage/status, POST /api/storage/optimize, GET /api/storage/snapshots`
- **User Interactions**: Trigger immediate storage compression/rotation, adjust retention policies, view historical storage growth charts.
- **Verification Status**: `FULL_RUNTIME_VERIFIED`
- **Known Limitations / Notes**: None observed.

## 4. Reproducible Screen Capture Protocol

To capture report-ready figures from the running frontend:
1. Start backend: `.\venv\Scripts\python.exe scripts/start_all.py`
2. Start frontend dev server: `npm --prefix frontend run dev` (running on `http://localhost:5173`)
3. Log in with demo credentials (`admin@aegisops.io` / `AegisAdmin2026!`)
4. Navigate to each tab via the sidebar to capture:
   - **Figure 1**: Multi-Tenant Operations Dashboard (`/`)
   - **Figure 2**: Dual-Solution RCA with Gemini 3.8 Flash (`/?tab=rca`)
   - **Figure 3**: Digital Twin Replica Lab with 17-Step Lifecycle (`/?tab=testing-lab`)
   - **Figure 4**: Approval Center Governance & Risk Tiers (`/?tab=approvals`)
   - **Figure 5**: Closed-Loop Recovery Orchestrator with 8-Point Empirical Validation (`/?tab=recovery`)
   - **Figure 6**: Platform Settings with Dynamic Model Discovery (`/?tab=settings`)
