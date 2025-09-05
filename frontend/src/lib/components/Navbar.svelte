<script>
    import { sidebarStore } from '$lib/stores/ui.js';
    
    function toggleSidebar() {
        sidebarStore.update(state => ({
            ...state,
            expanded: !state.expanded
        }));
    }
</script>

<nav class="navbar">
    <div class="nav-left">
        <button class="sidebar-toggle" on:click={toggleSidebar}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/>
            </svg>
        </button>
        
        <div class="brand">
            <span class="brand-name">Rhea</span>
            <span class="brand-subtitle">Advanced LLM Chat</span>
        </div>
    </div>
    
    <div class="nav-right">
        <div class="connection-status">
            <div class="status-indicator connected"></div>
            <span>Connected</span>
        </div>
    </div>
</nav>

<style>
    .navbar {
        height: 60px;
        background: var(--bg-secondary);
        border-bottom: 1px solid var(--border-primary);
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 20px;
        position: relative;
        z-index: 100;
    }

    .nav-left {
        display: flex;
        align-items: center;
        gap: 16px;
    }

    .sidebar-toggle {
        background: none;
        border: none;
        color: var(--text-secondary);
        cursor: pointer;
        padding: 8px;
        border-radius: 6px;
        transition: all 0.2s;
    }

    .sidebar-toggle:hover {
        color: var(--text-primary);
        background: var(--bg-tertiary);
    }

    .brand {
        display: flex;
        flex-direction: column;
    }

    .brand-name {
        font-size: 18px;
        font-weight: 600;
        color: var(--text-primary);
        line-height: 1;
    }

    .brand-subtitle {
        font-size: 12px;
        color: var(--text-secondary);
        line-height: 1;
    }

    .nav-right {
        display: flex;
        align-items: center;
    }

    .connection-status {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 14px;
        color: var(--text-secondary);
    }

    .status-indicator {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--accent-error);
    }

    .status-indicator.connected {
        background: var(--accent-success);
    }
</style>