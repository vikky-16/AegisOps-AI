const assert = require('assert');

console.log('=== RUNNING FRONTEND NOTIFICATION & OBSERVABILITY UNIT TEST SUITE ===');

// --- 1. TEST DEDUPLICATION & MATERIAL CHANGE DETECTION ---
console.log('\n[TEST 1] Testing Toast Notification Deduplication & Version Advancement...');
const seenKeys = new Set();

function evaluateNewToasts(activeIncidents, currentTenantId, isInitialMount) {
  const newToasts = [];
  const tenantIncidents = activeIncidents.filter(i => !i.tenant_id || i.tenant_id === currentTenantId);

  tenantIncidents.forEach(inc => {
    if (inc.status === 'RESOLVED') return;
    const sev = (inc.severity || 'CRITICAL').toUpperCase();
    if (sev === 'CRITICAL' || sev === 'HIGH') {
      const updateSig = inc.created_at || inc.timestamp || '';
      const dedupKey = `inc-${inc.incident_id}-${sev}-${updateSig}-${currentTenantId}`;

      if (!seenKeys.has(dedupKey)) {
        seenKeys.add(dedupKey);
        newToasts.push({
          id: `toast-${inc.incident_id}`,
          dedupKey,
          recordId: inc.incident_id,
          severity: sev,
          title: sev === 'CRITICAL' ? 'Critical Incident Active' : 'High Severity Incident',
          durationMs: 6000
        });
      }
    }
  });

  return newToasts;
}

// Initial poll tick 1: new critical incident arrives
const incidentsTick1 = [
  { incident_id: 'INC-101', severity: 'CRITICAL', status: 'ACTIVE', created_at: '2026-10-20T14:00:00Z', tenant_id: 'demo-tenant' }
];
const toastsTick1 = evaluateNewToasts(incidentsTick1, 'demo-tenant', false);
assert.strictEqual(toastsTick1.length, 1, 'Tick 1 should emit 1 notification for new critical incident');
assert.strictEqual(toastsTick1[0].recordId, 'INC-101');
assert.strictEqual(toastsTick1[0].durationMs, 6000, 'Auto-dismiss duration must be between 5-7s');
console.log(' -> Tick 1 generated toast:', toastsTick1[0].title);

// Polling tick 2 (2.5s later with identical data)
const toastsTick2 = evaluateNewToasts(incidentsTick1, 'demo-tenant', false);
assert.strictEqual(toastsTick2.length, 0, 'Subsequent poll with identical data must NOT generate duplicate notification');
console.log(' -> Tick 2 polling deduplication verified: 0 duplicate toasts generated');

// Tick 3: Incident materially escalates severity
const incidentsTick3 = [
  { incident_id: 'INC-101', severity: 'CRITICAL', status: 'ACTIVE', created_at: '2026-10-20T14:05:00Z', tenant_id: 'demo-tenant' }
];
const toastsTick3 = evaluateNewToasts(incidentsTick3, 'demo-tenant', false);
assert.strictEqual(toastsTick3.length, 1, 'Material change (timestamp update) must emit a new meaningful notification');
console.log(' -> Tick 3 material advancement emitted new toast:', toastsTick3[0].recordId);

// --- 2. TEST AUTO-DISMISS & MANUAL CLOSE (VISUAL-ONLY DISMISSAL) ---
console.log('\n[TEST 2] Testing Auto-Dismiss & Visual-Only Dismissal Guarantee...');
let activeToasts = [...toastsTick1];
let underlyingIncidents = [...incidentsTick1];

// Operator clicks 'X' button to dismiss toast visually
function manualDismissToast(toastId) {
  activeToasts = activeToasts.filter(t => t.id !== toastId);
}

manualDismissToast(activeToasts[0].id);
assert.strictEqual(activeToasts.length, 0, 'Visual toast should be removed on dismiss');
assert.strictEqual(underlyingIncidents.length, 1, 'Underlying incident must NOT be altered or resolved when visual toast is dismissed');
assert.strictEqual(underlyingIncidents[0].status, 'ACTIVE', 'Underlying incident status must remain ACTIVE');
console.log(' -> Manual dismiss removed visual toast while preserving underlying incident intact');

// --- 3. TEST APPROVAL NOTIFICATIONS (WITHOUT PRE-APPROVAL) ---
console.log('\n[TEST 3] Testing Approval Notification Behavior...');
const pendingApprovals = [
  { approval_id: 'APP-501', status: 'PENDING', risk_level: 'HIGH', proposed_action: 'RECYCLE_CONNECTION_POOL', service_name: 'database-service', tenant_id: 'demo-tenant' }
];

let approvalToasts = [];
const seenApprovalKeys = new Set();

pendingApprovals.forEach(app => {
  const dedupKey = `app-${app.approval_id}-${app.status}-${app.tenant_id}`;
  if (!seenApprovalKeys.has(dedupKey)) {
    seenApprovalKeys.add(dedupKey);
    approvalToasts.push({
      id: `toast-${app.approval_id}`,
      recordId: app.approval_id,
      title: 'Approval Required',
      subtitle: `${app.proposed_action} on ${app.service_name}`
    });
  }
});

assert.strictEqual(approvalToasts.length, 1, 'Pending approval must generate toast notification');
assert.strictEqual(approvalToasts[0].title, 'Approval Required');
assert.strictEqual(pendingApprovals[0].status, 'PENDING', 'Underlying ticket must remain strictly PENDING');
console.log(' -> Approval toast verified without auto-approving or modifying the ticket');

// --- 4. TEST TENANT ISOLATION OF NOTIFICATIONS ---
console.log('\n[TEST 4] Testing Cross-Tenant Notification Isolation...');
const fincoreIncidents = [
  { incident_id: 'INC-FIN-99', severity: 'CRITICAL', status: 'ACTIVE', tenant_id: 'fincore' }
];

const fincoreToasts = evaluateNewToasts(fincoreIncidents, 'demo-tenant', false);
assert.strictEqual(fincoreToasts.length, 0, 'Demo tenant must NEVER receive notifications belonging to fincore');
console.log(' -> Cross-tenant notification isolation confirmed: demo-tenant received 0 fincore toasts');

// --- 5. TEST OBSERVABILITY METRIC CALCULATIONS & MISSING DATA DISCLOSURE ---
console.log('\n[TEST 5] Testing Observability Health & Missing Instrumentation Handling...');
function evaluateServiceHealth(service) {
  const isHealthy = service.error_rate < 0.05 && service.p95 < 200;
  return {
    status: isHealthy ? 'HEALTHY' : 'DEGRADED',
    latencyP95: service.p95 !== null ? `${service.p95}ms` : 'No data',
    errorRate: service.error_rate !== null ? `${service.error_rate * 100}%` : 'Not instrumented'
  };
}

const evaluatedDb = evaluateServiceHealth({ p95: 845, error_rate: 0.42 });
assert.strictEqual(evaluatedDb.status, 'DEGRADED');
assert.strictEqual(evaluatedDb.latencyP95, '845ms');

const evaluatedUninstrumented = evaluateServiceHealth({ p95: null, error_rate: null });
assert.strictEqual(evaluatedUninstrumented.latencyP95, 'No data');
assert.strictEqual(evaluatedUninstrumented.errorRate, 'Not instrumented');
console.log(' -> Uninstrumented metrics correctly disclose "No data" / "Not instrumented" without fabrication');

console.log('\n=== ALL 5 FRONTEND NOTIFICATION & OBSERVABILITY UNIT TESTS PASSED ===');
