import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "ModusFlow.AllInOneDetailer",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "ModusFlowAllInOneDetailer") return;

        // --- helpers ---

        /** Return all inputs whose name matches slot_N */
        function getSlotInputs(node) {
            return node.inputs.filter(inp => /^slot_\d+$/.test(inp.name));
        }

        /**
         * Ensure there is always exactly one unconnected slot at the end.
         * - If every slot is connected → append slot_(N+1)
         * - If 2+ trailing slots are unconnected → remove the last one (keep ≥ 1)
         */
        function syncSlots(node) {
            const slotInputs = getSlotInputs(node);
            if (slotInputs.length === 0) {
                node.addInput("slot_1", "DETAILER_SLOT");
                node.setDirtyCanvas(true, true);
                return;
            }

            const lastSlot = slotInputs[slotInputs.length - 1];
            const secondLastSlot = slotInputs.length >= 2
                ? slotInputs[slotInputs.length - 2]
                : null;

            const lastConnected = lastSlot.link != null;
            const secondLastConnected = secondLastSlot ? secondLastSlot.link != null : true;

            if (lastConnected) {
                // All trailing slots filled — add a new empty one
                const nextNum = slotInputs.length + 1;
                node.addInput(`slot_${nextNum}`, "DETAILER_SLOT");
                node.setDirtyCanvas(true, true);
            } else if (!lastConnected && !secondLastConnected && slotInputs.length > 1) {
                // Two unconnected at the end — remove the last one
                const idx = node.inputs.indexOf(lastSlot);
                node.removeInput(idx);
                node.setDirtyCanvas(true, true);
                // Recurse in case there are more to trim
                syncSlots(node);
            }
        }

        // --- lifecycle hooks ---

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);
            // Make sure slot_1 exists when a node is freshly placed
            if (getSlotInputs(this).length === 0) {
                this.addInput("slot_1", "DETAILER_SLOT");
            }
        };

        const onConnectionsChange = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function (type, index, connected, link_info) {
            onConnectionsChange?.apply(this, arguments);
            // LiteGraph.INPUT === 1
            if (type !== 1) return;
            const inp = this.inputs[index];
            if (inp && /^slot_\d+$/.test(inp.name)) {
                syncSlots(this);
            }
        };
    },
});
