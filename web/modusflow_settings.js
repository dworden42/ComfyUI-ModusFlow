import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

/**
 * ModusFlow Settings Extension
 * Integrates ModusFlow configuration directly into ComfyUI's native Settings panel.
 */

app.registerExtension({
    name: "ModusFlow.Settings",

    async setup() {
        if (!app.ui?.settings?.addSetting) {
            return;
        }

        // Fetch current configuration from backend
        let serverConfig = {
            ollama_url: "http://127.0.0.1:11434",
            ollama_timeout: 120,
            civitai_api_key: "",
            prompts_save_directory: ""
        };

        try {
            const resp = await api.fetchApi("/modusflow/get_config");
            if (resp.ok) {
                const res = await resp.json();
                if (res.success && res.data) {
                    serverConfig = Object.assign(serverConfig, res.data);
                }
            }
        } catch (e) {
            console.warn("[ModusFlow Settings] Could not fetch server config:", e);
        }

        // Debounced saver to prevent rapid POST spam during typing
        let saveTimeout = null;
        const pendingChanges = {};

        const commitChanges = async () => {
            const payload = Object.assign({}, pendingChanges);
            for (const k of Object.keys(pendingChanges)) {
                delete pendingChanges[k];
            }
            try {
                await api.fetchApi("/modusflow/save_config", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
            } catch (err) {
                console.error("[ModusFlow Settings] Failed to save config to server:", err);
            }
        };

        const queueSave = (key, val) => {
            pendingChanges[key] = val;
            if (saveTimeout) {
                clearTimeout(saveTimeout);
            }
            saveTimeout = setTimeout(commitChanges, 400);
        };

        // 1. Ollama Server URL
        app.ui.settings.addSetting({
            id: "ModusFlow.OllamaURL",
            category: ["ModusFlow", "Server & API", "OllamaURL"],
            name: "ModusFlow: Ollama Server URL",
            type: "text",
            defaultValue: serverConfig.ollama_url || "http://127.0.0.1:11434",
            tooltip: "Endpoint for local Ollama instance (default: http://127.0.0.1:11434)",
            sortOrder: 30,
            onChange: (newVal, oldVal) => {
                if (newVal !== undefined && oldVal !== undefined && newVal !== oldVal) {
                    queueSave("ollama_url", newVal);
                }
            }
        });

        // 2. Ollama Request Timeout
        app.ui.settings.addSetting({
            id: "ModusFlow.OllamaTimeout",
            category: ["ModusFlow", "Server & API", "OllamaTimeout"],
            name: "ModusFlow: Ollama Timeout (seconds)",
            type: "number",
            defaultValue: serverConfig.ollama_timeout || 120,
            tooltip: "Timeout in seconds for Ollama requests (default: 120)",
            sortOrder: 20,
            onChange: (newVal, oldVal) => {
                if (newVal !== undefined && oldVal !== undefined && newVal !== oldVal) {
                    queueSave("ollama_timeout", Number(newVal) || 120);
                }
            }
        });

        // 3. Civitai API Key
        app.ui.settings.addSetting({
            id: "ModusFlow.CivitaiKey",
            category: ["ModusFlow", "Server & API", "CivitaiKey"],
            name: "ModusFlow: Civitai API Key",
            type: "text",
            defaultValue: serverConfig.civitai_api_key || "",
            tooltip: "API key for fetching Civitai LoRA preview images and metadata",
            sortOrder: 10,
            onChange: (newVal, oldVal) => {
                if (newVal !== undefined && oldVal !== undefined && newVal !== oldVal) {
                    queueSave("civitai_api_key", newVal);
                }
            }
        });

        // 4. Prompts Save Directory Override
        app.ui.settings.addSetting({
            id: "ModusFlow.PromptsSaveDirectory",
            category: ["ModusFlow", "Storage", "PromptsSaveDirectory"],
            name: "ModusFlow: Prompts Directory Override",
            type: "text",
            defaultValue: serverConfig.prompts_save_directory || "",
            tooltip: "Custom directory to save prompt JSON files. Leave empty for default: BASE_DIR/saved_prompts",
            sortOrder: 10,
            onChange: (newVal, oldVal) => {
                if (newVal !== undefined && oldVal !== undefined && newVal !== oldVal) {
                    queueSave("prompts_save_directory", newVal);
                }
            }
        });
    }
});
