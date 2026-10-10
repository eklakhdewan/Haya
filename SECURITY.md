# Security and Privacy Protocol

## 1. Security model

Assume:
- prompts can be malicious;
- tool outputs can be malicious;
- retrieved memory can be poisoned;
- LLM output is untrusted;
- devices can be compromised;
- external providers can fail.

## 2. Threat matrix

| Threat | Control |
|---|---|
| Prompt injection | tool isolation + policy engine |
| Tool poisoning | schema validation + output sanitization |
| Sandbox escape | external microVM sandbox |
| Secret leakage | secret manager + redaction |
| Device abuse | allowlist + RBAC + confirmation |
| Memory poisoning | provenance + confidence + user correction |
| Replay | nonce + timestamp + idempotency |
| Stolen device token | rotation + revocation |
| SSRF | egress allowlist |
| Excessive tool loops | max iterations |
| Data leakage | minimum-data principle |

## 3. Sandbox rules

- no host filesystem
- no host process access
- no ambient cloud credentials
- network disabled by default
- dependency installation restricted
- execution timeout
- memory/CPU quota
- output cap
- ephemeral filesystem

## 4. Device rules

Default:
- OPEN_APP: low risk
- SYSTEM_SETTING: medium/high risk
- SEND_SMS: high risk
- MAKE_CALL: high risk

High-risk actions require explicit user approval unless the user has configured an explicit trusted policy.

## 5. Authentication

Use short-lived access tokens and device-bound credentials.

Never put provider API keys in:
- Android app bundle
- frontend JavaScript
- Git
- logs
- prompts

## 6. PII

Minimize PII sent to external providers. Redact where appropriate.

Do not claim that redaction makes privacy absolute. It is a risk reduction layer.

## 7. Memory deletion

Deletion must propagate to:
1. canonical memory record
2. Qdrant point
3. Neo4j nodes/edges
4. caches
5. derived indexes where applicable

Keep only an audit tombstone if required by the chosen privacy policy.

## 8. Security gates before release

- dependency audit
- secret scan
- SAST
- container scan
- auth tests
- authorization tests
- sandbox escape tests
- prompt injection tests
- device action abuse tests
