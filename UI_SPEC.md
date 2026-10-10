# UI Specification

## 1. Product UI

Hina is voice-first. The dashboard is a control plane, not the primary assistant.

## 2. Dashboard pages

### `/`
Live session:
- connection status
- mic state
- current transcript
- response stream
- latency timeline

### `/memory`
- searchable memories
- source conversation
- confidence
- created/updated time
- graph view
- delete/correct controls

### `/actions`
- action history
- risk level
- confirmation state
- result
- revoke device

### `/sandbox`
- execution ID
- code preview
- stdout/stderr
- execution time
- network policy

### `/traces`
- trace ID
- stage timings
- provider calls
- errors

## 3. UX states

```text
IDLE
LISTENING
THINKING
SPEAKING
INTERRUPTED
EXECUTING
WAITING_FOR_CONFIRMATION
ERROR
OFFLINE
```

## 4. Confirmation UX

High-risk actions must display:
- action
- target
- exact payload summary
- reason
- Approve
- Deny

Never hide dangerous payload details behind a generic "Continue" button.

## 5. Memory UX

Every durable memory must show:
- statement
- confidence
- source
- timestamp
- edit/delete control

## 6. Accessibility

- keyboard navigation
- readable contrast
- captions/transcript
- explicit audio status
- no color-only status indicators
