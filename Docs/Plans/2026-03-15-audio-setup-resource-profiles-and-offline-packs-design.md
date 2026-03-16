# Audio Setup Resource Profiles And Offline Packs Design

## Summary

This design extends the existing bundle-first audio setup flow in `/setup` with two follow-on capabilities:

1. real differentiation inside each hardware-local bundle via `resource_profile`
2. a phased offline provisioning model built around importable `audio bundle packs`

The main correction from the first bundle design is that a bundle can no longer be treated as a single fixed install plan. The stable operator-facing unit remains the hardware family:

- `cpu_local`
- `apple_silicon_local`
- `nvidia_local`
- `hosted_plus_local_backup`

But the actual plan must now come from:

`bundle_id + resource_profile + catalog_version`

This avoids an explosion of top-level bundle ids while still allowing materially different install and verification behavior.

## Goals

- Keep `/setup` hardware-first for operator comprehension.
- Differentiate local bundles by real resource tiers instead of labels alone.
- Make recommendations conservative when machine capability signals are weak.
- Preserve compatibility with the existing bundle-first rollout.
- Make safe reruns exact-match and profile-aware.
- Add a practical offline provisioning path without overpromising full dependency portability in v1.

## Non-Goals

- Replacing the existing bundle ids with a large matrix like `cpu_local_light`.
- Building a full resumable workflow engine in this pass.
- Shipping a platform-independent offline installer that bundles every native dependency.
- Exposing every profile and every provider at once in the default `/setup` path.
- Removing the advanced engine picker.

## Problems With The Naive Next Step

The obvious extension, “add `light`, `balanced`, and `performance` and later zip up models,” has several structural problems in the current implementation:

1. The setup API and readiness state are bundle-only today, so profile selection would be ambiguous unless `resource_profile` becomes a first-class field everywhere.
2. Safe rerun currently keys off coarse engine-level step names. That will produce false skips once `light` and `performance` use different models or dependency variants.
3. Verification is bundle-level and generic. It does not currently prove that the selected profile’s expected model, device, or fallback chain is healthy.
4. The recommender only has a shallow machine profile today, so profile selection must be conservative until RAM and related signals are available.
5. Offline provisioning is currently incompatible with live-only dependency paths such as Hugging Face downloads and git-based package installs.

The design below treats these as compatibility constraints, not edge cases.

## Design Principles

- Hardware family first, profile second
- Exact-match provisioning identity
- Conservative recommendation when signals are incomplete
- Evidence before readiness
- Progressive disclosure in the UI
- Phased offline support instead of one oversized promise
- Manifest-driven docs and pack metadata

## Revised Architecture

The audio setup contract becomes:

`machine profile -> recommended family/profile pair -> provisioning plan expansion -> verification -> readiness report`

The selected family remains the primary operator-facing choice. The selected profile is a secondary choice within that family.

### Family Model

Each bundle family keeps:

- shared operator-facing label and description
- shared guided or manual prerequisites
- shared offline suitability
- shared family-level constraints
- a set of named resource profiles

### Resource Profile Model

Each profile declares the actual install-time differences:

- default STT engine and model selection
- default TTS engine and variants
- optional auxiliary assets
- config overrides
- expected disk estimate
- expected resource class
- expected fallback order
- verification expectations

The standard local profiles are:

- `light`
- `balanced`
- `performance`

The hybrid hosted family stays effectively `balanced` in v1 unless it gains a meaningful second profile later.

## Data Model And Compatibility Changes

### Catalog

The bundle catalog should move from a flat `bundle -> plan` structure to:

- `AudioBundleFamily`
- `AudioResourceProfile`
- `catalog_version`

Recommended minimum compatibility fields:

- `bundle_id`
- `resource_profile`
- `catalog_version`
- `selection_key`

Where `selection_key` is a normalized identity derived from the exact family/profile/catalog combination.

### Readiness State

The persisted readiness record should be extended to include:

- `selected_bundle_id`
- `selected_resource_profile`
- `catalog_version`
- `selection_key`
- `installed_profiles`
- `installed_asset_manifests`
- `last_verification`
- `remediation_items`

`resource_profile` must default to `balanced` for older records so the current bundle-only state remains interpretable.

### API Contract

Setup APIs should accept and return the selected profile explicitly.

Provision and verify requests become conceptually:

```json
{
  "bundle_id": "nvidia_local",
  "resource_profile": "balanced"
}
```

Recommendations should return ranked `family + profile` pairs, not just families.

## Recommendation Model

The recommender should remain hardware-first in presentation, but internally it should score profile pairs.

### V1 Trusted Signals

- platform
- architecture
- Apple Silicon
- CUDA availability
- FFmpeg presence
- eSpeak presence
- free disk
- download availability

### V1 Conservative Policy

When RAM or VRAM is unknown:

- prefer `balanced`
- fall back to `light` if disk is tight or prerequisites are weak
- do not recommend `performance` unless there is positive evidence

The recommendation result should include:

- recommended family
- recommended profile
- ranked alternatives
- confidence level
- exclusion reasons

## Provisioning Design

Provisioning must expand from `family + profile`, not just `family`.

### Expansion Rules

- family contributes shared prerequisites and baseline defaults
- profile contributes concrete engines, model sizes, config overrides, and verification expectations
- the expanded plan is serialized into a deterministic manifest

### Step Identity

Safe rerun must key off profile-aware step identities. Step names should include enough information to avoid false skips, for example:

- family
- profile
- engine
- model or variant
- catalog version

The implementation does not need a resumable DAG, but it does need deterministic skip identity.

### Profile Switching

Profile switching should be explicit about leftover assets.

When switching profiles, setup should classify assets as:

- `required for selected profile`
- `retained but unused`
- `removable`

V1 does not need automatic pruning, but it should surface the difference so disk estimates remain honest.

## Verification Design

Verification must become profile-aware.

It should validate:

- the expected primary STT engine and configured model
- the expected primary TTS engine and configured variant
- required local assets for the selected profile
- expected runtime path, such as CUDA or Apple-local acceleration where applicable
- hosted credentials and endpoint reachability when the selected family depends on hosted defaults

Secondary fallbacks should remain advisory in v1.

Readiness still resolves to:

- `ready`
- `ready_with_warnings`
- `partial`
- `failed`

But those states now refer to the selected family/profile pair rather than the family alone.

## Setup UI Design

The current audio step is already dense, so profile selection must be introduced through progressive disclosure.

### Recommended UI

1. Show the recommended hardware family card.
2. Within the selected family card, show profile chips or small cards:
   - `Light`
   - `Balanced`
   - `Performance`
3. For each profile, show:
   - speed/quality summary
   - expected disk footprint
   - expected resource pressure
   - offline suitability
4. Keep alternative families collapsed behind the existing “Choose different bundle” affordance.
5. Keep offline pack import as a separate provisioning mode, not another inline control on the main happy path.

This keeps the stage readable while still surfacing the real choice.

## Offline Provisioning Design

Offline provisioning should be phased.

### V1: Preseeded Model And Manifest Packs

An `audio bundle pack` should contain:

- `bundle_id`
- `resource_profile`
- `catalog_version`
- platform and architecture constraints
- Python version constraints
- model asset manifest with exact revisions
- predownloaded local assets where practical
- config defaults
- checksums

V1 assumption:

- the target machine can already satisfy Python dependencies locally
- the pack solves model and manifest portability first

This is the practical first step for air-gapped or bandwidth-constrained installs.

### V2: Full Dependency Packs

Later, extend packs with:

- local wheelhouse
- pinned dependency manifest
- stronger platform and ABI checks

This is the first point at which the product can claim a more complete offline provisioning story.

### Import Mode

`/setup` should expose a secondary provisioning mode:

- `Online provisioning`
- `Import offline pack`

Import should:

- validate checksums
- validate platform and Python compatibility
- register imported assets in the readiness state
- report any remaining guided prerequisites

## Docs Strategy

Docs must become profile-aware and pack-aware.

The manifest-driven generator should emit:

- family overview
- per-profile default engines and models
- disk and resource expectations
- offline-pack compatibility
- prerequisite automation tier

The docs should not be treated as manually curated truth once profiles diverge.

## Testing Strategy

### Unit

- catalog family/profile validation
- readiness migration defaults for missing `resource_profile`
- recommendation scoring for family/profile pairs
- deterministic step-key generation
- pack manifest validation

### Integration

- setup recommendations return family/profile pairs
- setup provisioning persists selected profile and exact selection key
- safe rerun does not skip across mismatched profiles
- verification respects the selected profile
- offline pack import validates compatibility and updates readiness

### UI Contract

- selected family and selected profile render distinctly
- profile changes update provisioning payloads
- import mode remains secondary to the main online flow

## Rollout

### Phase 1

- add `resource_profile`, `catalog_version`, and exact-match step identity
- keep `balanced` as the implicit compatibility default
- update recommendations, provisioning, readiness, and verification to use profile-aware selection

### Phase 2

- add setup UI profile selection and manifest-driven docs
- introduce asset retention accounting for profile switches

### Phase 3

- add v1 offline bundle packs for model/manifests
- expose import mode in `/setup`

### Phase 4

- evaluate full dependency packs only after the v1 import path is stable

## Recommendation

The next implementation should start by making the current bundle architecture profile-aware before adding more ambitious offline mechanics. That means compatibility fields, exact-match safe reruns, and profile-aware verification first.

Only after that foundation exists should the project add preseeded offline packs, beginning with model and manifest portability rather than a full dependency bundle.
