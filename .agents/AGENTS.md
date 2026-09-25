# ComfyUI-ModusFlow Workspace Rules

The following rules apply specifically to this workspace when using the Gemini/Antigravity agent.

## Mandatory Syntax Validation

After every file edit, validate syntax immediately before doing anything else:

- **JavaScript**: `node --check <filepath>`
- **Python**: `python -m py_compile <filepath>`

If validation fails, fix the error before making any other changes. Never make multiple edits without validating between them.

## File Editing Rules

- Read the target area before editing to ensure exact whitespace and indentation matches
- When adding features, prefer rewriting entire functions over multiple small replacements
- If code becomes corrupted, rewrite from scratch rather than patching
- Never use placeholder comments like `...existing code...` in replacements

## Project Structure

- **Backend (Python)**: `modules/*.py` and `__init__.py`
- **Frontend (JavaScript)**: `web/*.js`
- **Node Registration**: All nodes must appear in both `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS` in `__init__.py`
- **API Routes**: Defined in `__init__.py` via `@server.PromptServer.instance.routes`
- **Documentation**: One `.md` per node in `docs/`, all linked from `README.md`

## Documentation Requirements

Every code change requires a corresponding documentation update:

- **New feature**: add to the relevant node doc in `docs/`; update `README.md` if it affects the overview
- **Modified feature**: update affected parameters, inputs, outputs, and troubleshooting sections
- **New node**: create `docs/<NodeName>.md` with overview, features, inputs/outputs, usage, tips, and troubleshooting; link from `README.md`
- **Breaking change**: document clearly and provide migration guidance

## ComfyUI Node Patterns

### Frontend JavaScript

```javascript
app.registerExtension({
    name: "modusflow.NodeName",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "NodeClassName") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                onNodeCreated?.apply(this, arguments);
                // node setup
            };
        }
    }
});
```

### Backend Python

```python
class NodeClassName:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}, "optional": {}, "hidden": {}}

    RETURN_TYPES = ()
    FUNCTION = "method_name"
    OUTPUT_NODE = False  # True for output nodes
    CATEGORY = "ModusFlow"
```

### API Routes

```python
@server.PromptServer.instance.routes.get("/modusflow/endpoint")
async def handler(request):
    try:
        return web.json_response({"success": True, "data": result})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})
```

## File Edit Workflow

1. Read the target code section
2. Make the edit
3. Validate syntax immediately (`node --check` or `python -m py_compile`)
4. If invalid: fix the error, re-validate, do not touch other files until it passes
5. Test functionality in ComfyUI
6. Move to the next change only after validation and testing pass

## Testing Checklist

| Change type | Steps |
|---|---|
| JavaScript edit | `node --check <file>` → check browser console → test node in ComfyUI |
| Python edit | `python -m py_compile <file>` → restart ComfyUI → test node |
| API change | test endpoint via browser or curl → verify error handling and response format |
