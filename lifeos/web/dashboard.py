"""LifeOS Web Dashboard UI - Clean, minimalist operations interface."""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LifeOS</title>
    <style>
        :root {
            --bg-base: #090d16;
            --bg-surface: #111827;
            --bg-elevated: #1f2937;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --accent: #2563eb;
            --accent-hover: #1d4ed8;
            --success: #059669;
            --warning: #d97706;
            --danger: #dc2626;
            --border: #374151;
            --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-base);
            color: var(--text-main);
            font-family: var(--font-sans);
            line-height: 1.5;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }

        header {
            background: var(--bg-surface);
            border-bottom: 1px solid var(--border);
            padding: 0.85rem 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .brand {
            font-size: 1rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            color: var(--text-main);
            font-family: var(--font-mono);
        }

        .service-badges {
            display: flex;
            gap: 0.4rem;
        }

        .badge {
            font-size: 0.75rem;
            font-family: var(--font-mono);
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            background: var(--bg-elevated);
            color: var(--text-muted);
            border: 1px solid var(--border);
        }

        .badge.online {
            border-color: rgba(5, 150, 105, 0.5);
            color: #34d399;
        }

        main {
            flex: 1;
            max-width: 1200px;
            width: 100%;
            margin: 0 auto;
            padding: 1.5rem;
            display: grid;
            grid-template-columns: 1fr 320px;
            gap: 1.5rem;
        }

        @media (max-width: 860px) {
            main {
                grid-template-columns: 1fr;
            }
        }

        .card {
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 1.25rem;
            margin-bottom: 1.25rem;
        }

        .command-input-group {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 0.75rem;
        }

        .command-input {
            flex: 1;
            background: var(--bg-base);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 0.75rem 1rem;
            color: var(--text-main);
            font-size: 0.95rem;
            font-family: var(--font-sans);
            outline: none;
        }

        .command-input:focus {
            border-color: var(--accent);
        }

        .btn-primary {
            background: var(--accent);
            color: #fff;
            border: none;
            border-radius: 4px;
            padding: 0 1.25rem;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
        }

        .btn-primary:hover {
            background: var(--accent-hover);
        }

        .btn-primary:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .quick-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
        }

        .chip {
            background: var(--bg-elevated);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 0.25rem 0.6rem;
            font-size: 0.75rem;
            font-family: var(--font-mono);
            color: var(--text-muted);
            cursor: pointer;
        }

        .chip:hover {
            color: var(--text-main);
            border-color: var(--accent);
        }

        .pipeline-card {
            display: none;
        }

        .pipeline-card.active {
            display: block;
        }

        .agent-cluster {
            display: flex;
            justify-content: space-between;
            margin: 1rem 0;
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 0.75rem;
            background: var(--bg-base);
        }

        .agent-node {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0.25rem;
        }

        .agent-status-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--border);
        }

        .agent-node.working .agent-status-indicator {
            background: var(--accent);
        }

        .agent-node.completed .agent-status-indicator {
            background: var(--success);
        }

        .agent-label {
            font-size: 0.75rem;
            font-family: var(--font-mono);
            color: var(--text-muted);
        }

        .briefing-card {
            display: none;
        }

        .briefing-card.visible {
            display: block;
        }

        .briefing-title {
            font-size: 0.9rem;
            font-family: var(--font-mono);
            font-weight: 600;
            margin-bottom: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .briefing-content {
            white-space: pre-line;
            color: var(--text-main);
            font-size: 0.95rem;
            font-family: var(--font-sans);
            line-height: 1.6;
        }

        /* Modal */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 100;
        }

        .modal-overlay.open {
            display: flex;
        }

        .modal {
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 6px;
            width: 90%;
            max-width: 480px;
            padding: 1.5rem;
        }

        .modal-header {
            font-size: 1rem;
            font-weight: 600;
            color: var(--warning);
            margin-bottom: 0.75rem;
            font-family: var(--font-mono);
        }

        .action-list {
            background: var(--bg-base);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 0.5rem 0.75rem;
            margin: 0.75rem 0;
            max-height: 200px;
            overflow-y: auto;
            font-family: var(--font-mono);
            font-size: 0.8rem;
        }

        .action-item {
            padding: 0.35rem 0;
            border-bottom: 1px solid var(--border);
        }

        .action-item:last-child {
            border-bottom: none;
        }

        .modal-buttons {
            display: flex;
            justify-content: flex-end;
            gap: 0.5rem;
            margin-top: 1.25rem;
        }

        .btn-cancel {
            background: transparent;
            color: var(--text-muted);
            border: 1px solid var(--border);
            padding: 0.4rem 0.85rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.85rem;
        }

        .btn-confirm {
            background: var(--success);
            color: #fff;
            border: none;
            padding: 0.4rem 1rem;
            border-radius: 4px;
            font-weight: 600;
            cursor: pointer;
            font-size: 0.85rem;
        }

        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
            font-family: var(--font-mono);
            font-weight: 600;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
        }

        .task-list {
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
        }

        .task-item {
            background: var(--bg-base);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 0.6rem;
            display: flex;
            align-items: flex-start;
            gap: 0.5rem;
        }

        .task-checkbox {
            margin-top: 0.2rem;
            cursor: pointer;
        }

        .task-title {
            font-size: 0.85rem;
            color: var(--text-main);
        }

        .task-meta {
            font-size: 0.75rem;
            font-family: var(--font-mono);
            color: var(--text-muted);
            margin-top: 0.15rem;
        }
    </style>
</head>
<body>

    <header>
        <div class="brand">lifeos</div>
        <div style="display: flex; align-items: center; gap: 0.75rem;">
            <div class="service-badges">
                <span class="badge online">calendar</span>
                <span class="badge online">gmail</span>
                <span class="badge online">drive</span>
                <span class="badge online">slack</span>
                <span class="badge online">mongodb</span>
                <span class="badge online">ollama</span>
            </div>
            <div id="authContainer"></div>
        </div>
    </header>

    <main>
        <div>
            <div class="card">
                <form id="commandForm" onsubmit="handleCommandSubmit(event)">
                    <div class="command-input-group">
                        <input
                            type="text"
                            id="commandInput"
                            class="command-input"
                            placeholder="Instruction (e.g. 'Summarize my week')"
                            autocomplete="off"
                            required
                        />
                        <button type="submit" id="submitBtn" class="btn-primary">Execute</button>
                    </div>
                </form>
                <div class="quick-chips">
                    <span class="chip" onclick="setCommand('Summarize my week')">Summarize my week</span>
                    <span class="chip" onclick="setCommand('Create tasks from my unread emails')">Tasks from unread emails</span>
                    <span class="chip" onclick="setCommand('Block focus time tomorrow morning')">Block focus time</span>
                    <span class="chip" onclick="setCommand('Organize my drive project folder')">Organize drive folder</span>
                </div>
            </div>

            <div id="pipelineCard" class="card pipeline-card">
                <div class="briefing-title">A2A Protocol Dispatch</div>
                <div class="agent-cluster">
                    <div id="agent-orchestrator" class="agent-node">
                        <div class="agent-status-indicator"></div>
                        <span class="agent-label">orchestrator</span>
                    </div>
                    <div id="agent-calendar" class="agent-node">
                        <div class="agent-status-indicator"></div>
                        <span class="agent-label">calendar</span>
                    </div>
                    <div id="agent-email" class="agent-node">
                        <div class="agent-status-indicator"></div>
                        <span class="agent-label">email</span>
                    </div>
                    <div id="agent-file" class="agent-node">
                        <div class="agent-status-indicator"></div>
                        <span class="agent-label">file</span>
                    </div>
                    <div id="agent-task" class="agent-node">
                        <div class="agent-status-indicator"></div>
                        <span class="agent-label">task</span>
                    </div>
                    <div id="agent-notification" class="agent-node">
                        <div class="agent-status-indicator"></div>
                        <span class="agent-label">slack</span>
                    </div>
                </div>
                <p id="pipelineStatus" style="font-size: 0.8rem; font-family: var(--font-mono); color: var(--text-muted);"></p>
            </div>

            <div id="briefingCard" class="card briefing-card">
                <div class="briefing-title">Result</div>
                <div id="briefingContent" class="briefing-content"></div>
            </div>
        </div>

        <div>
            <div class="card">
                <div class="panel-header">
                    <span>Task Board</span>
                    <button onclick="loadTasks()" style="background: none; border: none; color: var(--text-muted); cursor: pointer; font-family: var(--font-mono); font-size: 0.8rem;">[refresh]</button>
                </div>
                <ul id="taskList" class="task-list">
                    <li style="color: var(--text-muted); font-size: 0.8rem;">Loading...</li>
                </ul>
            </div>
        </div>
    </main>

    <div id="confirmModal" class="modal-overlay">
        <div class="modal">
            <div class="modal-header">Confirmation Required</div>
            <p id="modalPrompt" style="font-size: 0.9rem; color: var(--text-main);"></p>
            <div id="actionList" class="action-list"></div>
            <div class="modal-buttons">
                <button onclick="respondConfirmation(false)" class="btn-cancel">Reject</button>
                <button onclick="respondConfirmation(true)" class="btn-confirm">Approve</button>
            </div>
        </div>
    </div>

    <script>
        let currentConfirmationId = null;

        function setCommand(text) {
            document.getElementById('commandInput').value = text;
            document.getElementById('commandInput').focus();
        }

        async function handleCommandSubmit(e) {
            e.preventDefault();
            const input = document.getElementById('commandInput');
            const btn = document.getElementById('submitBtn');
            const cmd = input.value.trim();
            if (!cmd) return;

            btn.disabled = true;
            document.getElementById('briefingCard').classList.remove('visible');
            const pipelineCard = document.getElementById('pipelineCard');
            pipelineCard.classList.add('active');
            
            resetAgentNodes();
            setAgentState('orchestrator', 'working');
            document.getElementById('pipelineStatus').innerText = 'Planning execution...';

            try {
                const resp = await fetch('/api/command', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command: cmd })
                });
                const data = await resp.json();

                if (data.status === 'confirmation_required') {
                    openConfirmationModal(data);
                    return;
                }

                setAgentState('orchestrator', 'completed');
                (data.agents_contacted || []).forEach(a => setAgentState(a, 'completed'));
                document.getElementById('pipelineStatus').innerText = `Completed in ${data.duration_ms || 0}ms.`;

                if (data.briefing) {
                    document.getElementById('briefingContent').innerText = data.briefing;
                    document.getElementById('briefingCard').classList.add('visible');
                }
                loadTasks();
            } catch (err) {
                document.getElementById('pipelineStatus').innerText = 'Error: ' + err.message;
            } finally {
                btn.disabled = false;
            }
        }

        function openConfirmationModal(data) {
            currentConfirmationId = data.confirmation_id;
            document.getElementById('modalPrompt').innerText = data.prompt;
            const actionList = document.getElementById('actionList');
            actionList.innerHTML = '';

            (data.pending_actions || []).forEach(act => {
                const item = document.createElement('div');
                item.className = 'action-item';
                item.innerText = `${act.action}: ${act.title || act.summary || act.folder_name || ''}`;
                actionList.appendChild(item);
            });

            document.getElementById('confirmModal').classList.add('open');
        }

        async function respondConfirmation(approved) {
            document.getElementById('confirmModal').classList.remove('open');
            if (!currentConfirmationId) return;

            document.getElementById('pipelineStatus').innerText = approved ? 'Executing approved writes...' : 'Action rejected.';
            try {
                const resp = await fetch('/api/confirm', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ confirmation_id: currentConfirmationId, approved: approved })
                });
                const res = await resp.json();
                document.getElementById('briefingContent').innerText = res.message || 'Done.';
                document.getElementById('briefingCard').classList.add('visible');
                loadTasks();
            } catch (err) {
                alert('Confirmation error: ' + err.message);
            }
        }

        function resetAgentNodes() {
            ['orchestrator', 'calendar', 'email', 'file', 'task', 'notification'].forEach(id => {
                const el = document.getElementById('agent-' + id);
                if (el) el.className = 'agent-node';
            });
        }

        function setAgentState(id, state) {
            const el = document.getElementById('agent-' + id);
            if (el) {
                el.className = 'agent-node ' + state;
            }
        }

        async function loadTasks() {
            const list = document.getElementById('taskList');
            try {
                const resp = await fetch('/api/tasks');
                const data = await resp.json();
                const tasks = data.tasks || [];

                if (tasks.length === 0) {
                    list.innerHTML = '<li style="color: var(--text-muted); font-size: 0.8rem;">No open tasks.</li>';
                    return;
                }

                list.innerHTML = '';
                tasks.forEach(t => {
                    const li = document.createElement('li');
                    li.className = 'task-item';
                    li.innerHTML = `
                        <input type="checkbox" class="task-checkbox" ${t.status === 'completed' ? 'checked' : ''} onchange="toggleTask('${t.task_id}')">
                        <div>
                            <div class="task-title" style="${t.status === 'completed' ? 'text-decoration: line-through; opacity: 0.5;' : ''}">${t.title}</div>
                            <div class="task-meta">${t.priority} ${t.due_date ? '• due ' + t.due_date : ''}</div>
                        </div>
                    `;
                    list.appendChild(li);
                });
            } catch (err) {
                list.innerHTML = '<li style="color: var(--danger); font-size: 0.8rem;">Error loading tasks.</li>';
            }
        }

        async function toggleTask(taskId) {
            await fetch(`/api/tasks/${taskId}/toggle`, { method: 'POST' });
            loadTasks();
        }

        async function initAuth() {
            try {
                const resp = await fetch('/api/auth/config');
                const cfg = await resp.json();
                const container = document.getElementById('authContainer');
                if (!container) return;

                if (cfg.clerk_configured && cfg.clerk_publishable_key) {
                    const script = document.createElement('script');
                    script.src = 'https://cdn.jsdelivr.net/npm/@clerk/clerk-js@latest/dist/clerk.browser.js';
                    script.async = true;
                    script.crossOrigin = 'anonymous';
                    script.onload = async () => {
                        const clerk = new window.Clerk(cfg.clerk_publishable_key);
                        await clerk.load();
                        if (clerk.user) {
                            clerk.mountUserButton(container);
                            fetch('/api/auth/clerk/sync-tokens', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ user_id: clerk.user.id, provider: 'oauth_google' })
                            }).catch(() => {});
                        } else {
                            const btn = document.createElement('button');
                            btn.className = 'btn-primary';
                            btn.style.padding = '0.2rem 0.6rem';
                            btn.style.fontSize = '0.75rem';
                            btn.innerText = 'Sign In';
                            btn.onclick = () => clerk.openSignIn();
                            container.appendChild(btn);
                        }
                    };
                    document.head.appendChild(script);
                } else {
                    container.innerHTML = '<span class="badge" style="color: var(--text-muted); font-size: 0.7rem;">Free Tier</span>';
                }
            } catch (err) {
                // Ignore in local offline mode
            }
        }

        window.onload = () => {
            loadTasks();
            initAuth();
        };
    </script>
</body>
</html>
"""
