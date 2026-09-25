import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

/**
 * This extension adds a "Refresh" button to the OllamaPromptRefiner node
 * to allow dynamic reloading of the available Ollama models.
 */
app.registerExtension({
	name: "ModusFlow.OllamaPromptRefiner.Widgets",

	async beforeRegisterNodeDef(nodeType, nodeData, app) {
		// We only want to modify the "OllamaPromptRefiner" node
		if (nodeData.name === "OllamaPromptRefiner") {
			// Get the original onNodeCreated function to extend it
			const onNodeCreated = nodeType.prototype.onNodeCreated;

			nodeType.prototype.onNodeCreated = function () {
				// Call the original function
				onNodeCreated?.apply(this, arguments);

				// The `ollama_url` widget is removed, so we don't need to find it.
				const modelWidget = this.widgets.find((w) => w.name === "ollama_model");

				if (!modelWidget) {
					// Don't return here, we still want to set up the bypass UI toggling
				}

				// Define the callback function for the button
				const refreshCallback = async (button) => {
					const originalName = button.name;
					button.name = "🔄 Refreshing...";
					button.disabled = true;

					try {
						const ollama_url_widget = this.widgets.find(w => w.name === "ollama_url");
						// The URL is no longer a direct widget. We have to assume the backend has the right one.
						const params = new URLSearchParams(); // No URL needed, backend uses config
						const response = await api.fetchApi(`/modusflow/refresh_ollama_models?${params}`);

						if (response.success && Array.isArray(response.data)) {
							const models = response.data;
							if (modelWidget) {
								modelWidget.options.values = models;
								if (!models.includes(modelWidget.value)) {
									modelWidget.value = models[0] || "";
								}
							}
						} else {
							alert(`Error refreshing Ollama models: ${response.message || 'Unknown error'}`);
						}
					} catch (error) {
						alert("Error refreshing Ollama models. Check console for details.");
					} finally {
						button.name = originalName;
						button.disabled = false;
					}
				};

				// Add the button widget
				const refreshButton = this.addWidget("button", "🔄 Refresh", null, refreshCallback);
				refreshButton.options = { serialize: false }; // Don't save the button state

				// --- UI Toggling for Bypass --- 
				const node = this;
				const refinerStatusWidget = node.widgets.find(w => w.name === "refiner_status");

				if (!refinerStatusWidget) {
					return;
				}

				const widgetsToToggle = [
					"mode",
					"ollama_model",
					"refine_mode_system_prompt",
					"generate_mode_system_prompt",
					"pose_reference_system_prompt",
					"temperature",
					"max_tokens",
					"image_usage",
					"🔄 Refresh"
				].map(name => node.widgets.find(w => w.name === name)).filter(Boolean);

				// Function to toggle widget visibility
				const toggleOllamaWidgets = () => {
					const isBypassed = refinerStatusWidget.value === "bypassed";

					widgetsToToggle.forEach(widget => {
						if (!widget.originalType) {
							widget.originalType = widget.type;
						}
						widget.type = isBypassed ? "hidden" : widget.originalType;
					});

					node.computeSize();
					node.setDirtyCanvas(true, true);
				};

				// Wrap the callback for refiner_status to toggle widgets on change
				const originalCallback = refinerStatusWidget.callback;
				refinerStatusWidget.callback = function() {
					originalCallback?.apply(this, arguments);
					toggleOllamaWidgets();
				};

				// Initial toggle on node creation
				setTimeout(toggleOllamaWidgets, 0);

				// --- Sync Widget Values on Load ---
				// This ensures that when a workflow is loaded, the UI elements (like textareas)
				// correctly display the values stored in the workflow's JSON data.
				const syncWidgetValues = () => {
					node.widgets.forEach(widget => {
						if (widget.inputEl && widget.inputEl.value !== widget.value) {
							widget.inputEl.value = widget.value;
						}
					});
				};
				// Use a timeout to ensure all widgets and their inputEl are created before syncing.
				setTimeout(syncWidgetValues, 0);

				// --- UI Toggling for Latent Input ---
				const latentInput = node.inputs.find(i => i.name === "latent");
				const widthWidget = node.widgets.find(w => w.name === "width");
				const heightWidget = node.widgets.find(w => w.name === "height");
				const useImageDimWidget = node.widgets.find(w => w.name === "use_image_dimensions");

				// Store the function on the node instance so onConnectionsChange can access it
				this.updateLatentWidgetState = () => {
					const isConnected = latentInput && (latentInput.link !== null && latentInput.link !== undefined);
					const widgets = [widthWidget, heightWidget, useImageDimWidget].filter(Boolean);
					
					widgets.forEach(widget => {
						// For standard text/number/combo inputs which have an inputEl
						if (widget.inputEl) {
							widget.inputEl.disabled = isConnected;
							widget.inputEl.style.opacity = isConnected ? 0.5 : 1.0;
						}
					});
				};

				// Initial state check
				setTimeout(() => this.updateLatentWidgetState(), 0);
			};

			// Hijack onConnectionsChange on the prototype to update widget state
			const onConnectionsChange = nodeType.prototype.onConnectionsChange;
			nodeType.prototype.onConnectionsChange = function(type, index, connected, link_info) {
				onConnectionsChange?.apply(this, arguments);

				// Check if our custom state update function exists on the instance and call it
				if (this.updateLatentWidgetState) {
					this.updateLatentWidgetState();
				}
			};
		}
		// Inject CSS to make all textareas resizable
		if (!document.getElementById('modusflow-resize-textarea-style')) {
			const style = document.createElement('style');
			style.id = 'modusflow-resize-textarea-style';
			style.innerHTML = `
				textarea {
					resize: both !important;
					min-height: 40px;
					min-width: 120px;
				}
			`;
			document.head.appendChild(style);
		}
	},
});