"""Critic Agent responsible for safety verification, policy compliance, and action validation."""

from typing import Any

from orchestrator.core.models import CriticCheckResult, IntentType, RiskLevel


class Critic:
    """Evaluates proposed actions against security policies, ground truth, and confirmation requirements."""

    PROHIBITED_COMMAND_PATTERNS = [
        "rm -rf",
        "format c:",
        "drop database",
        "drop table",
        ":(){ :|:& };:",
        "chmod 777",
        "/etc/shadow",
        "/etc/passwd",
    ]

    MEMORY_INJECTION_PATTERNS = [
        "ignore previous instructions",
        "new system instruction",
        "system override",
        "you are now in developer mode",
    ]

    def verify_action(
        self,
        action_type: str,
        payload: dict[str, Any],
        confirmed: bool = False,
        risk_level: RiskLevel = RiskLevel.LOW,
    ) -> CriticCheckResult:
        """Evaluate an action proposed by a specialist before execution."""
        reasons: list[str] = []
        policy_compliant = True

        # 1. Check for command injection in strings within payload
        payload_str = str(payload).lower()
        for pattern in self.PROHIBITED_COMMAND_PATTERNS:
            if pattern in payload_str:
                policy_compliant = False
                reasons.append(f"Prohibited destructive command detected: '{pattern}'")

        # 2. Check for memory poisoning / system injection
        for pattern in self.MEMORY_INJECTION_PATTERNS:
            if pattern in payload_str:
                policy_compliant = False
                reasons.append(f"Potential memory contamination or prompt injection: '{pattern}'")

        # 3. Check for missing human confirmation on high-risk operations
        if risk_level == RiskLevel.HIGH and not confirmed:
            reasons.append("High-risk operation requires explicit human confirmation token")
            return CriticCheckResult(
                approved=False,
                groundedness_score=1.0,
                policy_compliant=policy_compliant,
                reasons=reasons,
            )

        # 4. Device action specific checks
        if action_type == "device":
            intent_type = payload.get("intent_type")
            if (
                intent_type in [IntentType.SEND_SMS.value, IntentType.MAKE_CALL.value]
                and not confirmed
            ):
                reasons.append(f"Device intent {intent_type} requires explicit user confirmation")
                return CriticCheckResult(
                    approved=False,
                    groundedness_score=1.0,
                    policy_compliant=policy_compliant,
                    reasons=reasons,
                )

        approved = policy_compliant and (len(reasons) == 0)
        return CriticCheckResult(
            approved=approved,
            groundedness_score=1.0 if policy_compliant else 0.0,
            policy_compliant=policy_compliant,
            reasons=reasons,
        )
