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
    /* ...existing styles from original file... */
    
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
