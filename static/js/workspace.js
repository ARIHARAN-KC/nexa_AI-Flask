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
        
        // Update coder tab
        const codeHTML = Array.isArray(data.code) ? 
            data.code.map(file => `
                <div class="bg-white p-3 rounded-lg shadow mb-4">
                    <h4 class="font-medium">${file.file || 'Untitled'}</h4>
                    <pre class="bg-gray-100 p-2 rounded mt-2 overflow-x-auto text-sm">${file.code || 'No code generated'}</pre>
                </div>
            `).join('') : '';
        
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