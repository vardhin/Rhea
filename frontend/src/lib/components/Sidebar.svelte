<script>
    import { sidebarStore } from '$lib/stores/ui.js';
    
    let { expanded = $bindable(), currentView = $bindable() } = $props();
    
    const navigationItems = [
        { id: 'chat', label: 'Chat', icon: 'chat' },
        { id: 'settings', label: 'Settings', icon: 'settings' },
        { id: 'models', label: 'Models', icon: 'models' },
        { id: 'functions', label: 'Functions', icon: 'functions' }
    ];
    
    // Mock chat conversations
    let conversations = $state([
        { id: '1', title: 'Getting Started with AI', timestamp: '2 minutes ago' },
        { id: '2', title: 'Python Programming Help', timestamp: '1 hour ago' },
        { id: '3', title: 'Creative Writing Ideas', timestamp: '3 hours ago' }
    ]);
    
    function selectView(viewId) {
        currentView = viewId;
        if (viewId !== 'chat') {
            expanded = true;
        }
    }
    
    function newChat() {
        const newId = Date.now().toString();
        conversations.unshift({
            id: newId,
            title: 'New Chat',
            timestamp: 'Just now'
        });
    }
</script>

<aside class="sidebar" class:expanded>
    <div class="sidebar-header">
        <button class="new-chat-btn" on:click={newChat}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 4v16m8-8H4"/>
            </svg>
            New Chat
        </button>
    </div>
    
    <div class="sidebar-content">
        {#if currentView === 'chat' || !expanded}
            <!-- Chat List View -->
            <div class="conversations">
                <h3 class="section-title">Recent Chats</h3>
                <div class="conversation-list">
                    {#each conversations as conversation}
                        <button class="conversation-item">
                            <div class="conversation-title">{conversation.title}</div>
                            <div class="conversation-timestamp">{conversation.timestamp}</div>
                        </button>
                    {/each}
                </div>
            </div>
        {:else if currentView === 'settings'}
            <!-- Settings View -->
            <div class="settings-panel">
                <h3 class="section-title">Settings</h3>
                <div class="settings-content">
                    <p>Settings panel will be implemented here</p>
                </div>
            </div>
        {:else if currentView === 'models'}
            <!-- Models View -->
            <div class="models-panel">
                <h3 class="section-title">Models</h3>
                <div class="models-content">
                    <p>Models panel will be implemented here</p>
                </div>
            </div>
        {:else if currentView === 'functions'}
            <!-- Functions View -->
            <div class="functions-panel">
                <h3 class="section-title">Functions</h3>
                <div class="functions-content">
                    <p>Functions panel will be implemented here</p>
                </div>
            </div>
        {/if}
    </div>
    
    <div class="sidebar-footer">
        <nav class="nav-menu">
            {#each navigationItems as item}
                <button 
                    class="nav-item" 
                    class:active={currentView === item.id}
                    on:click={() => selectView(item.id)}
                >
                    <div class="nav-icon">
                        {#if item.icon === 'chat'}
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                            </svg>
                        {:else if item.icon === 'settings'}
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M12 15a3 3 0 100-6 3 3 0 000 6z"/>
                                <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/>
                            </svg>
                        {:else if item.icon === 'models'}
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                            </svg>
                        {:else if item.icon === 'functions'}
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/>
                            </svg>
                        {/if}
                    </div>
                    {#if expanded}
                        <span class="nav-label">{item.label}</span>
                    {/if}
                </button>
            {/each}
        </nav>
    </div>
</aside>

<style>
    .sidebar {
        width: 64px;
        background: var(--bg-secondary);
        border-right: 1px solid var(--border-primary);
        display: flex;
        flex-direction: column;
        transition: width var(--transition-normal);
        overflow: hidden;
    }
    
    .sidebar.expanded {
        width: 320px;
    }
    
    .sidebar-header {
        padding: 16px 12px;
        border-bottom: 1px solid var(--border-primary);
    }
    
    .new-chat-btn {
        width: 100%;
        background: var(--accent-primary);
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
        transition: background var(--transition-fast);
    }
    
    .new-chat-btn:hover {
        background: var(--accent-secondary);
    }
    
    .sidebar-content {
        flex: 1;
        overflow-y: auto;
        padding: 16px 12px;
    }
    
    .section-title {
        font-size: 14px;
        font-weight: 600;
        color: var(--text-secondary);
        margin: 0 0 12px 0;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .conversation-list {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    
    .conversation-item {
        background: none;
        border: none;
        color: var(--text-primary);
        padding: 12px 16px;
        border-radius: 8px;
        cursor: pointer;
        text-align: left;
        transition: background var(--transition-fast);
    }
    
    .conversation-item:hover {
        background: var(--bg-tertiary);
    }
    
    .conversation-title {
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .conversation-timestamp {
        font-size: 12px;
        color: var(--text-muted);
    }
    
    .sidebar-footer {
        padding: 16px 12px;
        border-top: 1px solid var(--border-primary);
    }
    
    .nav-menu {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    
    .nav-item {
        background: none;
        border: none;
        color: var(--text-secondary);
        padding: 12px 16px;
        border-radius: 8px;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 14px;
        font-weight: 500;
        transition: all var(--transition-fast);
        min-height: 44px;
    }
    
    .nav-item:hover {
        background: var(--bg-tertiary);
        color: var(--text-primary);
    }
    
    .nav-item.active {
        background: var(--accent-primary);
        color: white;
    }
    
    .nav-icon {
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .nav-label {
        flex: 1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .settings-content,
    .models-content,
    .functions-content {
        color: var(--text-secondary);
        font-size: 14px;
        padding: 20px;
        text-align: center;
    }
    
    /* Hide content when sidebar is collapsed */
    .sidebar:not(.expanded) .new-chat-btn span,
    .sidebar:not(.expanded) .nav-label,
    .sidebar:not(.expanded) .section-title,
    .sidebar:not(.expanded) .conversation-list {
        display: none;
    }
    
    .sidebar:not(.expanded) .new-chat-btn {
        justify-content: center;
        padding: 12px;
    }
</style>