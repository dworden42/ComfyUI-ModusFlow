import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

app.registerExtension({
	name: "ModusFlow.ImageForPrompting.Widgets",

	async beforeRegisterNodeDef(nodeType, nodeData, app) {
		if (nodeData.name === "ImageForPrompting") {
			const onNodeCreated = nodeType.prototype.onNodeCreated;

			nodeType.prototype.onNodeCreated = function () {
				onNodeCreated?.apply(this, arguments);

				const node = this;
				const modelWidget = node.widgets.find((w) => w.name === "model");
				const imageWidget = node.widgets.find((w) => w.name === "image_or_folder");

				// --- Refresh Button Logic ---
				if (modelWidget && imageWidget) {
					const refreshCallback = async (button) => {
						const originalName = button.name;
						button.name = "🔄 Refreshing...";
						button.disabled = true;

						try {
							const modelPromise = api.fetchApi(`/modusflow/refresh_ollama_models`).then(r => r.json());
							const imagePromise = api.fetchApi(`/modusflow/refresh_input_files`).then(r => r.json());

							const [modelJson, imageJson] = await Promise.all([modelPromise, imagePromise]);

							if (modelJson.success && Array.isArray(modelJson.data)) {
								const models = modelJson.data;
								const currentValue = modelWidget.value;
								modelWidget.options.values = models;
								if (models.includes(currentValue)) {
									modelWidget.value = currentValue;
								}
							} else {
								alert(`Error refreshing Ollama models: ${modelJson.message || 'Unknown error'}`);
							}

							if (imageJson.success && Array.isArray(imageJson.data)) {
								const images = imageJson.data;
								const currentValue = imageWidget.value;
								imageWidget.options.values = images;
								if (images.includes(currentValue)) {
									imageWidget.value = currentValue;
								}
							} else {
								alert(`Error refreshing image list: ${imageJson.message || 'Unknown error'}`);
							}

						} catch (error) {
							alert("Error refreshing widgets. Check console for details.");
						} finally {
							button.name = originalName;
							button.disabled = false;
						}
					};

					const refreshButton = node.addWidget("button", "🔄 Refresh Lists", null, refreshCallback);
					refreshButton.options = { serialize: false };
				}

				// --- Input Connection Logic ---
				// This logic prevents validation errors when an image is connected, overriding the dropdown.
				const updateWidgetState = () => {
					const imageInput = node.inputs.find(i => i.name === "image");
					if (imageWidget && imageInput) {
						const isConnected = imageInput.link !== null && imageInput.link !== undefined;
						
						// Disable the widget to provide a visual cue that it's being ignored.
						if (imageWidget.inputEl) {
							imageWidget.inputEl.disabled = isConnected;
						}

						// If connected, and the current value is invalid, reset it to prevent validation errors.
						if (isConnected) {
							const options = imageWidget.options.values || [];
							if (options.length > 0 && !options.includes(imageWidget.value)) {
								imageWidget.value = options[0];
							}
						}
					}
				};

				// Hijack onConnectionsChange to respond to connection events.
				const onConnectionsChange = nodeType.prototype.onConnectionsChange;
				nodeType.prototype.onConnectionsChange = function(type, index, connected, link_info) {
					onConnectionsChange?.apply(this, arguments);
					updateWidgetState();
				};

				// Ensure the state is correct on initial node creation/load.
				// Use a timeout to ensure widgets are fully initialized.
				setTimeout(updateWidgetState, 0);

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

				// --- UI Toggling for Dimension Override ---
				const overrideWidget = node.widgets.find(w => w.name === "override_dimensions");
				const widthOverrideWidget = node.widgets.find(w => w.name === "width");
				const heightOverrideWidget = node.widgets.find(w => w.name === "height");

				const toggleOverrideWidgets = () => {
					if (!overrideWidget || !widthOverrideWidget || !heightOverrideWidget) return;

					const isOverriding = overrideWidget.value === "on";
					const widgetsToToggle = [widthOverrideWidget, heightOverrideWidget];

					widgetsToToggle.forEach(widget => {
						if (widget.inputEl) {
							widget.inputEl.disabled = !isOverriding;
							widget.inputEl.style.opacity = isOverriding ? 1.0 : 0.5;
						}
					});
				};

				if (overrideWidget) {
					const originalCallback = overrideWidget.callback;
					overrideWidget.callback = function() {
						originalCallback?.apply(this, arguments);
						toggleOverrideWidgets();
					};
				}
				setTimeout(toggleOverrideWidgets, 0); // Initial state check
			};
		}
	},
});