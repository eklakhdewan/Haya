# Agent Topology and Contracts

## 1. Supervisor

Input:
```json
{"session_id":"...", "user_id":"...", "text":"...", "trace_id":"..."}
```

Output:
```json
{
  "route":"conversation|memory|tool|coder|device",
  "confidence":0.0,
  "requires_confirmation":false
}
```

Responsibilities:
- classify intent
- enforce policy
- choose specialist
- cap loops

It must not directly perform privileged actions.

## 2. Memory Agent

Extracts candidate:
- Person
- Preference
- Project
- Event
- Organization
- Skill
- Relationship

Every candidate requires:
- source turn ID
- confidence
- timestamp
- operation: CREATE/UPDATE/DELETE/IGNORE

## 3. Coder Agent

Flow:
1. understand task
2. generate code
3. static policy check
4. execute in sandbox
5. inspect stdout/stderr
6. repair at most 2 times
7. return result

Never:
- execute on host
- access arbitrary credentials
- silently enable network
- persist arbitrary files outside sandbox

## 4. Tool Agent

All tools implement:

```python
class Tool:
    name: str
    description: str
    input_schema: dict
    risk_level: str
    requires_confirmation: bool

    async def execute(self, payload: dict) -> dict:
        ...
```

## 5. Device Agent

Must produce a typed mobile intent.

No direct Android API calls from the LLM.

## 6. Critic

Checks:
- answer groundedness
- tool result consistency
- policy compliance
- memory contamination
- missing confirmation

The critic may reject a proposed action. It may not override a security policy.
