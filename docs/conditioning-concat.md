# Conditioning Concat

Encode a text string and concatenate it onto an existing conditioning.

## Overview

The ModusFlow Conditioning Concat node encodes a text prompt with a given CLIP model and appends the result to an existing conditioning. This is useful for adding extra terms, style tags, or subject descriptors to a conditioning that was produced by another node without having to re-encode the original prompt.

## Inputs

| Input | Type | Description |
|-------|------|-------------|
| clip | CLIP | CLIP model used to encode the new text |
| conditioning | CONDITIONING | Existing conditioning to append to |
| text | STRING | Text to encode and concatenate |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| conditioning | CONDITIONING | Original conditioning with the new text encoding appended |

## Usage Patterns

### Appending Style Tags
```
CLIP Text Encode → conditioning ──┐
                                   ├──▶ Conditioning Concat → KSampler positive
"oil painting, dramatic lighting" ┘
```

### Extending Multi-CLIP Output
```
Multi-CLIP Text Encode → conditioning ──┐
                                         ├──▶ Conditioning Concat
clip1 ────────────────────────────────── ┘
"additional subject detail"
```

### Chaining Multiple Appends
```
Conditioning Concat → conditioning → Conditioning Concat → KSampler
```

## Tips

- **Order matters**: The new text is concatenated after the existing entries; the model sees the combined result
- **Empty text**: Passing an empty string will encode a blank prompt — connect text conditionally if needed
- **Same CLIP**: Use the same CLIP model that produced the original conditioning for consistent embedding space

## Troubleshooting

- **Shape mismatch errors**: Ensure the CLIP used matches the one that produced the input conditioning
- **No effect on output**: Verify the node is wired into the positive/negative input of the sampler and text is non-empty
