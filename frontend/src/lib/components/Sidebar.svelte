<script>
    import { sidebarStore } from '$lib/stores/ui.js';
    import { Plus, MessageCircle, Settings, Shield, Code, ChevronLeft, ChevronRight } from 'lucide-svelte';
    
    let { expanded = $bindable(), currentView = $bindable() } = $props();
    let isAnimatingOut = $state(false);
    
    const navigationItems = [
        { id: 'chat', label: 'Chat', icon: MessageCircle },
        { id: 'settings', label: 'Settings', icon: Settings },
        { id: 'models', label: 'Models', icon: Shield },
        { id: 'functions', label: 'Functions', icon: Code }
    ];
    
    // Mock chat conversations
    let conversations = $state([
        { id: '1', title: 'Getting Started with AI', timestamp: '2 minutes ago' },
        { id: '2', title: 'Python Programming Help', timestamp: '1 hour ago' },
        { id: '3', title: 'Creative Writing Ideas', timestamp: '3 hours ago' }
    ]);
    


    function selectView(viewId) {
        if (!expanded) {
            // If collapsed, expand and show selected tab
            expanded = true;
            currentView = viewId;
            sidebarStore.update(store => ({ ...store, expanded: true, currentView: viewId }));
        } else if (currentView === viewId) {
            // If expanded and same tab, collapse
            expanded = false;
            sidebarStore.update(store => ({ ...store, expanded: false }));
        } else {
            // If expanded and different tab, switch tab and stay expanded
            currentView = viewId;
            sidebarStore.update(store => ({ ...store, currentView: viewId }));
        }
    }
    

    function newChat() {
        const newId = Date.now().toString();
        conversations.unshift({
            id: newId,
            title: 'New Chat',
            timestamp: 'Just now'
        });
        currentView = 'chat';
        // Do not force expand here
        sidebarStore.update(store => ({ ...store, currentView: 'chat' }));
    }
    
    function toggleExpanded() {
        expanded = !expanded;
        sidebarStore.update(store => ({ ...store, expanded }));
    }
    
    function selectConversation(conversationId) {
        console.log('Selected conversation:', conversationId);
    }
    
    // Handle clicks outside the sidebar to contract (but don't hide completely)
    function handleDocumentClick(event) {
        const sidebar = event.target.closest('.sidebar-container');
        if (!sidebar && expanded) {
            expanded = false;
            sidebarStore.update(store => ({ ...store, expanded: false }));
        }
    }

    // Watch for sidebar visibility changes to trigger exit animation
    let visible = $state(true);
    $effect(() => {
        const currentVisible = $sidebarStore.visible;
        if (visible && !currentVisible) {
            // Sidebar is being hidden - trigger exit animation
            isAnimatingOut = true;
            setTimeout(() => {
                visible = currentVisible;
                isAnimatingOut = false;
            }, 300); // Match animation duration
        } else if (!visible && currentVisible) {
            // Sidebar is being shown - show immediately
            visible = currentVisible;
        }
    });
</script>

<svelte:document on:click={handleDocumentClick} />

{#if visible}
<!-- Unified Sidebar Container with fade and expand/contract animations -->
<aside class="sidebar-container" class:expanded class:animating-out={isAnimatingOut}>
    <!-- Main Sidebar Content (visible when expanded) -->
    <div class="sidebar-content-wrapper" class:show={expanded}>
        <div class="sidebar-header">
            <button class="new-chat-btn" on:click={newChat}>
                <Plus size={16} />
                <span class="btn-text">New Chat</span>
            </button>
        </div>
        
        <div class="sidebar-content">
            {#if currentView === 'chat'}
                <!-- Chat List View -->
                <div class="conversations">
                    <h3 class="section-title">Recent Chats</h3>
                    <div class="conversation-list">
                        {#each conversations as conversation}
                            <button 
                                class="conversation-item"
                                on:click={() => selectConversation(conversation.id)}
                            >
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
                        <div class="setting-item">
                            <label>Theme</label>
                            <select>
                                <option>Light</option>
                                <option>Dark</option>
                                <option>Auto</option>
                            </select>
                        </div>
                        <div class="setting-item">
                            <label>Language</label>
                            <select>
                                <option>English</option>
                                <option>Spanish</option>
                                <option>French</option>
                            </select>
                        </div>
                    </div>
                </div>
            {:else if currentView === 'models'}
                <!-- Models View -->
                <div class="models-panel">
                    <h3 class="section-title">AI Models</h3>
                    <div class="models-content">
                        <div class="model-item">
                            <div class="model-name">GPT-4</div>
                            <div class="model-status">Active</div>
                        </div>
                        <div class="model-item">
                            <div class="model-name">Claude 3</div>
                            <div class="model-status">Available</div>
                        </div>
                    </div>
                </div>
            {:else if currentView === 'functions'}
                <!-- Functions View -->
                <div class="functions-panel">
                    <h3 class="section-title">Functions</h3>
                    <div class="functions-content">
                        <div class="function-item">
                            <div class="function-name">Web Search</div>
                            <div class="function-toggle">
                                <input type="checkbox" checked />
                            </div>
                        </div>
                        <div class="function-item">
                            <div class="function-name">Code Execution</div>
                            <div class="function-toggle">
                                <input type="checkbox" />
                            </div>
                        </div>
                    </div>
                </div>
            {/if}
        </div>

        <!-- Horizontal Navigation Pills (only show when expanded) -->
        <div class="horizontal-nav-pills">
            {#each navigationItems as item}
                <button 
                    class="pill-button" 
                    class:active={currentView === item.id}
                    on:click={() => selectView(item.id)}
                    title={item.label}
                >
                    
                </button>
            {/each}
        </div>
    </div>
    
    <!-- Navigation Pills (only show when contracted) -->
    <div class="sidebar-navigation">
        <!-- New Chat Button (only show in pill mode) -->
        {#if !expanded}
            <button class="nav-button new-chat" on:click={newChat} title="New Chat">
                <Plus size={18} />
            </button>
        {/if}
        
        <!-- Navigation Items (always show, now act as toggle/selectors) -->
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
        
    <!-- Remove toggle button, navigation buttons now handle expand/collapse -->
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
        flex-direction: column;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
        backdrop-filter: blur(16px);
        z-index: 100;
        overflow: hidden;
        
        /* Pill mode - compact */
        width: 56px;
        padding: 8px;
        
        /* Fade in animation - smooth entrance */
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
    
    /* Expanded state - reduced height and smooth expand animation */
    .sidebar-container.expanded {
        width: 320px;
        height: 55vh; /* Further reduced height */
        max-height: 420px; /* Further reduced max height */
        min-height: 320px; /* Further reduced min height */
        border-radius: 16px;
        padding: 0;
        transform: translateY(-50%);
        
        /* Smooth expand transition */
        transition: width 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                   height 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                   border-radius 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                   padding 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94);
    }
    
    /* Contract transition - smooth contraction without bounce */
    .sidebar-container:not(.expanded) {
        transition: width 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                   height 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                   border-radius 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                   padding 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
    }
    
    /* Sidebar Content Wrapper - only visible when expanded */
    .sidebar-content-wrapper {
        flex: 1;
        display: none;
        flex-direction: column;
        min-height: 0;
        opacity: 0;
        transform: translateY(10px);
        transition: opacity 0.3s ease-out, transform 0.3s ease-out;
    }
    
    .sidebar-content-wrapper.show {
        display: flex;
        opacity: 1;
        transform: translateY(0);
        /* Delay content appearance for smoother expand */
        transition: opacity 0.3s ease-out 0.2s, transform 0.3s ease-out 0.2s;
    }
    
    /* Hide content immediately when contracting */
    .sidebar-container:not(.expanded) .sidebar-content-wrapper {
        opacity: 0;
        transform: translateY(10px);
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
        padding: 13px;
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
    }
    
    .conversation-item:hover {
        background: var(--bg-tertiary, #f8f9fa);
        transform: translateX(2px);
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
        color: var(--text-muted, #9ca3af);
    }
    
    .settings-content,
    .models-content,
    .functions-content {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }
    
    .setting-item,
    .model-item,
    .function-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px;
        background: var(--bg-tertiary, #f8f9fa);
        border-radius: 8px;
        transition: all 0.2s ease;
    }
    
    .setting-item:hover,
    .model-item:hover,
    .function-item:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
    
    .setting-item label,
    .model-name,
    .function-name {
        font-size: 14px;
        font-weight: 500;
        color: var(--text-primary, #000000);
    }
    
    .model-status {
        font-size: 12px;
        padding: 4px 8px;
        background: var(--accent-primary, #007bff);
        color: white;
        border-radius: 4px;
    }
    
    .setting-item select {
        padding: 4px 8px;
        border-radius: 4px;
        border: 1px solid var(--border-primary, #e5e5e5);
        transition: border-color 0.2s ease;
    }
    
    .setting-item select:focus {
        border-color: var(--accent-primary, #007bff);
        outline: none;
    }

    /* Horizontal Navigation Pills (when expanded) */
    .horizontal-nav-pills {
        display: flex;
        justify-content: center;
        gap: 4px;
        padding: 12px 16px;
        border-top: 1px solid var(--border-primary, #e5e5e5);
        flex-shrink: 0;
        background: var(--bg-secondary, #ffffff);
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
        
        /* Pill mode - compact buttons */
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
        margin-bottom: 4px;
    }
    
    .nav-button.new-chat:hover {
        background: var(--accent-secondary, #0056b3);
    }
    
    .nav-button.toggle {
        background: var(--bg-tertiary, #f8f9fa);
        margin-top: 4px;
    }
    
    .nav-button.toggle:hover {
        background: var(--accent-primary, #007bff);
        color: white;
    }
    
    /* Navigation Text - only for toggle button */
    .nav-text {
        display: none;
    }
    
    .btn-text {
        opacity: 1;
        transform: translateX(0);
        transition: all 0.3s ease-out 0.25s;
    }
    
    /* Tooltips for pill mode */
    .sidebar-container:not(.expanded) .nav-button::after {
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
    
    .sidebar-container:not(.expanded) .nav-button:hover::after {
        opacity: 1;
        transition-delay: 0.5s;
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
</style>
