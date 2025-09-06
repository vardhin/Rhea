<script>
    import Navbar from '$lib/components/Navbar.svelte';
    import Sidebar from '$lib/components/Sidebar.svelte';
    import ChatWindow from '$lib/components/ChatWindow.svelte';
    import { sidebarStore } from '$lib/stores/ui.js';
    import { themeStore } from '$lib/stores/theme.js';

    let sidebarExpanded = $state(false);
    let sidebarVisible = $state(true);
    let currentView = $state('chat'); // chat, settings, models, functions

    // Subscribe to stores
    $effect(() => {
        sidebarExpanded = $sidebarStore.expanded;
        sidebarVisible = $sidebarStore.visible;
    });
</script>

<div class="main-container" data-theme={$themeStore.currentTheme}>
    <Navbar />
    
    <div class="content-container">
        <div class="sidebar-container" class:visible={sidebarVisible}>
            <Sidebar 
                bind:expanded={sidebarExpanded}
                bind:currentView={currentView}
            />
        </div>
        
        <ChatWindow 
            {sidebarExpanded}
            {currentView}
        />
    </div>
</div>

<style>
    .main-container {
        height: 100vh;
        display: flex;
        flex-direction: column;
        background: var(--bg-primary);
        padding-top: 60px; /* Add padding for fixed navbar */
    }

    .content-container {
        flex: 1;
        display: flex;
        overflow: hidden;
        position: relative;
    }

    .sidebar-container {
        flex-shrink: 0;
        height: 100%;
        position: relative;
        z-index: 10;
        transition: opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1), 
                    transform 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                    visibility 0.3s;
        transform: translateX(0);
        opacity: 1;
        visibility: visible;
    }

    .sidebar-container:not(.visible) {
        opacity: 0;
        transform: translateX(-20px);
        visibility: hidden;
    }
</style>
