
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
document.addEventListener('DOMContentLoaded', () => {
    initializeIDE();
    setupEventListeners();
    loadProjectFromSession() || loadWorkspaceProject();
});

async function initializeIDE() {
    try {
        const serverFiles = await loadFilesFromServer();
        ideState.files = serverFiles || {};
    } catch (_) {}
    updateFileExplorer();
    showEditorOverlay();
}

// -------------------------------
// Event Binding
// -------------------------------
function setupEventListeners() {
    document.getElementById('save-file').onclick = saveCurrentFile;
    document.getElementById('new-file').onclick = createNewFile;
    document.getElementById('new-folder').onclick = createNewFolder;
    document.getElementById('refresh-explorer').onclick = updateFileExplorer;
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
    updateFileExplorer();
    hideEditorOverlay();
}

async function saveCurrentFile() {
    if (!ideState.activeFile) return;

    const content = document.getElementById('code-editor').value;
    await saveFileToServer(ideState.activeFile, content);

    ideState.files[ideState.activeFile].content = content;
    ideState.unsavedChanges.delete(ideState.activeFile);

    updateEditorTabs();
    updateFileExplorer();
    addTerminalOutput(`Saved ${ideState.activeFile}`);
}

// -------------------------------
// Server API
// -------------------------------
async function loadFilesFromServer() {
    const res = await fetch('/api/ide/files');
    const data = await res.json();
    return data.files || {};
}

async function saveFileToServer(filePath, content) {
    const res = await fetch('/api/ide/files', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: filePath, content })
    });
    if (!res.ok) throw new Error('Save failed');
}

async function createFileOnServer(filePath, content) {
    await fetch('/api/ide/files', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: filePath, content })
    });
}

async function deleteFileOnServer(filePath) {
    await fetch('/api/ide/files', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: filePath })
    });
}

// -------------------------------
// Create / Delete / Rename
// -------------------------------
async function createNewFile() {
    const name = prompt('File name:');
    if (!name) return;

    await createFileOnServer(name, '');
    ideState.files[name] = {
        name,
        path: name,
        content: '',
        language: detectLanguage(name),
        lastModified: new Date().toISOString()
    };

    updateFileExplorer();
    openFile(name);
}

async function deleteFile(filePath) {
    if (!confirm(`Delete ${filePath}?`)) return;

    await deleteFileOnServer(filePath);
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

function renameFile(oldPath) {
    const newName = prompt('New name:', ideState.files[oldPath].name);
    if (!newName) return;

    const folder = oldPath.includes('/') ? oldPath.split('/').slice(0, -1).join('/') + '/' : '';
    const newPath = folder + newName;

    ideState.files[newPath] = { ...ideState.files[oldPath], name: newName, path: newPath };
    delete ideState.files[oldPath];

    updateFileExplorer();
}

// -------------------------------
// Editor State
// -------------------------------
function handleEditorChange() {
    if (!ideState.activeFile) return;
    ideState.unsavedChanges.add(ideState.activeFile);
    updateEditorTabs();
    updateFileExplorer();
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
        el.oncontextmenu = e => {
            e.preventDefault();
            showFileContextMenu(e, el.dataset.path);
        };
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
                deleteFile(tab.dataset.file);
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

console.log('Nexa IDE loaded');
