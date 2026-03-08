# Model Pricing Catalog Cleanup Design

**Date:** 2026-03-06

## Goal

Remove outdated or unavailable models from the pricing catalog so it only advertises current provider-backed model IDs, while preserving a narrow compatibility path for obvious renames.

## Context

`tldw_Server_API/Config_Files/model_pricing.json` is not just a billing reference. The backend uses it to enumerate provider models for commercial providers, and the frontend consumes those backend model lists for pickers and generated requests. As a result, stale catalog entries are surfaced as selectable models throughout the product.

## Decision

Adopt a strict cleanup policy:

- Remove model IDs that are no longer listed on current official provider pricing or model pages.
- Keep only live, documented model IDs in provider blocks.
- Add top-level `model_aliases` entries only where the migration target is clear and low-risk.
- Do not keep deprecated IDs in provider blocks just to preserve discovery compatibility.

## Why This Approach

This keeps the catalog aligned with what users can actually select and call today. It avoids continuing to advertise dead or preview-only IDs, while still allowing a few obvious legacy requests to resolve through aliases instead of failing immediately.

## Scope

The cleanup will focus on providers whose entries are currently most likely to drift and that were already touched during the pricing refresh:

- `openai`
- `anthropic`
- `moonshot`
- `zai`

It may also prune clearly stale entries from other providers when the current provider documentation makes the removal unambiguous.

## Alias Policy

Aliases are only appropriate when all of the following are true:

- The old ID is no longer current.
- The replacement is a documented current model.
- The replacement is the clear successor, not merely a similar tier.

Examples of acceptable alias cases:

- legacy family aliases that now map to a documented canonical ID
- old shorthand names where the provider’s official API has standardized on a new exact identifier

Examples that should not get aliases:

- preview models with no clear successor
- older reasoning or multimodal models that differ materially from current families
- provider-specific experimental IDs

## Data Flow Impact

After cleanup:

- `list_provider_models()` will stop returning removed IDs.
- provider model list endpoints will stop advertising removed IDs.
- UI model pickers will no longer surface removed IDs.
- requests using alias-covered legacy IDs can still resolve to current models through chat alias loading.

## Testing Strategy

Add focused tests that verify:

- removed models no longer appear in provider model enumeration
- alias-covered legacy IDs resolve to the expected current ID
- representative current models still return exact pricing from `PricingCatalog`

## Risks

- Some clients may still send removed model IDs.
- Over-aggressive aliasing could silently reroute requests to materially different models.

## Mitigations

- Use aliases only for obvious renames.
- Prefer hard removal over speculative remapping.
- Keep tests focused on both enumeration and compatibility behavior so the intended policy is enforced.
