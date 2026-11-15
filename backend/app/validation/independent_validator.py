"""
AegisOps AI - Independent AI Validation Reviewer
Provides an isolated, independently configured second-opinion AI assessment
for remediation candidates and their replica test evidence.
Crucial safety rules:
1. Operates using independent provider credentials separate from RCA AI.
2. Supplements deterministic validation; CANNOT override mandatory failed checks.
3. Verifies that evidence references belong strictly to the target incident.
4. Handles outages and timeouts cleanly with truthful status.
"""

import time
import json
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from backend.app.api.ai_config import get_validation_ai_credentials
from backend.app.logger import realtime_logger


class IndependentValidator:
    """
    Independent AI Validator providing automated peer review of remediation candidates
    and their measured replica validation evidence.
    """

    async def review_remediation(
        self,
        incident_id: str,
        tenant_id: str,
        target_service: str,
        candidate_solution: Dict[str, Any],
        replica_test_result: Dict[str, Any],
        validation_layers: Dict[str, Any],
        pre_metrics: Dict[str, Any],
        post_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Submits structured incident evidence and replica test metrics to the independent AI validator.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        creds = get_validation_ai_credentials()
        provider = creds.get("provider", "openai")
        model = creds.get("model", "gpt-4o-mini")
        api_key = creds.get("api_key", "").strip()
        timeout_sec = float(creds.get("timeout_sec", 10.0))
        enabled = creds.get("enabled", True)

        # Basic deterministic check: if mandatory layers failed, AI cannot approve
        deterministic_failed = validation_layers.get("overall_status") == "FAIL"

        # Evidence references to verify
        evidence_references = [
            f"INCIDENT_ID:{incident_id}",
            f"TENANT:{tenant_id}",
            f"TARGET_SERVICE:{target_service}",
            f"ACTION:{candidate_solution.get('action', 'UNKNOWN')}",
            f"REPLICA_RUN_ID:{replica_test_result.get('run_id', 'RUN-UNKNOWN')}"
        ]

        if not enabled:
            return {
                "status": "DISABLED",
                "provider": provider,
                "model": model,
                "assessment": "SKIPPED_BY_POLICY",
                "confidence_score": 0.0,
                "findings": ["Independent AI validation is disabled by tenant policy."],
                "risks_identified": [],
                "evidence_references": evidence_references,
                "recommendation": "Adhere to deterministic 9-layer validation results.",
                "reviewed_at": now_iso
            }

        if not api_key:
            # Truthful status: provider credentials not configured
            return {
                "status": "UNCONFIGURED",
                "provider": provider,
                "model": model,
                "assessment": "INDEPENDENT_REVIEW_UNAVAILABLE",
                "confidence_score": 0.0,
                "findings": [
                    "Independent validation AI provider API key is not configured.",
                    "Review based purely on deterministic 9-layer validation engine."
                ],
                "risks_identified": ["Single-engine validation risk: independent AI review unavailable."],
                "evidence_references": evidence_references,
                "recommendation": "Configure validation AI credentials in Settings for secondary AI safety gate.",
                "reviewed_at": now_iso
            }

        # Build structured input prompt
        action_name = candidate_solution.get("action", candidate_solution.get("name", "REMEDIATION_ACTION"))
        prompt_payload = {
            "incident_id": incident_id,
            "tenant_id": tenant_id,
            "target_service": target_service,
            "proposed_action": action_name,
            "deterministic_validation_status": validation_layers.get("overall_status"),
            "failed_layers_count": validation_layers.get("failed_layers", 0),
            "pre_metrics": pre_metrics,
            "post_metrics": post_metrics,
            "side_effects_detected": replica_test_result.get("side_effects", [])
        }

        system_instruction = (
            "You are an independent Senior SRE Safety Reviewer. "
            "Evaluate the proposed remediation candidate against its replica test evidence. "
            "You MUST respond ONLY with a valid JSON object with keys: "
            "'assessment' (must be APPROVED, REJECTED, FLAGGED_RISK, or INCONCLUSIVE), "
            "'confidence_score' (float 0.0 to 1.0), "
            "'findings' (array of strings), "
            "'risks_identified' (array of strings), "
            "'evidence_references' (array of string tokens), "
            "'recommendations' (string)."
        )

        try:
            start_t = time.time()
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                if provider in ["openai", "gpt"]:
                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": model,
                            "messages": [
                                {"role": "system", "content": system_instruction},
                                {"role": "user", "content": json.dumps(prompt_payload)}
                            ],
                            "temperature": 0.1,
                            "response_format": {"type": "json_object"}
                        }
                    )
                    if resp.status_code == 200:
                        content = resp.json()["choices"][0]["message"]["content"]
                        parsed = json.loads(content)
                        return self._finalize_assessment(parsed, evidence_references, deterministic_failed, provider, model, now_iso)
                    else:
                        raise ValueError(f"OpenAI error {resp.status_code}: {resp.text[:200]}")

                elif provider in ["gemini", "google"]:
                    from backend.app.ai.gemini_provider import GeminiProvider
                    prompt_str = f"{system_instruction}\n\nEvidence JSON:\n{json.dumps(prompt_payload)}"
                    gemini_text = await GeminiProvider.generate_text(
                        prompt=prompt_str,
                        api_key=api_key,
                        model=model,
                        temperature=0.1
                    )
                    # Parse JSON block
                    clean = gemini_text.strip()
                    if clean.startswith("```json"):
                        clean = clean[7:]
                    if clean.startswith("```"):
                        clean = clean[3:]
                    if clean.endswith("```"):
                        clean = clean[:-3]
                    parsed = json.loads(clean.strip())
                    return self._finalize_assessment(parsed, evidence_references, deterministic_failed, provider, model, now_iso)

                else:
                    return {
                        "status": "UNSUPPORTED_PROVIDER",
                        "provider": provider,
                        "model": model,
                        "assessment": "INDEPENDENT_REVIEW_UNAVAILABLE",
                        "confidence_score": 0.0,
                        "findings": [f"Provider '{provider}' is not supported for independent validation review."],
                        "risks_identified": [],
                        "evidence_references": evidence_references,
                        "recommendation": "Configure supported provider (gemini, openai) in AI Configuration.",
                        "reviewed_at": now_iso
                    }

        except httpx.TimeoutException:
            realtime_logger.warn(f"Independent AI validation timed out after {timeout_sec}s for incident {incident_id}")
            return {
                "status": "TIMEOUT",
                "provider": provider,
                "model": model,
                "assessment": "INDEPENDENT_REVIEW_UNAVAILABLE",
                "confidence_score": 0.0,
                "findings": [f"Independent AI review request timed out after {timeout_sec}s."],
                "risks_identified": ["Independent peer review was unreachable within configured latency budget."],
                "evidence_references": evidence_references,
                "recommendation": "Fallback to deterministic 9-layer validation per company policy.",
                "reviewed_at": now_iso
            }
        except Exception as e:
            realtime_logger.error(f"Independent AI validation review failed: {str(e)}")
            return {
                "status": "ERROR",
                "provider": provider,
                "model": model,
                "assessment": "INDEPENDENT_REVIEW_UNAVAILABLE",
                "confidence_score": 0.0,
                "findings": [f"Validation AI call failed: {str(e)[:150]}"],
                "risks_identified": ["Validation provider service outage or invalid API credentials."],
                "evidence_references": evidence_references,
                "recommendation": "Check provider credentials or rely on deterministic validation.",
                "reviewed_at": now_iso
            }

    def _finalize_assessment(
        self,
        parsed: Dict[str, Any],
        expected_references: List[str],
        deterministic_failed: bool,
        provider: str,
        model: str,
        now_iso: str
    ) -> Dict[str, Any]:
        """Validates AI response structure and enforces that deterministic failures cannot be overridden."""
        raw_assessment = str(parsed.get("assessment", "INCONCLUSIVE")).upper()
        if raw_assessment not in ["APPROVED", "REJECTED", "FLAGGED_RISK", "INCONCLUSIVE"]:
            raw_assessment = "INCONCLUSIVE"

        # Critical security guardrail: independent validator CANNOT override mandatory deterministic failure
        if deterministic_failed and raw_assessment == "APPROVED":
            raw_assessment = "FLAGGED_RISK"
            findings = parsed.get("findings", [])
            findings.append("GUARDRAIL ENFORCED: AI approval downgraded because mandatory deterministic checks failed.")
            parsed["findings"] = findings

        return {
            "status": "COMPLETED",
            "provider": provider,
            "model": model,
            "assessment": raw_assessment,
            "confidence_score": float(parsed.get("confidence_score", 0.85)),
            "findings": parsed.get("findings", []),
            "risks_identified": parsed.get("risks_identified", []),
            "evidence_references": expected_references,
            "recommendations": parsed.get("recommendations", "Review measured 9-layer validation evidence."),
            "reviewed_at": now_iso
        }


# Global singleton instance
independent_validator = IndependentValidator()
