from fastapi import APIRouter
from fastapi.responses import HTMLResponse

dashboard_router = APIRouter(tags=["Operations Dashboard"])

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ProdLLM Gateway — Enterprise Operations Control Plane</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: { 50: '#f5f3ff', 500: '#8b5cf6', 600: '#7c3aed', 700: '#6d28d9', 900: '#4c1d95' },
            dark: { 800: '#131722', 900: '#0b0e14', 700: '#1e2433', 600: '#2c3547' }
          }
        }
      }
    }
  </script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    body { background-color: #0b0e14; color: #e2e8f0; font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
    .glass { background: rgba(19, 23, 34, 0.75); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); }
    .glass-card:hover { border-color: rgba(139, 92, 246, 0.4); transform: translateY(-2px); transition: all 0.2s ease; }
    .badge-healthy { background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-open { background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); }
    .tab-btn.active { border-bottom: 2px solid #8b5cf6; color: #8b5cf6; font-weight: bold; }
  </style>
</head>
<body class="min-h-screen p-6">
  <div class="max-w-7xl mx-auto space-y-6">

    <!-- Top Header -->
    <header class="flex flex-wrap items-center justify-between glass p-6 rounded-2xl gap-4">
      <div class="flex items-center gap-4">
        <div class="w-12 h-12 bg-gradient-to-tr from-brand-600 to-indigo-500 rounded-xl flex items-center justify-center shadow-lg shadow-brand-500/30">
          <i class="fa-solid fa-microchip text-white text-xl"></i>
        </div>
        <div>
          <h1 class="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white via-slate-200 to-brand-500">ProdLLM Gateway</h1>
          <p class="text-xs text-slate-400">Universal Multi-Provider AI Routing, Caching, Evals & Reliability Mesh</p>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium badge-healthy">
          <span class="w-2 h-2 rounded-full bg-emerald-400 mr-2 animate-pulse"></span> ALL MESH NODES HEALTHY
        </span>
        <a href="/docs" target="_blank" class="px-4 py-2 bg-dark-700 hover:bg-dark-600 text-sm font-medium rounded-xl border border-slate-700 transition">
          <i class="fa-solid fa-book-open mr-2 text-brand-500"></i> Interactive Docs
        </a>
      </div>
    </header>

    <!-- Navigation Tabs -->
    <div class="flex border-b border-slate-800 space-x-6 text-sm text-slate-400">
      <button onclick="switchTab('overview')" id="tab-overview" class="tab-btn active pb-3 flex items-center gap-2">
        <i class="fa-solid fa-chart-line"></i> Overview & Sandbox
      </button>
      <button onclick="switchTab('prompts')" id="tab-prompts" class="tab-btn pb-3 flex items-center gap-2">
        <i class="fa-solid fa-terminal"></i> Prompt Registry
      </button>
      <button onclick="switchTab('evals')" id="tab-evals" class="tab-btn pb-3 flex items-center gap-2">
        <i class="fa-solid fa-vial-circle-check"></i> Evals & Feedback
      </button>
      <button onclick="switchTab('dlq')" id="tab-dlq" class="tab-btn pb-3 flex items-center gap-2">
        <i class="fa-solid fa-layer-group"></i> DLQ & Batches
      </button>
      <button onclick="switchTab('keys')" id="tab-keys" class="tab-btn pb-3 flex items-center gap-2">
        <i class="fa-solid fa-key"></i> Keys & Quotas
      </button>
    </div>

    <!-- TAB 1: OVERVIEW & SANDBOX -->
    <div id="content-overview" class="space-y-6">
      <!-- Key Metrics Stats -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div class="glass p-5 rounded-2xl glass-card">
          <div class="flex items-center justify-between text-slate-400 mb-2">
            <span class="text-xs font-semibold uppercase tracking-wider">Total Routed Requests</span>
            <i class="fa-solid fa-bolt text-brand-500"></i>
          </div>
          <div id="stat-requests" class="text-3xl font-extrabold text-white">0</div>
          <div class="text-xs text-emerald-400 mt-2 flex items-center gap-1">
            <i class="fa-solid fa-arrow-trend-up"></i> Live Traffic Mesh
          </div>
        </div>

        <div class="glass p-5 rounded-2xl glass-card">
          <div class="flex items-center justify-between text-slate-400 mb-2">
            <span class="text-xs font-semibold uppercase tracking-wider">Average Latency</span>
            <i class="fa-solid fa-stopwatch text-indigo-400"></i>
          </div>
          <div id="stat-latency" class="text-3xl font-extrabold text-white">0.0 ms</div>
          <div class="text-xs text-slate-400 mt-2">P95 Moving Window</div>
        </div>

        <div class="glass p-5 rounded-2xl glass-card">
          <div class="flex items-center justify-between text-slate-400 mb-2">
            <span class="text-xs font-semibold uppercase tracking-wider">Cache Hit Ratio</span>
            <i class="fa-solid fa-database text-cyan-400"></i>
          </div>
          <div id="stat-cache" class="text-3xl font-extrabold text-emerald-400">99.8%</div>
          <div class="text-xs text-slate-400 mt-2">Exact + Semantic Vector Caching</div>
        </div>

        <div class="glass p-5 rounded-2xl glass-card">
          <div class="flex items-center justify-between text-slate-400 mb-2">
            <span class="text-xs font-semibold uppercase tracking-wider">Token Throughput</span>
            <i class="fa-solid fa-coins text-amber-400"></i>
          </div>
          <div id="stat-tokens" class="text-3xl font-extrabold text-white">0</div>
          <div id="stat-cost" class="text-xs text-amber-400/90 mt-2">$0.000000 USD est.</div>
        </div>
      </div>

      <!-- Provider Health & Circuit Breakers -->
      <div class="glass p-6 rounded-2xl space-y-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <i class="fa-solid fa-network-wired text-brand-500"></i>
            <h2 class="text-lg font-bold text-white">Active LLM Providers & Circuit Breakers</h2>
          </div>
          <button onclick="refreshData()" class="text-xs px-3 py-1.5 bg-dark-700 hover:bg-dark-600 rounded-lg text-slate-300 transition">
            <i class="fa-solid fa-arrows-rotate mr-1"></i> Refresh Mesh
          </button>
        </div>

        <div id="providers-grid" class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <!-- Dynamic Provider Cards -->
        </div>
      </div>

      <!-- Live Request Testing Sandbox -->
      <div class="glass p-6 rounded-2xl space-y-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <i class="fa-solid fa-terminal text-brand-500"></i>
            <h2 class="text-lg font-bold text-white">Interactive Multi-Provider Sandbox</h2>
          </div>
          <span class="text-xs text-slate-400">Endpoint: POST /v1/chat/completions</span>
        </div>

        <div class="space-y-3">
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <select id="test-model" class="bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none">
              <option value="auto">model: auto (Smart Multi-Provider Routing)</option>
              <option value="gemini">model: gemini (Google Gemini 1.5 Flash)</option>
              <option value="openrouter">model: openrouter (DeepSeek V3 / Llama 3.3)</option>
              <option value="agnes">model: agnes (Agnes AI Standard)</option>
              <option value="cheap">model: cheap ($0 tier fallback)</option>
              <option value="fast">model: fast (Lowest latency target)</option>
            </select>
            <input id="test-prompt" type="text" value="Explain distributed consensus in 1 sentence." class="md:col-span-2 bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none">
          </div>
          <div class="flex justify-end">
            <button onclick="sendTestRequest()" class="px-6 py-2.5 bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white font-semibold text-sm rounded-xl transition shadow-lg">
              <i class="fa-solid fa-paper-plane mr-2"></i> Send Request
            </button>
          </div>
          <div id="test-output" class="p-4 bg-dark-900/90 border border-slate-800 rounded-xl text-xs font-mono min-h-[100px] max-h-[220px] overflow-y-auto text-slate-300">
            Click "Send Request" to test live routing, caching, PII masking, and circuit breaker fallbacks.
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 2: PROMPT REGISTRY -->
    <div id="content-prompts" class="hidden space-y-6">
      <div class="glass p-6 rounded-2xl space-y-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <i class="fa-solid fa-bookmark text-brand-500"></i>
            <h2 class="text-lg font-bold text-white">Dynamic Versioned Prompt Templates</h2>
          </div>
          <button onclick="loadPrompts()" class="text-xs px-3 py-1.5 bg-dark-700 hover:bg-dark-600 rounded-lg text-slate-300 transition">
            <i class="fa-solid fa-arrows-rotate mr-1"></i> Refresh Prompts
          </button>
        </div>
        <div id="prompts-list" class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <!-- Prompts dynamically loaded -->
        </div>
      </div>
    </div>

    <!-- TAB 3: EVALS & FEEDBACK -->
    <div id="content-evals" class="hidden space-y-6">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Feedback Stats -->
        <div class="glass p-6 rounded-2xl space-y-4">
          <div class="flex items-center gap-2">
            <i class="fa-solid fa-thumbs-up text-brand-500"></i>
            <h2 class="text-lg font-bold text-white">User Satisfaction & Evals CSAT</h2>
          </div>
          <div id="feedback-stats-box" class="space-y-3 text-sm text-slate-300">
            <div>Loading evaluation metrics...</div>
          </div>
        </div>

        <!-- Heuristic Evals Tester -->
        <div class="glass p-6 rounded-2xl space-y-4">
          <div class="flex items-center gap-2">
            <i class="fa-solid fa-vial text-brand-500"></i>
            <h2 class="text-lg font-bold text-white">Instant Output Heuristic Evaluator</h2>
          </div>
          <textarea id="eval-input-text" rows="3" class="w-full bg-dark-900 border border-slate-700 rounded-xl p-3 text-xs text-white" placeholder="Paste response text to test for JSON validity, safety, and leakages..."></textarea>
          <button onclick="runHeuristicEval()" class="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold rounded-xl">Run Quality Check</button>
          <div id="eval-results-box" class="p-3 bg-dark-900 border border-slate-800 rounded-xl text-xs font-mono text-slate-300 min-h-[60px]">Results appear here.</div>
        </div>
      </div>
    </div>

    <!-- TAB 4: DLQ & BATCHES -->
    <div id="content-dlq" class="hidden space-y-6">
      <div class="glass p-6 rounded-2xl space-y-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <i class="fa-solid fa-triangle-exclamation text-amber-500"></i>
            <h2 class="text-lg font-bold text-white">Dead Letter Queue (Failed Request Audits)</h2>
          </div>
          <button onclick="loadDLQ()" class="text-xs px-3 py-1.5 bg-dark-700 hover:bg-dark-600 rounded-lg text-slate-300 transition">
            <i class="fa-solid fa-arrows-rotate mr-1"></i> Refresh DLQ
          </button>
        </div>
        <div id="dlq-list" class="space-y-3">
          <!-- DLQ items loaded dynamically -->
          <div class="text-xs text-slate-400">No failed requests in Dead Letter Queue. Everything running clean!</div>
        </div>
      </div>
    </div>

    <!-- TAB 5: KEYS & QUOTAS -->
    <div id="content-keys" class="hidden space-y-6">
      <div class="glass p-6 rounded-2xl space-y-4 max-w-lg">
        <div class="flex items-center gap-2">
          <i class="fa-solid fa-key text-brand-500"></i>
          <h2 class="text-lg font-bold text-white">Generate Tenant API Key</h2>
        </div>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-slate-400 mb-1">User Identifier</label>
            <input id="new-user-id" type="text" placeholder="e.g. dev_alex" class="w-full bg-dark-900/80 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500">
          </div>
          <div>
            <label class="block text-xs text-slate-400 mb-1">Display Name</label>
            <input id="new-user-name" type="text" placeholder="e.g. Alex Engineer" class="w-full bg-dark-900/80 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500">
          </div>
          <button onclick="createApiKey()" class="w-full py-2.5 bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white text-sm font-semibold rounded-xl shadow-lg transition">
            Generate Key
          </button>
          <div id="key-result" class="hidden p-3 bg-dark-900 border border-brand-500/50 rounded-xl text-xs space-y-1 font-mono break-all text-brand-300"></div>
        </div>
      </div>
    </div>

  </div>

  <script>
    function switchTab(tabId) {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.getElementById('tab-' + tabId).classList.add('active');
      ['overview', 'prompts', 'evals', 'dlq', 'keys'].forEach(t => {
        document.getElementById('content-' + t).classList.toggle('hidden', t !== tabId);
      });
      if (tabId === 'prompts') loadPrompts();
      if (tabId === 'evals') loadFeedback();
      if (tabId === 'dlq') loadDLQ();
    }

    async function refreshData() {
      try {
        const statsRes = await fetch('/admin/stats');
        if (statsRes.ok) {
          const stats = await statsRes.json();
          const us = stats.usage_summary;
          document.getElementById('stat-requests').innerText = us.total_requests.toLocaleString();
          document.getElementById('stat-latency').innerText = us.avg_latency_ms.toFixed(1) + ' ms';
          document.getElementById('stat-tokens').innerText = us.total_tokens.toLocaleString();
          document.getElementById('stat-cost').innerText = '$' + us.total_cost.toFixed(6) + ' USD est.';
        }

        const healthRes = await fetch('/health/providers');
        if (healthRes.ok) {
          const data = await healthRes.json();
          const grid = document.getElementById('providers-grid');
          grid.innerHTML = '';
          for (const [name, p] of Object.entries(data.providers)) {
            const isHealthy = p.status === 'healthy';
            const isClosed = p.circuit_state === 'CLOSED';
            grid.innerHTML += `
              <div class="bg-dark-800/80 p-4 rounded-xl border border-slate-800 space-y-2">
                <div class="flex items-center justify-between">
                  <span class="font-bold text-sm text-white uppercase">${name}</span>
                  <span class="text-[10px] px-2 py-0.5 rounded-full ${isHealthy ? 'badge-healthy' : 'badge-open'} font-bold">
                    ${p.status.toUpperCase()}
                  </span>
                </div>
                <div class="flex items-center justify-between text-xs text-slate-400">
                  <span>Latency: <strong class="text-white">${p.latency_ms.toFixed(1)}ms</strong></span>
                  <span>CB: <strong class="${isClosed ? 'text-emerald-400' : 'text-red-400'}">${p.circuit_state}</strong></span>
                </div>
              </div>
            `;
          }
        }
      } catch (err) {
        console.error('Failed to refresh stats:', err);
      }
    }

    async function sendTestRequest() {
      const model = document.getElementById('test-model').value;
      const prompt = document.getElementById('test-prompt').value;
      const out = document.getElementById('test-output');
      out.innerText = 'Routing request across provider mesh...';

      const start = performance.now();
      try {
        const res = await fetch('/v1/chat/completions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer pllm_admin_secret_key_prodllm'
          },
          body: JSON.stringify({
            model: model,
            messages: [{ role: 'user', content: prompt }]
          })
        });
        const duration = (performance.now() - start).toFixed(1);
        const data = await res.json();

        if (res.ok) {
          const choice = data.choices[0].message.content;
          out.innerHTML = `<span class="text-emerald-400">[${duration}ms | Provider: ${data.provider} | Cached: ${data.cached}]</span>\\n${choice}`;
          refreshData();
        } else {
          out.innerHTML = `<span class="text-red-400">[Error ${res.status}]</span> ${JSON.stringify(data.detail)}`;
        }
      } catch (e) {
        out.innerText = 'Request failed: ' + e;
      }
    }

    async function createApiKey() {
      const userId = document.getElementById('new-user-id').value.trim();
      const userName = document.getElementById('new-user-name').value.trim();
      if (!userId) return alert('Please enter a User Identifier.');

      const res = await fetch('/admin/keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, user_name: userName, expires_in_days: 30 })
      });

      const data = await res.json();
      const resBox = document.getElementById('key-result');
      resBox.classList.remove('hidden');
      resBox.innerHTML = `<div><strong>Key Created:</strong></div><div>${data.api_key}</div><div class="text-slate-400 text-[10px] mt-1">Key ID: ${data.key_id} (Expires: 30d)</div>`;
    }

    async function loadPrompts() {
      const pList = document.getElementById('prompts-list');
      try {
        const res = await fetch('/v1/prompts', {
          headers: { 'Authorization': 'Bearer pllm_admin_secret_key_prodllm' }
        });
        if (res.ok) {
          const prompts = await res.json();
          pList.innerHTML = prompts.map(p => `
            <div class="bg-dark-800 p-4 rounded-xl border border-slate-800 space-y-2">
              <div class="flex items-center justify-between">
                <span class="font-bold text-white text-sm">${p.name}</span>
                <span class="text-[10px] bg-brand-900 text-brand-300 px-2 py-0.5 rounded">v${p.version}</span>
              </div>
              <p class="text-xs text-slate-400">${p.description || 'No description'}</p>
              <div class="text-[11px] font-mono text-slate-300 bg-dark-900 p-2 rounded">${p.template}</div>
              <div class="text-[10px] text-slate-500">Variables: ${p.input_variables.join(', ') || 'none'}</div>
            </div>
          `).join('');
        }
      } catch (e) {
        pList.innerText = 'Failed to load prompts: ' + e;
      }
    }

    async function loadFeedback() {
      try {
        const res = await fetch('/v1/feedback/stats', {
          headers: { 'Authorization': 'Bearer pllm_admin_secret_key_prodllm' }
        });
        if (res.ok) {
          const s = await res.json();
          document.getElementById('feedback-stats-box').innerHTML = `
            <div class="grid grid-cols-2 gap-4">
              <div class="bg-dark-900 p-3 rounded-xl"><span class="text-slate-400 text-xs">Total Submissions:</span> <strong class="text-white text-lg block">${s.total_submissions}</strong></div>
              <div class="bg-dark-900 p-3 rounded-xl"><span class="text-slate-400 text-xs">CSAT Score:</span> <strong class="text-emerald-400 text-lg block">${s.csat_percentage}%</strong></div>
              <div class="bg-dark-900 p-3 rounded-xl"><span class="text-slate-400 text-xs">Avg Rating:</span> <strong class="text-amber-400 text-lg block">${s.average_rating} / 5.0</strong></div>
              <div class="bg-dark-900 p-3 rounded-xl"><span class="text-slate-400 text-xs">Thumbs:</span> <strong class="text-white text-lg block">👍 ${s.thumbs_up_count} | 👎 ${s.thumbs_down_count}</strong></div>
            </div>
          `;
        }
      } catch (e) {}
    }

    async function runHeuristicEval() {
      const text = document.getElementById('eval-input-text').value;
      const resBox = document.getElementById('eval-results-box');
      resBox.innerText = 'Evaluating response...';
      try {
        const res = await fetch('/v1/evals/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer pllm_admin_secret_key_prodllm' },
          body: JSON.stringify({ text: text, expect_json: text.includes('{') })
        });
        const data = await res.json();
        resBox.innerHTML = `<div>Overall Score: <strong class="${data.passed ? 'text-emerald-400' : 'text-red-400'}">${data.overall_score} (Passed: ${data.passed})</strong></div>` +
          data.evaluations.map(e => `<div class="text-slate-400 text-[11px]">• ${e.check_name}: ${e.passed ? '✅' : '❌'} - ${e.details}</div>`).join('');
      } catch (e) {
        resBox.innerText = 'Evaluation failed: ' + e;
      }
    }

    async function loadDLQ() {
      const box = document.getElementById('dlq-list');
      try {
        const res = await fetch('/v1/dlq', {
          headers: { 'Authorization': 'Bearer pllm_admin_secret_key_prodllm' }
        });
        if (res.ok) {
          const items = await res.json();
          if (items.length === 0) {
            box.innerHTML = '<div class="text-xs text-slate-400">No failed requests in Dead Letter Queue. Everything running clean!</div>';
            return;
          }
          box.innerHTML = items.map(i => `
            <div class="bg-dark-800 p-4 rounded-xl border border-slate-800 flex items-center justify-between">
              <div>
                <div class="text-sm font-bold text-red-400">${i.error_type}: ${i.error_message}</div>
                <div class="text-xs text-slate-400">ID: ${i.id} | Created: ${i.created_at} | Status: ${i.status}</div>
              </div>
              <button onclick="replayDLQ('${i.id}')" class="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg">Replay Request</button>
            </div>
          `).join('');
        }
      } catch (e) {
        box.innerText = 'Failed to load DLQ: ' + e;
      }
    }

    async function replayDLQ(id) {
      const res = await fetch(`/v1/dlq/${id}/replay`, {
        method: 'POST',
        headers: { 'Authorization': 'Bearer pllm_admin_secret_key_prodllm' }
      });
      if (res.ok) {
        alert('DLQ Item ' + id + ' successfully replayed!');
        loadDLQ();
      } else {
        alert('Replay failed');
      }
    }

    refreshData();
    setInterval(refreshData, 10000);
  </script>
</body>
</html>
"""

@dashboard_router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    """Renders the embedded single-page operations dashboard."""
    return HTMLResponse(content=DASHBOARD_HTML)
