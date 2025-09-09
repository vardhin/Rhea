<script>
    import { onMount } from "svelte";
    import { Plus, MessageCircle, Settings, Shield, Code } from "lucide-svelte";
    import {
        ollamaStore,
        conversationStore,
        ollamaActions,
        conversationActions,
        sidebarStore,
    } from "$lib/stores/ollama.js";
    //import './sidebar.css';

    let { expanded = $bindable(), currentView = $bindable() } = $props();
    let isLoading = $state(false);

    const navigationItems = [
        { id: "chat", label: "Chat", icon: MessageCircle },
        { id: "settings", label: "Settings", icon: Settings },
        { id: "models", label: "Models", icon: Shield },
        { id: "functions", label: "Functions", icon: Code },
    ];

    onMount(async () => {
        // Initialize connection and load data
        await ollamaActions.checkConnection();
    });

    async function selectModel(modelName) {
        try {
            isLoading = true;
            await ollamaActions.selectModel(modelName);
        } catch (error) {
            console.error("Failed to select model:", error);
        } finally {
            isLoading = false;
        }
    }

    async function newChat() {
        try {
            const newConv = await conversationActions.create(
                "New Chat",
                $ollamaStore.selectedModel,
            );
            currentView = "chat";
        } catch (error) {
            console.error("Failed to create new chat:", error);
        }
    }

    function selectView(viewId) {
        if (!expanded) {
            expanded = true;
            currentView = viewId;
        } else if (currentView === viewId) {
            expanded = false;
        } else {
            currentView = viewId;
        }
    }

    function toggleExpanded() {
        expanded = !expanded;
    }

    async function selectConversation(conversationId) {
        try {
            await conversationActions.select(conversationId);
            currentView = "chat";
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

    async function toggleTool(toolName) {
        const currentStore = $ollamaStore;
        const selectedTools = currentStore.tools.selected.map((tool) =>
            tool.function ? tool.function.name : tool,
        );

        let newSelection;
        if (selectedTools.includes(toolName)) {
            // Remove tool
            newSelection = selectedTools.filter((name) => name !== toolName);
        } else {
            // Add tool
            newSelection = [...selectedTools, toolName];
        }

        try {
            await ollamaActions.selectTools(newSelection);
        } catch (error) {
            console.error("Failed to toggle tool:", error);
        }
    }

    async function toggleThinkingMode() {
        const currentMode = $ollamaStore.thinkingMode;
        try {
            await ollamaActions.setThinkingMode(
                !currentMode.enabled,
                currentMode.level,
            );
        } catch (error) {
            console.error("Failed to toggle thinking mode:", error);
        }
    }

    async function setReasoningLevel(level) {
        const currentMode = $ollamaStore.thinkingMode;
        try {
            await ollamaActions.setThinkingMode(
                currentMode.enabled,
                parseInt(level),
            );
        } catch (error) {
            console.error("Failed to set reasoning level:", error);
        }
    }

    // Handle clicks outside the sidebar to contract (but don't hide completely)
    function handleDocumentClick(event) {
        const sidebar = event.target.closest(".sidebar-container");
        if (!sidebar && expanded) {
            expanded = false;
            sidebarStore.update((store) => ({ ...store, expanded: false }));
        }
    }

    // Watch for sidebar visibility changes to trigger exit animation
    let visible = $state(true);
    let isAnimatingOut = $state(false);
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
                        {#if isLoading}
                            <div class="loading-indicator">
                                Loading conversations...
                            </div>
                        {:else if $conversationStore.conversations.length > 0}
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
                                                {new Date(
                                                    conversation.timestamp,
                                                ).toLocaleString()}
                                            </div>
                                            <div class="conversation-model">
                                                {conversation.model ||
                                                    "No model"}
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
                {:else if currentView === "settings"}
                    <!-- Settings View -->
                    <div class="settings-panel">
                        <h3 class="section-title">Connection Settings</h3>
                        <div class="settings-content">
                            <div class="setting-item">
                                <label>Connection Status</label>
                                <div
                                    class="status-indicator"
                                    class:connected={$ollamaStore.isConnected}
                                >
                                    {$ollamaStore.isConnected
                                        ? "Connected"
                                        : "Disconnected"}
                                </div>
                            </div>
                            <div class="setting-item">
                                <label>FastAPI Server</label>
                                <span>{$ollamaStore.serverUrl}</span>
                            </div>
                            <div class="setting-item">
                                <label>Ollama Server</label>
                                <span>{$ollamaStore.ollamaUrl}</span>
                            </div>
                        </div>

                        <h3 class="section-title">Model Parameters</h3>
                        <div class="settings-content">
                            <div class="setting-item">
                                <label for="temperature">Temperature</label>
                                <input
                                    id="temperature"
                                    type="range"
                                    min="0"
                                    max="2"
                                    step="0.1"
                                    value={$ollamaStore.parameters
                                        ?.temperature || 0.7}
                                    on:input={(e) => {
                                        const newParams = {
                                            ...$ollamaStore.parameters,
                                            temperature: parseFloat(
                                                e.target.value,
                                            ),
                                        };
                                        ollamaActions.updateParameters(
                                            newParams,
                                        );
                                    }}
                                />
                                <span
                                    >{$ollamaStore.parameters?.temperature ||
                                        0.7}</span
                                >
                            </div>
                            <div class="setting-item">
                                <label for="num_ctx">Context Size</label>
                                <select
                                    id="num_ctx"
                                    value={$ollamaStore.parameters?.num_ctx ||
                                        2048}
                                    on:change={(e) => {
                                        const newParams = {
                                            ...$ollamaStore.parameters,
                                            num_ctx: parseInt(e.target.value),
                                        };
                                        ollamaActions.updateParameters(
                                            newParams,
                                        );
                                    }}
                                >
                                    {#each Object.entries($ollamaStore.constants.contextSizes) as [size, label]}
                                        <option value={parseInt(size)}
                                            >{label}</option
                                        >
                                    {/each}
                                </select>
                            </div>
                            <div class="setting-item">
                                <label for="top_p">Top P</label>
                                <input
                                    id="top_p"
                                    type="range"
                                    min="0"
                                    max="1"
                                    step="0.05"
                                    value={$ollamaStore.parameters?.top_p ||
                                        0.9}
                                    on:input={(e) => {
                                        const newParams = {
                                            ...$ollamaStore.parameters,
                                            top_p: parseFloat(e.target.value),
                                        };
                                        ollamaActions.updateParameters(
                                            newParams,
                                        );
                                    }}
                                />
                                <span
                                    >{$ollamaStore.parameters?.top_p ||
                                        0.9}</span
                                >
                            </div>
                        </div>

                        <h3 class="section-title">System Message</h3>
                        <div class="settings-content">
                            <div class="setting-item">
                                <label>Presets</label>
                                <select
                                    on:change={(e) =>
                                        ollamaActions.selectSystemPreset(
                                            e.target.value,
                                        )}
                                >
                                    <option value="">Select a preset...</option>
                                    {#each $ollamaStore.systemPresets as preset}
                                        <option value={preset.name}
                                            >{preset.name}</option
                                        >
                                    {/each}
                                </select>
                            </div>
                            <div class="setting-item full-width">
                                <label for="system-message"
                                    >Custom System Message</label
                                >
                                <textarea
                                    id="system-message"
                                    bind:value={$ollamaStore.systemMessage}
                                    on:input={(e) =>
                                        ollamaActions.updateSystemMessage(
                                            e.target.value,
                                        )}
                                    rows="3"
                                    placeholder="Enter your custom system message..."
                                ></textarea>
                            </div>
                        </div>
                    </div>
                {:else if currentView === "models"}
                    <!-- Models View -->
                    <div class="models-panel">
                        <h3 class="section-title">Available Models</h3>
                        {#if isLoading}
                            <div class="loading-indicator">
                                Loading models...
                            </div>
                        {:else if $ollamaStore.models.length > 0}
                            <div class="models-content">
                                {#each $ollamaStore.models as model}
                                    <div
                                        class="model-item"
                                        class:selected={model.model ===
                                            $ollamaStore.selectedModel}
                                    >
                                        <div class="model-info">
                                            <div class="model-name">
                                                {model.model}
                                            </div>
                                            <div class="model-details">
                                                <span class="model-size"
                                                    >{model.details
                                                        ?.parameter_size ||
                                                        "Unknown size"}</span
                                                >
                                                <span class="model-modified">
                                                    {model.modified_at
                                                        ? new Date(
                                                              model.modified_at,
                                                          ).toLocaleDateString()
                                                        : "Unknown date"}
                                                </span>
                                            </div>
                                        </div>
                                        <div class="model-actions">
                                            <button
                                                class="select-model-btn"
                                                class:active={model.model ===
                                                    $ollamaStore.selectedModel}
                                                on:click={() =>
                                                    selectModel(model.model)}
                                                disabled={isLoading}
                                            >
                                                {model.model ===
                                                $ollamaStore.selectedModel
                                                    ? "Selected"
                                                    : "Select"}
                                            </button>
                                        </div>
                                    </div>
                                {/each}
                            </div>
                        {:else}
                            <div class="empty-state">
                                <p>No models available.</p>
                                <p>Pull a model from Ollama first.</p>
                            </div>
                        {/if}

                        {#if $ollamaStore.selectedModel && $ollamaStore.modelInfo}
                            <div class="model-info-panel">
                                <h3 class="section-title">Model Details</h3>
                                <div class="model-details-content">
                                    <div class="detail-item">
                                        <label>Name</label>
                                        <span
                                            >{$ollamaStore.modelInfo.details
                                                ?.family || "Unknown"}</span
                                        >
                                    </div>
                                    <div class="detail-item">
                                        <label>Parameters</label>
                                        <span
                                            >{$ollamaStore.modelInfo.details
                                                ?.parameter_size ||
                                                "Unknown"}</span
                                        >
                                    </div>
                                    <div class="detail-item">
                                        <label>Quantization</label>
                                        <span
                                            >{$ollamaStore.modelInfo.details
                                                ?.quantization_level ||
                                                "Unknown"}</span
                                        >
                                    </div>
                                </div>
                            </div>
                        {/if}
                    </div>
                {:else if currentView === "functions"}
                    <!-- Functions View -->
                    <div class="functions-panel">
                        <h3 class="section-title">Available Tools</h3>
                        {#if Object.keys($ollamaStore.tools.available).length > 0}
                            <div class="functions-content">
                                {#each Object.entries($ollamaStore.tools.available) as [toolName, toolDef]}
                                    {@const isSelected =
                                        $ollamaStore.tools.selected.some(
                                            (selected) =>
                                                (typeof selected === "string" &&
                                                    selected === toolName) ||
                                                (typeof selected === "object" &&
                                                    selected.function?.name ===
                                                        toolName),
                                        )}
                                    {@const functionInfo =
                                        toolDef.function || toolDef}
                                    <div class="function-item">
                                        <div class="function-info">
                                            <div class="function-name">
                                                {functionInfo.name || toolName}
                                            </div>
                                            <div class="function-description">
                                                {functionInfo.description ||
                                                    "No description available"}
                                            </div>
                                            {#if functionInfo.parameters?.properties}
                                                <div
                                                    class="function-parameters"
                                                >
                                                    <small
                                                        >Parameters: {Object.keys(
                                                            functionInfo
                                                                .parameters
                                                                .properties,
                                                        ).join(", ")}</small
                                                    >
                                                </div>
                                            {/if}
                                        </div>
                                        <div class="function-toggle">
                                            <input
                                                type="checkbox"
                                                checked={isSelected}
                                                on:change={() =>
                                                    toggleTool(toolName)}
                                            />
                                        </div>
                                    </div>
                                {/each}
                            </div>
                        {:else}
                            <div class="loading-indicator">
                                Loading tools...
                            </div>
                        {/if}

                        <h3 class="section-title">Enhanced Reasoning</h3>
                        <div class="thinking-mode-content">
                            <div class="function-item">
                                <div class="function-info">
                                    <div class="function-name">
                                        GPT-OSS Thinking Mode
                                    </div>
                                    <div class="function-description">
                                        Enable step-by-step reasoning for
                                        compatible models (GPT-OSS series)
                                    </div>
                                </div>
                                <div class="function-toggle">
                                    <input
                                        type="checkbox"
                                        checked={$ollamaStore.thinkingMode
                                            .enabled}
                                        on:change={toggleThinkingMode}
                                    />
                                </div>
                            </div>

                            {#if $ollamaStore.thinkingMode.enabled}
                                <div class="reasoning-level">
                                    <label>Reasoning Depth</label>
                                    <select
                                        bind:value={
                                            $ollamaStore.thinkingMode.level
                                        }
                                        on:change={(e) =>
                                            setReasoningLevel(e.target.value)}
                                    >
                                        <option value={1}
                                            >Level 1 - Basic</option
                                        >
                                        <option value={2}
                                            >Level 2 - Detailed</option
                                        >
                                        <option value={3}>Level 3 - Deep</option
                                        >
                                    </select>
                                </div>
                            {/if}
                        </div>
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
        transition:
            width 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94),
            border-radius 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94);
    }

    /* Contract transition */
    .sidebar-container:not(.expanded) {
        transition:
            width 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94),
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
        transition:
            opacity 0.3s ease-out,
            transform 0.3s ease-out;
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
        transition:
            opacity 0.3s ease-out 0.2s,
            transform 0.3s ease-out 0.2s;
    }

    /* Hide content immediately when contracting */
    .sidebar-container:not(.expanded) .sidebar-content-wrapper {
        opacity: 0;
        transform: translateX(-10px);
        transition:
            opacity 0.2s ease-out,
            transform 0.2s ease-out;
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

    .function-parameters {
        margin-top: 4px;
        color: var(--text-muted, #9ca3af);
        font-size: 11px;
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
</style>
