# Relations Layer (V1)

This folder stores one-off enriched knowledge artifacts generated from the current corpus.

## Files
- `entity_index.v1.json`: extracted entities such as product models, capabilities, and modules
- `relation_graph.v1.json`: flat relation edges with source card ids
- `product_to_components.v1.json`: product model -> component list
- `product_to_capabilities.v1.json`: product model -> capability list
- `capability_to_scenarios.v1.json`: capability -> scenario list
- `module_to_dataflows.v1.json`: module -> dataflow / interface terms
- `layer_to_modules.v1.json`: architecture layer -> module list
- `card_summaries.v1.json`: short per-card semantic summary for quick browse
- `concept_index.v1.json`: concept -> related cards

## Intended use
Use these files as the first association layer before deep reading full card bodies.
