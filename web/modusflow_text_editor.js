import { app } from "../../scripts/app.js";

// ModusFlow Text Editor — positive/negative prompts with category-filtered save/load

app.registerExtension({
    name: "modusflow.TextEditor",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "ModusFlowTextEditor") {

            // ── onNodeCreated ─────────────────────────────────────────────────────
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
                const node = this;

                // Locate Python-registered widgets
                const positiveWidget = node.widgets?.find(w => w.name === "positive");
                const negativeWidget  = node.widgets?.find(w => w.name === "negative");
                const dropdownWidget  = node.widgets?.find(w => w.name === "saved_prompt");

                if (positiveWidget) positiveWidget.label = "Positive";
                if (negativeWidget)  negativeWidget.label  = "Negative";

                // ── Negative widget height control ────────────────────────────────
                // ComfyUI's new frontend uses _arrangeWidgets() which checks:
                //   if widget.computeSize  → computedHeight = computeSize()[1] + 4  (FIXED)
                //   else if computeLayoutSize → goes into flexible pool, grows with node
                // The multiline textarea widget has computeLayoutSize (flexible) by default,
                // which causes it to expand when the node is tall or when zooming.
                //
                // Fix: add computeSize to make it take the FIXED path.
                // The Vue component then sets element.style.height from computedHeight
                // inside a CSS-scaled container — no scale multiplication needed here.
                const NEG_H = 80;

                if (negativeWidget) {
                    negativeWidget.computeSize = function() {
                        return [0, NEG_H];
                    };
                    // Disable the native textarea resize handle; the height is managed above.
                    requestAnimationFrame(() => {
                        const ta = negativeWidget.inputEl || negativeWidget.element;
                        if (ta) { ta.style.resize = "none"; ta.style.overflow = "auto"; }
                    });
                }

                // ── Prompt cache ──────────────────────────────────────────────────
                node._allPrompts    = [];
                node._savedCategory = undefined;

                // ── Category filter combo ─────────────────────────────────────────
                // Add it first, then splice it before saved_prompt so it appears above.
                const categoryWidget = node.addWidget(
                    "combo",
                    "category_filter",
                    "--all categories--",
                    (v) => applyFilter(node, v),
                    { values: ["--all categories--"] }
                );
                categoryWidget.label = "Category";

                // Move category_filter to just before saved_prompt in the widget list
                if (dropdownWidget) {
                    const dropIdx = node.widgets.indexOf(dropdownWidget);
                    const catIdx  = node.widgets.indexOf(categoryWidget);
                    if (dropIdx >= 0 && catIdx > dropIdx) {
                        node.widgets.splice(catIdx, 1);
                        node.widgets.splice(dropIdx, 0, categoryWidget);
                    }
                }

                // ── Prompt dropdown → load on select ─────────────────────────────
                if (dropdownWidget) {
                    dropdownWidget.callback = function(value) {
                        if (value && value !== "--select prompt--" && value !== "--no prompts found--") {
                            loadPrompt(node, value);
                        }
                    };
                }

                // ── Category text entry (for saving/updating prompts) ─────────────
                const promptCategoryWidget = node.addWidget(
                    "text",
                    "prompt_category",
                    "",
                    () => {},
                    {}
                );
                promptCategoryWidget.label = "Prompt Category";

                // ── Action buttons ────────────────────────────────────────────────
                node.addWidget("button", "Save Prompt",     null, () => showSaveDialog(node));
                node.addWidget("button", "Update Selected", null, () => updatePrompt(node));
                node.addWidget("button", "Refresh List",    null, () => refreshPrompts(node));

                // ── Initial size ──────────────────────────────────────────────────
                node.size = [520, 750];
                node.resizable = true;

                // Auto-populate on first creation
                requestAnimationFrame(() => refreshPrompts(node));

                return r;
            };

            // ── onConfigure (workflow load / paste) ───────────────────────────────
            // Called AFTER onNodeCreated when a saved workflow is restored.
            // widgets_values layout (matches onSerialize below):
            //   [0] positive  [1] negative  [2] category_filter  [3] saved_prompt  [4] prompt_category
            const onConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function(config) {
                if (onConfigure) onConfigure.apply(this, arguments);
                const vals = config?.widgets_values;
                // Stash saved category so refreshPrompts can restore it after
                // the async API call rebuilds options.values.
                if (vals?.[2] !== undefined) {
                    this._savedCategory = vals[2];
                }
                // Restore prompt_category text widget directly (plain string, no async needed).
                if (vals?.[4] !== undefined) {
                    const cw = this.widgets?.find(w => w.name === "prompt_category");
                    if (cw) { cw.value = vals[4]; if (cw.inputEl) cw.inputEl.value = vals[4]; }
                }
            };

            // ── onSerialize ───────────────────────────────────────────────────────
            // Widget order:  positive, negative, category_filter, saved_prompt, prompt_category, btns
            const onSerialize = nodeType.prototype.onSerialize;
            nodeType.prototype.onSerialize = function(o) {
                if (onSerialize) onSerialize.apply(this, arguments);
                const pw  = this.widgets?.find(w => w.name === "positive");
                const nw  = this.widgets?.find(w => w.name === "negative");
                const cfw = this.widgets?.find(w => w.name === "category_filter");
                const dw  = this.widgets?.find(w => w.name === "saved_prompt");
                const pcw = this.widgets?.find(w => w.name === "prompt_category");
                if (!o.widgets_values) o.widgets_values = [];
                if (pw)  o.widgets_values[0] = pw.value;
                if (nw)  o.widgets_values[1] = nw.value;
                if (cfw) o.widgets_values[2] = cfw.value;
                if (dw)  o.widgets_values[3] = dw.value;
                if (pcw) o.widgets_values[4] = pcw.value;
            };

            // ── Helper: set widget value AND update the visible textarea ──────────
            function setTextValue(widget, value) {
                if (!widget) return;
                widget.value = value;
                if (widget.inputEl) widget.inputEl.value = value;
            }

            // ── Load a JSON prompt file into the text boxes ───────────────────────
            function loadPrompt(node, filename) {
                fetch("/modusflow/load_prompt", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ filename })
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        setTextValue(node.widgets?.find(w => w.name === "positive"),        data.data.positive || "");
                        setTextValue(node.widgets?.find(w => w.name === "negative"),         data.data.negative || "");
                        setTextValue(node.widgets?.find(w => w.name === "prompt_category"),  data.data.category || "");
                        app.graph.setDirtyCanvas(true, true);
                    } else {
                        console.error("[ModusFlow] Load error:", data.message);
                    }
                })
                .catch(err => console.error("[ModusFlow] Load error:", err.message));
            }

            // ── Filter saved_prompt dropdown by category ──────────────────────────
            function applyFilter(node, category) {
                const dw = node.widgets?.find(w => w.name === "saved_prompt");
                if (!dw) return;
                const all = node._allPrompts || [];
                const filenames = (!category || category === "--all categories--")
                    ? all.map(p => p.filename)
                    : all.filter(p => (p.category || "") === category).map(p => p.filename);

                dw.options.values = filenames.length
                    ? ["--select prompt--", ...filenames]
                    : ["--no prompts found--"];

                if (!dw.options.values.includes(dw.value)) {
                    dw.value = dw.options.values[0];
                }
                app.graph.setDirtyCanvas(true, true);
            }

            // ── Fetch prompt list; rebuild category combo + dropdown ───────────────
            function refreshPrompts(node) {
                const dw = node.widgets?.find(w => w.name === "saved_prompt");
                const cw = node.widgets?.find(w => w.name === "category_filter");
                if (!dw) return;

                fetch("/modusflow/list_prompts")
                    .then(r => r.json())
                    .then(data => {
                        if (!data.success) return;
                        node._allPrompts = data.data;

                        const cats = [...new Set(
                            data.data.map(p => (p.category || "").trim()).filter(Boolean)
                        )].sort();

                        if (cw) {
                            const target = (node._savedCategory !== undefined)
                                ? node._savedCategory
                                : cw.value;
                            node._savedCategory = undefined;

                            cw.options.values = ["--all categories--", ...cats];
                            cw.value = cw.options.values.includes(target) ? target : "--all categories--";
                        }
                        applyFilter(node, cw ? cw.value : "--all categories--");
                    })
                    .catch(err => console.error("[ModusFlow] Refresh error:", err.message));
            }

            // ── Save current text to a new file ───────────────────────────────────
            function showSaveDialog(node) {
                const pw  = node.widgets?.find(w => w.name === "positive");
                const nw  = node.widgets?.find(w => w.name === "negative");
                const pcw = node.widgets?.find(w => w.name === "prompt_category");
                if (!pw) return;

                const filename = prompt("Filename (without extension):");
                if (!filename?.trim()) return;
                const category = (pcw?.value || "").trim();

                fetch("/modusflow/save_prompt", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        filename: filename.trim(),
                        category: category,
                        positive: pw.value || "",
                        negative: nw?.value || ""
                    })
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) { alert("Saved: " + filename.trim() + ".json"); refreshPrompts(node); }
                    else alert("Save failed: " + data.message);
                })
                .catch(err => alert("Save error: " + err.message));
            }

            // ── Overwrite the currently selected prompt ───────────────────────────
            function updatePrompt(node) {
                const pw  = node.widgets?.find(w => w.name === "positive");
                const nw  = node.widgets?.find(w => w.name === "negative");
                const dw  = node.widgets?.find(w => w.name === "saved_prompt");
                const pcw = node.widgets?.find(w => w.name === "prompt_category");

                const selected = dw?.value;
                if (!selected || selected === "--select prompt--" || selected === "--no prompts found--") {
                    alert("Select a saved prompt from the dropdown first.");
                    return;
                }
                if (!confirm('Overwrite "' + selected + '" with the current text?')) return;

                const base     = selected.replace(/\.json$/i, "");
                const category = (pcw?.value || "").trim();

                fetch("/modusflow/save_prompt", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ filename: base, category, positive: pw?.value || "", negative: nw?.value || "" })
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) alert('"' + selected + '" updated.');
                    else alert("Update failed: " + data.message);
                })
                .catch(err => alert("Update error: " + err.message));
            }
        }
    }
});