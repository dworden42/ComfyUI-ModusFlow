import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

// Track all ModusFlowLoraLoader nodes for refresh
const loraLoaderNodes = new Set();

// Hook into ComfyUI's refresh mechanism
const originalRefresh = api.refresh;
api.refresh = async function() {
    const result = await originalRefresh.call(this);
    
    // Refresh all LoRA loader nodes after model refresh
    for (const node of loraLoaderNodes) {
        if (node.refreshLoraList) {
            node.refreshLoraList();
        }
    }
    
    return result;
};

// Also hook into folder_paths refresh if available
if (window.app && window.app.refreshComboInNodes) {
    const originalRefreshCombo = window.app.refreshComboInNodes;
    window.app.refreshComboInNodes = function() {
        const result = originalRefreshCombo.apply(this, arguments);
        
        // Refresh LoRA nodes when combo boxes are refreshed
        for (const node of loraLoaderNodes) {
            if (node.refreshLoraList) {
                node.refreshLoraList();
            }
        }
        
        return result;
    };
}

// Listen for 'R' key press events specifically
document.addEventListener('keydown', function(e) {
    if (e.key === 'r' || e.key === 'R') {
        // Small delay to allow ComfyUI's refresh to complete first
        setTimeout(() => {
            for (const node of loraLoaderNodes) {
                if (node.refreshLoraList) {
                    node.refreshLoraList();
                }
            }
        }, 100);
    }
});

/**
 * Creates a new DOM element.
 * @param {string} tag The tag name of the element.
 * @param {object} attrs Attributes to set on the element.
 * @param  {...any} children Child elements or text to append.
 * @returns {HTMLElement}
 */
function createElement(tag, attrs = {}, ...children) {
    const el = document.createElement(tag);
    const { dataset, ...otherAttrs } = attrs;
    Object.assign(el, otherAttrs);
    if (dataset) {
        Object.assign(el.dataset, dataset);
    }
    for (const child of children) {
        el.append(child);
    }
    return el;
}

/**
 * Creates a searchable dropdown component with the search bar inside the dropdown.
 * @param {string[]} loras The list of all available LoRA names to search through.
 * @param {string} selectedValue The currently selected LoRA name.
 * @param {(newValue: string) => void} onChange Callback function when a new LoRA is selected.
 * @returns {HTMLElement} The container element for the searchable dropdown.
 */
function createSearchableDropdown(loras, selectedValue, onChange, globalFilter = "") {
    const container = createElement("div", { className: "modusflow-lora-search-container" });

    const display = createElement("div", {
        className: "modusflow-lora-select-display",
        textContent: selectedValue || "Select a LoRA...",
        title: selectedValue,
    });

    let activeDropdown = null;

    const closeDropdown = () => {
        if (activeDropdown) {
            activeDropdown.remove();
            activeDropdown = null;
            window.removeEventListener("click", handleGlobalClick, true);
            window.removeEventListener("contextmenu", handleGlobalClick, true);
        }
    };

    const handleGlobalClick = (e) => {
        if (activeDropdown && !activeDropdown.contains(e.target) && e.target !== display) {
            closeDropdown();
        }
    };

    const openDropdown = () => {
        if (activeDropdown) {
            closeDropdown();
            return;
        }

        const dropdown = createElement("div", { className: "modusflow-lora-search-dropdown" });
        const searchInput = createElement("input", {
            type: "text",
            className: "modusflow-lora-search-input-internal",
            placeholder: "Search LoRAs...",
        });
        const itemsContainer = createElement("div", { className: "modusflow-lora-search-items-container" });

        // Virtualized rendering: only render items that are visible or near-visible
        const ITEM_HEIGHT = 24; // Approximate height of each item in pixels
        const RENDER_BUFFER = 10; // Number of extra items to render above/below viewport
        let currentFilter = "";
        let filteredLoras = [];
        let renderedRange = { start: 0, end: 0 };

        function populateDropdown(internalFilter = "") {
            currentFilter = internalFilter;
            const globallyFiltered = loras.filter(l => l.toLowerCase().includes(globalFilter.toLowerCase()));
            filteredLoras = globallyFiltered.filter(l => l.toLowerCase().includes(internalFilter.toLowerCase()));

            if (filteredLoras.length === 0) {
                itemsContainer.innerHTML = `<div class="modusflow-lora-search-item-none">No matches found</div>`;
                return;
            }

            // For small lists (< 100 items), render everything at once (faster than virtualization overhead)
            if (filteredLoras.length < 100) {
                renderAllItems();
            } else {
                // For large lists, use virtualization
                setupVirtualization();
            }
        }

        function renderAllItems() {
            const fragment = document.createDocumentFragment();
            filteredLoras.forEach(loraName => {
                const item = createElement("div", {
                    className: "modusflow-lora-search-item",
                    textContent: loraName,
                    title: loraName,
                });
                item.addEventListener("mousedown", (e) => {
                    e.preventDefault();
                    display.textContent = loraName;
                    display.title = loraName;
                    onChange(loraName);
                    closeDropdown();
                });
                fragment.appendChild(item);
            });
            itemsContainer.innerHTML = "";
            itemsContainer.appendChild(fragment);
        }

        function setupVirtualization() {
            // Create a spacer to maintain scroll height
            const totalHeight = filteredLoras.length * ITEM_HEIGHT;
            itemsContainer.innerHTML = "";
            itemsContainer.style.position = "relative";
            itemsContainer.style.height = `${totalHeight}px`;

            const viewport = createElement("div", { 
                className: "modusflow-lora-viewport",
                style: "position: absolute; top: 0; left: 0; right: 0;"
            });
            itemsContainer.appendChild(viewport);

            function renderVisibleItems() {
                const scrollTop = itemsContainer.scrollTop;
                const containerHeight = itemsContainer.clientHeight;
                
                const startIndex = Math.max(0, Math.floor(scrollTop / ITEM_HEIGHT) - RENDER_BUFFER);
                const endIndex = Math.min(
                    filteredLoras.length,
                    Math.ceil((scrollTop + containerHeight) / ITEM_HEIGHT) + RENDER_BUFFER
                );

                // Only re-render if the range changed significantly
                if (startIndex === renderedRange.start && endIndex === renderedRange.end) {
                    return;
                }

                renderedRange = { start: startIndex, end: endIndex };

                const fragment = document.createDocumentFragment();
                for (let i = startIndex; i < endIndex; i++) {
                    const loraName = filteredLoras[i];
                    const item = createElement("div", {
                        className: "modusflow-lora-search-item",
                        textContent: loraName,
                        title: loraName,
                        style: `position: absolute; top: ${i * ITEM_HEIGHT}px; left: 0; right: 0;`
                    });
                    item.addEventListener("mousedown", (e) => {
                        e.preventDefault();
                        display.textContent = loraName;
                        display.title = loraName;
                        onChange(loraName);
                        closeDropdown();
                    });
                    fragment.appendChild(item);
                }

                viewport.innerHTML = "";
                viewport.appendChild(fragment);
            }

            renderVisibleItems();
            itemsContainer.addEventListener("scroll", renderVisibleItems);
        }

        // Debounce search input to avoid re-rendering on every keystroke
        let searchTimeout;
        searchInput.addEventListener("input", () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => populateDropdown(searchInput.value), 150);
        });

        dropdown.append(searchInput, itemsContainer);
        document.body.appendChild(dropdown);
        activeDropdown = dropdown;

        const rect = display.getBoundingClientRect();
        dropdown.style.left = `${rect.left}px`;
        dropdown.style.top = `${rect.bottom + 2}px`;
        dropdown.style.minWidth = `${rect.width}px`;
        dropdown.style.display = "flex";

        populateDropdown("");
        searchInput.value = "";
        setTimeout(() => searchInput.focus(), 0);

        setTimeout(() => {
            window.addEventListener("click", handleGlobalClick, true);
            window.addEventListener("contextmenu", handleGlobalClick, true);
        }, 0);
    };

    display.addEventListener("click", openDropdown);

    container.append(display);
    return container;
}

/**
 * Creates a number input that can be changed with the mouse wheel.
 * @param {number} initialValue The starting value.
 * @param {number} min The minimum allowed value.
 * @param {number} max The maximum allowed value.
 * @param {number} step The amount to increment/decrement by.
 * @param {(newValue: number) => void} onChange Callback function when the value changes.
 * @returns {HTMLInputElement} The input element.
 */
function createNumberInput(initialValue, min, max, step, onChange) {
    const input = createElement("input", {
        type: "number",
        className: "modusflow-lora-strength-input",
        value: parseFloat(initialValue).toFixed(2),
        min,
        max,
        step,
        title: "Strength (scroll to adjust)"
    });

    const update = () => {
        let value = parseFloat(input.value);
        if (isNaN(value)) value = 0;
        value = Math.max(min, Math.min(max, value)); // Clamp value
        onChange(value);
    };

    input.addEventListener("change", update);
    input.addEventListener("blur", () => {
        // Format to 2 decimal places on blur
        input.value = parseFloat(input.value).toFixed(2);
    });

    input.addEventListener("wheel", (e) => {
        e.preventDefault();
        const direction = e.deltaY > 0 ? -1 : 1;
        let value = parseFloat(input.value) + (direction * step);
        value = Math.max(min, Math.min(max, value));
        input.value = value.toFixed(2);
        onChange(value);
    }, { passive: false });

    return input;
}

/**
 * Creates a CSS-based toggle switch.
 * @param {boolean} initialState The initial on/off state.
 * @param {(newState: boolean) => void} onChange Callback function when the state changes.
 * @returns {{element: HTMLElement, setChecked: (isChecked: boolean) => void}} The label element and a function to update its state.
 */
function createToggleSwitch(initialState, onChange) {
    const label = createElement("label", { className: "modusflow-lora-toggle-switch" });
    const input = createElement("input", { type: "checkbox", checked: initialState });
    const slider = createElement("span", { className: "modusflow-lora-toggle-slider" });

    input.addEventListener("change", () => {
        onChange(input.checked);
    });

    label.append(input, slider);
    
    return {
        element: label,
        setChecked: (isChecked) => {
            if (input.checked !== isChecked) {
                input.checked = isChecked;
            }
        }
    };
}

function createContextMenu(items, event) {
    // Remove any existing context menu
    const existingMenu = document.querySelector(".modusflow-context-menu");
    if (existingMenu) {
        existingMenu.remove();
    }

    const menu = createElement("div", { className: "modusflow-context-menu" });

    items.forEach(item => {
        if (item.isSeparator) {
            menu.appendChild(createElement("div", { className: "modusflow-context-menu-separator" }));
            return;
        }
        const menuItem = createElement("div", { className: "modusflow-context-menu-item", textContent: item.label });
        menuItem.onclick = (e) => {
            e.stopPropagation();
            item.callback();
            menu.remove();
        };
        menu.appendChild(menuItem);
    });

    document.body.appendChild(menu);

    // Position the menu
    menu.style.left = `${event.clientX}px`;
    menu.style.top = `${event.clientY}px`;

    // Close on outside click
    const closeListener = (e) => {
        if (!menu.contains(e.target)) {
            menu.remove();
            window.removeEventListener("click", closeListener);
            window.removeEventListener("contextmenu", closeListener);
        }
    };
    setTimeout(() => {
        window.addEventListener("click", closeListener);
        window.addEventListener("contextmenu", closeListener);
    }, 0);
}

/**
 * Creates a key-value display section.
 * @param {string} key The title/key for the section.
 * @param {HTMLElement} valueElement The element representing the value.
 * @param {boolean} blockLayout If true, the key is displayed as a block above the value.
 * @returns {HTMLElement}
 */
function createKeyValueSection(key, valueElement, blockLayout = false) {
    const subsection = createElement("div", { className: "modusflow-lora-info-subsection" });
    if (blockLayout) {
        subsection.classList.add("modusflow-lora-info-subsection-block");
    }
    const keyEl = createElement("strong", { textContent: `${key}:` });
    subsection.append(keyEl, valueElement);
    return subsection;
}

/**
 * Copies text to the clipboard and provides user feedback on a button.
 * Includes error handling for the modern clipboard API.
 * @param {string} text The text to copy.
 * @param {HTMLElement} button The button element to show feedback on.
 */
function copyTextToClipboard(text, button) {
    // Don't try to copy if there's nothing to copy.
    if (!text) {
        return;
    }

    const showFeedback = (success) => {
        if (!button || !document.body.contains(button)) return;
        const originalText = button.textContent;
        button.textContent = success ? "Copied!" : "Copied!";
        setTimeout(() => {
            if (document.body.contains(button)) {
                button.textContent = originalText;
            }
        }, 1500);
    };

    // Modern, secure method (preferred)
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            showFeedback(true);
        }).catch(err => {
            
            alert("Could not copy text to clipboard. Your browser may have blocked this action. Check the console (F12) for details.");
            showFeedback(false);
        });
    } 
    // Legacy fallback method for non-secure contexts (like HTTP)
    else {
        
        const textArea = document.createElement("textarea");
        textArea.value = text;
        
        // Make the textarea invisible
        textArea.style.position = 'fixed';
        textArea.style.top = '-9999px';
        textArea.style.left = '-9999px';

        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();

        try {
            const successful = document.execCommand('copy');
            if (!successful) throw new Error('execCommand returned false');
            showFeedback(true);
        } catch (err) {
            console.error('[ModusFlow LoRA Loader] Legacy copy command failed:', err);
            alert("Could not copy text. This browser may not support the legacy copy command.");
            showFeedback(false);
        }

        document.body.removeChild(textArea);
    }
}

function showLightbox(imageUrl) {
    const existingLightbox = document.getElementById("modusflow-lora-lightbox");
    if (existingLightbox) {
        existingLightbox.remove();
    }

    const lightbox = createElement("div", { id: "modusflow-lora-lightbox", className: "modusflow-lora-lightbox" });
    const lightboxImage = createElement("img", { 
        src: imageUrl, 
        alt: "Lightbox image",
        onload: () => lightbox.classList.add("modusflow-lora-lightbox-loaded") // Fade in
    });
    const closeHint = createElement("div", { className: "modusflow-lora-lightbox-close-hint", textContent: "Click anywhere to close" });
    
    lightbox.append(lightboxImage, closeHint);
    document.body.appendChild(lightbox);

    lightbox.onclick = () => lightbox.remove();
}

function showInfoModal(loraName, node) {
    // Remove any existing modals
    const existingModal = document.getElementById("modusflow-lora-info-modal");
    if (existingModal) {
        existingModal.remove();
    }

    // --- Create Modal Structure ---
    const modal = createElement("div", { id: "modusflow-lora-info-modal", className: "modusflow-lora-info-modal" });
    const modalContent = createElement("div", { className: "modusflow-lora-info-modal-content" });

    // Create a dedicated header for title and close button
    const header = createElement("div", { className: "modusflow-lora-info-modal-header" });
    const title = createElement("h3", { textContent: `Info for ${loraName}` });
    const closeButton = createElement("span", { className: "modusflow-lora-info-modal-close", textContent: "✖", title: "Close" });
    header.append(title, closeButton);
    
    // Unified layout structure
    const layout = createElement("div", { className: "modusflow-lora-info-layout" });
    const leftCol = createElement("div", { className: "modusflow-lora-info-col-left" });
    const rightCol = createElement("div", { className: "modusflow-lora-info-col-right" });
    layout.append(leftCol, rightCol);
    const statusArea = createElement("div", { className: "modusflow-lora-info-status", textContent: "Fetching info..." });

    modalContent.append(header, statusArea, layout);
    modal.appendChild(modalContent);
    document.body.appendChild(modal);

    // --- Positioning and Close Logic ---
    modal.style.display = "block";
    const closeModal = () => modal.remove();
    closeButton.onclick = closeModal;
    // modal.onclick = (e) => { if (e.target === modal) closeModal(); }; // Removed to prevent closing on outside click

    // --- Draggable Logic ---
    // The new header div is now the drag handle.

    const dragMouseDown = (e) => {
        if (e.button !== 0) return; // Only allow left-click drags
        e.preventDefault();
        let pos3 = e.clientX;
        let pos4 = e.clientY;

        // Switch from transform-based centering to explicit top/left for smooth dragging
        if (modalContent.style.transform !== 'none') {
            const rect = modalContent.getBoundingClientRect();
            modalContent.style.transform = 'none';
            modalContent.style.left = `${rect.left}px`;
            modalContent.style.top = `${rect.top}px`;
            modalContent.style.margin = '0';
        }

        const elementDrag = (e) => {
            e.preventDefault();
            let pos1 = pos3 - e.clientX;
            let pos2 = pos4 - e.clientY;
            pos3 = e.clientX;
            pos4 = e.clientY;
            modalContent.style.top = (modalContent.offsetTop - pos2) + "px";
            modalContent.style.left = (modalContent.offsetLeft - pos1) + "px";
        };

        const closeDragElement = () => {
            document.removeEventListener("mouseup", closeDragElement);
            document.removeEventListener("mousemove", elementDrag);
        };

        document.addEventListener("mouseup", closeDragElement);
        document.addEventListener("mousemove", elementDrag);
    };

    header.addEventListener("mousedown", dragMouseDown);

    // --- Fetch Both Local and Civitai Data Concurrently ---
    const localParams = new URLSearchParams({ name: loraName });
    const localPromise = api.fetchApi(`/modusflow/get_lora_metadata?${localParams}`).then(r => (r.json ? r.json() : r));

    const apiKeyWidget = node.widgets.find(w => w.name === "civitai_api_key");
    const apiKey = apiKeyWidget ? apiKeyWidget.value : "";
    const civitaiParams = new URLSearchParams({ name: loraName });
    if (apiKey && apiKey.trim()) {
        civitaiParams.set("api_key", apiKey.trim());
    }
    const civitaiPromise = api.fetchApi(`/modusflow/get_lora_civitai_info?${civitaiParams}`).then(r => (r.json ? r.json() : r));

    Promise.allSettled([localPromise, civitaiPromise]).then(([localResult, civitaiResult]) => {
        statusArea.style.display = 'none'; // Hide status indicator

        const localData = localResult.status === 'fulfilled' && localResult.value.success ? localResult.value.data : null;
        const civitaiData = civitaiResult.status === 'fulfilled' && civitaiResult.value.success ? civitaiResult.value.data : null;

        // --- Populate Left Column (Image & Links) ---
        const localPreviewUrl = localData?.preview_image_url;
        const civitaiPreviewUrl = civitaiData?.images?.[0];

        if (localPreviewUrl) {
            // The backend now provides a root-relative URL for the preview image (e.g., /view?filename=...).
            // The api.apiURL() function incorrectly prepends "/api" to this, resulting in a broken link.
            // We can use the URL directly as it's already correctly formatted.
            const img = createElement("img", {
                src: localPreviewUrl,
                alt: `Preview for ${loraName}`,
                title: "Click to view larger image",
                style: "cursor: pointer;"
            });
            // The local preview is already the full-size image.
            img.onclick = () => showLightbox(localPreviewUrl);
            leftCol.appendChild(img);
        } else if (civitaiPreviewUrl) {
            // Fallback to showing the first Civitai image here if no local one exists.
            const img = createElement("img", {
                src: civitaiPreviewUrl,
                alt: `Preview for ${loraName}`,
                title: "Click to view larger image",
                style: "cursor: pointer;"
            });
            img.onclick = () => {
                // Request a larger version for the lightbox, similar to the thumbnails.
                const fullSizeUrl = civitaiPreviewUrl.replace(/width=\d+/, 'width=1200');
                showLightbox(fullSizeUrl);
            };
            leftCol.appendChild(img);
        } else {
            leftCol.textContent = "No preview available";
            leftCol.style.cssText = "display: flex; align-items: center; justify-content: center; height: 200px; color: #666; background-color: #222; border-radius: 4px;";
        }

        if (civitaiData?.modelId) {
            const linkSection = createElement("div", { className: "modusflow-lora-info-subsection", style: "text-align: center;" });
            const modelLink = createElement("a", {
                href: `https://civitai.com/models/${civitaiData.modelId}`,
                target: "_blank",
                rel: "noopener noreferrer",
                textContent: `View on Civitai`,
                title: `https://civitai.com/models/${civitaiData.modelId}`
            });
            linkSection.append(modelLink);
            if (civitaiData.creator) {
                linkSection.append(createElement("div", { className: "modusflow-lora-info-creator", textContent: `by ${civitaiData.creator}` }));
            }
            leftCol.appendChild(linkSection);
        }

        // --- Populate Right Column (Details) ---
        const localMeta = localData?.local_metadata || {};
        
        // Per user request, trained words should be pulled from local metadata only.
        let trainedWordsWithCounts = [];
        if (localMeta.ss_tag_frequency) {
            const tagData = localMeta.ss_tag_frequency.img || localMeta.ss_tag_frequency;
            if (tagData && typeof tagData === 'object') {
                trainedWordsWithCounts = Object.entries(tagData)
                    .filter(([tag, count]) => tag.split(' ').length <= 3) // Heuristic to filter out long sentences
                    .map(([tag, count]) => ({ tag, count }));
            }
        } else if (localMeta.ss_activation_text) {
            // Fallback for LoRAs without tag frequency but with activation text
            trainedWordsWithCounts = localMeta.ss_activation_text.split(',')
                .map(t => t.trim())
                .filter(Boolean)
                .map(tag => ({ tag, count: null })); // No count available
        }
        const allTriggers = trainedWordsWithCounts;

        if (allTriggers.length > 0) {
            const valueContainer = createElement("div", { className: "modusflow-lora-info-trigger-container" });
    
            const tagsContainer = createElement("div", { className: "modusflow-lora-info-tags-container" });
            const copySelectedButton = createElement("button", { textContent: "Copy Selected" });

            const updateCopySelectedButtonState = () => {
                const selectedCount = tagsContainer.querySelectorAll(".modusflow-lora-info-tag.selected").length;
                copySelectedButton.disabled = selectedCount === 0;
            };

            allTriggers.forEach(trigger => {
                const tagEl = createElement("span", { 
                    className: "modusflow-lora-info-tag", 
                    title: "Click to select/deselect",
                    dataset: { tag: trigger.tag } // Store raw tag for copying
                });

                const tagText = createElement("span", { className: "modusflow-lora-info-tag-text", textContent: trigger.tag });
                tagEl.appendChild(tagText);

                if (trigger.count !== null && trigger.count !== undefined) {
                    const tagCount = createElement("span", { className: "modusflow-lora-info-tag-count", textContent: trigger.count });
                    tagEl.appendChild(tagCount);
                }

                tagEl.onclick = () => {
                    tagEl.classList.toggle("selected");
                    updateCopySelectedButtonState();
                };
                tagsContainer.appendChild(tagEl);
            });

            const actionsContainer = createElement("div", { className: "modusflow-lora-info-trigger-actions" });
            
            const selectAllButton = createElement("button", { textContent: "Select All" });
            selectAllButton.onclick = () => {
                tagsContainer.querySelectorAll(".modusflow-lora-info-tag:not(.selected)").forEach(el => el.classList.add("selected"));
                updateCopySelectedButtonState();
            };

            const deselectAllButton = createElement("button", { textContent: "Deselect All" });
            deselectAllButton.onclick = () => {
                tagsContainer.querySelectorAll(".modusflow-lora-info-tag.selected").forEach(el => el.classList.remove("selected"));
                updateCopySelectedButtonState();
            };

            const spacer = createElement("div", { style: "flex-grow: 1;" }); // Pushes copy buttons to the right

            copySelectedButton.onclick = () => {
                const selectedTags = Array.from(tagsContainer.querySelectorAll(".modusflow-lora-info-tag.selected"))
                                        .map(el => el.dataset.tag);
                copyTextToClipboard(selectedTags.join(', '), copySelectedButton);
            };
            updateCopySelectedButtonState(); // Set initial state

            const copyAllButton = createElement("button", { textContent: "Copy All" });
            copyAllButton.onclick = () => {
                const allTagsText = allTriggers.map(t => t.tag);
                copyTextToClipboard(allTagsText.join(', '), copyAllButton);
            };

            actionsContainer.append(selectAllButton, deselectAllButton, spacer, copySelectedButton, copyAllButton);
            valueContainer.append(tagsContainer, actionsContainer);
            rightCol.appendChild(createKeyValueSection("Trigger Words", valueContainer, true));
        }

        // --- Local Description ---
        if (localMeta.description) {
            const descEl = createElement("div", { className: "modusflow-civitai-description" });
            descEl.innerHTML = localMeta.description;
            rightCol.appendChild(createKeyValueSection("Local Description", descEl, true));
        }

        // --- Civitai Info Section ---
        if (civitaiData) {
            const civitaiSection = createElement("details", { className: "modusflow-lora-info-subsection", open: true });
            const summary = createElement("summary", { textContent: "Civitai Info" });
            const civitaiContent = createElement("div", { className: "modusflow-lora-info-civitai-content" });

            // Model Name and ID
            if (civitaiData.modelName) {
                let titleText = civitaiData.modelName;
                const nameEl = createElement("div", { textContent: titleText, style: "margin-bottom: 5px;" });
                civitaiContent.appendChild(createKeyValueSection("Model", nameEl));
            }

            // Civitai Description
            if (civitaiData.description) {
                const descEl = createElement("div", { className: "modusflow-civitai-description" });
                descEl.innerHTML = civitaiData.description; // Assumes HTML from Civitai is safe
                civitaiContent.appendChild(createKeyValueSection("Description", descEl, true));
            }

            // Image Thumbnails
            if (civitaiData.images && civitaiData.images.length > 0) {
                const thumbContainer = createElement("div", { className: "modusflow-civitai-thumb-container" });
                civitaiData.images.forEach(imgUrl => {
                    const thumb = createElement("img", { src: imgUrl, className: "modusflow-civitai-thumb", title: "Click to view larger image" });
                    thumb.onclick = () => {
                        const fullSizeUrl = imgUrl.replace(/width=\d+/, 'width=1200'); // Request a larger version
                        showLightbox(fullSizeUrl);
                    };
                    thumbContainer.appendChild(thumb);
                });
                civitaiContent.appendChild(createKeyValueSection("Images", thumbContainer, true));
            }
            civitaiSection.append(summary, civitaiContent);
            rightCol.appendChild(civitaiSection);
        }

        // --- Full Local Metadata ---
        if (Object.keys(localMeta).length > 0) {
            const otherKeys = Object.keys(localMeta).filter(k => !['ss_activation_text', 'description', 'ss_tag_frequency'].includes(k));
            if (otherKeys.length > 0) {
                const otherMeta = createElement("details", { className: "modusflow-lora-info-subsection" });
                const summary = createElement("summary", { textContent: "Full Local Metadata" });
                const pre = createElement("pre", {});
                const otherData = {};
                otherKeys.forEach(k => otherData[k] = localMeta[k]);
                pre.textContent = JSON.stringify(otherData, null, 2);
                otherMeta.append(summary, pre);
                rightCol.appendChild(otherMeta);
            }
        }

        if (rightCol.innerHTML.trim() === "") {
            rightCol.textContent = "No detailed information available.";
        }

        if (!localData && !civitaiData) {
            layout.innerHTML = ""; // Clear layout
            statusArea.style.display = 'block';
            statusArea.textContent = "Failed to fetch any information.";
            const localError = localResult.status === 'rejected' ? localResult.reason.message : (localResult.value?.message || "Unknown error");
            const civitaiError = civitaiResult.status === 'rejected' ? civitaiResult.reason.message : (civitaiResult.value?.message || "Unknown error");
            statusArea.append(createElement("br"), `Local: ${localError}`, createElement("br"), `Civitai: ${civitaiError}`);
        }
    }).catch(error => {
        statusArea.style.display = 'block';
        statusArea.textContent = `An unexpected error occurred: ${error.message}`;
        
    });
}

app.registerExtension({
    name: "ModusFlow.LoraLoader.AdvancedUI",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "ModusFlowLoraLoader") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                onNodeCreated?.apply(this, arguments);
                const node = this;

                // --- WIDGETS ---
                const loraStackWidget = node.widgets.find((w) => w.name === "lora_stack");
                loraStackWidget.type = "hidden"; // This widget is for data transfer only
                loraStackWidget.hidden = true;
                loraStackWidget.computeSize = () => [0, -4];

                // Hide the native civitai_api_key widget - we'll use a custom DOM widget instead
                const apiKeyWidget = node.widgets.find((w) => w.name === "civitai_api_key");
                if (apiKeyWidget) {
                    apiKeyWidget.type = "hidden";
                    apiKeyWidget.hidden = true;
                    apiKeyWidget.computeSize = () => [0, -4];
                }

                // Ensure lora_filter widget is visible and serializes properly
                // It should persist across sessions as it's a regular STRING widget
                const loraFilterWidget = node.widgets.find((w) => w.name === "lora_filter");
                if (loraFilterWidget) {
                    // Make sure it's not hidden so it can serialize with the workflow
                    loraFilterWidget.type = "STRING";
                    // Ensure default value
                    if (loraFilterWidget.value === undefined || loraFilterWidget.value === null) {
                        loraFilterWidget.value = "";
                    }
                }

                const loraMetadataCache = {};

                async function displayValidationStatus(loraName, baseModelName, iconElement) {
                    if (!loraName || !baseModelName || baseModelName === "None" || baseModelName.startsWith("<")) {
                        iconElement.textContent = '';
                        return;
                    }
                
                    // State 1: Use cached data
                    if (loraMetadataCache[loraName] && loraMetadataCache[loraName].validated_for === baseModelName) {
                        const cacheEntry = loraMetadataCache[loraName];
                        if (cacheEntry.loading) {
                            iconElement.textContent = '⏳';
                            iconElement.title = 'Loading metadata...';
                            return;
                        }
                        if (cacheEntry.error) {
                            iconElement.textContent = '❓';
                            iconElement.title = `Could not fetch metadata: ${cacheEntry.error}`;
                            return;
                        }
                
                        const validation = cacheEntry.data?.validation;
                
                        if (!validation) {
                            iconElement.textContent = '';
                            iconElement.title = '';
                            return;
                        }
                
                        switch (validation.status) {
                            case 'incompatible':
                                iconElement.textContent = '⚠️';
                                break;
                            case 'compatible':
                                iconElement.textContent = '✅';
                                break;
                            default:
                                iconElement.textContent = '❔';
                                break;
                        }
                        iconElement.title = validation.message;
                        return;
                    }
                
                    // State 2: Fetch data (or re-fetch if base model changed)
                    loraMetadataCache[loraName] = { loading: true, validated_for: baseModelName };
                    iconElement.textContent = '⏳';
                    iconElement.title = 'Loading metadata...';
                
                    try {
                        const params = new URLSearchParams({ name: loraName, base_model_name: baseModelName });
                        const response = await api.fetchApi(`/modusflow/get_lora_metadata?${params}`).then(r => r.json());
                
                        if (response.success) {
                            loraMetadataCache[loraName] = { data: response.data, validated_for: baseModelName };
                        } else {
                            throw new Error(response.message || 'Failed to fetch');
                        }
                    } catch (e) {
                        loraMetadataCache[loraName] = { error: e.message, validated_for: baseModelName };
                    }
                
                    // Re-run to display the result from the now-populated cache
                    displayValidationStatus(loraName, baseModelName, iconElement);
                }

                let allLoras = []; // This will hold all available LoRA names

                // --- HEADER ---
                const headerContainer = createElement("div", { className: "modusflow-lora-header" });
                const statusSpan = createElement("span", { className: "modusflow-lora-status-span" });

                const { element: toggleAllSwitch, setChecked: setToggleAllChecked } = createToggleSwitch(false, () => {
                    const stack = getStack();
                    if (stack.length === 0) return;

                    // If all are on, turn them all off. Otherwise, turn them all on.
                    const allOn = stack.every(lora => lora.enabled);
                    const newState = !allOn;

                    const newStack = stack.map(lora => {
                        lora.enabled = newState;
                        return lora;
                    });
                    updateStack(newStack);
                });

                const addButton = createElement("button", { textContent: "Add LoRA", className: "modusflow-lora-header-button" });
                addButton.addEventListener("click", () => {
                    const currentStack = getStack();
                    const globalFilter = (loraFilterWidget?.value || "").toLowerCase();
                    const availableLoras = allLoras.filter(l => l.toLowerCase().includes(globalFilter));

                    currentStack.push({
                        name: availableLoras[0] || allLoras[0] || "", // Use first available, fallback to first overall
                        enabled: true,
                        strength: 1.0,
                    });
                    updateStack(currentStack);
                });

                const cleanButton = createElement("button", { textContent: "Clean Up", className: "modusflow-lora-header-button" });
                cleanButton.addEventListener("click", () => {
                    if (confirm("This will remove all disabled LoRAs from the list. Are you sure?")) {
                        const stack = getStack();
                        const newStack = stack.filter(lora => lora.enabled);
                        updateStack(newStack);
                    }
                });

                // --- Civitai API Key Widget ---
                // Create a compact API key input that goes in the header
                const apiKeyWidgetData = node.widgets.find(w => w.name === "civitai_api_key");
                let apiKeyHeaderElement = null;
                if (apiKeyWidgetData) {
                    const apiKeyContainer = createElement("div", { className: "modusflow-api-key-header" });
                    
                    const apiKeyInput = createElement("input", {
                        type: "text",
                        value: apiKeyWidgetData.value,
                        placeholder: "Civitai API Key",
                        className: "modusflow-api-key-input-compact",
                        title: "Civitai API Key (saved with workflow)"
                    });
                    node.modusflowApiKeyInput = apiKeyInput; // Store a reference for later updates
                    
                    apiKeyInput.addEventListener("input", (e) => {
                        // When the user types, update the widget's value.
                        // This ensures it's saved with the workflow.
                        apiKeyWidgetData.value = e.target.value;
                    });
     
                    const saveButton = createElement("button", { 
                        textContent: "💾", 
                        title: "Save to config.json (persists across browsers/reinstalls)",
                        className: "modusflow-api-key-save-button-compact"
                    });
     
                    saveButton.addEventListener("click", async () => {
                        // The save button reads from the widget and saves to the server config.
                        const keyToSave = apiKeyWidgetData.value.trim();
                        const originalText = saveButton.textContent;
                        saveButton.textContent = "💾...";
                        saveButton.disabled = true;
                        try {
                            const response = await api.fetchApi("/modusflow/save_civitai_key", {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ api_key: keyToSave }),
                            }).then(r => r.json());
                            if (!response.success) throw new Error(response.message || "Failed to save key.");
                            saveButton.textContent = "✅";
                        } catch (e) {
                            
                            alert(`Failed to save API key: ${e.message}`);
                            saveButton.textContent = "❌";
                        } finally {
                            setTimeout(() => { saveButton.textContent = originalText; saveButton.disabled = false; }, 2000);
                        }
                    });
                    
                    apiKeyContainer.append(apiKeyInput, saveButton);
                    apiKeyHeaderElement = apiKeyContainer;
                }

                headerContainer.append(toggleAllSwitch, addButton, cleanButton, statusSpan);
                if (apiKeyHeaderElement) {
                    headerContainer.append(apiKeyHeaderElement);
                }

                const listContainer = createElement("div", { className: "modusflow-lora-list-dynamic" });
                const mainWidgetContainer = createElement("div", { className: "modusflow-lora-main-container" }, headerContainer, listContainer);
                node.addDOMWidget("advanced_list", "html", mainWidgetContainer, { serialize: false });

                // --- STATE MANAGEMENT ---
                function getStack() {
                    try {
                        return JSON.parse(loraStackWidget.value || "[]");
                    } catch (e) {
                        
                        return [];
                    }
                }

                function updateStack(stack) {
                    loraStackWidget.value = JSON.stringify(stack);
                    renderList();
                }

                // Setup callback for lora_filter widget to re-render on changes
                 if (loraFilterWidget) {
                     const originalCallback = loraFilterWidget.callback;
                     loraFilterWidget.callback = function() {
                         // First, execute the original callback to ensure the widget's value is updated for serialization.
                         originalCallback?.apply(this, arguments);
                         // Then, re-render the list to apply the filter visually.
                         renderList();
                     };
                 }

                const baseModelWidget = node.widgets.find(w => w.name === "base_model_name");
                if (baseModelWidget) {
                    baseModelWidget.callback = () => {
                        // When the base model changes, just re-render the list.
                        // The validation logic will automatically use the new value.
                        renderList();
                    };
                }

                // --- RENDERING ---
                function renderList() {
                    // Force sync widget values to their DOM elements to fix state issues on refresh.
                    const loraFilterWidget = node.widgets.find(w => w.name === "lora_filter");
                    if (loraFilterWidget && loraFilterWidget.inputEl && loraFilterWidget.inputEl.value !== loraFilterWidget.value) {
                        loraFilterWidget.inputEl.value = loraFilterWidget.value;
                    }
                    const apiKeyWidgetData = node.widgets.find(w => w.name === "civitai_api_key");
                    if (apiKeyWidgetData && node.modusflowApiKeyInput && node.modusflowApiKeyInput.value !== apiKeyWidgetData.value) {
                        node.modusflowApiKeyInput.value = apiKeyWidgetData.value;
                    }

                    const stack = getStack();
                    listContainer.innerHTML = ""; // Clear previous list

                    const globalFilter = (loraFilterWidget?.value || "").toLowerCase();
                    const availableLoras = allLoras;
                    const baseModelName = baseModelWidget?.value || "";

                    if (stack.length === 0) {
                        listContainer.innerHTML = `<div class="modusflow-lora-list-message">No LoRAs added.</div>`;
                    }

                    stack.forEach((lora, index) => {
                        const row = createElement("div", { 
                            className: "modusflow-lora-row", 
                            draggable: true,
                            dataset: { index } // Store index for D&D
                        });

                        const dragHandle = createElement("div", { 
                            className: "modusflow-lora-drag-handle", 
                            textContent: "⠿",
                            title: "Drag to reorder"
                        });

                        const validationIcon = createElement("div", { className: "modusflow-lora-validation-icon" });

                        const { element: toggle } = createToggleSwitch(lora.enabled, (newState) => {
                            const currentStack = getStack();
                            currentStack[index].enabled = newState;
                            updateStack(currentStack);
                        });

                        const dropdown = createSearchableDropdown(availableLoras, lora.name, (newValue) => {
                            const currentStack = getStack();
                            currentStack[index].name = newValue;
                            updateStack(currentStack); // Re-render to update closures
                        }, globalFilter);

                        const updateStrength = (newValue) => {
                            const currentStack = getStack();
                            currentStack[index].strength = parseFloat(newValue);
                            loraStackWidget.value = JSON.stringify(currentStack); // Update without re-rendering
                        };

                        // Use a larger step for buttons, but allow fine-tuning via manual input.
                        const stepValue = 0.05;
                        const strengthInput = createNumberInput(lora.strength, -2, 2, stepValue, updateStrength);

                        const removeButton = createElement("button", { textContent: "✖", className: "modusflow-lora-remove-button" });
                        removeButton.addEventListener("click", () => {
                            const currentStack = getStack();
                            currentStack.splice(index, 1);
                            updateStack(currentStack);
                        });

                        row.append(dragHandle, toggle, validationIcon, dropdown, strengthInput, removeButton);
                        listContainer.appendChild(row);
                        displayValidationStatus(lora.name, baseModelName, validationIcon);

                        // Add context menu listener to the row
                        row.addEventListener("contextmenu", (e) => {
                            e.preventDefault();
                            // Get the current lora name directly from the dropdown display at the time of click
                            const currentLoraName = dropdown.querySelector('.modusflow-lora-select-display').textContent.trim();
                            const menuItems = [{
                                label: "Show Info...",
                                callback: () => showInfoModal(currentLoraName, node)
                            }];
                            createContextMenu(menuItems, e);
                        });

                        // --- Drag and Drop Event Listeners ---
                        row.addEventListener("dragstart", (e) => {
                            e.dataTransfer.setData("text/plain", index);
                            setTimeout(() => row.classList.add("modusflow-lora-dragging"), 0);
                        });

                        row.addEventListener("dragend", () => {
                            document.querySelectorAll('.modusflow-lora-row').forEach(r => {
                                r.classList.remove("modusflow-lora-dragging", "modusflow-lora-drag-over-top", "modusflow-lora-drag-over-bottom");
                            });
                        });

                        row.addEventListener("dragover", (e) => {
                            e.preventDefault();
                            const draggingRow = document.querySelector(".modusflow-lora-dragging");
                            if (!draggingRow || draggingRow === row) return;

                            const rect = row.getBoundingClientRect();
                            const isAfter = e.clientY > rect.top + rect.height / 2;
                            
                            // This is a bit inefficient, but ensures a clean state
                            document.querySelectorAll('.modusflow-lora-row').forEach(r => r.classList.remove("modusflow-lora-drag-over-top", "modusflow-lora-drag-over-bottom"));

                            if (isAfter) {
                                row.classList.add("modusflow-lora-drag-over-bottom");
                            } else {
                                row.classList.add("modusflow-lora-drag-over-top");
                            }
                        });

                        row.addEventListener("drop", (e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            
                            const fromIndex = parseInt(e.dataTransfer.getData("text/plain"), 10);
                            let toIndex = index; // The original index of the drop target row

                            const isAfter = row.classList.contains("modusflow-lora-drag-over-bottom");
                            row.classList.remove("modusflow-lora-drag-over-top", "modusflow-lora-drag-over-bottom");

                            if (fromIndex === toIndex) return;

                            const stack = getStack();
                            // Remove the item from its original position.
                            // The `[itemToMove]` syntax is array destructuring to get the first element of the returned array.
                            const [itemToMove] = stack.splice(fromIndex, 1);

                            // After splicing, the index of the target element might have shifted.
                            // If we moved an item from before the target, the target's index is now one less.
                            if (fromIndex < toIndex) {
                                toIndex--;
                            }

                            // Now, insert the item at the correct new position.
                            stack.splice(toIndex + (isAfter ? 1 : 0), 0, itemToMove);

                            updateStack(stack);
                        });

                        row.style.display = "grid";
                    });

                    const allOn = stack.length > 0 && stack.every(l => l.enabled);
                    setToggleAllChecked(allOn);

                    // Update status text
                    const enabledCount = stack.filter(s => s.enabled).length;
                    const totalCount = stack.length;

                    const statusText = `${enabledCount} / ${totalCount} enabled`;
                    statusSpan.textContent = statusText;
                    statusSpan.title = `${enabledCount} of ${totalCount} LoRAs are enabled in the current stack.`;
                    if (globalFilter) {
                        statusSpan.title += `\nDropdowns are pre-filtered by: "${globalFilter}"`;
                    }

                    node.computeSize();
                }

                // --- INITIALIZATION ---
                function refreshLoras() {
                    api.fetchApi("/modusflow/get_loras")
                        .then(r => (r.json ? r.json() : r)) // Defensively parse JSON
                        .then(response => {
                            if (response.success && Array.isArray(response.data)) {
                                allLoras = response.data;
                            } else {
                                
                                allLoras = [];
                            }
                            renderList(); // Re-render with the new list
                        })
                        .catch(e => {});
                }

                // Add refresh method to the node for external access
                node.refreshLoraList = refreshLoras;
                
                // Track this node for refresh events
                loraLoaderNodes.add(node);
                
                // Clean up when node is removed
                const originalOnRemoved = node.onRemoved;
                node.onRemoved = function() {
                    loraLoaderNodes.delete(node);
                    if (originalOnRemoved) {
                        originalOnRemoved.apply(this, arguments);
                    }
                };

                // Initial fetch
                refreshLoras();
                // Listen for external refresh events from ComfyUI (e.g., pressing 'R')
                api.addEventListener("loras_updated", refreshLoras);
            };
        }
    },
});

// --- STYLES ---
if (!document.getElementById("modusflow-lora-loader-styles")) {
    const style =createElement("style", {
        id: "modusflow-lora-loader-styles",
        innerHTML: `
            .modusflow-lora-main-container {
                display: flex;
                flex-direction: column;
                width: 100%;
                height: 100%;
                min-height: 0;
                overflow: hidden;
            }
            .modusflow-lora-list-dynamic {
                width: 100%;
                display: flex;
                flex-direction: column;
                gap: 4px;
                overflow-y: auto;
                overflow-x: hidden;
                flex: 1;
                min-height: 0;
            }
            .modusflow-lora-header {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 4px;
                flex-wrap: wrap;
            }
            .modusflow-lora-header-button {
                flex-grow: 1;
                padding: 2px 4px;
                font-size: 0.85em;
            }
            .modusflow-lora-status-span {
                font-size: 0.8em;
                color: #999;
                text-align: right;
                flex-grow: 2;
            }
            .modusflow-api-key-header {
                display: flex;
                gap: 4px;
                align-items: center;
                flex-basis: 100%;
                margin-top: 4px;
            }
            .modusflow-api-key-input-compact {
                flex-grow: 1;
                padding: 2px 4px;
                font-size: 0.85em;
                background: #222;
                border: 1px solid #444;
                color: #eee;
                border-radius: 3px;
            }
            .modusflow-api-key-save-button-compact {
                flex-shrink: 0;
                padding: 2px 6px;
                font-size: 0.85em;
                line-height: 1;
                min-width: 28px;
            }
            .modusflow-lora-row {
                display: grid;
                grid-template-columns: auto auto 18px 1fr auto auto;
                align-items: center;
                gap: 4px;
                padding: 2px;
                border-radius: 2px;
                font-size: 0.85em;
            }
            .modusflow-lora-validation-icon {
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.1em;
                user-select: none;
            }
            .modusflow-lora-row:hover {
                background-color: rgba(255, 255, 255, 0.05);
            }
            .modusflow-lora-drag-handle {
                cursor: grab;
                color: #888;
                padding: 0 4px;
                font-size: 1.2em;
                line-height: 1;
                user-select: none;
            }
            .modusflow-lora-dragging {
                opacity: 0.4;
            }
            .modusflow-lora-drag-over-top {
                border-top: 2px solid #4a90e2;
            }
            .modusflow-lora-drag-over-bottom {
                border-bottom: 2px solid #4a90e2;
            }
            .modusflow-lora-info-modal-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                cursor: move;
                user-select: none;
                padding-bottom: 10px;
                margin-bottom: 15px;
                border-bottom: 1px solid #444;
            }
            .modusflow-lora-info-modal-header h3 {
                margin: 0; /* Reset default h3 margin */
            }
            .modusflow-lora-info-layout {
                display: grid;
                grid-template-columns: 256px 1fr;
                gap: 15px;
                margin-top: 15px;
                /* Added for vertical resizing */
                flex-grow: 1;
                min-height: 0;
            }
            .modusflow-lora-info-col-left {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            .modusflow-lora-info-col-left img {
                width: 100%;
                border-radius: 4px;
                object-fit: contain;
                background-color: #1e1e1e;
            }
            .modusflow-lora-info-col-right {
                min-width: 0;
                display: flex;
                flex-direction: column;
                gap: 15px;
                flex-grow: 1; /* Allow this column to fill vertical space */
                min-height: 0; /* Crucial for flex children with overflow */
                /* max-height: 60vh; REMOVED to allow vertical resizing */
                overflow-y: auto;
            }
            .modusflow-context-menu {
                position: fixed;
                z-index: 3000; /* Higher than the modal */
                background-color: #282828;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px 0;
                box-shadow: 0 2px 10px rgba(0,0,0,0.5);
                font-family: sans-serif;
                font-size: 0.9em;
                min-width: 150px;
            }
            .modusflow-context-menu-item {
                padding: 8px 12px;
                cursor: pointer;
                color: #eee;
                white-space: nowrap;
            }
            .modusflow-context-menu-item:hover {
                background-color: #4a90e2;
            }
            .modusflow-context-menu-separator {
                height: 1px;
                background-color: #444;
                margin: 4px 0;
            }

            .modusflow-lora-fetch-button {
                width: 100%;
                padding: 6px;
                font-size: 0.9em;
            }
            .modusflow-civitai-img-container {
                text-align: center;
                margin-bottom: 15px;
            }
            .modusflow-civitai-img-container img {
                max-width: 100%;
                max-height: 400px;
                border-radius: 4px;
                background-color: #1e1e1e;
            }
            .modusflow-civitai-description {
                margin-top: 5px;
                padding: 10px;
                background-color: #1e1e1e;
                border-radius: 4px;
                max-height: 200px;
                overflow-y: auto;
            }
            .modusflow-lora-info-modal {
                display: none;
                position: fixed;
                z-index: 2000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                overflow: auto;
                background-color: rgba(0,0,0,0.6);
                font-family: sans-serif;
            }
            .modusflow-lora-info-modal-content {
                background-color: #282828;
                /* margin: 10% auto; REMOVED for draggable/resizable */
                padding: 20px;
                border: 1px solid #555;
                width: 800px; /* Set a fixed initial width instead of a percentage. */
                max-width: 95vw; /* Allow resizing up to most of the viewport width. */
                max-height: 95vh; /* Add max-height for consistency with resizing. */
                border-radius: 5px;
                color: #eee;
                position: relative;
                /* ADDED for draggable/resizable */
                position: absolute;
                left: 50%;
                top: 50%;
                transform: translate(-50%, -50%);
                resize: both;
                overflow: hidden; /* Contains the resize handle and children */
                min-width: 550px;
                min-height: 400px;
                display: flex;
                flex-direction: column;
            }
            .modusflow-lora-info-modal-close {
                color: #aaa;
                /* float: right; REMOVED for flexbox alignment */
                font-size: 28px;
                font-weight: bold;
                line-height: 1;
                cursor: pointer;
            }
            .modusflow-lora-info-modal-close:hover,
            .modusflow-lora-info-modal-close:focus {
                color: white;
                text-decoration: none;
            }
            .modusflow-lora-info-status {
                padding: 10px;
                background-color: #333;
                border-radius: 4px;
                text-align: center;
            }
            .modusflow-lora-info-sub-content {
                padding-left: 5px;
            }
            .modusflow-lora-info-subsection {
                margin-bottom: 10px;
            }
            .modusflow-lora-info-subsection strong {
                vertical-align: top;
            }
            .modusflow-lora-info-subsection-block strong {
                display: block;
                margin-bottom: 5px;
            }
            .modusflow-lora-info-subsection-block .modusflow-lora-info-trigger-wrapper {
                /* This is a child of a block-layout subsection, so it doesn't need a top margin */
                margin-top: 0;
            }
            .modusflow-lora-info-subsection a {
                color: #68a6f2;
                text-decoration: none;
            }
            .modusflow-lora-info-subsection a:hover {
                text-decoration: underline;
            }
            .modusflow-lora-info-creator {
                font-size: 0.9em; color: #aaa; margin-top: 4px;
            }
            .modusflow-lora-info-trigger-container {
                display: flex;
                flex-direction: column;
                gap: 10px;
                margin-top: 5px;
            }
            .modusflow-lora-info-tags-container {
                display: flex;
                flex-wrap: wrap;
                gap: 6px;
                padding: 8px;
                background-color: #1e1e1e;
                border: 1px solid #444;
                border-radius: 4px;
                max-height: 150px;
                overflow-y: auto;
            }
            .modusflow-lora-info-tag {
                background-color: #3a3a3a;
                color: #ddd;
                padding: 3px 4px 3px 8px;
                border-radius: 12px;
                font-size: 0.9em;
                cursor: pointer;
                border: 1px solid #555;
                transition: background-color 0.2s, border-color 0.2s;
                user-select: none;
                display: flex;
                align-items: center;
                gap: 6px;
            }
            .modusflow-lora-info-tag:hover {
                background-color: #4a4a4a;
                border-color: #777;
            }
            .modusflow-lora-info-tag.selected {
                background-color: #4a90e2;
                color: white;
                border-color: #68a6f2;
            }
            .modusflow-lora-info-tag-count {
                background-color: rgba(0,0,0,0.3);
                color: #eee;
                border-radius: 8px;
                font-size: 0.85em;
                padding: 1px 6px;
                min-width: 10px;
                text-align: center;
                line-height: 1.2;
                font-weight: bold;
            }
            .modusflow-lora-info-tag.selected .modusflow-lora-info-tag-count {
                background-color: rgba(255,255,255,0.2);
            }
            .modusflow-lora-info-trigger-actions {
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .modusflow-lora-info-trigger-actions button {
                padding: 4px 10px;
                font-size: 0.9em;
            }
            .modusflow-lora-info-trigger-actions button:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            .modusflow-lora-info-col-right details summary { cursor: pointer; font-weight: bold; }
            .modusflow-lora-info-col-right pre { background-color: #1e1e1e; padding: 10px; border-radius: 4px; margin-top: 5px; font-family: monospace; white-space: pre-wrap; word-break: break-all; max-height: 250px; overflow-y: auto; }
            .modusflow-lora-search-container {
                position: relative;
                width: 100%;
                min-width: 0; /* Prevents the container from overflowing its grid cell */
            }
            .modusflow-lora-info-civitai-content {
                padding-left: 15px;
                margin-top: 10px;
                border-left: 2px solid #444;
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            .modusflow-civitai-thumb-container {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin-top: 5px;
            }
            .modusflow-civitai-thumb {
                height: 128px;
                width: auto;
                border-radius: 4px;
                cursor: pointer;
                transition: transform 0.2s ease;
                background-color: #1e1e1e;
            }
            .modusflow-civitai-thumb:hover {
                transform: scale(1.05);
            }
            .modusflow-lora-lightbox {
                position: fixed;
                top: 0; left: 0; width: 100%; height: 100%;
                background-color: rgba(0, 0, 0, 0.85);
                display: flex; justify-content: center; align-items: center;
                z-index: 4000;
                cursor: pointer;
                opacity: 0;
                transition: opacity 0.3s ease;
            }
            .modusflow-lora-lightbox.modusflow-lora-lightbox-loaded { opacity: 1; }
            .modusflow-lora-lightbox img {
                max-width: 90vw; max-height: 90vh;
                object-fit: contain; border-radius: 4px;
            }
            .modusflow-lora-lightbox-close-hint {
                position: absolute; top: 20px; right: 20px;
                color: #ccc; font-size: 1.2em; background-color: rgba(0,0,0,0.5);
                padding: 5px 10px; border-radius: 5px;
            }
            .modusflow-lora-search-container {
                position: relative;
                width: 100%;
                min-width: 0; /* Prevents the container from overflowing its grid cell */
            }
            .modusflow-lora-select-display {
                padding: 2px 4px;
                background-color: #222;
                border: 1px solid #444;
                border-radius: 3px;
                cursor: pointer;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                text-align: left;
            }
            .modusflow-lora-select-display:hover {
                background-color: #333;
            }
            .modusflow-lora-search-dropdown {
                display: none;
                position: fixed;
                background-color: #222;
                border: 1px solid #555;
                z-index: 99999;
                min-width: 100%; /* Ensure it's at least as wide as the input */
                width: max-content; /* Allow it to expand for long LoRA names */
                max-width: 1280px; /* Prevent dropdown from being too wide */
                box-sizing: border-box;
                flex-direction: column;
            }
            .modusflow-lora-search-input-internal {
                width: calc(100% - 10px);
                margin: 5px;
                box-sizing: border-box;
            }
            .modusflow-lora-search-items-container {
                max-height: 250px; /* Leave space for search input */
                overflow-y: auto;
                overflow-x: auto; /* Allow horizontal scroll for long names */
            }
            .modusflow-lora-viewport {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
            }
            .modusflow-lora-search-item {
                padding: 3px 6px;
                cursor: pointer;
                white-space: nowrap;
                font-size: 0.85em;
                /* overflow and text-overflow are removed to allow full name visibility */
            }
            .modusflow-lora-search-item:hover {
                background-color: #444;
            }
            .modusflow-lora-search-item-none {
                padding: 3px 6px;
                font-style: italic;
                color: #888;
                font-size: 0.85em;
            }
            .modusflow-lora-strength-input {
                width: 45px;
                text-align: center;
                background: #222;
                border: 1px solid #444;
                color: #eee;
                border-radius: 3px;
                padding: 1px 2px;
                -moz-appearance: textfield;
            }
            .modusflow-lora-remove-button {
                background: none;
                border: none;
                color: #F55;
                cursor: pointer;
                font-size: 1.1em;
                padding: 0 4px;
                opacity: 0.7;
            }
            .modusflow-lora-remove-button:hover {
                opacity: 1;
                color: #F00;
            }
            .modusflow-lora-list-message {
                font-style: italic;
                color: #888;
                padding: 5px;
                text-align: center;
            }
            /* Toggle Switch CSS */
            .modusflow-lora-toggle-switch {
                position: relative;
                display: inline-block;
                width: 34px;
                height: 18px;
            }
            .modusflow-lora-toggle-switch input {
                opacity: 0;
                width: 0;
                height: 0;
            }
            .modusflow-lora-toggle-slider {
                position: absolute;
                cursor: pointer;
                top: 0; left: 0; right: 0; bottom: 0;
                background-color: #555;
                transition: .4s;
                border-radius: 18px;
            }
            .modusflow-lora-toggle-slider:before {
                position: absolute; content: "";
                height: 12px; width: 12px;
                left: 3px; bottom: 3px;
                background-color: white;
                transition: .4s; border-radius: 50%;
            }
            input:checked + .modusflow-lora-toggle-slider { background-color: #2196F3; }
            input:checked + .modusflow-lora-toggle-slider:before { transform: translateX(16px); }
            .modusflow-lora-header .modusflow-lora-toggle-switch {
                transform: scale(0.8);
            }
        `
    });
    document.head.appendChild(style);
}