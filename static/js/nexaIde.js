// IDE State Management
let ideState = {
    files: {},
    openFiles: [],
    activeFile: null,
    fileTree: {},
    unsavedChanges: new Set()
};

// File type icons mapping
const fileIcons = {
    // Programming languages
    'py': '🐍', 'js': '📜', 'jsx': '⚛️', 'ts': '📘', 'tsx': '⚛️',
    'java': '☕', 'cpp': '⚙️', 'c': '⚙️', 'cs': '🔷', 'php': '🐘',
    'rb': '💎', 'go': '🐹', 'rs': '🦀', 'swift': '🐦',
    
    // Web technologies
    'html': '🌐', 'css': '🎨', 'scss': '🎨', 'sass': '🎨', 'less': '🎨',
    'vue': '💚', 'json': '📋', 'xml': '📄',
    
    // Configuration
    'yml': '⚙️', 'yaml': '⚙️', 'toml': '⚙️', 'ini': '⚙️', 'cfg': '⚙️',
    'env': '🔧', 'gitignore': '📝', 'dockerfile': '🐳',
    
    // Documents
    'md': '📖', 'txt': '📄', 'pdf': '📕', 'rst': '📚',
    
    // Images
    'png': '🖼️', 'jpg': '🖼️', 'jpeg': '🖼️', 'gif': '🖼️',
    'svg': '🖼️', 'ico': '🖼️', 'bmp': '🖼️',
    
    // Default
    'default': '📄'
};

// Language detection
const languageMap = {
    'py': 'python', 'js': 'javascript', 'jsx': 'javascript', 
    'ts': 'typescript', 'tsx': 'typescript', 'java': 'java',
    'cpp': 'cpp', 'c': 'cpp', 'cs': 'csharp', 'php': 'php',
    'rb': 'ruby', 'go': 'go', 'rs': 'rust', 'swift': 'swift',
    'html': 'html', 'css': 'css', 'scss': 'scss', 'sass': 'sass', 'less': 'less',
    'vue': 'vue', 'json': 'json', 'xml': 'xml', 'md': 'markdown',
    'yml': 'yaml', 'yaml': 'yaml', 'toml': 'toml', 'ini': 'ini',
    'dockerfile': 'docker'
};

// Initialize IDE when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Nexa IDE Initializing...');
    initializeIDE();
    setupEventListeners();
    
    // Try to load from session first, then from workspace
    const savedProject = sessionStorage.getItem('nexa_ide_project');
    if (savedProject) {
        try {
            const projectData = JSON.parse(savedProject);
            if (projectData.files && Object.keys(projectData.files).length > 0) {
                console.log('Loading from session storage...');
                loadProjectFromSession();
            } else {
                console.log('No files in session, loading workspace project...');
                setTimeout(loadWorkspaceProject, 1000);
            }
        } catch (error) {
            console.log('Error loading from session, loading workspace...');
            setTimeout(loadWorkspaceProject, 1000);
        }
    } else {
        console.log('No session data, loading workspace project...');
        setTimeout(loadWorkspaceProject, 1000);
    }
});

// Initialize IDE
function initializeIDE() {
    console.log('Initializing Nexa IDE...');
    updateFileExplorer();
    showEditorOverlay();
}

// Event Listeners for IDE
function setupEventListeners() {
    // Save file
    document.getElementById('save-file').addEventListener('click', saveCurrentFile);
    
    // New file
    document.getElementById('new-file').addEventListener('click', createNewFile);
    
    // New folder
    document.getElementById('new-folder').addEventListener('click', createNewFolder);
    
    // Refresh explorer
    document.getElementById('refresh-explorer').addEventListener('click', refreshFileExplorer);
    
    // Collapse all
    document.getElementById('collapse-all').addEventListener('click', collapseAllFolders);
    
    // Clear terminal
    document.getElementById('clear-terminal').addEventListener('click', clearTerminal);
    
    // Terminal input
    document.getElementById('terminal-input').addEventListener('keydown', handleTerminalInput);
    
    // Editor content changes
    document.getElementById('code-editor').addEventListener('input', handleEditorChange);
    
    // Load workspace project button
    document.getElementById('load-workspace-project').addEventListener('click', loadWorkspaceProject);
    
    // Create sample files (dynamic button)
    document.addEventListener('click', function(e) {
        if (e.target.id === 'create-sample-files') {
            createSampleFiles();
        }
    });
    
    // Keyboard shortcuts
    document.addEventListener('keydown', handleKeyboardShortcuts);
}

// Keyboard shortcuts
function handleKeyboardShortcuts(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        saveCurrentFile();
    }
    
    if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault();
        createNewFile();
    }
    
    if ((e.ctrlKey || e.metaKey) && e.altKey && e.key === 'n') {
        e.preventDefault();
        createNewFolder();
    }
    
    if ((e.ctrlKey || e.metaKey) && e.key === '`') {
        e.preventDefault();
        focusTerminal();
    }
}

// Focus terminal
function focusTerminal() {
    document.getElementById('terminal-input').focus();
}

// Load workspace project
async function loadWorkspaceProject() {
    try {
        addTerminalOutput('Loading workspace project...', 'command');
        
        const response = await fetch('/api/ide/load_workspace_project', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        console.log('LoadWorkspaceProject response:', data);

        if (response.ok) {
            addTerminalOutput(data.message, 'output');

            if (data.files && Object.keys(data.files).length > 0) {
                console.log('Populating files from backend...');
                
                // Clear existing files
                ideState.files = {};
                
                // Process each file from the backend response
                Object.entries(data.files).forEach(([filePath, fileData]) => {
                    console.log(`Processing file: ${filePath}`);
                    
                    // Ensure content is properly handled
                    let content = fileData.content || '';
                    
                    // Clean up the file path - remove any unwanted characters
                    const cleanFilePath = filePath.replace(/^\.\//, '').trim();
                    
                    ideState.files[cleanFilePath] = {
                        name: cleanFilePath.split('/').pop(),
                        path: cleanFilePath,
                        content: content,
                        language: detectLanguage(cleanFilePath),
                        lastModified: fileData.last_modified || new Date().toISOString()
                    };
                    
                    console.log(`Added file: ${cleanFilePath}`);
                });
                
                console.log('Files populated:', Object.keys(ideState.files));
                
                // Debug the file structure
                debugFileStructure();
                
                // Update UI
                updateFileExplorer();
                
                // Auto-open the first file
                const firstFile = Object.keys(ideState.files)[0];
                if (firstFile) {
                    setTimeout(() => {
                        openFile(firstFile);
                        addTerminalOutput(`Successfully loaded ${Object.keys(ideState.files).length} files. Opened: ${firstFile}`);
                    }, 500);
                }
                
                // Save to session storage
                saveProjectToSession();
                
            } else {
                console.log('No files in response');
                addTerminalOutput('No files found in workspace project.', 'warning');
                showSampleFilesOption();
            }
        } else {
            console.error('Load failed:', data);
            addTerminalOutput(`Error: ${data.error}`, 'error');
            showSampleFilesOption();
        }
    } catch (error) {
        console.error('Error loading workspace project:', error);
        addTerminalOutput(`Error loading workspace project: ${error.message}`, 'error');
        showSampleFilesOption();
    }
}

// Debug file structure
function debugFileStructure() {
    console.log('=== IDE STATE DEBUG ===');
    console.log('Files:', Object.keys(ideState.files));
    console.log('Open files:', ideState.openFiles);
    console.log('Active file:', ideState.activeFile);
    
    // Log each file's details
    Object.entries(ideState.files).forEach(([path, file]) => {
        console.log(`File: ${path}`, {
            name: file.name,
            contentLength: file.content.length,
            language: file.language
        });
    });
    console.log('=== END DEBUG ===');
}

// Add this function to show sample files option when no workspace project is found
function showSampleFilesOption() {
    const explorer = document.getElementById('file-explorer');
    explorer.innerHTML = `
        <div class="text-center text-gray-500 dark:text-gray-400 py-8">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-12 w-12 mx-auto mb-2 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
            <p class="text-sm mb-2">No workspace project found</p>
            <p class="text-xs mb-4">Create a project in the workspace first, then reload here.</p>
            <button id="create-sample-files" class="mt-2 px-3 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700 transition-colors">
                Create Sample Files
            </button>
            <button id="load-workspace-project" class="mt-2 px-3 py-1 bg-indigo-600 text-white rounded text-xs hover:bg-indigo-700 transition-colors ml-2">
                Reload Workspace Project
            </button>
        </div>
    `;
    
    // Re-attach event listeners for dynamic buttons
    const sampleBtn = document.getElementById('create-sample-files');
    const loadBtn = document.getElementById('load-workspace-project');
    if (sampleBtn) sampleBtn.addEventListener('click', createSampleFiles);
    if (loadBtn) loadBtn.addEventListener('click', loadWorkspaceProject);
}

function createNewFile() {
    const fileName = prompt('Enter file name (include extension):', 'newfile.py');
    if (!fileName) return;
    
    // Validate file name - allow slashes for nested files
    if (fileName.includes('..') || fileName.includes('~')) {
        alert('Please enter a valid file name without path traversal characters');
        return;
    }
    
    const filePath = fileName;
    
    // Check if file already exists
    if (ideState.files[filePath]) {
        if (!confirm(`File "${filePath}" already exists. Overwrite?`)) {
            return;
        }
    }
    
    ideState.files[filePath] = {
        name: fileName.split('/').pop(),
        path: filePath,
        content: getDefaultContent(fileName),
        language: detectLanguage(fileName),
        lastModified: new Date().toISOString()
    };
    
    updateFileExplorer();
    openFile(filePath);
    addTerminalOutput(`Created new file: ${filePath}`);
    
    // Save to session
    saveProjectToSession();
    
    // Save to server
    saveFileToServer(filePath, ideState.files[filePath].content);
}

function createNewFolder() {
    const folderName = prompt('Enter folder name:', 'new-folder');
    if (!folderName) return;
    
    // Validate folder name
    if (folderName.includes('..') || folderName.includes('~')) {
        alert('Please enter a valid folder name without path traversal characters');
        return;
    }
    
    // Create folder path (ensure it ends with /)
    const folderPath = folderName.endsWith('/') ? folderName : folderName + '/';
    
    // Check if folder already exists
    const existingFiles = Object.keys(ideState.files);
    const folderExists = existingFiles.some(file => file.startsWith(folderPath));
    
    if (folderExists) {
        alert(`Folder "${folderName}" already exists.`);
        return;
    }
    
    // Create a placeholder README file in the folder
    const readmePath = `${folderPath}README.md`;
    
    ideState.files[readmePath] = {
        name: 'README.md',
        path: readmePath,
        content: `# ${folderName}\n\nThis folder was created in Nexa IDE.\n\n## Description\n\nAdd your project files here.`,
        language: 'markdown',
        lastModified: new Date().toISOString()
    };
    
    updateFileExplorer();
    addTerminalOutput(`Created new folder: ${folderName}`);
    
    // Auto-expand the new folder
    setTimeout(() => {
        const folderElement = document.querySelector(`[data-path="${folderPath.replace(/\/$/, '')}"]`);
        if (folderElement) {
            folderElement.classList.remove('collapsed');
        }
    }, 100);
    
    // Save to session
    saveProjectToSession();
}

function getDefaultContent(filename) {
    const extension = filename.split('.').pop().toLowerCase();
    
    const templates = {
        'py': `#!/usr/bin/env python3
"""
${filename}
Created in Nexa IDE
"""

def main():
    print("Hello from ${filename}!")
    return "Hello, World!"

if __name__ == "__main__":
    main()`,

        'js': `// ${filename}
// Created in Nexa IDE

function main() {
    console.log("Hello from ${filename}!");
    return "Hello, World!";
}

// Execute main function
main();`,

        'html': `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${filename}</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 40px;
        }
    </style>
</head>
<body>
    <h1>Hello from ${filename}!</h1>
    <p>This file was created in Nexa IDE.</p>
</body>
</html>`,

        'css': `/* ${filename} */
/* Created in Nexa IDE */

body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 20px;
    background-color: #f5f5f5;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
}`,

        'md': `# ${filename}

This file was created in Nexa IDE.

## Features

- Edit code in the browser
- File management
- Terminal integration
- Syntax highlighting`
    };
    
    return templates[extension] || `// ${filename}\n// Created in Nexa IDE\n`;
}

function openFile(filePath) {
    if (!ideState.files[filePath]) {
        addTerminalOutput(`File not found: ${filePath}`, 'error');
        return;
    }
    
    // Add to open files if not already open
    if (!ideState.openFiles.includes(filePath)) {
        ideState.openFiles.push(filePath);
    }
    
    // Set as active file
    ideState.activeFile = filePath;
    
    // Update UI
    updateEditorTabs();
    loadFileContent(filePath);
    updateFileExplorer();
    hideEditorOverlay();
    
    // Update file info
    document.getElementById('current-file').textContent = filePath;
    document.getElementById('file-language').textContent = ideState.files[filePath].language || 'text';
    
    // Enable save button if there are unsaved changes
    document.getElementById('save-file').disabled = !ideState.unsavedChanges.has(filePath);
    
    addTerminalOutput(`Opened file: ${filePath}`);
}

function loadFileContent(filePath) {
    const file = ideState.files[filePath];
    const editor = document.getElementById('code-editor');
    
    if (file) {
        editor.value = file.content;
        editor.disabled = false;
        
        // Apply basic syntax highlighting
        applySyntaxHighlighting(editor, file.language);
    }
}

function saveCurrentFile() {
    if (!ideState.activeFile) {
        addTerminalOutput('No file is currently open', 'error');
        return;
    }
    
    const editor = document.getElementById('code-editor');
    const filePath = ideState.activeFile;
    
    ideState.files[filePath].content = editor.value;
    ideState.files[filePath].lastModified = new Date().toISOString();
    ideState.unsavedChanges.delete(filePath);
    
    // Update UI
    document.getElementById('save-file').disabled = true;
    updateEditorTabs();
    updateFileExplorer();
    
    // Show success message
    addTerminalOutput(`File "${filePath}" saved successfully.`);
    
    // Save to server
    saveFileToServer(filePath, editor.value);
    
    // Save to session
    saveProjectToSession();
}

function saveFileToServer(filePath, content) {
    fetch('/api/ide/save_file', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            file_path: filePath,
            content: content
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('File saved to server:', data);
    })
    .catch(error => {
        console.error('Error saving file to server:', error);
        addTerminalOutput('Error saving file to server', 'error');
    });
}

function closeFile(filePath) {
    if (ideState.unsavedChanges.has(filePath)) {
        if (!confirm(`You have unsaved changes in "${filePath}". Close anyway?`)) {
            return;
        }
    }
    
    // Remove from open files
    const index = ideState.openFiles.indexOf(filePath);
    if (index > -1) {
        ideState.openFiles.splice(index, 1);
    }
    
    // Clear active file if it's the one being closed
    if (ideState.activeFile === filePath) {
        ideState.activeFile = null;
        document.getElementById('code-editor').value = '';
        document.getElementById('code-editor').disabled = true;
        document.getElementById('current-file').textContent = 'No file selected';
        document.getElementById('file-language').textContent = '';
        showEditorOverlay();
    }
    
    updateEditorTabs();
    updateFileExplorer();
    addTerminalOutput(`Closed file: ${filePath}`);
    
    // Save to session
    saveProjectToSession();
}

// File Explorer
function updateFileExplorer() {
    const explorer = document.getElementById('file-explorer');
    
    if (Object.keys(ideState.files).length === 0) {
        showSampleFilesOption();
        return;
    }
    
    // Build file tree
    const tree = buildFileTree();
    explorer.innerHTML = renderFileTree(tree);
    console.log('Explorer updated with files:', Object.keys(ideState.files));
    
    // Add event listeners to file items
    document.querySelectorAll('.file-item').forEach(item => {
        // Remove existing listeners to avoid duplicates
        const newItem = item.cloneNode(true);
        item.parentNode.replaceChild(newItem, item);
        
        newItem.addEventListener('click', () => openFile(newItem.dataset.path));
        newItem.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            showFileContextMenu(e, newItem.dataset.path);
        });
    });
    
    // Add event listeners to folder items
    document.querySelectorAll('.folder-item').forEach(item => {
        const toggle = item.querySelector('.folder-toggle');
        if (toggle) {
            toggle.addEventListener('click', (e) => {
                e.stopPropagation();
                item.classList.toggle('collapsed');
            });
        }
        item.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            const folderPath = item.dataset.path || '';
            showFolderContextMenu(e, folderPath);
        });
    });
    
    // Re-attach sample files button listener if present
    const sampleBtn = document.getElementById('create-sample-files');
    const loadBtn = document.getElementById('load-workspace-project');
    if (sampleBtn) sampleBtn.addEventListener('click', createSampleFiles);
    if (loadBtn) loadBtn.addEventListener('click', loadWorkspaceProject);
}

function buildFileTree() {
    const tree = {};
    
    Object.keys(ideState.files).forEach(filePath => {
        // Handle both flat and nested paths
        const parts = filePath.split('/').filter(part => part.trim() !== '');
        let currentLevel = tree;
        
        for (let i = 0; i < parts.length; i++) {
            const part = parts[i];
            const isFile = i === parts.length - 1;
            
            if (!currentLevel[part]) {
                if (isFile) {
                    currentLevel[part] = { 
                        type: 'file', 
                        path: filePath,
                        unsaved: ideState.unsavedChanges.has(filePath)
                    };
                } else {
                    currentLevel[part] = { 
                        type: 'folder', 
                        children: {},
                        path: parts.slice(0, i + 1).join('/'),
                        expanded: true  // Auto-expand folders
                    };
                }
            }
            
            if (!isFile) {
                currentLevel = currentLevel[part].children;
            }
        }
    });
    
    return tree;
}

function renderFileTree(tree, level = 0, path = '') {
    let html = '';
    
    Object.keys(tree).sort((a, b) => {
        const aIsFolder = tree[a].type === 'folder';
        const bIsFolder = tree[b].type === 'folder';
        
        if (aIsFolder && !bIsFolder) return -1;
        if (!aIsFolder && bIsFolder) return 1;
        return a.localeCompare(b);
    }).forEach(key => {
        const item = tree[key];
        const fullPath = path ? `${path}/${key}` : key;
        
        if (item.type === 'folder') {
            const isActive = ideState.activeFile && ideState.activeFile.startsWith(fullPath + '/');
            const hasChildren = Object.keys(item.children).length > 0;
            const isExpanded = item.expanded !== false; // Default to expanded
            
            html += `
                <div class="folder-item ${isActive ? 'active' : ''} ${isExpanded ? '' : 'collapsed'}" data-path="${fullPath}">
                    <div class="file-item flex items-center py-1 px-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded cursor-pointer">
                        <span class="folder-toggle mr-1 transform transition-transform ${hasChildren ? '' : 'invisible'}">${isExpanded ? '▼' : '▶'}</span>
                        <span class="folder-icon mr-2">📁</span>
                        <span class="flex-1 truncate">${key}</span>
                    </div>
                    <div class="folder-children ml-4 ${isExpanded ? '' : 'hidden'}">
                        ${renderFileTree(item.children, level + 1, fullPath)}
                    </div>
                </div>
            `;
        } else {
            const isActive = ideState.activeFile === item.path;
            const isUnsaved = item.unsaved;
            const icon = getFileIcon(key);
            
            html += `
                <div class="file-item flex items-center py-1 px-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded cursor-pointer ${isActive ? 'active bg-blue-100 dark:bg-blue-900' : ''}" 
                     data-path="${item.path}">
                    <span class="file-icon mr-2">${icon}</span>
                    <span class="flex-1 truncate">${key}</span>
                    ${isUnsaved ? '<span class="text-orange-500 text-xs ml-2">●</span>' : ''}
                </div>
            `;
        }
    });
    
    return html;
}

function getFileIcon(filename) {
    const extension = filename.split('.').pop().toLowerCase();
    return fileIcons[extension] || fileIcons.default;
}

function detectLanguage(filename) {
    const extension = filename.split('.').pop().toLowerCase();
    return languageMap[extension] || 'text';
}

function showFileContextMenu(event, filePath) {
    // Simple context menu implementation
    const menu = document.createElement('div');
    menu.className = 'fixed bg-white dark:bg-gray-800 shadow-lg rounded border border-gray-200 dark:border-gray-700 z-50';
    menu.style.left = `${event.pageX}px`;
    menu.style.top = `${event.pageY}px`;
    
    menu.innerHTML = `
        <div class="py-1">
            <button class="context-menu-item w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-700" data-action="rename" data-file="${filePath}">Rename</button>
            <button class="context-menu-item w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-700" data-action="delete" data-file="${filePath}">Delete</button>
            <button class="context-menu-item w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-700" data-action="download" data-file="${filePath}">Download</button>
        </div>
    `;
    
    document.body.appendChild(menu);
    
    // Add event listeners to context menu items
    menu.querySelectorAll('.context-menu-item').forEach(item => {
        item.addEventListener('click', (e) => {
            const action = e.target.dataset.action;
            const file = e.target.dataset.file;
            handleFileContextAction(action, file);
            document.body.removeChild(menu);
        });
    });
    
    // Close menu when clicking elsewhere
    const closeMenu = (e) => {
        if (!menu.contains(e.target)) {
            document.body.removeChild(menu);
            document.removeEventListener('click', closeMenu);
        }
    };
    
    setTimeout(() => {
        document.addEventListener('click', closeMenu);
    }, 100);
}

function showFolderContextMenu(event, folderPath) {
    // Similar to file context menu but for folders
    console.log('Folder context menu:', folderPath);
}

function handleFileContextAction(action, filePath) {
    switch (action) {
        case 'rename':
            renameFile(filePath);
            break;
        case 'delete':
            deleteFile(filePath);
            break;
        case 'download':
            downloadFile(filePath);
            break;
    }
}

function renameFile(filePath) {
    const newName = prompt('Enter new file name:', ideState.files[filePath].name);
    if (!newName || newName === ideState.files[filePath].name) return;
    
    if (newName.includes('/') || newName.includes('\\') || newName.includes('..')) {
        alert('Invalid file name');
        return;
    }
    
    // Close file if it's open
    if (ideState.openFiles.includes(filePath)) {
        closeFile(filePath);
    }
    
    // Update file entry
    const newPath = newName;
    ideState.files[newPath] = {
        ...ideState.files[filePath],
        name: newName,
        path: newPath
    };
    
    delete ideState.files[filePath];
    
    updateFileExplorer();
    addTerminalOutput(`Renamed file: ${filePath} -> ${newPath}`);
    saveProjectToSession();
}

function deleteFile(filePath) {
    if (!confirm(`Are you sure you want to delete "${filePath}"?`)) {
        return;
    }
    
    // Close file if it's open
    if (ideState.openFiles.includes(filePath)) {
        closeFile(filePath);
    }
    
    // Remove from unsaved changes
    ideState.unsavedChanges.delete(filePath);
    
    // Delete file
    delete ideState.files[filePath];
    
    updateFileExplorer();
    addTerminalOutput(`Deleted file: ${filePath}`);
    saveProjectToSession();
}

function downloadFile(filePath) {
    const file = ideState.files[filePath];
    if (!file) return;
    
    const blob = new Blob([file.content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = file.name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    addTerminalOutput(`Downloaded file: ${filePath}`);
}

// Editor Tabs
function updateEditorTabs() {
    const tabsContainer = document.getElementById('editor-tabs');
    
    tabsContainer.innerHTML = ideState.openFiles.map(filePath => {
        const file = ideState.files[filePath];
        const isActive = ideState.activeFile === filePath;
        const isUnsaved = ideState.unsavedChanges.has(filePath);
        const icon = getFileIcon(file.name);
        
        return `
            <div class="editor-tab flex items-center px-3 py-2 border-r border-gray-200 dark:border-gray-700 cursor-pointer ${isActive ? 'active bg-white dark:bg-gray-800 border-b-2 border-blue-500' : 'bg-gray-100 dark:bg-gray-900'}" data-file="${filePath}">
                <span class="mr-2">${icon}</span>
                <span class="flex-1 truncate text-sm">${file.name}</span>
                ${isUnsaved ? '<span class="text-orange-500 text-xs ml-2">●</span>' : ''}
                <span class="editor-tab-close ml-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300" data-file="${filePath}">×</span>
            </div>
        `;
    }).join('');
    
    // Add event listeners to tabs
    document.querySelectorAll('.editor-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            if (e.target.classList.contains('editor-tab-close')) {
                closeFile(e.target.dataset.file);
            } else {
                openFile(tab.dataset.file);
            }
        });
    });
}

// Editor functionality
function handleEditorChange() {
    if (!ideState.activeFile) return;
    
    const filePath = ideState.activeFile;
    ideState.unsavedChanges.add(filePath);
    
    // Update UI
    document.getElementById('save-file').disabled = false;
    updateEditorTabs();
    updateFileExplorer();
}

function applySyntaxHighlighting(editor, language) {
    // Basic syntax highlighting would be implemented here
    // For a full implementation, you might want to use a library like Monaco Editor
    // or CodeMirror instead of a simple textarea
    console.log('Applying syntax highlighting for:', language);
}

function showEditorOverlay() {
    document.getElementById('editor-overlay').style.display = 'flex';
    document.getElementById('code-editor').style.display = 'none';
}

function hideEditorOverlay() {
    document.getElementById('editor-overlay').style.display = 'none';
    document.getElementById('code-editor').style.display = 'block';
}

// Terminal functionality
function handleTerminalInput(e) {
    if (e.key === 'Enter') {
        const input = e.target.value.trim();
        if (!input) return;
        
        addTerminalCommand(input);
        processTerminalCommand(input);
        e.target.value = '';
    }
}

function processTerminalCommand(command) {
    const args = command.split(' ');
    const cmd = args[0].toLowerCase();
    
    switch (cmd) {
        case 'ls':
        case 'dir':
            listFiles();
            break;
        case 'cat':
            if (args[1]) {
                showFileContent(args[1]);
            } else {
                addTerminalOutput('Usage: cat <filename>', 'error');
            }
            break;
        case 'cd':
            if (args[1]) {
                changeDirectory(args[1]);
            } else {
                addTerminalOutput('/workspace');
            }
            break;
        case 'pwd':
            addTerminalOutput('/workspace');
            break;
        case 'touch':
            if (args[1]) {
                createFileViaTerminal(args[1]);
            } else {
                addTerminalOutput('Usage: touch <filename>', 'error');
            }
            break;
        case 'mkdir':
            if (args[1]) {
                createFolderViaTerminal(args[1]);
            } else {
                addTerminalOutput('Usage: mkdir <foldername>', 'error');
            }
            break;
        case 'rm':
            if (args[1]) {
                deleteFileViaTerminal(args[1]);
            } else {
                addTerminalOutput('Usage: rm <filename>', 'error');
            }
            break;
        case 'clear':
            clearTerminal();
            break;
        case 'help':
            showTerminalHelp();
            break;
        case 'echo':
            addTerminalOutput(args.slice(1).join(' '));
            break;
        case 'date':
            addTerminalOutput(new Date().toString());
            break;
        case 'load-project':
            loadWorkspaceProject();
            break;
        case 'save-project':
            saveAllFiles();
            break;
        default:
            addTerminalOutput(`Command not found: ${cmd}`, 'error');
            addTerminalOutput('Type "help" for available commands', 'info');
    }
}

function saveAllFiles() {
    let savedCount = 0;
    
    Object.keys(ideState.files).forEach(filePath => {
        if (ideState.unsavedChanges.has(filePath)) {
            ideState.unsavedChanges.delete(filePath);
            saveFileToServer(filePath, ideState.files[filePath].content);
            savedCount++;
        }
    });
    
    updateEditorTabs();
    updateFileExplorer();
    addTerminalOutput(`Saved ${savedCount} files.`);
    saveProjectToSession();
}

function changeDirectory(dir) {
    addTerminalOutput(`cd: Directory navigation not implemented in web IDE. Current directory: /workspace`);
}

function createFileViaTerminal(filename) {
    if (!filename) return;
    
    if (ideState.files[filename]) {
        addTerminalOutput(`File "${filename}" already exists`, 'error');
        return;
    }
    
    ideState.files[filename] = {
        name: filename.split('/').pop(),
        path: filename,
        content: '',
        language: detectLanguage(filename),
        lastModified: new Date().toISOString()
    };
    
    updateFileExplorer();
    addTerminalOutput(`Created file: ${filename}`);
    saveProjectToSession();
}

function createFolderViaTerminal(folderName) {
    if (!folderName) return;
    
    const folderPath = folderName.endsWith('/') ? folderName : folderName + '/';
    
    if (Object.keys(ideState.files).some(file => file.startsWith(folderPath))) {
        addTerminalOutput(`Folder "${folderName}" already exists or contains files`, 'error');
        return;
    }
    
    const readmePath = `${folderPath}README.md`;
    ideState.files[readmePath] = {
        name: 'README.md',
        path: readmePath,
        content: `# ${folderName}\n\nFolder created via terminal.`,
        language: 'markdown',
        lastModified: new Date().toISOString()
    };
    
    updateFileExplorer();
    addTerminalOutput(`Created folder: ${folderName}`);
    saveProjectToSession();
}

function deleteFileViaTerminal(filename) {
    if (!ideState.files[filename]) {
        addTerminalOutput(`File not found: ${filename}`, 'error');
        return;
    }
    
    if (ideState.openFiles.includes(filename)) {
        closeFile(filename);
    }
    
    delete ideState.files[filename];
    ideState.unsavedChanges.delete(filename);
    
    updateFileExplorer();
    addTerminalOutput(`Deleted file: ${filename}`);
    saveProjectToSession();
}

function listFiles() {
    const files = Object.keys(ideState.files);
    if (files.length === 0) {
        addTerminalOutput('No files available');
    } else {
        files.forEach(file => {
            const fileInfo = ideState.files[file];
            const size = new Blob([fileInfo.content]).size;
            const date = new Date(fileInfo.lastModified).toLocaleDateString();
            addTerminalOutput(`${file.padEnd(30)} ${size.toString().padStart(8)} bytes  ${date}`);
        });
    }
}

function showTerminalHelp() {
    addTerminalOutput('Available commands:');
    addTerminalOutput('  ls, dir     - List files');
    addTerminalOutput('  cat <file>  - Show file content');
    addTerminalOutput('  touch <file>- Create new file');
    addTerminalOutput('  mkdir <dir> - Create new folder');
    addTerminalOutput('  rm <file>   - Delete file');
    addTerminalOutput('  clear       - Clear terminal');
    addTerminalOutput('  pwd         - Show current directory');
    addTerminalOutput('  echo <text> - Print text');
    addTerminalOutput('  date        - Show current date and time');
    addTerminalOutput('  load-project- Load workspace project');
    addTerminalOutput('  save-project- Save all files');
    addTerminalOutput('  help        - Show this help');
}

function showFileContent(filename) {
    const file = ideState.files[filename];
    if (file) {
        addTerminalOutput(`Content of ${filename}:`);
        addTerminalOutput('---');
        addTerminalOutput(file.content);
        addTerminalOutput('---');
    } else {
        addTerminalOutput(`File not found: ${filename}`, 'error');
    }
}

function addTerminalCommand(command) {
    const terminal = document.getElementById('terminal');
    const line = document.createElement('div');
    line.className = 'terminal-line terminal-command';
    line.textContent = `$ ${command}`;
    terminal.appendChild(line);
    terminal.scrollTop = terminal.scrollHeight;
}

function addTerminalOutput(output, type = 'output') {
    const terminal = document.getElementById('terminal');
    const line = document.createElement('div');
    line.className = `terminal-line terminal-${type}`;
    line.textContent = output;
    terminal.appendChild(line);
    terminal.scrollTop = terminal.scrollHeight;
}

function clearTerminal() {
    document.getElementById('terminal').innerHTML = `
        <div class="terminal-line">Terminal cleared</div>
        <div class="terminal-line">Nexa IDE Terminal - Ready</div>
    `;
}

// Utility functions
function refreshFileExplorer() {
    updateFileExplorer();
    addTerminalOutput('File explorer refreshed.');
}

function collapseAllFolders() {
    document.querySelectorAll('.folder-item').forEach(folder => {
        folder.classList.add('collapsed');
    });
    addTerminalOutput('All folders collapsed.');
}

// Sample files for demonstration
function createSampleFiles() {
    ideState.files = {
        'main.py': {
            name: 'main.py',
            path: 'main.py',
            content: `#!/usr/bin/env python3
"""
Main application file
Created in Nexa IDE
"""

import json
import math
from datetime import datetime

class Calculator:
    """A simple calculator class"""
    
    def __init__(self):
        self.history = []
    
    def add(self, a, b):
        result = a + b
        self.history.append(f"{a} + {b} = {result}")
        return result
    
    def multiply(self, a, b):
        result = a * b
        self.history.append(f"{a} * {b} = {result}")
        return result
    
    def get_history(self):
        return self.history

def main():
    """Main function"""
    print("Welcome to the Calculator App!")
    calc = Calculator()
    
    # Perform some calculations
    result1 = calc.add(10, 5)
    result2 = calc.multiply(4, 7)
    
    print(f"10 + 5 = {result1}")
    print(f"4 * 7 = {result2}")
    print("Calculation history:", calc.get_history())
    
    return {
        "timestamp": datetime.now().isoformat(),
        "results": [result1, result2]
    }

if __name__ == "__main__":
    main()`,
            language: 'python',
            lastModified: new Date().toISOString()
        },
        'app.js': {
            name: 'app.js',
            path: 'app.js',
            content: `// Main JavaScript application
// Created in Nexa IDE

class App {
    constructor(name) {
        this.name = name;
        this.version = '1.0.0';
        this.data = [];
    }

    initialize() {
        console.log(\`Initializing \${this.name} v\${this.version}\`);
        this.loadData();
        this.setupEventListeners();
        return this;
    }

    loadData() {
        // Simulate loading data
        this.data = [
            { id: 1, name: 'Item 1', value: 100 },
            { id: 2, name: 'Item 2', value: 200 },
            { id: 3, name: 'Item 3', value: 300 }
        ];
        console.log('Data loaded:', this.data);
    }

    setupEventListeners() {
        console.log('Event listeners setup complete');
    }

    render() {
        const output = \`
            <div class="app">
                <h1>Welcome to \${this.name}</h1>
                <div class="data-container">
                    \${this.data.map(item => \`
                        <div class="data-item" key="\${item.id}">
                            <span>\${item.name}</span>
                            <span>\${item.value}</span>
                        </div>
                    \`).join('')}
                </div>
            </div>
        \`;
        return output;
    }
}

// Create and initialize the app
const myApp = new App('Nexa IDE Demo');
myApp.initialize();

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = App;
}`,
            language: 'javascript',
            lastModified: new Date().toISOString()
        },
        'styles.css': {
            name: 'styles.css',
            path: 'styles.css',
            content: `/* Main stylesheet for Nexa IDE Demo */
/* Created in Nexa IDE */

:root {
    --primary-color: #3b82f6;
    --secondary-color: #1e40af;
    --background-color: #f8fafc;
    --text-color: #1f2937;
    --border-color: #e5e7eb;
}

.dark {
    --background-color: #0f172a;
    --text-color: #f1f5f9;
    --border-color: #374151;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background-color: var(--background-color);
    color: var(--text-color);
    line-height: 1.6;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

.header {
    background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
    color: white;
    padding: 2rem;
    border-radius: 12px;
    margin-bottom: 2rem;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.data-container {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
}

.data-item {
    background: white;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1rem;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    transition: transform 0.2s, box-shadow 0.2s;
}

.data-item:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.dark .data-item {
    background: #1e293b;
    border-color: #374151;
}

@media (max-width: 768px) {
    .container {
        padding: 10px;
    }
    
    .data-container {
        grid-template-columns: 1fr;
    }
}`,
            language: 'css',
            lastModified: new Date().toISOString()
        },
        'README.md': {
            name: 'README.md',
            path: 'README.md',
            content: `# Nexa IDE Demo Project

## Overview
This is a sample project demonstrating the capabilities of Nexa IDE.

## Project Structure

\`\`\`
project/
├── main.py          # Python application
├── app.js           # JavaScript application  
├── styles.css       # CSS stylesheet
└── README.md        # Project documentation
\`\`\`

## Features

- **Multi-language Support**: Python, JavaScript, CSS, Markdown
- **File Management**: Create, edit, rename, delete files
- **Syntax Highlighting**: Automatic language detection
- **Terminal Integration**: Built-in command line interface
- **Real-time Editing**: Instant feedback and auto-save

## Getting Started

1. Open files in the editor by clicking on them in the file explorer
2. Make changes to the code
3. Use the terminal for various commands:
   - \`ls\` - List all files
   - \`cat <filename>\` - View file content
   - \`clear\` - Clear terminal

## Keyboard Shortcuts

- \`Ctrl/Cmd + S\` - Save current file
- \`Ctrl/Cmd + N\` - Create new file
- \`Ctrl/Cmd + \\`\` - Focus terminal

## Technologies Used

- HTML5, CSS3, JavaScript
- Tailwind CSS for styling
- Prism.js for syntax highlighting
- Custom file system management

## License

MIT License - Feel free to use this project as a starting point for your own IDE implementations!`,
            language: 'markdown',
            lastModified: new Date().toISOString()
        }
    };
    
    updateFileExplorer();
    addTerminalOutput('Sample project created successfully!');
    addTerminalOutput('Try opening the files in the editor to see syntax highlighting.');
    saveProjectToSession();
}

// Load project from session storage
function loadProjectFromSession() {
    const savedProject = sessionStorage.getItem('nexa_ide_project');
    if (savedProject) {
        try {
            const projectData = JSON.parse(savedProject);
            ideState.files = projectData.files || {};
            ideState.openFiles = projectData.openFiles || [];
            ideState.activeFile = projectData.activeFile || null;
            
            updateFileExplorer();
            if (ideState.activeFile) {
                openFile(ideState.activeFile);
            }
            
            addTerminalOutput('Project loaded from session');
            console.log('Loaded from session:', Object.keys(ideState.files));
        } catch (error) {
            console.error('Error loading project from session:', error);
            addTerminalOutput('Error loading project from session', 'error');
        }
    }
}

// Save project to session storage
function saveProjectToSession() {
    const projectData = {
        files: ideState.files,
        openFiles: ideState.openFiles,
        activeFile: ideState.activeFile,
        timestamp: new Date().toISOString()
    };
    
    sessionStorage.setItem('nexa_ide_project', JSON.stringify(projectData));
    console.log('Project saved to session storage');
}

// Auto-save project every 30 seconds
setInterval(saveProjectToSession, 30000);

// Export functions for use in workspace
window.NexaIDE = {
    loadGeneratedFiles: function(codeFiles) {
        if (codeFiles && codeFiles.length) {
            // Clear existing files
            ideState.files = {};
            
            // Add generated files to IDE
            codeFiles.forEach(file => {
                if (file.file && file.code) {
                    const cleanFilename = file.file.replace(/['"`]/g, '').trim();
                    let cleanCode = file.code || '';
                    
                    // Remove code block markers if present
                    if (cleanCode.startsWith('```') && cleanCode.endsWith('```')) {
                        const firstNewline = cleanCode.indexOf('\n');
                        cleanCode = cleanCode.slice(firstNewline + 1, -3).trim();
                    }
                    
                    ideState.files[cleanFilename] = {
                        name: cleanFilename.split('/').pop(),
                        path: cleanFilename,
                        content: cleanCode,
                        language: detectLanguage(cleanFilename),
                        lastModified: new Date().toISOString()
                    };
                }
            });
            
            updateFileExplorer();
            addTerminalOutput(`Loaded ${codeFiles.length} generated files into IDE.`);
            
            // Open the first file
            const firstFile = Object.keys(ideState.files)[0];
            if (firstFile) {
                openFile(firstFile);
            }
            
            saveProjectToSession();
        }
    },
    
    getCurrentProject: function() {
        return {
            files: ideState.files,
            openFiles: ideState.openFiles,
            activeFile: ideState.activeFile
        };
    },
    
    // Test function for debugging
    testFileLoading: function() {
        // Manually add one file to test
        ideState.files['test.txt'] = {
            name: 'test.txt',
            path: 'test.txt', 
            content: 'This is a test file',
            language: 'text',
            lastModified: new Date().toISOString()
        };
        updateFileExplorer();
        console.log('Test file should be visible now');
    }
};

console.log('Nexa IDE initialized successfully!');