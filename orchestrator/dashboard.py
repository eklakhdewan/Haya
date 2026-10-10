"""Developer Dashboard UI rendering the Hina Control Plane."""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HINA — Developer Control Plane & Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: rgba(17, 24, 39, 0.85);
      --card-border: rgba(255, 255, 255, 0.08);
      --accent-cyan: #06b6d4;
      --accent-indigo: #6366f1;
      --accent-violet: #8b5cf6;
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text-main);
      font-family: 'Inter', -apple-system, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    /* Top Navigation Header */
    header {
      background: rgba(15, 23, 42, 0.9);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--card-border);
      padding: 16px 28px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 50;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-logo {
      width: 32px;
      height: 32px;
      background: linear-gradient(135deg, var(--accent-cyan), var(--accent-indigo));
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 16px;
      color: white;
    }
    .brand-title {
      font-size: 18px;
      font-weight: 700;
      letter-spacing: -0.5px;
    }
    .brand-version {
      font-size: 11px;
      background: rgba(99, 102, 241, 0.2);
      color: #a5b4fc;
      padding: 2px 8px;
      border-radius: 12px;
      font-weight: 600;
    }

    .nav-tabs {
      display: flex;
      gap: 6px;
      background: rgba(0, 0, 0, 0.3);
      padding: 4px;
      border-radius: 10px;
      border: 1px solid var(--card-border);
    }
    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s ease;
    }
    .tab-btn.active, .tab-btn:hover {
      background: rgba(255, 255, 255, 0.08);
      color: var(--text-main);
    }
    .tab-btn.active {
      background: linear-gradient(135deg, rgba(6, 182, 212, 0.2), rgba(99, 102, 241, 0.2));
      color: var(--accent-cyan);
      border: 1px solid rgba(6, 182, 212, 0.3);
    }

    .status-pill {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      font-weight: 500;
      background: rgba(16, 185, 129, 0.12);
      color: #34d399;
      padding: 6px 14px;
      border-radius: 20px;
      border: 1px solid rgba(16, 185, 129, 0.25);
    }
    .status-dot {
      width: 8px;
      height: 8px;
      background: var(--success);
      border-radius: 50%;
      box-shadow: 0 0 10px var(--success);
    }

    /* Main Container */
    main {
      flex: 1;
      max-width: 1300px;
      width: 100%;
      margin: 0 auto;
      padding: 28px 24px;
    }

    .view-panel { display: none; }
    .view-panel.active { display: block; }

    /* Grid Layouts */
    .dashboard-grid {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 24px;
    }

    .card {
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 24px;
      margin-bottom: 24px;
    }
    .card-title {
      font-size: 15px;
      font-weight: 600;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    /* Live Session View */
    .voice-control-box {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px 20px;
      background: rgba(0, 0, 0, 0.25);
      border-radius: 12px;
      margin-bottom: 20px;
    }
    .mic-btn {
      background: linear-gradient(135deg, var(--accent-cyan), var(--accent-indigo));
      border: none;
      color: white;
      font-weight: 600;
      padding: 10px 22px;
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: opacity 0.2s;
    }
    .mic-btn:hover { opacity: 0.9; }

    .transcript-feed {
      min-height: 220px;
      max-height: 380px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 12px;
      padding: 12px;
      background: rgba(0, 0, 0, 0.3);
      border-radius: 10px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
    }
    .feed-msg {
      padding: 10px 14px;
      border-radius: 8px;
      line-height: 1.5;
    }
    .feed-msg.user {
      background: rgba(99, 102, 241, 0.15);
      border-left: 3px solid var(--accent-indigo);
      align-self: flex-start;
      width: 90%;
    }
    .feed-msg.assistant {
      background: rgba(6, 182, 212, 0.15);
      border-left: 3px solid var(--accent-cyan);
      align-self: flex-start;
      width: 90%;
    }
    .feed-msg.event {
      font-size: 11px;
      color: var(--text-muted);
      align-self: center;
    }

    /* Metrics & Timing timeline */
    .metric-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      font-size: 13px;
    }
    .metric-val {
      font-family: 'JetBrains Mono', monospace;
      font-weight: 600;
      color: var(--accent-cyan);
    }

    /* Tables */
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      text-align: left;
      padding: 12px 14px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }
    th {
      color: var(--text-muted);
      font-weight: 500;
      font-size: 12px;
      text-transform: uppercase;
    }
    .badge {
      display: inline-block;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 600;
    }
    .badge-low { background: rgba(16, 185, 129, 0.2); color: #34d399; }
    .badge-med { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
    .badge-high { background: rgba(239, 68, 68, 0.2); color: #f87171; }

    /* Code Console */
    textarea {
      width: 100%;
      height: 160px;
      background: rgba(0, 0, 0, 0.4);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      color: #e5e7eb;
      font-family: 'JetBrains Mono', monospace;
      padding: 12px;
      font-size: 13px;
      margin-bottom: 12px;
      resize: vertical;
    }
    .console-out {
      background: #000;
      border-radius: 8px;
      padding: 14px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      color: #34d399;
      min-height: 120px;
      white-space: pre-wrap;
    }

    .btn-action {
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid var(--card-border);
      color: white;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 12px;
      cursor: pointer;
    }
    .btn-action:hover { background: rgba(255, 255, 255, 0.15); }
    .btn-danger { background: rgba(239, 68, 68, 0.2); color: #f87171; border-color: rgba(239, 68, 68, 0.4); }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <div class="brand-logo">H</div>
      <div class="brand-title">HINA</div>
      <span class="brand-version">v1.0 Control Plane</span>
    </div>

    <nav class="nav-tabs">
      <button class="tab-btn active" onclick="switchTab('live')">Live Session</button>
      <button class="tab-btn" onclick="switchTab('memory')">Memory Vault</button>
      <button class="tab-btn" onclick="switchTab('actions')">Device Actions</button>
      <button class="tab-btn" onclick="switchTab('sandbox')">Code Sandbox</button>
      <button class="tab-btn" onclick="switchTab('traces')">Traces</button>
    </nav>

    <div class="status-pill">
      <span class="status-dot"></span>
      <span id="orchestratorStatus">Orchestrator Online</span>
    </div>
  </header>

  <main>
    <!-- 1. Live Session View -->
    <div id="view-live" class="view-panel active">
      <div class="dashboard-grid">
        <div>
          <div class="card">
            <div class="card-title">Realtime Voice Session</div>
            <div class="voice-control-box">
              <div>
                <strong>WebSocket Media Gateway</strong>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">Connected to /v1/realtime/ws</div>
              </div>
              <button class="mic-btn" id="simulateTurnBtn" onclick="simulateTurn()">
                <span>🎙️ Simulate Spoken Turn</span>
              </button>
            </div>

            <div class="transcript-feed" id="liveTranscriptFeed">
              <div class="feed-msg event">[SYSTEM] Realtime Voice Gateway connected and ready for turns.</div>
            </div>
          </div>
        </div>

        <div>
          <div class="card">
            <div class="card-title">Latency Budget & Metrics</div>
            <div class="metric-item">
              <span>Turn Detection (VAD)</span>
              <span class="metric-val">&lt; 150 ms</span>
            </div>
            <div class="metric-item">
              <span>STT Finalization</span>
              <span class="metric-val">&lt; 150 ms</span>
            </div>
            <div class="metric-item">
              <span>Hybrid Memory Retrieval</span>
              <span class="metric-val">&lt; 100 ms</span>
            </div>
            <div class="metric-item">
              <span>LLM First Token</span>
              <span class="metric-val">&lt; 250 ms</span>
            </div>
            <div class="metric-item">
              <span>TTS First Audio Frame</span>
              <span class="metric-val">&lt; 150 ms</span>
            </div>
            <div class="metric-item" style="border-top: 1px solid rgba(255,255,255,0.1); margin-top: 8px;">
              <strong>Perceived Total Target</strong>
              <strong class="metric-val" style="color: var(--success);">&lt; 500 ms</strong>
            </div>
          </div>

          <div class="card">
            <div class="card-title">Active Specialists</div>
            <div style="font-size: 13px; display: flex; flex-direction: column; gap: 8px;">
              <div>• <strong>Supervisor:</strong> Intent Classifier &amp; Loop Capper</div>
              <div>• <strong>Critic:</strong> Groundedness &amp; Injection Defense</div>
              <div>• <strong>Coder:</strong> Isolated E2B Execution with 2x Repair</div>
              <div>• <strong>Device:</strong> Schema-Validated Android Intents</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 2. Memory View -->
    <div id="view-memory" class="view-panel">
      <div class="card">
        <div class="card-title">
          <span>Persistent Hybrid Memory Vault (Qdrant + Neo4j)</span>
          <button class="btn-action" onclick="refreshMemories()">Refresh</button>
        </div>
        <div style="margin-bottom: 16px; display: flex; gap: 10px;">
          <input type="text" id="memorySearchInput" placeholder="Search memories (e.g. project, Python, preference)..." 
                 style="flex: 1; padding: 10px 14px; background: rgba(0,0,0,0.3); border: 1px solid var(--card-border); border-radius: 8px; color: white; font-size: 13px;">
          <button class="btn-action" onclick="searchMemory()">Search</button>
        </div>
        <table id="memoryTable">
          <thead>
            <tr>
              <th>Memory ID</th>
              <th>Statement</th>
              <th>Score / Confidence</th>
              <th>Provenance Turn</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="memoryTableBody">
            <tr><td colspan="5" style="color: var(--text-muted); text-align: center;">Click Search or Refresh to inspect memories</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 3. Actions View -->
    <div id="view-actions" class="view-panel">
      <div class="card">
        <div class="card-title">
          <span>Android Action Audit Trail</span>
          <button class="btn-action" onclick="loadAuditTrail()">Refresh Audit Log</button>
        </div>
        <table>
          <thead>
            <tr>
              <th>Action ID</th>
              <th>Device</th>
              <th>Intent</th>
              <th>Risk</th>
              <th>Confirmation</th>
              <th>Result</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody id="actionsTableBody">
            <tr><td colspan="7" style="color: var(--text-muted); text-align: center;">Loading action audit trail...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 4. Sandbox View -->
    <div id="view-sandbox" class="view-panel">
      <div class="card">
        <div class="card-title">Isolated MicroVM Sandbox Console</div>
        <textarea id="sandboxCodeInput"># Pure sandboxed Python code
def calculate_pi(n_terms):
    pi = 0
    sign = 1
    for i in range(1, n_terms * 2, 2):
        pi += sign * (4 / i)
        sign *= -1
    return pi

print(f"Calculated Pi: {calculate_pi(5000)}")
</textarea>
        <button class="mic-btn" onclick="runSandboxCode()" style="margin-bottom: 16px;">Execute in Isolated Sandbox</button>
        <div class="card-title" style="font-size: 13px;">Execution Result &amp; Stdout/Stderr:</div>
        <div class="console-out" id="sandboxOutputConsole">Ready for execution...</div>
      </div>
    </div>

    <!-- 5. Traces View -->
    <div id="view-traces" class="view-panel">
      <div class="card">
        <div class="card-title">
          <span>OpenTelemetry Distributed Traces</span>
          <button class="btn-action" onclick="loadTraces()">Refresh Traces</button>
        </div>
        <table>
          <thead>
            <tr>
              <th>Trace ID</th>
              <th>Session</th>
              <th>Operation</th>
              <th>Total Duration</th>
              <th>Status</th>
              <th>Start Time</th>
            </tr>
          </thead>
          <tbody id="tracesTableBody">
            <tr><td colspan="6" style="color: var(--text-muted); text-align: center;">Click Refresh to load traces</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </main>

  <script>
    function switchTab(tabId) {
      document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
      document.querySelectorAll('.view-panel').forEach(panel => panel.classList.remove('active'));
      
      const targetBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick').includes(tabId));
      if (targetBtn) targetBtn.classList.add('active');
      
      const panel = document.getElementById(`view-${tabId}`);
      if (panel) panel.classList.add('active');

      if (tabId === 'actions') loadAuditTrail();
      if (tabId === 'memory') searchMemory();
      if (tabId === 'traces') loadTraces();
    }

    async function simulateTurn() {
      const feed = document.getElementById('liveTranscriptFeed');
      const userText = "What is 45 * 120 + 384?";
      
      feed.innerHTML += `<div class="feed-msg user"><strong>User:</strong> ${userText}</div>`;
      feed.scrollTop = feed.scrollHeight;

      try {
        const res = await fetch('/v1/supervisor/route', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            session_id: 'web-session-' + Date.now(),
            user_id: 'dashboard-user',
            text: userText
          })
        });
        const data = await res.json();
        const route = data.data.route;
        
        feed.innerHTML += `<div class="feed-msg event">[SUPERVISOR] Routed to '${route}' with confidence ${data.data.confidence}</div>`;
        
        // Execute tool if tool route
        if (route === 'tool') {
          const toolRes = await fetch('/v1/tools/execute', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
              tool_name: 'calculator',
              payload: {expression: '45 * 120 + 384'}
            })
          });
          const toolData = await toolRes.json();
          feed.innerHTML += `<div class="feed-msg assistant"><strong>Hina:</strong> Calculated result is ${toolData.data.result}.</div>`;
        } else {
          feed.innerHTML += `<div class="feed-msg assistant"><strong>Hina:</strong> Response generated.</div>`;
        }
        feed.scrollTop = feed.scrollHeight;
      } catch (err) {
        feed.innerHTML += `<div class="feed-msg event" style="color: var(--danger);">[ERROR] ${err.message}</div>`;
      }
    }

    async function searchMemory() {
      const query = document.getElementById('memorySearchInput').value || 'project';
      const tbody = document.getElementById('memoryTableBody');
      try {
        const res = await fetch('/v1/memory/query', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({query: query, top_k: 10, include_graph: true})
        });
        const json = await res.json();
        const items = json.data.items;
        if (!items || items.length === 0) {
          tbody.innerHTML = `<tr><td colspan="5" style="color: var(--text-muted); text-align: center;">No memories found matching '${query}'</td></tr>`;
          return;
        }
        tbody.innerHTML = items.map(it => `
          <tr>
            <td style="font-family: monospace;">${it.memory_id.substring(0, 8)}...</td>
            <td>${it.text}</td>
            <td><strong>${it.score}</strong></td>
            <td>${it.source_turn_id}</td>
            <td><button class="btn-action btn-danger" onclick="deleteMemory('${it.memory_id}')">Delete</button></td>
          </tr>
        `).join('');
      } catch(e) {
        tbody.innerHTML = `<tr><td colspan="5" style="color: var(--danger); text-align: center;">${e.message}</td></tr>`;
      }
    }

    async function deleteMemory(id) {
      if (!confirm('Are you sure you want to permanently delete this memory?')) return;
      await fetch(`/v1/memory/${id}`, {method: 'DELETE'});
      searchMemory();
    }

    async function loadAuditTrail() {
      const tbody = document.getElementById('actionsTableBody');
      try {
        const res = await fetch('/v1/device/audit');
        const json = await res.json();
        const records = json.data;
        if (!records || records.length === 0) {
          tbody.innerHTML = `<tr><td colspan="7" style="color: var(--text-muted); text-align: center;">No device action audits recorded yet.</td></tr>`;
          return;
        }
        tbody.innerHTML = records.map(r => {
          const riskClass = r.risk.toLowerCase() === 'high' ? 'badge-high' : r.risk.toLowerCase() === 'medium' ? 'badge-med' : 'badge-low';
          return `
            <tr>
              <td style="font-family: monospace;">${r.action_id.substring(0, 8)}...</td>
              <td style="font-family: monospace;">${r.device_id.substring(0, 8)}...</td>
              <td><strong>${r.intent_type}</strong></td>
              <td><span class="badge ${riskClass}">${r.risk}</span></td>
              <td>${r.confirmation}</td>
              <td style="color: ${r.result === 'success' ? 'var(--success)' : 'var(--danger)'}">${r.result}</td>
              <td style="color: var(--text-muted);">${r.requested_at.substring(11, 19)} UTC</td>
            </tr>
          `;
        }).join('');
      } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7" style="color: var(--danger); text-align: center;">${e.message}</td></tr>`;
      }
    }

    async function runSandboxCode() {
      const code = document.getElementById('sandboxCodeInput').value;
      const consoleEl = document.getElementById('sandboxOutputConsole');
      consoleEl.textContent = 'Executing in isolated microVM sandbox...';
      try {
        const res = await fetch('/v1/sandbox/execute', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({code: code, timeout_ms: 5000, network: 'disabled'})
        });
        const json = await res.json();
        const data = json.data;
        consoleEl.textContent = `Status: ${data.status} (exit code: ${data.exit_code}, ${data.execution_time_ms}ms)\\n\\n[STDOUT]\\n${data.stdout}\\n[STDERR]\\n${data.stderr}`;
      } catch (e) {
        consoleEl.textContent = `Error: ${e.message}`;
      }
    }

    async function loadTraces() {
      const tbody = document.getElementById('tracesTableBody');
      try {
        const res = await fetch('/v1/traces');
        const json = await res.json();
        const records = json.data;
        if (!records || records.length === 0) {
          tbody.innerHTML = `<tr><td colspan="6" style="color: var(--text-muted); text-align: center;">No traces recorded yet. Traces populate automatically during turns.</td></tr>`;
          return;
        }
        tbody.innerHTML = records.map(t => `
          <tr>
            <td style="font-family: monospace;">${t.trace_id.substring(0, 8)}...</td>
            <td style="font-family: monospace;">${t.session_id ? t.session_id.substring(0, 8) + '...' : '-'}</td>
            <td><strong>${t.operation}</strong></td>
            <td style="color: var(--accent-cyan); font-weight: 600;">${t.total_duration_ms} ms</td>
            <td>${t.status}</td>
            <td style="color: var(--text-muted);">${t.start_time.substring(11, 19)} UTC</td>
          </tr>
        `).join('');
      } catch (e) {
        tbody.innerHTML = `<tr><td colspan="6" style="color: var(--danger); text-align: center;">${e.message}</td></tr>`;
      }
    }
  </script>
</body>
</html>
"""
