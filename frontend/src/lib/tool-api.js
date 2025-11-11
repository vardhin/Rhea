/**
 * Tool Use Agent API Client
 * Handles communication with the frontend_proxy.py server
 */

const TOOL_PROXY_URL = 'http://localhost:8001';

/**
 * WebSocket-based question asking with streaming responses
 */
export async function askQuestionStreaming(question) {
    const ws = new WebSocket(`ws://localhost:8001/ws/ask`);
    
    return new Promise((resolve, reject) => {
        const messageQueue = [];
        let resolveIterator = null;
        let isDone = false;
        let isConnected = false;
        
        ws.onopen = () => {
            isConnected = true;
            ws.send(JSON.stringify({ question }));
        };
        
        ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                
                // Add to queue
                if (resolveIterator) {
                    resolveIterator({ value: message, done: false });
                    resolveIterator = null;
                } else {
                    messageQueue.push(message);
                }
                
                // Close on final or error
                if (message.type === 'final' || message.type === 'error' || message.type === 'timeout') {
                    isDone = true;
                    setTimeout(() => ws.close(), 100);
                }
            } catch (error) {
                console.error('Failed to parse WebSocket message:', error);
                reject(error);
            }
        };
        
        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            reject(new Error('WebSocket connection failed'));
        };
        
        ws.onclose = () => {
            isDone = true;
            if (resolveIterator) {
                resolveIterator({ value: undefined, done: true });
                resolveIterator = null;
            }
        };
        
        // Return async iterator
        const iterator = {
            [Symbol.asyncIterator]() {
                return this;
            },
            
            async next() {
                // Return queued messages first
                if (messageQueue.length > 0) {
                    return { value: messageQueue.shift(), done: false };
                }
                
                // If done, return done
                if (isDone) {
                    return { value: undefined, done: true };
                }
                
                // Wait for next message
                return new Promise((resolve) => {
                    resolveIterator = resolve;
                });
            },
            
            async return() {
                isDone = true;
                if (ws.readyState === WebSocket.OPEN) {
                    ws.close();
                }
                return { value: undefined, done: true };
            }
        };
        
        resolve(iterator);
    });
}

/**
 * REST API call for non-streaming question
 */
export async function askQuestion(question) {
    const response = await fetch(`${TOOL_PROXY_URL}/ask`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question })
    });
    
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
}

/**
 * Tool Store API Functions
 */

// List all tools
export async function listTools(params = {}) {
    const queryParams = new URLSearchParams({
        active_only: params.activeOnly ?? true,
        exclude_bugged: params.excludeBugged ?? true,
        ...(params.category && { category: params.category })
    });
    
    const response = await fetch(`${TOOL_PROXY_URL}/tools?${queryParams}`);
    if (!response.ok) throw new Error(`Failed to list tools: ${response.status}`);
    return await response.json();
}

// Get tool by ID
export async function getTool(toolId) {
    const response = await fetch(`${TOOL_PROXY_URL}/tools/${toolId}`);
    if (!response.ok) throw new Error(`Failed to get tool: ${response.status}`);
    return await response.json();
}

// Get tool by name
export async function getToolByName(toolName) {
    const response = await fetch(`${TOOL_PROXY_URL}/tools/name/${toolName}`);
    if (!response.ok) throw new Error(`Failed to get tool: ${response.status}`);
    return await response.json();
}

// Create new tool
export async function createTool(toolData) {
    const response = await fetch(`${TOOL_PROXY_URL}/tools`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(toolData)
    });
    
    if (!response.ok) throw new Error(`Failed to create tool: ${response.status}`);
    return await response.json();
}

// Update tool
export async function updateTool(toolId, updates) {
    const response = await fetch(`${TOOL_PROXY_URL}/tools/${toolId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(updates)
    });
    
    if (!response.ok) throw new Error(`Failed to update tool: ${response.status}`);
    return await response.json();
}

// Delete tool
export async function deleteTool(toolId) {
    const response = await fetch(`${TOOL_PROXY_URL}/tools/${toolId}`, {
        method: 'DELETE'
    });
    
    if (!response.ok) throw new Error(`Failed to delete tool: ${response.status}`);
    return await response.json();
}

// Execute tool by ID
export async function executeToolById(toolId, params = {}) {
    const response = await fetch(`${TOOL_PROXY_URL}/tools/${toolId}/execute`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ params })
    });
    
    if (!response.ok) throw new Error(`Failed to execute tool: ${response.status}`);
    return await response.json();
}

// Execute tool by name
export async function executeToolByName(toolName, params = {}) {
    const response = await fetch(`${TOOL_PROXY_URL}/tools/name/${toolName}/execute`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ params })
    });
    
    if (!response.ok) throw new Error(`Failed to execute tool: ${response.status}`);
    return await response.json();
}

// Search tools
export async function searchTools(query, params = {}) {
    const queryParams = new URLSearchParams({
        exclude_bugged: params.excludeBugged ?? true,
        limit: params.limit ?? 10,
        threshold: params.threshold ?? 0.3
    });
    
    const response = await fetch(`${TOOL_PROXY_URL}/tools/search/${encodeURIComponent(query)}?${queryParams}`);
    if (!response.ok) throw new Error(`Failed to search tools: ${response.status}`);
    return await response.json();
}

// List bugged tools
export async function listBuggedTools() {
    const response = await fetch(`${TOOL_PROXY_URL}/tools/bugged/list`);
    if (!response.ok) throw new Error(`Failed to list bugged tools: ${response.status}`);
    return await response.json();
}

// Clear bug status
export async function clearBugStatus(toolId) {
    const response = await fetch(`${TOOL_PROXY_URL}/tools/${toolId}/clear-bugs`, {
        method: 'POST'
    });
    
    if (!response.ok) throw new Error(`Failed to clear bug status: ${response.status}`);
    return await response.json();
}

// Deactivate tool
export async function deactivateTool(toolId) {
    const response = await fetch(`${TOOL_PROXY_URL}/tools/${toolId}/deactivate`, {
        method: 'POST'
    });
    
    if (!response.ok) throw new Error(`Failed to deactivate tool: ${response.status}`);
    return await response.json();
}

// Check server health
export async function checkHealth() {
    const response = await fetch(`${TOOL_PROXY_URL}/`);
    if (!response.ok) throw new Error(`Health check failed: ${response.status}`);
    return await response.json();
}

// Tool Agent Mode - streams thinking process
async function sendMessageToolAgent() {
    const userMessage = messageInput.trim();
    messageInput = '';
    
    // Ensure we have a current conversation
    let conversationId = $conversationStore.currentId;
    if (!conversationId) {
        conversationId = await conversationActions.createConversation();
    }
    
    // Add user message
    const userMessageObj = {
        id: Date.now().toString(),
        role: 'user',
        content: userMessage,
        timestamp: new Date().toISOString()
    };
    
    conversationActions.addMessage(conversationId, userMessageObj);
    
    isGenerating = true;
    conversationActions.setLoading(true);
    
    try {
        // Create assistant message placeholder
        const assistantMessage = {
            id: Date.now().toString() + '_assistant',
            role: 'assistant',
            content: '',
            toolAgentSteps: [],
            timestamp: new Date().toISOString()
        };
        
        conversationActions.addMessage(conversationId, assistantMessage);
        
        // Stream from tool agent
        const stream = await askQuestionStreaming(userMessage);
        currentStream = stream;
        
        let fullContent = '';
        let agentSteps = [];
        let currentStreamText = ''; // Accumulate stream chunks
        
        for await (const message of stream) {
            // Check if generation was stopped
            if (!currentStream) break;
            
            console.log('Tool Agent Message:', message.type, message.data);
            
            switch (message.type) {
                case 'start':
                    fullContent = '🔄 Starting...\n\n';
                    conversationActions.updateLastMessage(conversationId, fullContent);
                    break;
                    
                case 'iteration':
                    fullContent += `\n**Iteration ${message.data.number}**\n`;
                    conversationActions.updateLastMessage(conversationId, fullContent);
                    break;
                    
                case 'thinking':
                    fullContent += `🤔 ${message.data.message}\n`;
                    conversationActions.updateLastMessage(conversationId, fullContent);
                    break;
                
                case 'stream':
                    // Real-time character streaming from AI
                    currentStreamText += message.data.chunk;
                    // Update the message with streamed content
                    const streamContent = fullContent + '\n💭 AI Response:\n' + currentStreamText;
                    conversationActions.updateLastMessage(conversationId, streamContent);
                    break;
                
                case 'response_complete':
                    // Finalize the streamed response
                    fullContent += '\n💭 AI Response:\n' + currentStreamText;
                    currentStreamText = '';
                    conversationActions.updateLastMessage(conversationId, fullContent);
                    break;
                    
                case 'state':
                    fullContent += `\n📍 **State**: ${message.data.state}\n`;
                    fullContent += `💭 **Reasoning**: ${message.data.reasoning}\n`;
                    conversationActions.updateLastMessage(conversationId, fullContent);
                    
                    agentSteps.push({
                        type: 'state',
                        state: message.data.state,
                        reasoning: message.data.reasoning
                    });
                    break;
                    
                case 'action':
                    if (message.data.action) {
                        fullContent += `🎯 **Action**: ${JSON.stringify(message.data.action, null, 2)}\n`;
                        conversationActions.updateLastMessage(conversationId, fullContent);
                    }
                    break;
                    
                case 'result':
                    if (message.data.result) {
                        fullContent += `✅ **Result**: ${JSON.stringify(message.data.result, null, 2)}\n`;
                        conversationActions.updateLastMessage(conversationId, fullContent);
                    }
                    
                    agentSteps.push({
                        type: 'result',
                        state: message.data.state,
                        result: message.data.result
                    });
                    break;
                    
                case 'final':
                    fullContent = `\n\n---\n\n### 🎯 Final Answer\n\n${message.data.answer}\n\n`;
                    fullContent += `**Confidence**: ${message.data.confidence}\n`;
                    fullContent += `**Iterations**: ${message.data.iterations}\n`;
                    conversationActions.updateLastMessage(conversationId, fullContent);
                    break;
                    
                case 'timeout':
                    fullContent += `\n\n⏱️ ${message.data.message}\n`;
                    conversationActions.updateLastMessage(conversationId, fullContent);
                    break;
                    
                case 'error':
                    fullContent += `\n\n❌ Error: ${message.data.message}\n`;
                    conversationActions.updateLastMessage(conversationId, fullContent);
                    break;
            }
        }
        
        // Auto-generate title if this is the first exchange
        if (messages.length === 1) {
            const title = generateConversationTitle(userMessage, fullContent);
            conversationActions.updateConversationTitle(conversationId, title);
        }
        
    } catch (error) {
        console.error('Tool Agent error:', error);
        
        const errorContent = `❌ Error: ${error.message || 'Failed to get response from tool agent'}`;
        conversationActions.updateLastMessage(conversationId, errorContent);
        conversationActions.setError(error.message);
    } finally {
        isGenerating = false;
        conversationActions.setLoading(false);
        currentStream = null;
    }
}