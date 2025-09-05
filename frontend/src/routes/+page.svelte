<script>
    import Navbar from '$lib/components/Navbar.svelte';
    import Sidebar from '$lib/components/Sidebar.svelte';
    import ChatWindow from '$lib/components/ChatWindow.svelte';
    import { sidebarStore } from '$lib/stores/ui.js';
    import { themeStore } from '$lib/stores/theme.js';

    let sidebarExpanded = $state(false);
    let currentView = $state('chat'); // chat, settings, models, functions

    // Subscribe to stores
    $effect(() => {
        sidebarExpanded = $sidebarStore.expanded;
    });
</script>

<div class="main-container" data-theme={$themeStore.currentTheme}>
    <Navbar />
    
    <div class="content-container">
        <Sidebar 
            bind:expanded={sidebarExpanded}
            bind:currentView={currentView}
        />
        
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
    }

    .content-container {
        flex: 1;
        display: flex;
        overflow: hidden;
    }
</style>
