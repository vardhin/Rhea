<script>
    import favicon from '$lib/assets/favicon.svg';
    import '../app.css';

    let { children } = $props();
</script>

<svelte:head>
    <link rel="icon" href={favicon} />
    <title>Rhea - Advanced LLM Chat</title>
</svelte:head>

<div class="app">
    {@render children?.()}
</div>

<style>
    :global(body) {
        margin: 0;
        padding: 0;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        background: var(--bg-primary);
        color: var(--text-primary);
    }

    .app {
        height: 100vh;
        overflow: hidden;
    }
</style>
