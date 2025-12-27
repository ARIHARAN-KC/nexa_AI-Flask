document.addEventListener('DOMContentLoaded', function() {
    // Tab switching
    document.querySelectorAll('.tab-button').forEach(button => {
        button.addEventListener('click', () => {
            // Update active tab
            document.querySelectorAll('.tab-button').forEach(btn => {
                btn.classList.remove('border-blue-500', 'text-blue-600');
                btn.classList.add('text-gray-500');
            });
            button.classList.add('border-blue-500', 'text-blue-600');
            
            // Show selected tab content
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.add('hidden');
            });
            document.getElementById(button.dataset.tab).classList.remove('hidden');
        });
    });
    
    // Chat functionality
    const sendPrompt = async () => {
        const prompt = document.getElementById('user-prompt').value.trim();
        if (!prompt) return;
        
        // Add user message
        addMessage('user', prompt);
        document.getElementById('user-prompt').value = '';
        
        try {
            const response = await fetch('/api/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt })
            });
            
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            
            const data = await response.json();
            
            if (data.error) {
                addMessage('assistant', `Error: ${data.error}`);
                return;
            }
            
            if (data.type === 'conversation') {
                addMessage('assistant', data.content);
            } else if (data.type === 'project') {
                updateWorkspace(data);
                addMessage('assistant', 'Project completed! Check the workspace tabs.');
            }
        } catch (error) {
            addMessage('assistant', 'Sorry, something went wrong. Please try again.');
            console.error('Error:', error);
        }
    };
    
    document.getElementById('send-prompt').addEventListener('click', sendPrompt);
    document.getElementById('user-prompt').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendPrompt();
    });
    
    function addMessage(role, content) {
        const chatMessages = document.getElementById('chat-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'flex items-start';
        
        const avatar = role === 'user' ? 
            "/static/assets/robot.png" : 
            "/static/assets/Nexa.svg";
            
        messageDiv.innerHTML = `
            <img src="${avatar}" class="w-8 h-8 rounded-full mr-3" alt="${role}">
            <div class="bg-gray-100 p-3 rounded-lg">
                <p>${content}</p>
            </div>
        `;
        
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    function updateWorkspace(data) {
        // Update planner tab
        document.getElementById('planner').innerHTML = `
            <h3 class="font-semibold mb-2">Project: ${data.plan.project}</h3>
            <div class="bg-white p-4 rounded-lg shadow">
                <h4 class="font-medium mb-2">Plan:</h4>
                <pre class="whitespace-pre-wrap bg-gray-50 p-2 rounded">${JSON.stringify(data.plan.plans, null, 2)}</pre>
                <h4 class="font-medium mt-4 mb-2">Summary:</h4>
                <p class="bg-gray-50 p-2 rounded">${data.plan.summary}</p>
            </div>
        `;
        
        // Update browser tab
        const keywordsHTML = Array.isArray(data.keywords) ? 
            data.keywords.map(k => `<span class="bg-green-100 text-green-800 px-2 py-1 rounded">${k}</span>`).join('') :
            '';
        
        const researchHTML = data.queries_results && typeof data.queries_results === 'object' ? 
            Object.entries(data.queries_results).map(([query, result]) => `
                <div class="bg-white p-3 rounded-lg shadow mb-2">
                    <h4 class="font-medium">${query}</h4>
                    <p class="text-sm text-gray-600 mt-1">${result.link || 'No link'}</p>
                    <p class="mt-2 text-sm">${result.content ? result.content.substring(0, 200) + '...' : 'No content'}</p>
                </div>
            `).join('') : '';
        
        document.getElementById('browser').innerHTML = `
            <div class="mb-4">
                <h3 class="font-semibold mb-2">Keywords:</h3>
                <div class="flex flex-wrap gap-2">
                    ${keywordsHTML}
                </div>
            </div>
            <div>
                <h3 class="font-semibold mb-2">Research Results:</h3>
                <div class="space-y-2">
                    ${researchHTML}
                </div>
            </div>
        `;
        
         const codeHTML = Array.isArray(data.code) ? 
        data.code.map(file => {
            console.log('Code file:', file);
            return `
                <div class="bg-white p-3 rounded-lg shadow mb-4">
                    <h4 class="font-medium">${file.file || 'Untitled'}</h4>
                    <pre class="bg-gray-100 p-2 rounded mt-2 overflow-x-auto text-sm">${file.code || 'No code generated'}</pre>
                </div>
            `;
        }).join('') : '';
    
    document.getElementById('coder').innerHTML = codeHTML || `
        <div class="text-gray-500 italic">No code generated.</div>
    `;
        
        // Update project tab
        document.getElementById('project').innerHTML = `
            <div class="bg-white p-4 rounded-lg shadow">
                <h3 class="font-semibold mb-2">Project Created:</h3>
                <pre class="bg-gray-100 p-2 rounded overflow-x-auto text-sm">${data.project?.reply || 'No project output'}</pre>
            </div>
        `;
    }
});

// Workspace IDE integration
document.getElementById('load-to-ide')?.addEventListener('click', async function() {
    try {
        const response = await fetch('/api/ide/load_workspace_project', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Open IDE in new tab
            window.open("{{ url_for('ide') }}", '_blank');
            
            // Show success message
            const chatMessages = document.getElementById('chat-messages');
            const successMsg = document.createElement('div');
            successMsg.className = 'flex items-start gap-3 animate-fade-in';
            successMsg.innerHTML = `
                <div class="relative">
                    <img src="{{ url_for('static', filename='assets/Nexa.svg') }}" class="w-8 h-8 rounded-full flex-shrink-0" alt="Nexa">
                    <div class="absolute -bottom-1 -right-1 bg-green-500 rounded-full w-3 h-3 border-2 border-white dark:border-gray-800"></div>
                </div>
                <div class="bg-gradient-to-br from-green-100 to-green-50 dark:from-green-900/80 dark:to-green-900/60 p-4 rounded-2xl shadow-sm max-w-[85%] relative">
                    <div class="absolute -left-2 top-4 w-4 h-4 rotate-45 bg-green-100 dark:bg-green-900/80"></div>
                    <p class="text-gray-800 dark:text-white">Project loaded into IDE! Opening IDE now...</p>
                    <p class="mt-2 text-sm text-gray-600 dark:text-gray-300">${data.message}</p>
                    <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">${data.count} files loaded</p>
                </div>
            `;
            chatMessages.appendChild(successMsg);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        } else {
            throw new Error(data.error);
        }
    } catch (error) {
        console.error('Error loading project to IDE:', error);
        const chatMessages = document.getElementById('chat-messages');
        const errorMsg = document.createElement('div');
        errorMsg.className = 'flex items-start gap-3 animate-fade-in';
        errorMsg.innerHTML = `
            <div class="relative">
                <img src="{{ url_for('static', filename='assets/Nexa.svg') }}" class="w-8 h-8 rounded-full flex-shrink-0" alt="Nexa">
                <div class="absolute -bottom-1 -right-1 bg-green-500 rounded-full w-3 h-3 border-2 border-white dark:border-gray-800"></div>
            </div>
            <div class="bg-gradient-to-br from-red-100 to-red-50 dark:from-red-900/80 dark:to-red-900/60 p-4 rounded-2xl shadow-sm max-w-[85%] relative">
                <div class="absolute -left-2 top-4 w-4 h-4 rotate-45 bg-red-100 dark:bg-red-900/80"></div>
                <p class="text-gray-800 dark:text-white">Failed to load project into IDE</p>
                <p class="mt-2 text-sm text-gray-600 dark:text-gray-300">${error.message}</p>
            </div>
        `;
        chatMessages.appendChild(errorMsg);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
});

// Refresh IDE files
document.getElementById('refresh-ide-files')?.addEventListener('click', async function() {
    try {
        const response = await fetch('/api/ide/files');
        const data = await response.json();
        
        if (response.ok) {
            updateRecentFilesList(data.files);
            
            // Show success message
            const chatMessages = document.getElementById('chat-messages');
            const successMsg = document.createElement('div');
            successMsg.className = 'flex items-start gap-3 animate-fade-in';
            successMsg.innerHTML = `
                <div class="relative">
                    <img src="{{ url_for('static', filename='assets/Nexa.svg') }}" class="w-8 h-8 rounded-full flex-shrink-0" alt="Nexa">
                    <div class="absolute -bottom-1 -right-1 bg-green-500 rounded-full w-3 h-3 border-2 border-white dark:border-gray-800"></div>
                </div>
                <div class="bg-gradient-to-br from-blue-100 to-blue-50 dark:from-blue-900/80 dark:to-blue-900/60 p-4 rounded-2xl shadow-sm max-w-[85%] relative">
                    <div class="absolute -left-2 top-4 w-4 h-4 rotate-45 bg-blue-100 dark:bg-blue-900/80"></div>
                    <p class="text-gray-800 dark:text-white">IDE files refreshed</p>
                    <p class="mt-2 text-sm text-gray-600 dark:text-gray-300">${data.count} files available in IDE</p>
                </div>
            `;
            chatMessages.appendChild(successMsg);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        } else {
            throw new Error(data.error);
        }
    } catch (error) {
        console.error('Error refreshing IDE files:', error);
    }
});

function updateRecentFilesList(files) {
    const recentFilesList = document.getElementById('recent-files-list');
    
    if (!files || Object.keys(files).length === 0) {
        recentFilesList.innerHTML = '<p class="text-gray-500 dark:text-gray-400 text-sm">No files in IDE</p>';
        return;
    }
    
    const fileList = Object.keys(files).slice(0, 5).map(filePath => {
        const fileName = filePath.split('/').pop();
        return `
            <div class="flex items-center justify-between py-2 border-b border-gray-200 dark:border-gray-700 last:border-b-0">
                <div class="flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-gray-400 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span class="text-sm text-gray-700 dark:text-gray-300 truncate">${fileName}</span>
                </div>
                <span class="text-xs text-gray-500 dark:text-gray-400">${files[filePath].last_modified ? new Date(files[filePath].last_modified).toLocaleDateString() : ''}</span>
            </div>
        `;
    }).join('');
    
    recentFilesList.innerHTML = fileList;
}

// Load recent files on page load
document.addEventListener('DOMContentLoaded', function() {
    // Load recent files after a short delay
    setTimeout(() => {
        fetch('/api/ide/files')
            .then(response => response.json())
            .then(data => {
                if (data.files) {
                    updateRecentFilesList(data.files);
                }
            })
            .catch(error => {
                console.error('Error loading recent files:', error);
            });
    }, 1000);
});