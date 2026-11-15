export interface ServiceMetric {
  service_name: string;
  timestamp: string;
  status: string;
  healthy: boolean;
  cpu_percent: number;
  memory_mb: number;
  request_count: number;
  error_count: number;
  error_rate: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  active_connections: number;
  anomaly_score: number;
  is_anomaly: number;
}

export interface ServiceDetail {
  name: string;
  display_name: string;
  port: number;
  url: string;
  role: string;
  criticality: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  status: string;
  healthy: boolean;
  cpu_percent: number;
  memory_mb: number;
  request_count: number;
  error_count: number;
  error_rate: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  active_connections: number;
  anomaly_score: number;
  is_anomaly: number;
}

export interface IncidentTimelineEvent {
  timestamp: string;
  service: string;
  type: string;
  message: string;
  event_id?: string | null;
}

export interface Incident {
  incident_id: string;
  tenant_id?: string;
  company?: string;
  title: string;
  description: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  status: 'OPEN' | 'INVESTIGATING' | 'ROOT_CAUSE_IDENTIFIED' | 'AWAITING_APPROVAL' | 'APPROVED' | 'REMEDIATING' | 'VERIFYING' | 'RESOLVED' | 'REJECTED' | 'REMEDIATION_FAILED' | 'ESCALATED' | string;
  primary_service: string;
  affected_services: string[];
  affected_resources?: string[];
  affected_dependencies?: string[];
  event_ids?: string[];
  correlation_id?: string;
  correlated_event_count: number;
  event_count?: number;
  detected_at?: string;
  anomaly_ids?: string[];
  supporting_evidence?: string[];
  alternative_hypotheses?: any[];
  propagation_path?: string[];
  confidence_pct?: number;
  error_rate?: number;
  baseline_error_rate?: number;
  propagation_depth?: number;
  anomaly_score: number;
  root_cause?: string;
  root_cause_service: string;
  root_cause_category: string;
  root_cause_summary: string;
  root_cause_confidence?: number;
  rca_confidence: number;
  rca_evidence: string[];
  business_impact_score: number;
  estimated_users_affected: number;
  sla_breach_risk: string;
  blast_radius?: BlastRadiusInfo;
  ranked_candidates?: RootCauseCandidateItem[];
  correlation_explanation?: CorrelationExplanation;
  correlation_score?: number;
  dependency_chain?: string[];
  correlation_graph?: CorrelationGraphData;
  historical_match?: HistoricalMatchInfo;
  telemetry_signature?: any;
  decision_factors?: Record<string, any>;
  recommended_action: string | null;
  alternative_action: string | null;
  action_risk_level: string;
  approval_status?: string;
  remediation_status?: string;
  verification_status?: string;
  recovery_status: string;
  timeline: IncidentTimelineEvent[];
  lifecycle_state?: string;
  hypotheses?: any;
  candidate_solutions?: any[];
  execution_history?: any[];
  side_effects_detected?: boolean;
  validation_report?: any;
  validation_criteria?: any[];
  iteration_count?: number;
  max_iterations?: number;
  state_transitions?: any[];
  failure_signature?: string;
  error_category?: string;
  selected_solution?: any;
  created_at: string;
  started_at?: string;
  latency_p95_ms?: number;
  latency?: number | string;
  updated_at?: string;
  resolved_at?: string;
}

export interface CorrelationNode {
  id: string;
  name: string;
  display_name: string;
  role: 'ROOT' | 'DIRECTLY_AFFECTED' | 'DOWNSTREAM_AFFECTED' | 'SECONDARY_SYMPTOMS' | 'HEALTHY';
  status: string;
  criticality: string;
  service_type: string;
  topological_depth: number;
  explanation: string;
}

export interface CorrelationEdge {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  confidence: number;
  is_cascade_edge: boolean;
  status: string;
}

export interface CorrelationGraphData {
  root_service: string;
  classification: {
    ROOT: string[];
    DIRECTLY_AFFECTED: string[];
    DOWNSTREAM_AFFECTED: string[];
    SECONDARY_SYMPTOMS: string[];
    HEALTHY: string[];
  };
  propagation_path: string[];
  nodes: CorrelationNode[];
  edges: CorrelationEdge[];
  affected_count: number;
  healthy_count: number;
}

export interface HistoricalMatchInfo {
  is_known_pattern: boolean;
  pattern_name?: string;
  matched_incident_id?: string;
  similarity_score?: number;
  similarity_pct?: number;
  historical_occurrences?: number;
  recommended_action?: string;
  success_rate?: number;
  success_rate_pct?: number;
  avg_mttr_seconds?: number;
  confidence_boost?: number;
}

export interface FailureScenarioItem {
  id: string;
  name: string;
  category: string;
  target_service: string;
  severity: string;
  description: string;
  recommended_action: string;
  alternative_action: string;
  detection_signals: string[];
  verification_metrics: string[];
}

export interface OrchestratorStatus {
  orchestrator_enabled: boolean;
  auto_mode: boolean;
  interval_seconds: number;
  time_until_next_seconds: number;
  next_injection_timestamp: number;
  active_scenario: FailureScenarioItem | null;
  active_scenario_start: number | null;
  lifecycle_state: 'IDLE' | 'INJECTING' | 'ACTIVE' | 'DETECTED' | 'INVESTIGATING' | 'RCA' | 'REMEDIATING' | 'VERIFYING' | 'RESOLVED' | 'LEARNED';
  execution_mode: 'CONTROLLED_DEMO';
  can_inject_next: boolean;
  scenarios_executed_count: number;
  total_available_scenarios: number;
}

export interface BlastRadiusInfo {
  failing_service?: string;
  criticality: string;
  direct_impact: string[];
  downstream_impact: string[];
  affected_services: string[];
  affected_services_count: number;
  affected_requests: number;
  customer_facing: boolean;
  impact_level: string;
  blast_radius_score: number;
  dependency_chain?: string[];
}

export interface RootCauseCandidateItem {
  rank: number;
  service: string;
  display_name?: string;
  category: string;
  confidence: number;
  confidence_pct: number;
  score: number;
  causal_onset_time?: string;
  rationale?: string;
  is_primary?: boolean;
}

export interface CorrelationExplanation {
  confidence: number;
  confidence_pct: number;
  total_correlated_events: number;
  reasons: string[];
  dependency_chain: string[];
}

export interface ServiceDependency {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  confidence: number;
  confidence_pct: number;
  observation_count: number;
  correlated_failures_count: number;
  status: 'INFERRED' | 'VALIDATED' | string;
  evidence: string[];
  first_seen?: string;
  last_seen?: string;
  request_volume?: string;
  request_rate?: number;
  latency?: string;
  latency_ms?: number;
  error_rate?: string;
  error_rate_pct?: number;
  dependency_status?: string;
  direction?: string;
  is_incident_path?: boolean;
}

export interface ServiceNode {
  id: string;
  service_id?: string;
  name: string;
  display_name: string;
  role?: string;
  service_type: string;
  status: 'HEALTHY' | 'WARNING' | 'DEGRADED' | 'CRITICAL' | 'FAILED' | 'UNKNOWN' | string;
  health_status?: 'HEALTHY' | 'WARNING' | 'DEGRADED' | 'CRITICAL' | 'FAILED' | 'UNKNOWN' | string;
  criticality: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | string;
  owner: string;
  environment: string;
  resource_id?: string;
  port: number;
  url: string;
  customer_facing?: boolean;
  request_rate?: number | string;
  error_rate?: number;
  p95_latency?: number;
  cpu?: number;
  ram?: number;
  availability?: number;
  active_incidents?: string[];
  role_in_incident?: 'ROOT' | 'ROOT_CAUSE' | 'DIRECTLY_AFFECTED' | 'DOWNSTREAM_AFFECTED' | 'AFFECTED' | 'SECONDARY_SYMPTOMS' | 'HEALTHY' | string;
  is_root_cause?: boolean;
  is_affected?: boolean;
  dominant_problem?: string;
  problem_badge?: string;
  why_degraded?: {
    summary: string;
    evidence: Record<string, any>;
  };
  baseline?: {
    error_rate: number;
    latency_p95_ms: number;
    cpu_percent: number;
    memory_mb: number;
    request_rate: number;
  };
  metrics?: {
    cpu_percent: number;
    memory_mb: number;
    error_rate: number;
    request_count: number;
    latency_p95_ms: number;
    active_connections: number;
  };
}

export interface DependencyGraphData {
  nodes: ServiceNode[];
  edges: ServiceDependency[];
  total_services: number;
  total_dependencies: number;
  tenant_id?: string;
  incident_context?: {
    incident_id: string;
    title?: string;
    severity?: string;
    root_cause_service: string;
    affected_services: string[];
    propagation_path: string[];
    critical_path: string[];
    classification?: Record<string, string[]>;
    blast_radius?: any;
  };
}


export interface TelemetryStats {
  events_per_sec: number;
  events_per_min: number;
  total_events: number;
  total_errors?: number;
  kafka_throughput_mb_s: number;
  consumer_lag: number;
  pipeline_latency_ms: number;
}

export interface ApprovalStats {
  pending_approvals: number;
  pending_count: number;
  total_pending: number;
  unique_incidents: number;
  unique_incidents_requiring_approval: number;
  high_risk: number;
  high_risk_count: number;
  medium_risk: number;
  medium_risk_count: number;
  low_risk: number;
  low_risk_count: number;
  approved_today: number;
  rejected_today: number;
  total_reviewed: number;
  total_tickets: number;
}

export interface ApprovalTicket {
  approval_id: string;
  incident_id: string;
  tenant_id?: string;
  service?: string;
  service_name: string;
  incident_severity?: string;
  severity?: string;
  incident_title?: string;
  detected_problem?: string;
  problem?: string;
  root_cause?: string;
  root_cause_confidence?: number;
  rca_confidence?: number;
  confidence?: number;
  evidence_summary?: any;
  evidence?: any[];
  affected_services?: string[];
  affected_services_count?: number;
  blast_radius?: string;
  blast_radius_score?: number;
  proposed_recovery_action?: string;
  proposed_action: string;
  action?: string;
  recommended_action?: string;
  alternative_action?: string;
  why_this_recovery_was_selected?: string;
  why_selected?: string;
  why_approval_required?: string;
  expected_outcome?: string;
  expected_result?: string;
  expected_impact?: string;
  risk_level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | string;
  risk?: string;
  risk_score?: number;
  sandbox_status?: string;
  validation_status?: string;
  safety_checks?: any;
  safety_check_passed?: boolean;
  blocked_reasons?: string[];
  rollback_available?: boolean;
  rollback_plan?: string;
  attempt_number?: number;
  attempt_history?: any[];
  created_at: string;
  expires_at?: string | null;
  requested_by?: string;
  requested_at?: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED' | 'CANCELLED' | string;
  approver_role_requirement?: string;
  required_role?: string;
  decision?: string | null;
  reviewed_by?: string | null;
  approved_by?: string | null;
  rejected_by?: string | null;
  review_notes?: string | null;
  reason?: string | null;
  approved_at?: string | null;
  rejected_at?: string | null;
  reviewed_at?: string | null;
  controlled_execution_plan?: string[];
  recovery_procedure?: string[];
  verification_plan?: string;
  failure_type?: string;
  estimated_downtime_sec?: number;
  historical_success?: string;
  solution?: string;
}

export interface RecoveryExecution {
  execution_id: string;
  incident_id: string;
  approval_id?: string | null;
  service_name: string;
  action: string;
  status: 'SUCCESS' | 'FAILED' | 'ROLLED_BACK' | string;
  success?: boolean;
  duration_ms: number;
  verification_status?: string;
  verification_result?: any;
  verification_details?: any;
  result?: any;
  error?: string | null;
  executed_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface StorageStatus {
  total_gb: number;
  used_gb: number;
  available_gb: number;
  used_percentage: number;
  growth_rate_gb_per_hour: number;
  predicted_critical_hours: number;
  log_files_count: number;
  compressed_archives_count: number;
  recommendation?: string;
  top_consumers: Array<{ 
    path?: string; 
    name?: string;
    size_mb?: number; 
    size_gb?: number;
    category?: string;
    percentage?: number;
    service?: string;
  }>;
}

export interface ControlledEvaluationResult {
  evaluation_id: string;
  incident_id: string;
  reproduction_status: 'REPRODUCED' | 'PARTIALLY_REPRODUCED' | 'NOT_REPRODUCED' | 'REPRODUCTION_FAILED' | string;
  failure_reproduced: boolean;
  evaluated_solutions: Array<{
    solution_id: string;
    action: string;
    attempt: number;
    failure_reproduced: boolean;
    action_executed: boolean;
    original_error_resolved: boolean;
    workflow_result: string;
    side_effects: string[];
    side_effects_detected: boolean;
    validation_result: 'VALIDATED' | 'SIDE_EFFECT_DETECTED' | 'FAILED' | 'REPRODUCTION_FAILED' | string;
    confidence: number;
    blast_radius: string;
    risk: string;
  }>;
  best_solution_id?: string;
  best_action?: string;
  selection_rationale?: string;
  completed_at: string;
}

export interface ValidationCriteriaItem {
  id: string;
  criterion: string;
  status: 'PASS' | 'FAIL' | 'WARN' | 'INSUFFICIENT_EVIDENCE' | string;
  observed_evidence: string;
  expected_condition: string;
  actual_condition: string;
  timestamp: string;
  source: string;
  details: string;
}

export interface RecoveryPerformanceMetrics {
  recovery_success_rate_pct: number;
  false_recovery_rate_pct: number;
  first_attempt_success_rate_pct: number;
  eventual_recovery_rate_pct: number;
  average_recovery_attempts: number;
  time_to_validated_recovery_sec: number;
  side_effect_rate_pct: number;
  total_recoveries_executed: number;
  total_recoveries_validated: number;
  total_side_effects_detected: number;
}

export interface RcaAnalysisResponse {
  incident_id: string;
  analysis_source: 'DETERMINISTIC' | 'AI + TELEMETRY';
  problem: string;
  root_cause: string;
  when_started: string;
  where_located: string;
  why_occurred: string;
  first_affected_service: string;
  subsequently_affected_services: string[];
  evidence_citations: Array<{
    timestamp: string;
    service: string;
    event_id: string;
    trace_id: string;
    metric: string;
    observed_value: string;
    expected_value: string;
    source: string;
  }>;
  alternative_causes_considered: string[];
  confidence: number;
  solution_options: Array<{
    solution_id: string;
    action: string;
    reason: string;
    expected_result: string;
    risk: string;
    blast_radius: string;
    affected_services: string[];
    rollback_method: string;
    approval_required: string;
    historical_success: string;
    confidence: number;
  }>;
  risk_assessment: Record<string, any>;
}

export interface RcaInvestigateResponse {
  question: string;
  incident_id: string;
  answer: string;
  analysis_source: 'DETERMINISTIC' | 'AI + TELEMETRY';
  evidence_citations: Array<{
    timestamp: string;
    service: string;
    event_id: string;
    trace_id: string;
    metric: string;
    observed_value: string;
    expected_value: string;
    source: string;
  }>;
}

export interface AssistantResponse {
  answer: string;
  confidence: number;
  intent: string;
  sources: string[];
  suggested_actions?: string[];
}

export interface LogEntry {
  timestamp: string;
  service: string;
  level: string;
  event_type: string;
  message: string;
  fingerprint?: string;
  trace_id?: string;
  metadata?: Record<string, any>;
}

export interface LogFingerprint {
  fingerprint: string;
  service: string;
  event_type: string;
  level: string;
  template: string;
  sample_message?: string;
  occurrences: number;
  first_seen: string;
  last_seen: string;
}

export interface LogSummary {
  total_logs: number;
  by_level: Record<string, number>;
  by_service: Record<string, number>;
  unique_fingerprints: number;
  buffer_capacity: number;
  buffer_usage: number;
}

export interface PaginatedLogs {
  items: LogEntry[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PlatformSettings {
  auto_healing_enabled: boolean;
  max_autonomous_risk_score: number;
  anomaly_sensitivity: number;
  storage_alert_threshold: number;
  webhook_notifications: string;
}

export interface ConnectorInfo {
  connector_id: string;
  name: string;
  type: string;
  description: string;
  enabled: boolean;
  status: string;
  auth_required: boolean;
  total_events: number;
  event_rate_eps: number;
  last_event_at: string | null;
  error_count: number;
  last_error: string | null;
}

export interface RunbookInfo {
  id: string;
  name: string;
  description: string;
  affected_component: string;
  risk_level: string;
  approval_required: boolean;
  prerequisites: string[];
  dry_run?: {
    estimated_recovery_time_sec: number;
    expected_downtime_sec: number;
    estimated_reclaimed_gb?: number;
    data_loss_risk: string;
  };
  action: {
    type: string;
    endpoint?: string;
    payload?: Record<string, any>;
  };
  verification: Record<string, any>;
  rollback?: {
    available: boolean;
    description: string;
    runbook_id?: string;
  };
}

export interface DryRunResult {
  success: boolean;
  runbook_id: string;
  runbook_name: string;
  target_service: string;
  risk_level: string;
  estimated_recovery_time_sec: number;
  expected_downtime_sec: number;
  estimated_reclaimed_gb: number;
  data_loss_risk: string;
  rollback_available: boolean;
  dry_run_passed: boolean;
  simulation_notes: string;
}

export interface OperationFeedItem {
  id: string;
  timestamp: string;
  time_display: string;
  phase: string;
  service: string;
  message: string;
  severity: string;
  metadata?: Record<string, any>;
}

export interface SimulatorStatus {
  status: 'IDLE' | 'STREAMING' | 'PAUSED' | 'COMPLETED' | 'ERROR';
  scenario: string;
  events_streamed: number;
  target_count: number;
  configured_eps: number;
  current_eps: number;
  progress_percentage: number;
  elapsed_seconds: number;
  is_streaming: boolean;
  is_paused: boolean;
}

export interface LogHubDatasetInfo {
  id: string;
  name: string;
  category: string;
  description: string;
  total_raw_records: number;
  components: string[];
  sample_message: string;
  has_structured_csv: boolean;
}

export interface LogHubReplayStatus {
  status: 'IDLE' | 'STREAMING' | 'PAUSED' | 'COMPLETED' | 'ERROR';
  dataset: string;
  events_available: number;
  events_sent: number;
  events_received: number;
  events_processed: number;
  processing_rate: number;
  configured_eps: number;
  target_count: number;
  progress_percentage: number;
  elapsed_seconds: number;
  errors: number;
  anomalies: number;
  correlated_events: number;
  incidents: number;
  critical_incidents: number;
  is_streaming: boolean;
  is_paused: boolean;
}

export type EnvironmentMode = 'DEMO' | 'STAGING' | 'PRODUCTION-CONNECTED';

export type StreamConnectorStatus = 'CONNECTED' | 'STREAMING' | 'DISCONNECTED' | 'IDLE';

export interface StreamConsumerStatus {
  connector_id: string;
  name: string;
  status: StreamConnectorStatus;
  is_running: boolean;
  protocol: string;
  total_received: number;
  total_processed: number;
  total_failed: number;
  event_rate_eps: number;
  last_event_at: string | null;
}

export interface TelemetryStreamEvent {
  event_id: string;
  timestamp: string;
  source: string;
  service: string;
  severity: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  event_type: string;
  message: string;
}

export interface RemediationRunbook {
  runbook_id: string;
  name: string;
  version: string;
  description: string;
  failure_type: string;
  supported_services: string[];
  root_cause_conditions: any;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  approval_required: boolean;
  action?: string;
  estimated_duration_sec?: number;
  preconditions: string[];
  diagnostic_steps: any[];
  recovery_steps: any[];
  rollback_steps: any[];
  verification_steps: any[];
  side_effect_checks: any[];
  success_conditions: string[];
  failure_conditions: string[];
  max_attempts: number;
  historical_success_rate?: number;
  avg_recovery_time_sec?: number;
  total_executions?: number;
}

export interface RunbookStepExecution {
  step_number: number;
  step_name: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'WARNING';
  started_at: string;
  completed_at: string;
  output: string;
  evidence?: any;
  error?: string | null;
}

export interface RunbookExecutionRecord {
  execution_id: string;
  runbook_id: string;
  runbook_name: string;
  version: string;
  incident_id: string;
  target_service: string;
  action: string;
  status: 'RUNNING' | 'SUCCESS' | 'FAILED' | 'AWAITING_APPROVAL';
  current_stage: 'DIAGNOSE' | 'APPROVE' | 'EXECUTE' | 'REPLAY' | 'VERIFY' | 'COMPLETE' | 'FAILED';
  caller: string;
  started_at: string;
  completed_at?: string | null;
  duration_seconds?: number;
  success: boolean;
  steps: RunbookStepExecution[];
}

export interface TelemetryDiagnosticItem {
  event_id: string;
  source: string;
  source_type: string;
  timestamp: string;
  received_at: string;
  ingestion_latency_ms: number;
  service: string;
  host?: string;
  severity: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  event_type: string;
  message: string;
  attributes?: Record<string, any>;
}

export type TelemetryMode = 'LIVE_STREAM' | 'CONTROLLED_DEMO';

export interface ContinuousTelemetryStatus {
  is_running: boolean;
  configured_eps: number;
  actual_eps: number;
  events_per_sec?: number;
  events_per_min?: number;
  total_events: number;
  total_errors: number;
  kafka_throughput_mb_s?: number;
  consumer_lag?: number;
  pipeline_latency_ms?: number;
  avg_ingestion_latency_ms: number;
  last_event_time: string | null;
  active_failure_overrides: string[];
  recent_diagnostics_count: number;
}

export interface FailureScenarioInfo {
  id: string;
  name: string;
  primary: string;
  risk: string;
  description?: string;
}

export interface FailureSchedulerStatus {
  is_enabled: boolean;
  interval_seconds: number;
  time_to_next_failure_sec: number;
  total_failures_injected: number;
  current_scenario: string;
  current_scenario_id: string | null;
  selected_scenario_id?: string | null;
  available_scenarios: FailureScenarioInfo[];
}

export interface TelemetryDiagnosticsResponse {
  operating_mode: TelemetryMode;
  avg_ingestion_latency_ms: number;
  current_eps: number;
  total_events: number;
  total_errors: number;
  events: TelemetryDiagnosticItem[];
}

export interface TelemetryWebSocketMessage {
  type: string;
  timestamp: string;
  health_score: number;
  environment_mode?: string;
  operating_mode?: TelemetryMode;
  services: ServiceMetric[];
  services_health: Record<string, { status: string; healthy: boolean; state: string }>;
  active_incidents_count: number;
  pending_approvals_count: number;
  storage_percentage: number;
  storage_critical_hours: number;
  live_feed?: OperationFeedItem[];
  host_cpu?: number;
  host_memory?: number;
  stream_status?: StreamConsumerStatus;
  continuous_telemetry?: ContinuousTelemetryStatus;
  failure_scheduler?: FailureSchedulerStatus;
  diagnostics?: TelemetryDiagnosticItem[];
  dependencies?: DependencyGraphData;
  active_incidents?: Incident[];
}

export type ServiceOperationalStatus = 'HEALTHY' | 'DEGRADED' | 'CRITICAL' | 'DOWN' | 'UNKNOWN';
export type TelemetryConnectionStatus = 'CONNECTED' | 'DEGRADED' | 'DISCONNECTED' | 'PENDING';

export interface CanonicalOperationalState {
  tenant_id: string;
  service_id: string;
  service_name: string;
  display_name: string;
  role: string;
  service_type: string;
  port: number;
  environment: string;
  operational_status: ServiceOperationalStatus;
  telemetry_status: TelemetryConnectionStatus;
  dependency_status: string;
  request_rate: number;
  error_rate: number;
  p50?: number | null;
  p90?: number | null;
  p95?: number | null;
  p99?: number | null;
  cpu?: number | null;
  memory?: number | null;
  active_incidents: number;
  active_warnings: number;
  last_telemetry_at?: string | null;
  last_health_check_at?: string | null;
  updated_at: string;
  telemetry_sample_count: number;
  calculation_window: string;
  is_stale: boolean;
  stale_seconds: number;
  health_score: number;
  status_reasons: string[];
}

export interface SystemConsistencyAudit {
  status: 'PASS' | 'FAIL';
  tenant_id: string;
  checked_at: string;
  checks: {
    service_status: 'PASS' | 'FAIL';
    telemetry: 'PASS' | 'FAIL';
    incidents: 'PASS' | 'FAIL';
    approvals: 'PASS' | 'FAIL';
    recovery: 'PASS' | 'FAIL';
    dependencies: 'PASS' | 'FAIL';
    ml: 'PASS' | 'FAIL';
    tenant_isolation: 'PASS' | 'FAIL';
    timestamps: 'PASS' | 'FAIL';
  };
  discrepancies: string[];
  total_services_audited: number;
  active_incidents_audited: number;
  pending_approvals_audited: number;
}
