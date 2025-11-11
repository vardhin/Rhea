<script>
    import { onMount } from 'svelte';
    import { MessageCircle, Send, Plus, Square, Sparkles, Search, Loader, CheckCircle, AlertCircle, Clock, Zap } from 'lucide-svelte';
    import { conversationStore, conversationActions } from '$lib/stores/store.js';
    import { askQuestionStreaming } from '$lib/tool-api.js';
    import './chatwindow.css';
    
    let { sidebarExpanded, currentView } = $props();
    
    let messageInput = $state('');
    let isGenerating = $state(false);
    let showToolsMenu = $state(false);
    let messagesContainer;
    let currentStream = null;
    let textarea; // Add ref for textarea
    
    // Get current conversation using $derived
    const currentConversation = $derived(
        $conversationStore.conversations.find(
            conv => conv.id === $conversationStore.currentId
        )
    );
    
    const messages = $derived(currentConversation?.messages || []);
    
    onMount(() => {
        scrollToBottom();
    });
    
    function scrollToBottom() {
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }
    
    // Auto-resize textarea - watch messageInput changes
    $effect(() => {
        // This will trigger whenever messageInput changes
        messageInput;
        if (textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
        }
    });
    
    $effect(() => {
        if (messages.length > 0) {
            setTimeout(scrollToBottom, 50);
        }
    });

    async function sendMessage() {
        if (!messageInput.trim() || isGenerating) return;
        await sendMessageToolAgent();
        // Reset height after sending
        if (textarea) {
            textarea.style.height = 'auto';
        }
    }

    // Improved parse function to handle the actual format
    function parseMessageContent(content) {
        if (!content) return { sections: [] };
        
        const sections = [];
        const lines = content.split('\n');
        let currentSection = null;
        let i = 0;
        
        while (i < lines.length) {
            const line = lines[i];
            
            // Start marker
            if (line.includes('🔄 Starting...')) {
                if (currentSection) sections.push(currentSection);
                currentSection = { type: 'start', content: line };
                i++;
                continue;
            }
            
            // Iteration marker
            if (line.match(/\*\*Iteration \d+\*\*/)) {
                if (currentSection) sections.push(currentSection);
                const iterNum = line.match(/\d+/)?.[0] || '1';
                currentSection = { type: 'iteration', number: iterNum, steps: [] };
                i++;
                continue;
            }
            
            // Thinking marker (before state)
            if (line.includes('🤔 Consulting AI...') || line.includes('🤔')) {
                i++;
                continue;
            }
            
            // State marker - start of a new step
            if (line.includes('📍 **State**:')) {
                const state = line.split('📍 **State**:')[1]?.trim() || '';
                
                // Look ahead for reasoning, action, and result
                let reasoning = '';
                let action = '';
                let result = '';
                
                // Get reasoning (next line)
                i++;
                if (i < lines.length && lines[i].includes('💭 **Reasoning**:')) {
                    reasoning = lines[i].split('💭 **Reasoning**:')[1]?.trim() || '';
                    i++;
                }
                
                // Get action (if present)
                if (i < lines.length && lines[i].includes('🎯 **Action**:')) {
                    const actionStart = i;
                    i++;
                    let actionLines = [];
                    
                    // Collect action JSON lines until we hit Result or next section
                    while (i < lines.length && 
                           !lines[i].includes('✅ **Result**:') && 
                           !lines[i].includes('📍 **State**:') &&
                           !lines[i].includes('**Iteration') &&
                           !lines[i].includes('### 🎯 Final Answer')) {
                        actionLines.push(lines[i]);
                        i++;
                    }
                    action = actionLines.join('\n').trim();
                }
                
                // Get result (if present)
                if (i < lines.length && lines[i].includes('✅ **Result**:')) {
                    i++;
                    let resultLines = [];
                    
                    // Collect result JSON lines until we hit next section
                    while (i < lines.length && 
                           !lines[i].includes('📍 **State**:') &&
                           !lines[i].includes('**Iteration') &&
                           !lines[i].includes('### 🎯 Final Answer') &&
                           !lines[i].includes('🤔')) {
                        if (lines[i].trim()) {
                            resultLines.push(lines[i]);
                        }
                        i++;
                    }
                    result = resultLines.join('\n').trim();
                }
                
                // Add step to current iteration
                if (currentSection && currentSection.type === 'iteration') {
                    currentSection.steps.push({
                        state,
                        reasoning,
                        action,
                        result
                    });
                }
                continue;
            }
            
            // Final answer section
            if (line.includes('### 🎯 Final Answer')) {
                if (currentSection) sections.push(currentSection);
                i++;
                
                let finalContent = '';
                let confidence = '';
                let iterations = '';
                
                // Skip empty line and separator
                while (i < lines.length && (lines[i].trim() === '' || lines[i].includes('---'))) {
                    i++;
                }
                
                // Collect final answer content until we hit Confidence
                let contentLines = [];
                while (i < lines.length && !lines[i].includes('**Confidence**:')) {
                    if (lines[i].trim()) {
                        contentLines.push(lines[i]);
                    }
                    i++;
                }
                finalContent = contentLines.join('\n').trim();
                
                // Get confidence
                if (i < lines.length && lines[i].includes('**Confidence**:')) {
                    confidence = lines[i].split('**Confidence**:')[1]?.trim() || '';
                    i++;
                }
                
                // Get iterations
                if (i < lines.length && lines[i].includes('**Iterations**:')) {
                    iterations = lines[i].split('**Iterations**:')[1]?.trim() || '';
                    i++;
                }
                
                currentSection = {
                    type: 'final',
                    content: finalContent,
                    confidence,
                    iterations
                };
                continue;
            }
            
            i++;
        }
        
        // Push final section
        if (currentSection) {
            sections.push(currentSection);
        }
        
        return { sections };
    }

    // Tool Agent Mode - streams thinking process
    async function sendMessageToolAgent() {
        const userMessage = messageInput.trim();
        messageInput = '';
        
        let conversationId = $conversationStore.currentId;
        if (!conversationId) {
            conversationId = await conversationActions.create();
        }
        
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
            const assistantMessage = {
                id: Date.now().toString() + '_assistant',
                role: 'assistant',
                content: '',
                timestamp: new Date().toISOString()
            };
            
            conversationActions.addMessage(conversationId, assistantMessage);
            
            const stream = await askQuestionStreaming(userMessage);
            currentStream = stream;
            let fullContent = '';
            
            for await (const message of stream) {
                if (!currentStream) break;
                
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
                        
                    case 'state':
                        fullContent += `\n📍 **State**: ${message.data.state}\n`;
                        fullContent += `💭 **Reasoning**: ${message.data.reasoning}\n`;
                        conversationActions.updateLastMessage(conversationId, fullContent);
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
                        break;
                        
                    case 'final':
                        fullContent += `\n\n---\n\n### 🎯 Final Answer\n\n${message.data.answer}\n\n`;
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
            
            if (messages.length === 1) {
                const title = generateConversationTitle(userMessage, fullContent);
                conversationActions.updateConversationTitle(conversationId, title);
            }
            
        } catch (error) {
            console.error('Tool Agent error:', error);
            const errorContent = `❌ Error: ${error.message || 'Failed to get response from tool agent'}`;
            conversationActions.updateLastMessage(conversationId, errorContent);
            conversationActions.setError(error);
        } finally {
            isGenerating = false;
            conversationActions.setLoading(false);
            currentStream = null;
        }
    }
    
    function generateConversationTitle(userMessage, assistantResponse) {
        const words = userMessage.split(' ').slice(0, 6);
        let title = words.join(' ');
        if (words.length === 6) title += '...';
        return title.length > 50 ? title.substring(0, 47) + '...' : title;
    }
    
    function handleKeydown(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    }
    
    function toggleToolsMenu() {
        showToolsMenu = !showToolsMenu;
    }
    
    async function handleToolAction(action) {
        showToolsMenu = false;
        
        switch (action) {
            case 'refresh':
                await refreshChat();
                break;
        }
    }
    
    async function refreshChat() {
        if (currentStream) {
            currentStream = null;
        }
        
        isGenerating = false;
        conversationActions.setLoading(false);
        await conversationActions.create();
    }
    
    function handleClickOutside(event) {
        if (showToolsMenu && !event.target.closest('.tools-menu-container')) {
            showToolsMenu = false;
        }
    }
    
    function formatTimestamp(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        return date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    }
    
    async function stopGeneration() {
        if (currentStream) {
            currentStream = null;
        }
        
        isGenerating = false;
        conversationActions.setLoading(false);
        
        if ($conversationStore.currentId) {
            const currentContent = messages[messages.length - 1]?.content || '';
            const stoppedMessage = currentContent + '\n\n[Generation stopped by user]';
            conversationActions.updateLastMessage($conversationStore.currentId, stoppedMessage);
        }
    }

    function formatJson(jsonStr) {
        try {
            const obj = JSON.parse(jsonStr);
            return JSON.stringify(obj, null, 2);
        } catch {
            return jsonStr;
        }
    }
</script>

<svelte:window on:click={handleClickOutside} />

<main class="chat-window" class:sidebar-expanded={sidebarExpanded}>
    <div class="messages-container" bind:this={messagesContainer}>
        <div class="messages">
            {#if messages.length === 0}
                <div class="welcome-message">
                    <div class="welcome-icon">
                        <Sparkles size={48} />
                    </div>
                    <h2>Welcome to Rhea AI Chat</h2>
                    <div class="mode-badge">
                        <Zap size={16} />
                        Tool Agent Mode (Gemini)
                    </div>
                    <p>The agent will automatically create and use tools to answer your questions.</p>
                    <p class="welcome-hint">Start a conversation by typing a message below.</p>
                </div>
            {:else}
                {#each messages as message}
                    {@const parsed = parseMessageContent(message.content)}
                    <div class="message {message.role}" class:generating={message === messages[messages.length - 1] && isGenerating}>
                        {#if message.role === 'user'}
                            <div class="message-content user-message">
                                <div class="message-text">{message.content}</div>
                                <div class="message-timestamp">
                                    {formatTimestamp(message.timestamp)}
                                </div>
                            </div>
                        {:else}
                            <div class="message-content assistant-message">
                                
                                {#each parsed.sections as section}
                                    {#if section.type === 'start'}
                                        <div class="agent-start fade-in">
                                            <Loader class="spin" size={16} />
                                            <span>Starting agent workflow...</span>
                                        </div>
                                    {:else if section.type === 'iteration'}
                                        <div class="iteration-card slide-in">
                                            <div class="iteration-header">
                                                <div class="iteration-badge">
                                                    <Clock size={14} />
                                                    Iteration {section.number}
                                                </div>
                                            </div>
                                            
                                            {#each section.steps as step}
                                                <div class="agent-step fade-in-up">
                                                    <div class="step-state">
                                                        <div class="state-badge {step.state}">
                                                            {#if step.state === 'fetch_tool'}
                                                                <Search size={14} />
                                                            {:else if step.state === 'use_tool'}
                                                                <Zap size={14} />
                                                            {:else if step.state === 'exit_response'}
                                                                <CheckCircle size={14} />
                                                            {:else}
                                                                <CheckCircle size={14} />
                                                            {/if}
                                                            {step.state.replace('_', ' ')}
                                                        </div>
                                                    </div>
                                                    
                                                    {#if step.reasoning}
                                                        <div class="step-reasoning">
                                                            <div class="reasoning-label">💭 Reasoning</div>
                                                            <div class="reasoning-text">{step.reasoning}</div>
                                                        </div>
                                                    {/if}
                                                    
                                                    {#if step.action}
                                                        <div class="step-action">
                                                            <div class="action-label">
                                                                <Zap size={12} />
                                                                Action
                                                            </div>
                                                            <pre class="code-block">{formatJson(step.action)}</pre>
                                                        </div>
                                                    {/if}
                                                    
                                                    {#if step.result}
                                                        <div class="step-result">
                                                            <div class="result-label">
                                                                <CheckCircle size={12} />
                                                                Result
                                                            </div>
                                                            <pre class="code-block result">{formatJson(step.result)}</pre>
                                                        </div>
                                                    {/if}
                                                </div>
                                            {/each}
                                        </div>
                                    {:else if section.type === 'final'}
                                        <div class="final-answer fade-in">
                                            <div class="final-header">
                                                <Sparkles size={20} />
                                                <span>Final Answer</span>
                                            </div>
                                            <div class="final-content">
                                                {section.content}
                                            </div>
                                            {#if section.confidence || section.iterations}
                                                <div class="final-meta">
                                                    {#if section.confidence}
                                                        <div class="meta-badge confidence-{section.confidence}">
                                                            <CheckCircle size={14} />
                                                            Confidence: {section.confidence}
                                                        </div>
                                                    {/if}
                                                    {#if section.iterations}
                                                        <div class="meta-badge">
                                                            <Clock size={14} />
                                                            {section.iterations} iterations
                                                        </div>
                                                    {/if}
                                                </div>
                                            {/if}
                                        </div>
                                    {/if}
                                {/each}
                                
                                <div class="message-timestamp">
                                    {formatTimestamp(message.timestamp)}
                                </div>
                            </div>
                        {/if}
                    </div>
                {/each}
            {/if}
            
            {#if $conversationStore.error}
                <div class="error-message fade-in">
                    <AlertCircle size={20} />
                    <strong>Error:</strong> {$conversationStore.error}
                </div>
            {/if}
        </div>
        <div class="bottom-spacer"></div>
    </div>
    
    <div class="input-area floating">
        <div class="input-container">
            <div class="tools-menu-container">
                <button 
                    class="input-button tools-button"
                    on:click={toggleToolsMenu}
                    disabled={isGenerating}
                    title="Tools and Options"
                >
                    <Plus size={20} />
                </button>
                
                {#if showToolsMenu}
                    <div class="tools-menu">
                        <button 
                            class="tool-item"
                            on:click={() => handleToolAction('refresh')}
                            disabled={isGenerating}
                        >
                            <MessageCircle size={16} />
                            New Chat
                        </button>
                    </div>
                {/if}
            </div>
            
            <textarea
                bind:this={textarea}
                bind:value={messageInput}
                on:keydown={handleKeydown}
                placeholder="Ask anything - Tool Agent will handle it..."
                rows="1"
                disabled={isGenerating}
            ></textarea>
            
            {#if isGenerating}
                <button 
                    class="input-button stop-button"
                    on:click={stopGeneration}
                    title="Stop Generation"
                >
                    <Square size={20} />
                </button>
            {:else}
                <button 
                    class="input-button send-button"
                    on:click={sendMessage}
                    disabled={!messageInput.trim() || isGenerating}
                    title="Send Message"
                >
                    <Send size={20} />
                </button>
            {/if}
        </div>
    </div>
</main>

<style>
    /* Animation keyframes */
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateY(-10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }

    .fade-in {
        animation: fadeIn 0.5s ease-out;
    }

    .slide-in {
        animation: slideIn 0.6s ease-out;
    }

    .fade-in-up {
        animation: fadeInUp 0.5s ease-out;
    }

    .spin {
        animation: spin 2s linear infinite;
    }

    .chat-window {
        flex: 1;
        display: flex;
        flex-direction: column;
        height: 100%;
        background: var(--bg-primary);
        position: relative;
    }

    .messages-container {
        flex: 1;
        overflow-y: auto;
        padding: 0 20px;
    }

    .messages {
        max-width: 900px;
        margin: 0 auto;
        padding-top: 80px; /* Add space for first message below navbar */
        padding-bottom: 20px;
    }

    .bottom-spacer {
        height: 120px; /* Space for input area + extra padding */
    }

    /* Welcome message enhanced */
    .welcome-message {
        text-align: center;
        padding: 60px 20px;
        max-width: 600px;
        margin: 0 auto;
    }

    .welcome-icon {
        color: var(--accent-primary);
        margin-bottom: 24px;
        animation: pulse 2s ease-in-out infinite;
    }

    .welcome-message h2 {
        font-size: 28px;
        font-weight: 600;
        margin-bottom: 16px;
        color: var(--text-primary);
    }

    .mode-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        background: var(--accent-primary);
        color: white;
        border-radius: 20px;
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
    }

    .welcome-hint {
        color: var(--text-secondary);
        font-size: 14px;
    }

    /* Agent start */
    .agent-start {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px;
        background: rgba(79, 70, 229, 0.15);
        border-left: 3px solid var(--accent-primary);
        border-radius: 8px;
        margin-bottom: 16px;
        font-weight: 500;
        color: var(--accent-primary);
    }

    /* Iteration card */
    .iteration-card {
        background: #0a0a0a;
        border: 1px solid #1a1a1a;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
    }

    .iteration-header {
        margin-bottom: 16px;
    }

    .iteration-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px;
        background: var(--accent-primary);
        color: white;
        border-radius: 16px;
        font-size: 13px;
        font-weight: 600;
        box-shadow: 0 2px 4px rgba(79, 70, 229, 0.3);
    }

    /* Agent step */
    .agent-step {
        background: #0f0f0f;
        border: 1px solid #1a1a1a;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
        transition: all 0.3s ease;
    }

    .agent-step:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
        transform: translateY(-2px);
        border-color: #252525;
    }

    .step-state {
        margin-bottom: 12px;
    }

    .state-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
        text-transform: capitalize;
    }

    .state-badge.fetch_tool {
        background: var(--accent-success);
        color: white;
        box-shadow: 0 2px 4px rgba(16, 185, 129, 0.3);
    }

    .state-badge.use_tool {
        background: var(--accent-warning);
        color: white;
        box-shadow: 0 2px 4px rgba(245, 158, 11, 0.3);
    }

    .state-badge.exit_response {
        background: var(--accent-secondary);
        color: white;
        box-shadow: 0 2px 4px rgba(124, 58, 237, 0.3);
    }

    /* Step sections */
    .step-reasoning {
        margin-bottom: 12px;
        background: rgba(79, 70, 229, 0.12);
        padding: 12px;
        border-radius: 8px;
        border-left: 3px solid var(--accent-primary);
    }

    .reasoning-label {
        font-size: 12px;
        font-weight: 700;
        color: var(--accent-primary);
        margin-bottom: 8px;
        letter-spacing: 0.3px;
    }

    .reasoning-text {
        font-size: 14px;
        line-height: 1.6;
        color: #e0e0e0;
    }

    .step-action, .step-result {
        margin-top: 12px;
    }

    .action-label, .result-label {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 8px;
        letter-spacing: 0.5px;
    }

    .action-label {
        color: var(--accent-warning);
    }

    .result-label {
        color: var(--accent-success);
    }

    .code-block {
        background: #000000;
        color: #e2e8f0;
        padding: 12px;
        border-radius: 8px;
        font-size: 12px;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        overflow-x: auto;
        line-height: 1.5;
        box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.6);
        max-height: 300px;
        overflow-y: auto;
        border: 1px solid #1a1a1a;
    }

    .code-block.result {
        background: #001a12;
        color: #a7f3d0;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }

    /* Final answer */
    .final-answer {
        background: linear-gradient(135deg, #0a0a0a 0%, #121212 100%);
        border: 2px solid var(--accent-primary);
        border-radius: 12px;
        padding: 24px;
        margin-top: 20px;
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
    }

    .final-header {
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 20px;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 2px solid var(--accent-primary);
    }

    .final-header :global(svg) {
        color: var(--accent-primary);
    }

    .final-content {
        font-size: 15px;
        line-height: 1.7;
        color: #e0e0e0;
        margin-bottom: 16px;
        white-space: pre-wrap;
    }

    .final-meta {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
    }

    .meta-badge {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        background: #0f0f0f;
        border: 1px solid #1a1a1a;
        border-radius: 12px;
        font-size: 13px;
        font-weight: 600;
        color: #b0b0b0;
    }

    .meta-badge.confidence-high {
        background: var(--accent-success);
        color: white;
        border-color: var(--accent-success);
        box-shadow: 0 2px 4px rgba(16, 185, 129, 0.3);
    }

    .meta-badge.confidence-medium {
        background: var(--accent-warning);
        color: white;
        border-color: var(--accent-warning);
        box-shadow: 0 2px 4px rgba(245, 158, 11, 0.3);
    }

    .meta-badge.confidence-low {
        background: var(--accent-error);
        color: white;
        border-color: var(--accent-error);
        box-shadow: 0 2px 4px rgba(239, 68, 68, 0.3);
    }

    /* Error message enhanced */
    .error-message {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px;
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid var(--accent-error);
        border-radius: 8px;
        color: var(--accent-error);
        margin: 16px 0;
    }

    /* Message animations */
    .message.generating .message-content {
        animation: pulse 1.5s ease-in-out infinite;
    }

    .stop-button {
        background-color: var(--accent-error);
        color: white;
        transition: all 0.2s ease;
    }

    .stop-button:hover:not(:disabled) {
        opacity: 0.9;
        transform: scale(1.05);
    }

    .mode-indicator {
        position: absolute;
        top: -28px;
        left: 50%;
        transform: translateX(-50%);
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        background: rgba(79, 70, 229, 0.1);
        border: 1px solid rgba(79, 70, 229, 0.3);
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;
        color: var(--accent-primary);
    }

    /* Scrollbar styling */
    .code-block::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }

    .code-block::-webkit-scrollbar-track {
        background: rgba(0, 0, 0, 0.4);
        border-radius: 3px;
    }

    .code-block::-webkit-scrollbar-thumb {
        background: #2a2a2a;
        border-radius: 3px;
    }

    .code-block::-webkit-scrollbar-thumb:hover {
        background: #3a3a3a;
    }
</style>
