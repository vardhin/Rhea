<script>
    import { onMount } from "svelte";
    import { Plus, MessageCircle, Wrench } from "lucide-svelte";
    import {
        conversationStore,
        conversationActions,
        sidebarStore,
        sidebarActions,
        conversationUtils
    } from "$lib/stores/store.js";
    import { listTools, searchTools, clearBugStatus, deactivateTool } from '$lib/tool-api.js';

    // Bind to parent props (optional - for backward compatibility)
    let { expanded = $bindable(), currentView = $bindable() } = $props();
    
    // Sync with store
    $effect(() => {
        expanded = $sidebarStore.expanded;
        currentView = $sidebarStore.currentView;
    });
    
    // Sync changes back to store
    $effect(() => {
        if (expanded !== $sidebarStore.expanded) {
            sidebarActions.setExpanded(expanded);
        }
        if (currentView !== $sidebarStore.currentView) {
            sidebarActions.setView(currentView);
        }
    });

    const navigationItems = [
        { id: "chat", label: "Chat", icon: MessageCircle },
        { id: "agent-tools", label: "Agent Tools", icon: Wrench },
    ];

    // Tool Store state
    let agentTools = $state([]);
    let searchQuery = $state('');
    let isLoadingTools = $state(false);

    // Load agent tools
    async function loadAgentTools() {
        try {
            isLoadingTools = true;
            agentTools = await listTools({ activeOnly: false, excludeBugged: false });
        } catch (error) {
            console.error('Failed to load agent tools:', error);
        } finally {
            isLoadingTools = false;
        }
    }

    // Search agent tools
    async function handleToolSearch() {
        if (!searchQuery.trim()) {
            await loadAgentTools();
            return;
        }
        
        try {
            isLoadingTools = true;
            agentTools = await searchTools(searchQuery);
        } catch (error) {
            console.error('Failed to search tools:', error);
        } finally {
            isLoadingTools = false;
        }
    }

    // Clear bug status
    async function handleClearBugs(toolId) {
        try {
            await clearBugStatus(toolId);
            await loadAgentTools();
        } catch (error) {
            console.error('Failed to clear bug status:', error);
        }
    }

    // Deactivate tool
    async function handleDeactivateTool(toolId) {
        try {
            await deactivateTool(toolId);
            await loadAgentTools();
        } catch (error) {
            console.error('Failed to deactivate tool:', error);
        }
    }

    // Load tools when view changes to agent-tools
    $effect(() => {
        if ($sidebarStore.currentView === 'agent-tools' && $sidebarStore.expanded) {
            loadAgentTools();
        }
    });

    async function newChat() {
        try {
            await conversationActions.create("New Chat");
            sidebarActions.setView("chat");
        } catch (error) {
            console.error("Failed to create new chat:", error);
        }
    }

    function selectView(viewId) {
        sidebarActions.toggleView(viewId);
    }

    async function selectConversation(conversationId) {
        try {
            await conversationActions.select(conversationId);
            sidebarActions.setView("chat");
        } catch (error) {
            console.error("Failed to select conversation:", error);
        }
    }

    async function deleteConversation(conversationId, event) {
        event.stopPropagation();
        try {
            await conversationActions.delete(conversationId);
        } catch (error) {
            console.error("Failed to delete conversation:", error);
        }
    }

    // Handle clicks outside the sidebar
    function handleDocumentClick(event) {
        const sidebar = event.target.closest(".sidebar-container");
        if (!sidebar && $sidebarStore.expanded) {
            sidebarActions.setExpanded(false);
        }
    }

    // Watch for sidebar visibility changes
    let visible = $state(true);
    let isAnimatingOut = $state(false);
    $effect(() => {
        const currentVisible = $sidebarStore.visible;
        if (visible && !currentVisible) {
            isAnimatingOut = true;
            setTimeout(() => {
                visible = currentVisible;
                isAnimatingOut = false;
            }, 300);
        } else if (!visible && currentVisible) {
            visible = currentVisible;
        }
    });
</script>

<svelte:document on:click={handleDocumentClick} />

{#if visible}
    <!-- Unified Sidebar Container with horizontal expansion -->
    <aside
        class="sidebar-container"
        class:expanded
        class:animating-out={isAnimatingOut}
    >
        <!-- Left Navigation Panel (always visible) -->
        <div class="sidebar-navigation">
            <!-- New Chat Button -->
            <button
                class="nav-button new-chat"
                on:click={newChat}
                title="New Chat"
            >
                <Plus size={18} />
            </button>

            <!-- Navigation Items -->
            {#each navigationItems as item}
                <button
                    class="nav-button"
                    class:active={currentView === item.id}
                    on:click={() => selectView(item.id)}
                    title={item.label}
                >
                    <svelte:component this={item.icon} size={18} />
                </button>
            {/each}
        </div>

        <!-- Right Content Panel (visible when expanded) -->
        <div class="sidebar-content-wrapper" class:show={expanded}>
            <div class="sidebar-header">
                <button class="new-chat-btn" on:click={newChat}>
                    <Plus size={16} />
                    <span class="btn-text">New Chat</span>
                </button>
            </div>

            <div class="sidebar-content">
                {#if currentView === "chat"}
                    <!-- Chat List View -->
                    <div class="conversations">
                        <h3 class="section-title">Recent Chats</h3>
                        {#if $conversationStore.conversations.length > 0}
                            <div class="conversation-list">
                                {#each $conversationStore.conversations as conversation}
                                    <div class="conversation-item-wrapper">
                                        <button
                                            class="conversation-item"
                                            class:active={conversation.id ===
                                                $conversationStore.currentId}
                                            on:click={() =>
                                                selectConversation(
                                                    conversation.id,
                                                )}
                                        >
                                            <div class="conversation-title">
                                                {conversation.title}
                                            </div>
                                            <div class="conversation-timestamp">
                                                {conversationUtils.formatDate(conversation.timestamp)}
                                            </div>
                                        </button>
                                        <button
                                            class="delete-conversation"
                                            on:click={(e) =>
                                                deleteConversation(
                                                    conversation.id,
                                                    e,
                                                )}
                                            title="Delete conversation"
                                        >
                                            ×
                                        </button>
                                    </div>
                                {/each}
                            </div>
                        {:else}
                            <div class="empty-state">
                                <p>No conversations yet.</p>
                                <p>Start a new chat to begin!</p>
                            </div>
                        {/if}
                    </div>
                {:else if currentView === "agent-tools"}
                    <!-- Agent Tools View -->
                    <div class="agent-tools-panel">
                        <h3 class="section-title">Agent Tool Store</h3>
                        
                        <!-- Search -->
                        <div class="tool-search">
                            <input
                                type="text"
                                bind:value={searchQuery}
                                on:input={handleToolSearch}
                                placeholder="Search tools..."
                            />
                        </div>
                        
                        {#if isLoadingTools}
                            <div class="loading-indicator">Loading tools...</div>
                        {:else if agentTools.length > 0}
                            <div class="agent-tools-content">
                                {#each agentTools as tool}
                                    <div class="agent-tool-item" class:bugged={tool.is_bugged} class:inactive={!tool.is_active}>
                                        <div class="tool-header">
                                            <div class="tool-name">{tool.name}</div>
                                            <div class="tool-badges">
                                                {#if tool.is_bugged}
                                                    <span class="badge error">Bugged</span>
                                                {/if}
                                                {#if !tool.is_active}
                                                    <span class="badge inactive">Inactive</span>
                                                {/if}
                                            </div>
                                        </div>
                                        
                                        <div class="tool-description">{tool.description}</div>
                                        
                                        <div class="tool-meta">
                                            <span class="meta-item">📁 {tool.category || 'uncategorized'}</span>
                                            <span class="meta-item">▶️ {tool.execution_count} runs</span>
                                            {#if tool.bug_count > 0}
                                                <span class="meta-item error">🐛 {tool.bug_count} bugs</span>
                                            {/if}
                                        </div>
                                        
                                        {#if tool.tags && tool.tags.length > 0}
                                            <div class="tool-tags">
                                                {#each tool.tags as tag}
                                                    <span class="tag">{tag}</span>
                                                {/each}
                                            </div>
                                        {/if}
                                        
                                        <div class="tool-actions">
                                            {#if tool.is_bugged}
                                                <button
                                                    class="tool-action-btn"
                                                    on:click={() => handleClearBugs(tool.id)}
                                                >
                                                    Clear Bugs
                                                </button>
                                            {/if}
                                            {#if tool.is_active}
                                                <button
                                                    class="tool-action-btn danger"
                                                    on:click={() => handleDeactivateTool(tool.id)}
                                                >
                                                    Deactivate
                                                </button>
                                            {/if}
                                        </div>
                                    </div>
                                {/each}
                            </div>
                        {:else}
                            <div class="empty-state">
                                <p>No tools found.</p>
                            </div>
                        {/if}
                    </div>
                {/if}
            </div>
        </div>
    </aside>
{/if}

<style>
    
    .sidebar-container {
        position: fixed;
        left: 16px;
        top: 50%;
        transform: translateY(-50%);
        background: var(--bg-secondary, #ffffff);
        border: 1px solid var(--border-primary, #e5e5e5);
        border-radius: 20px;
        display: flex;
        flex-direction: row; /* Changed to row for horizontal layout */
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
        backdrop-filter: blur(16px);
        z-index: 100;
        overflow: hidden;
        
        /* Compact mode - only navigation visible */
        width: 56px;
        height: auto; /* Auto height based on navigation buttons */
        
        /* Fade in animation */
        opacity: 0;
        animation: fadeIn 0.4s ease-out 0.1s forwards;
    }
    
    /* Apply fade out when component is being removed */
    .sidebar-container.animating-out {
        animation: fadeOut 0.3s ease-out forwards !important;
    }
    
    /* Fade animations */
    @keyframes fadeIn {
        from { 
            opacity: 0; 
            transform: translateY(-50%) translateX(-20px) scale(0.95);
        }
        to { 
            opacity: 1; 
            transform: translateY(-50%) translateX(0) scale(1);
        }
    }
    
    @keyframes fadeOut {
        from { 
            opacity: 1; 
            transform: translateY(-50%) translateX(0) scale(1);
        }
        to { 
            opacity: 0; 
            transform: translateY(-50%) translateX(-20px) scale(0.95);
        }
    }
    
    /* Expanded state - horizontal expansion */
    .sidebar-container.expanded {
        width: 320px; /* Total width when expanded */
        border-radius: 16px;
        
        /* Smooth horizontal expand transition */
        transition: width 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                   border-radius 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94);
    }
    
    /* Contract transition */
    .sidebar-container:not(.expanded) {
        transition: width 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                   border-radius 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
    }
    
    /* Left Navigation Panel */
    .sidebar-navigation {
        display: flex;
        flex-direction: column;
        gap: 4px;
        padding: 8px;
        flex-shrink: 0;
        width: 56px; /* Fixed width for navigation */
        background: var(--bg-secondary, #ffffff);
    }
    
    /* Right Content Panel */
    .sidebar-content-wrapper {
        flex: 1;
        display: none;
        flex-direction: column;
        min-height: 0;
        opacity: 0;
        transform: translateX(-10px);
        transition: opacity 0.3s ease-out, transform 0.3s ease-out;
        border-left: 1px solid var(--border-primary, #e5e5e5);
        background: var(--bg-secondary, #ffffff);
        width: 264px; /* Content width: 320 - 56 = 264 */
        max-height: 55vh;
        min-height: 320px;
    }
    
    .sidebar-content-wrapper.show {
        display: flex;
        opacity: 1;
        transform: translateX(0);
        /* Delay content appearance for smoother expand */
        transition: opacity 0.3s ease-out 0.2s, transform 0.3s ease-out 0.2s;
    }
    
    /* Hide content immediately when contracting */
    .sidebar-container:not(.expanded) .sidebar-content-wrapper {
        opacity: 0;
        transform: translateX(-10px);
        transition: opacity 0.2s ease-out, transform 0.2s ease-out;
    }
    
    .sidebar-header {
        padding: 16px 16px 12px 16px;
        border-bottom: 1px solid var(--border-primary, #e5e5e5);
        flex-shrink: 0;
    }
    
    .new-chat-btn {
        width: 100%;
        background: var(--accent-primary, #007bff);
        color: white;
        border: none;
        padding: 12px 16px;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 8px;
        justify-content: center;
        transition: all 0.2s ease;
        transform: translateY(0);
    }
    
    .new-chat-btn:hover {
        background: var(--accent-secondary, #0056b3);
        transform: translateY(-1px);
    }
    
    .sidebar-content {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
        min-height: 0;
    }
    
    .section-title {
        font-size: 12px;
        font-weight: 600;
        color: var(--text-secondary, #6b7280);
        margin: 0 0 12px 0;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .conversation-list {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    
    .conversation-item-wrapper {
        position: relative;
        display: flex;
        align-items: center;
    }
    
    .conversation-item {
        background: none;
        border: none;
        color: var(--text-primary, #000000);
        padding: 12px;
        border-radius: 8px;
        cursor: pointer;
        text-align: left;
        transition: all 0.2s ease;
        width: 100%;
        flex: 1;
    }
    
    .conversation-item:hover {
        background: var(--bg-tertiary, #f8f9fa);
        transform: translateX(2px);
    }
    
    .conversation-item.active {
        background: var(--accent-primary, #007bff);
        color: white;
    }
    
    .delete-conversation {
        position: absolute;
        right: 8px;
        top: 50%;
        transform: translateY(-50%);
        background: rgba(255, 0, 0, 0.1);
        border: none;
        border-radius: 50%;
        width: 20px;
        height: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #dc3545;
        cursor: pointer;
        opacity: 0;
        transition: all 0.2s ease;
        font-size: 14px;
        line-height: 1;
    }
    
    .conversation-item-wrapper:hover .delete-conversation {
        opacity: 1;
    }
    
    .delete-conversation:hover {
        background: rgba(255, 0, 0, 0.2);
        transform: translateY(-50%) scale(1.1);
    }

    .conversation-title {
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        padding-right: 28px; /* Space for delete button */
    }
    
    .conversation-timestamp {
        font-size: 12px;
        color: var(--text-muted, #9ca3af);
        margin-bottom: 2px;
    }
    
    .conversation-model {
        font-size: 11px;
        color: var(--text-muted, #9ca3af);
        font-style: italic;
    }
    
    .loading-indicator {
        text-align: center;
        padding: 20px;
        color: var(--text-secondary, #6b7280);
        font-style: italic;
    }
    
    .empty-state {
        text-align: center;
        padding: 20px;
        color: var(--text-secondary, #6b7280);
    }
    
    .empty-state p {
        margin: 4px 0;
        font-size: 14px;
    }
    
    .status-indicator {
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;
        background: #dc3545;
        color: white;
    }
    
    .status-indicator.connected {
        background: #28a745;
    }
    
    .settings-content,
    .models-content,
    .functions-content,
    .thinking-mode-content {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }
    
    .setting-item,
    .model-item,
    .function-item,
    .detail-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px;
        background: var(--bg-tertiary, #f8f9fa);
        border-radius: 8px;
        transition: all 0.2s ease;
    }
    
    .setting-item.full-width {
        flex-direction: column;
        align-items: stretch;
        gap: 8px;
    }
    
    .setting-item.full-width label {
        align-self: flex-start;
    }
    
    .setting-item:hover,
    .model-item:hover,
    .function-item:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
    
    .model-item {
        flex-direction: column;
        align-items: stretch;
        gap: 8px;
    }
    
    .model-item.selected {
        background: var(--accent-primary, #007bff);
        color: white;
    }
    
    .model-info {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    
    .model-name {
        font-size: 14px;
        font-weight: 600;
    }
    
    .model-details {
        display: flex;
        gap: 8px;
        font-size: 12px;
        opacity: 0.8;
    }
    
    .model-actions {
        display: flex;
        justify-content: flex-end;
    }
    
    .select-model-btn {
        padding: 6px 12px;
        background: var(--accent-primary, #007bff);
        color: white;
        border: none;
        border-radius: 4px;
        font-size: 12px;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    
    .select-model-btn:hover:not(:disabled) {
        background: var(--accent-secondary, #0056b3);
    }
    
    .select-model-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }
    
    .select-model-btn.active {
        background: #28a745;
    }
    
    .model-info-panel {
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid var(--border-primary, #e5e5e5);
    }
    
    .model-details-content {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    
    .function-info {
        flex: 1;
    }
    
    .function-name {
        font-size: 14px;
        font-weight: 500;
        color: var(--text-primary, #000000);
        margin-bottom: 2px;
    }
    
    .function-description {
        font-size: 12px;
        color: var(--text-secondary, #6b7280);
        line-height: 1.3;
    }
    
    .reasoning-level {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px;
        background: var(--bg-tertiary, #f8f9fa);
        border-radius: 6px;
        margin-top: 8px;
    }
    
    .reasoning-level label {
        font-size: 13px;
        font-weight: 500;
    }
    
    .setting-item label,
    .detail-item label {
        font-size: 14px;
        font-weight: 500;
        color: var(--text-primary, #000000);
    }
    
    .setting-item input[type="range"] {
        flex: 1;
        margin: 0 8px;
    }
    
    .setting-item textarea {
        width: 100%;
        min-height: 60px;
        padding: 8px;
        border: 1px solid var(--border-primary, #e5e5e5);
        border-radius: 4px;
        font-size: 13px;
        font-family: inherit;
        resize: vertical;
        transition: border-color 0.2s ease;
    }
    
    .setting-item textarea:focus {
        border-color: var(--accent-primary, #007bff);
        outline: none;
    }

    .setting-item select,
    .reasoning-level select {
        padding: 4px 8px;
        border-radius: 4px;
        border: 1px solid var(--border-primary, #e5e5e5);
        transition: border-color 0.2s ease;
        background: white;
    }
    
    .setting-item select:focus,
    .reasoning-level select:focus {
        border-color: var(--accent-primary, #007bff);
        outline: none;
    }
    
    .nav-button {
        border: none;
        background: transparent;
        color: var(--text-secondary, #6b7280);
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        position: relative;
        
        /* Navigation button styling */
        width: 40px;
        height: 40px;
        border-radius: 16px;
        padding: 0;
    }
    
    .nav-button:hover {
        background: var(--bg-tertiary, #f8f9fa);
        color: var(--text-primary, #000000);
        transform: scale(1.05);
    }
    
    .nav-button.active {
        background: var(--accent-primary, #007bff);
        color: white;
        transform: scale(1.02);
    }
    
    .nav-button.new-chat {
        background: var(--accent-primary, #007bff);
        color: white;
        margin-bottom: 8px;
    }
    
    .nav-button.new-chat:hover {
        background: var(--accent-secondary, #0056b3);
    }
    
    /* Tooltips for navigation buttons */
    .nav-button::after {
        content: attr(title);
        position: absolute;
        left: calc(100% + 12px);
        top: 50%;
        transform: translateY(-50%);
        background: rgba(0, 0, 0, 0.9);
        color: white;
        padding: 6px 10px;
        border-radius: 6px;
        font-size: 12px;
        white-space: nowrap;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.2s ease;
        z-index: 1000;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }
    
    .nav-button:hover::after {
        opacity: 1;
        transition-delay: 0.5s;
    }
    
    /* Hide tooltips when expanded */
    .sidebar-container.expanded .nav-button::after {
        display: none;
    }
    
    .btn-text {
        opacity: 1;
        transform: translateX(0);
        transition: all 0.3s ease-out 0.25s;
    }
    
    /* Scrollbar styling */
    .sidebar-content::-webkit-scrollbar {
        width: 4px;
    }
    
    .sidebar-content::-webkit-scrollbar-track {
        background: transparent;
    }
    
    .sidebar-content::-webkit-scrollbar-thumb {
        background: var(--border-primary, #e5e5e5);
        border-radius: 2px;
    }
    
    .sidebar-content::-webkit-scrollbar-thumb:hover {
        background: var(--text-muted, #9ca3af);
    }


    
    .agent-tools-panel {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }
    
    .tool-search input {
        width: 100%;
        padding: 8px 12px;
        border: 1px solid var(--border-primary);
        border-radius: 6px;
        font-size: 13px;
    }
    
    .agent-tools-content {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    
    .agent-tool-item {
        padding: 12px;
        background: var(--bg-tertiary);
        border-radius: 8px;
        border: 1px solid var(--border-primary);
        transition: all 0.2s ease;
    }
    
    .agent-tool-item:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
    
    .agent-tool-item.bugged {
        border-color: #dc3545;
        background: rgba(220, 53, 69, 0.05);
    }
    
    .agent-tool-item.inactive {
        opacity: 0.6;
    }
    
    .tool-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }
    
    .tool-name {
        font-size: 14px;
        font-weight: 600;
        color: var(--text-primary);
    }
    
    .tool-badges {
        display: flex;
        gap: 4px;
    }
    
    .badge {
        font-size: 10px;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 500;
    }
    
    .badge.error {
        background: #dc3545;
        color: white;
    }
    
    .badge.inactive {
        background: #6c757d;
        color: white;
    }
    
    .tool-description {
        font-size: 12px;
        color: var(--text-secondary);
        margin-bottom: 8px;
        line-height: 1.4;
    }
    
    .tool-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 6px;
    }
    
    .meta-item {
        font-size: 11px;
        color: var(--text-muted);
    }
    
    .meta-item.error {
        color: #dc3545;
        font-weight: 500;
    }
    
    .tool-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
        margin-bottom: 8px;
    }
    
    .tag {
        font-size: 10px;
        padding: 2px 6px;
        background: rgba(0, 123, 255, 0.1);
        color: var(--accent-primary);
        border-radius: 4px;
    }
    
    .tool-actions {
        display: flex;
        gap: 6px;
        margin-top: 8px;
    }
    
    .tool-action-btn {
        font-size: 11px;
        padding: 4px 8px;
        border: none;
        border-radius: 4px;
        background: var(--accent-primary);
        color: white;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    
    .tool-action-btn:hover {
        opacity: 0.9;
    }
    
    .tool-action-btn.danger {
        background: #dc3545;
    }
</style>
