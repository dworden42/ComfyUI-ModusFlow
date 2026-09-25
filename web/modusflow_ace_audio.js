import { app } from "../../scripts/app.js";

// ModusFlow ACE Step Audio - Save/load tags and lyrics for song generation

app.registerExtension({
    name: "modusflow.AceStepAudio",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "ModusFlowAceStepAudio") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

            const titleWidget       = this.widgets.find(w => w.name === "title");
            const tagsWidget        = this.widgets.find(w => w.name === "tags");
            const savedTagsDropdown = this.widgets.find(w => w.name === "saved_tags");
            const lyricsWidget      = this.widgets.find(w => w.name === "lyrics");
            const savedLyricsDropdown = this.widgets.find(w => w.name === "saved_lyrics");
            const savedSongDropdown = this.widgets.find(w => w.name === "saved_song");

            // ── Tags dropdown ─────────────────────────────────────────────────
            if (savedTagsDropdown) {
                const orig = savedTagsDropdown.callback;
                savedTagsDropdown.callback = (value) => {
                    if (orig) orig.apply(this, arguments);
                    if (value && value !== "--select tags--" && value !== "--no tags found--") {
                        loadText("/modusflow/ace_audio/load_tags", { filename: value }, (text) => {
                            if (tagsWidget) { tagsWidget.value = text; app.graph.setDirtyCanvas(true, true); }
                        });
                    }
                };
            }

            this.addWidget("button", "💾 Save Tags", null, () => {
                saveTextDialog("tags", tagsWidget, savedTagsDropdown,
                    "/modusflow/ace_audio/save_tags", "/modusflow/ace_audio/list_tags",
                    "tags", "tags");
            });
            this.addWidget("button", "✏️ Update Tags", null, () => {
                updateTextDialog("tags", tagsWidget, savedTagsDropdown,
                    "/modusflow/ace_audio/save_tags", "tags");
            });

            // ── Lyrics dropdown ───────────────────────────────────────────────
            if (savedLyricsDropdown) {
                const orig = savedLyricsDropdown.callback;
                savedLyricsDropdown.callback = (value) => {
                    if (orig) orig.apply(this, arguments);
                    if (value && value !== "--select lyrics--" && value !== "--no lyrics found--") {
                        loadText("/modusflow/ace_audio/load_lyrics", { filename: value }, (text) => {
                            if (lyricsWidget) { lyricsWidget.value = text; app.graph.setDirtyCanvas(true, true); }
                        });
                    }
                };
            }

            this.addWidget("button", "💾 Save Lyrics", null, () => {
                saveTextDialog("lyrics", lyricsWidget, savedLyricsDropdown,
                    "/modusflow/ace_audio/save_lyrics", "/modusflow/ace_audio/list_lyrics",
                    "lyrics", "lyrics");
            });
            this.addWidget("button", "✏️ Update Lyrics", null, () => {
                updateTextDialog("lyrics", lyricsWidget, savedLyricsDropdown,
                    "/modusflow/ace_audio/save_lyrics", "lyrics");
            });

            // ── Song (combined) dropdown ──────────────────────────────────────
            if (savedSongDropdown) {
                const orig = savedSongDropdown.callback;
                savedSongDropdown.callback = (value) => {
                    if (orig) orig.apply(this, arguments);
                    if (value && value !== "--select song--" && value !== "--no songs found--") {
                        loadText("/modusflow/ace_audio/load", { filename: value }, (data) => {
                            if (titleWidget)  { titleWidget.value  = data.title  ?? ""; }
                            if (tagsWidget)   { tagsWidget.value   = data.tags   ?? ""; }
                            if (lyricsWidget) { lyricsWidget.value = data.lyrics ?? ""; }
                            app.graph.setDirtyCanvas(true, true);
                        }, true);
                    }
                };
            }

            this.addWidget("button", "💾 Save Song (Both)", null, () => {
                const rawTitle = titleWidget ? titleWidget.value.trim() : "";
                const filename = rawTitle || prompt("Enter filename to save song as (without extension):");
                if (!filename) return;
                post("/modusflow/ace_audio/save", {
                    filename,
                    title:  rawTitle,
                    tags:   tagsWidget   ? tagsWidget.value   : "",
                    lyrics: lyricsWidget ? lyricsWidget.value : "",
                }).then(data => {
                    if (data.success) {
                        alert(`Song saved as: ${filename}.json`);
                        refreshDropdown(savedSongDropdown, "/modusflow/ace_audio/list", "--select song--", "--no songs found--");
                    } else {
                        alert(`Error saving song: ${data.message}`);
                    }
                });
            });
            this.addWidget("button", "✏️ Update Song (Both)", null, () => {
                const selected = savedSongDropdown ? savedSongDropdown.value : null;
                if (!selected || selected === "--select song--" || selected === "--no songs found--") {
                    alert("Please select a saved song from the dropdown first.");
                    return;
                }
                if (!confirm(`Update "${selected}" with current title, tags and lyrics?`)) return;
                post("/modusflow/ace_audio/save", {
                    filename: selected.replace(/\.json$/, ""),
                    title:  titleWidget  ? titleWidget.value  : "",
                    tags:   tagsWidget   ? tagsWidget.value   : "",
                    lyrics: lyricsWidget ? lyricsWidget.value : "",
                }).then(data => {
                    if (data.success) alert(`"${selected}" updated.`);
                    else alert(`Error: ${data.message}`);
                });
            });

            // ── Shared refresh ────────────────────────────────────────────────
            this.addWidget("button", "🔄 Refresh All", null, () => {
                refreshDropdown(savedTagsDropdown,   "/modusflow/ace_audio/list_tags",   "--select tags--",   "--no tags found--");
                refreshDropdown(savedLyricsDropdown, "/modusflow/ace_audio/list_lyrics", "--select lyrics--", "--no lyrics found--");
                refreshDropdown(savedSongDropdown,   "/modusflow/ace_audio/list",        "--select song--",   "--no songs found--");
            });

            this.resizable = true;
            this.size = [460, 620];

            return r;
        };

        // Preserve widget values on serialisation (skip buttons)
        const onSerialize = nodeType.prototype.onSerialize;
        nodeType.prototype.onSerialize = function (o) {
            if (onSerialize) onSerialize.apply(this, arguments);
            if (!this.widgets) return;
            if (!o.widgets_values) o.widgets_values = [];
            this.widgets.forEach((w, i) => {
                if (w.type !== "button") o.widgets_values[i] = w.value;
            });
        };

        // ── shared helpers ────────────────────────────────────────────────────

        function post(url, body) {
            return fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            }).then(r => r.json()).catch(err => {
                console.error(`[ModusFlow AceStepAudio] POST ${url} error: ${err.message}`);
                return { success: false, message: err.message };
            });
        }

        /** Load text (or JSON object when isJson=true) and pass result to callback. */
        function loadText(url, body, callback, isJson = false) {
            post(url, body).then(data => {
                if (data.success) callback(isJson ? data.data : data.data);
                else console.error(`[ModusFlow AceStepAudio] Load error: ${data.message}`);
            });
        }

        function refreshDropdown(dropdown, listUrl, placeholder, emptyLabel) {
            if (!dropdown) return;
            fetch(listUrl)
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        dropdown.options.values = data.data.length
                            ? [placeholder, ...data.data]
                            : [emptyLabel];
                        dropdown.value = dropdown.options.values[0];
                        app.graph.setDirtyCanvas(true, true);
                    }
                })
                .catch(err => console.error(`[ModusFlow AceStepAudio] Refresh error: ${err.message}`));
        }

        function saveTextDialog(label, textWidget, dropdown, saveUrl, listUrl, payloadKey, ext) {
            const filename = prompt(`Enter filename to save ${label} as (without extension):`);
            if (!filename) return;
            const body = { filename };
            body[payloadKey] = textWidget ? textWidget.value : "";
            post(saveUrl, body).then(data => {
                if (data.success) {
                    alert(`${label} saved as: ${filename}.txt`);
                    const placeholder = `--select ${label}--`;
                    const emptyLabel  = `--no ${label} found--`;
                    refreshDropdown(dropdown, listUrl, placeholder, emptyLabel);
                } else {
                    alert(`Error saving ${label}: ${data.message}`);
                }
            });
        }

        function updateTextDialog(label, textWidget, dropdown, saveUrl, payloadKey) {
            const selected = dropdown ? dropdown.value : null;
            const placeholder = `--select ${label}--`;
            const emptyLabel  = `--no ${label} found--`;
            if (!selected || selected === placeholder || selected === emptyLabel) {
                alert(`Please select a saved ${label} from the dropdown first.`);
                return;
            }
            if (!confirm(`Update "${selected}" with the current ${label}?`)) return;
            const body = { filename: selected.replace(/\.txt$/, "") };
            body[payloadKey] = textWidget ? textWidget.value : "";
            post(saveUrl, body).then(data => {
                if (data.success) alert(`"${selected}" updated.`);
                else alert(`Error updating ${label}: ${data.message}`);
            });
        }
    },
});
