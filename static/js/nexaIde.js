// -------------------------------
// IDE State
// -------------------------------
let ideState = {
    files: {},
    openFiles: [],
    activeFile: null,
    unsavedChanges: new Set()
};

// -------------------------------
// Icons & Language Maps
// -------------------------------
const fileIcons = {
    py: '🐍', js: '📜', jsx: '⚛️', ts: '📘', tsx: '⚛️',
    java: '☕', cpp: '⚙️', c: '⚙️', cs: '🔷', php: '🐘',
    rb: '💎', go: '🐹', rs: '🦀',
    html: '🌐', css: '🎨', scss: '🎨',
    json: '📋', md: '📖',
    png: '🖼️', jpg: '🖼️', jpeg: '🖼️',
    default: '📄'
};

const languageMap = {
    py: 'python', js: 'javascript', jsx: 'javascript',
    ts: 'typescript', tsx: 'typescript',
    html: 'html', css: 'css',
    json: 'json', md: 'markdown'
};

// -------------------------------
// Init
// -------------------------------
document.addEventListener('DOMContentLoaded', async () => {
    setupEventListeners();

    if (!loadProjectFromSession()) {
        await loadWorkspaceProject();
    }

    updateFileExplorer();
    showEditorOverlay();
});

// -------------------------------
// Event Binding
// -------------------------------
function setupEventListeners() {
    document.getElementById('save-file').onclick = saveCurrentFile;
    document.getElementById('new-file').onclick = createNewFile;
    document.getElementById('refresh-explorer').onclick = reloadFiles;
    document.getElementById('clear-terminal').onclick = clearTerminal;

    document.getElementById('code-editor')
        .addEventListener('input', handleEditorChange);

    document.addEventListener('keydown', handleKeyboardShortcuts);
}

// -------------------------------
// Keyboard Shortcuts
// -------------------------------
function handleKeyboardShortcuts(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        saveCurrentFile();
    }
}

// -------------------------------
// Backend → Frontend Normalization
// -------------------------------
function normalizeServerFiles(serverFiles) {
    const normalized = {};

    Object.entries(serverFiles || {}).forEach(([path, data]) => {
        normalized[path] = {
            name: path.split('/').pop(),
            path,
            content: data.content || '',
            language: detectLanguage(path),
            lastModified: data.last_modified || new Date().toISOString()
        };
    });

    return normalized;
}

// -------------------------------
// File Loading
// -------------------------------
async function reloadFiles() {
    const res = await fetch('/api/ide/files');
    const data = await res.json();
    ideState.files = normalizeServerFiles(data.files);
    updateFileExplorer();
}

async function loadWorkspaceProject() {
    const res = await fetch('/api/ide/load_workspace_project', {
        method: 'POST'
    });
    const data = await res.json();

    if (data.files) {
        ideState.files = normalizeServerFiles(data.files);
        updateFileExplorer();

        const firstFile = Object.keys(ideState.files)[0];
        if (firstFile) openFile(firstFile);
    }
}

// -------------------------------
// File Operations
// -------------------------------
function openFile(filePath) {
    const file = ideState.files[filePath];
    if (!file) return;

    if (!ideState.openFiles.includes(filePath)) {
        ideState.openFiles.push(filePath);
    }

    ideState.activeFile = filePath;
    document.getElementById('code-editor').value = file.content;
    document.getElementById('code-editor').disabled = false;

    document.getElementById('current-file').textContent = filePath;
    document.getElementById('file-language').textContent = file.language;

    updateEditorTabs();
    hideEditorOverlay();
}

async function saveCurrentFile() {
    if (!ideState.activeFile) return;

    const content = document.getElementById('code-editor').value;

    await fetch('/api/ide/files', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            file_path: ideState.activeFile,
            content
        })
    });

    ideState.files[ideState.activeFile].content = content;
    ideState.unsavedChanges.delete(ideState.activeFile);

    updateEditorTabs();
    updateFileExplorer();
    addTerminalOutput(`Saved ${ideState.activeFile}`);
}

async function createNewFile() {
    const name = prompt('File name:');
    if (!name) return;

    await fetch('/api/ide/files', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            file_path: name,
            content: ''
        })
    });

    await reloadFiles();
    openFile(name);
}

async function deleteFile(filePath) {
    if (!confirm(`Delete ${filePath}?`)) return;

    await fetch('/api/ide/files', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: filePath })
    });

    ideState.unsavedChanges.delete(filePath);
    ideState.openFiles = ideState.openFiles.filter(f => f !== filePath);
    delete ideState.files[filePath];

    if (ideState.activeFile === filePath) {
        ideState.activeFile = null;
        showEditorOverlay();
    }

    updateEditorTabs();
    updateFileExplorer();
}

// -------------------------------
// Editor State
// -------------------------------
function handleEditorChange() {
    if (!ideState.activeFile) return;
    ideState.unsavedChanges.add(ideState.activeFile);
    updateEditorTabs();
}

// -------------------------------
// File Explorer
// -------------------------------
function updateFileExplorer() {
    const explorer = document.getElementById('file-explorer');
    explorer.innerHTML = renderFileTree(buildFileTree());
    bindExplorerEvents();
}

function buildFileTree() {
    const tree = {};
    Object.keys(ideState.files).forEach(path => {
        const parts = path.split('/');
        let cur = tree;
        parts.forEach((p, i) => {
            if (!cur[p]) {
                cur[p] = i === parts.length - 1
                    ? { type: 'file', path }
                    : { type: 'folder', children: {} };
            }
            cur = cur[p].children || {};
        });
    });
    return tree;
}

function renderFileTree(tree) {
    return Object.entries(tree).map(([k, v]) => {
        if (v.type === 'folder') {
            return `
                <div class="folder-item">
                    <div class="folder-header">📁 ${k}</div>
                    <div class="ml-4">${renderFileTree(v.children)}</div>
                </div>`;
        }
        return `
            <div class="file-item" data-path="${v.path}">
                ${getFileIcon(k)} ${k}
                ${ideState.unsavedChanges.has(v.path) ? '●' : ''}
            </div>`;
    }).join('');
}

function bindExplorerEvents() {
    document.querySelectorAll('.file-item').forEach(el => {
        el.onclick = () => openFile(el.dataset.path);
    });
}

// -------------------------------
// Tabs
// -------------------------------
function updateEditorTabs() {
    const tabs = document.getElementById('editor-tabs');
    tabs.innerHTML = ideState.openFiles.map(f => `
        <div class="editor-tab ${f === ideState.activeFile ? 'active' : ''}"
             data-file="${f}">
            ${getFileIcon(f)} ${ideState.files[f].name}
            ${ideState.unsavedChanges.has(f) ? '●' : ''}
            <span class="close">×</span>
        </div>
    `).join('');

    tabs.querySelectorAll('.editor-tab').forEach(tab => {
        tab.onclick = e => {
            if (e.target.classList.contains('close')) {
                ideState.openFiles = ideState.openFiles.filter(f => f !== tab.dataset.file);
                updateEditorTabs();
            } else {
                openFile(tab.dataset.file);
            }
        };
    });
}

// -------------------------------
// Terminal
// -------------------------------
function addTerminalOutput(msg) {
    const t = document.getElementById('terminal');
    const line = document.createElement('div');
    line.textContent = msg;
    t.appendChild(line);
    t.scrollTop = t.scrollHeight;
}

function clearTerminal() {
    document.getElementById('terminal').innerHTML = '';
}

// -------------------------------
// Utilities
// -------------------------------
function detectLanguage(name) {
    const ext = name.split('.').pop();
    return languageMap[ext] || 'text';
}

function getFileIcon(name) {
    const ext = name.split('.').pop();
    return fileIcons[ext] || fileIcons.default;
}

function showEditorOverlay() {
    document.getElementById('editor-overlay').style.display = 'flex';
    document.getElementById('code-editor').style.display = 'none';
}

function hideEditorOverlay() {
    document.getElementById('editor-overlay').style.display = 'none';
    document.getElementById('code-editor').style.display = 'block';
}

// -------------------------------
// Session Persistence
// -------------------------------
function saveProjectToSession() {
    sessionStorage.setItem('nexa_ide_project', JSON.stringify({
        files: ideState.files,
        openFiles: ideState.openFiles,
        activeFile: ideState.activeFile
    }));
}

function loadProjectFromSession() {
    const data = sessionStorage.getItem('nexa_ide_project');
    if (!data) return false;

    Object.assign(ideState, JSON.parse(data));
    updateFileExplorer();
    ideState.activeFile && openFile(ideState.activeFile);
    return true;
}

setInterval(saveProjectToSession, 30000);

console.log('Nexa IDE fully loaded');
