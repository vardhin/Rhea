<script>
    import { sidebarStore } from '$lib/stores/ui.js';
    import { Menu, X } from 'lucide-svelte';
    import { writable } from 'svelte/store';

    const menuOpen = writable(false);

    function toggleSidebar() {
        sidebarStore.update(state => ({
            ...state,
            visible: !state.visible
        }));
        menuOpen.update(open => !open);
    }
</script>

<nav class="navbar">
    <div class="nav-left">
        <button class="sidebar-toggle" on:click={toggleSidebar} aria-label="Toggle sidebar">
            {#if $menuOpen}
                <X size={20} class="icon-animated" />
            {:else}
                <Menu size={20} class="icon-animated" />
            {/if}
        </button>
        <div class="brand">
            <span class="brand-name">Rhea</span>
        </div>
    </div>
    <div class="nav-right">
        <div class="status-indicator connected"></div>
    </div>
</nav>

<style>
    .navbar {
        height: 60px;
        background: transparent;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 20px;
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        width: 100%;
        z-index: 100;
        box-sizing: border-box;
    }

    .nav-left {
        display: flex;
        align-items: center;
        gap: 16px;
        flex: 1;
    }

    .sidebar-toggle {
        background: var(--bg-primary);
        border: 1px solid var(--border-primary);
        color: var(--text-secondary);
        cursor: pointer;
        padding: 8px;
        border-radius: 12px;
        transition: all var(--transition-fast);
        display: flex;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        flex-shrink: 0;
    }

    .sidebar-toggle:hover {
        background: var(--bg-tertiary);
        color: var(--text-primary);
        border-color: var(--border-secondary);
        transform: translateY(-1px);
    }

    .icon-animated {
        transition: transform 0.3s cubic-bezier(.4,2,.3,1), opacity 0.2s;
    }

    .sidebar-toggle:active .icon-animated {
        transform: scale(0.95) rotate(-20deg);
    }

    .brand {
        display: flex;
        align-items: center;
        flex: 1;
    }

    .brand-name {
        font-size: 18px;
        font-weight: 600;
        color: var(--text-primary);
        line-height: 1;
    }

    .nav-right {
        display: flex;
        align-items: center;
        flex-shrink: 0;
    }

    .status-indicator {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: var(--accent-error);
        transition: all var(--transition-fast);
    }

    .status-indicator.connected {
        background: var(--accent-success);
    }
</style>