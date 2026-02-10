## Stage 1: Login-Event Trigger And Auth Gating
**Goal**: Make splash display strictly after successful login actions (password or magic-link), not on app mount/reload/navigation.
**Success Criteria**:
- Splash is not shown on initial app load, refresh, or route changes unless a successful login just occurred.
- Splash is shown after successful login from all supported login entry points.
- Splash behavior is consistent in both `/login` and onboarding login flows.
**Tests**:
- Integration test: failed login -> no splash.
- Integration test: successful password login -> splash appears once.
- Integration test: successful magic-link verify -> splash appears once.
- Integration test: refresh after successful login -> no splash.
**Status**: Complete

## Stage 2: Runtime Correctness And Compile-Safe Fixes
**Goal**: Resolve runtime/typing bugs that can break effects or produce incorrect animation behavior.
**Success Criteria**:
- `terminal_boot` card no longer causes runtime errors with object-based boot sequence config.
- `TextExplosion` timing is corrected (no double `dt` conversion), and invalid particle fields are removed or properly modeled.
- `QuantumParticles` uses alive particle count correctly.
- `SpyVsSpy` scanline logic no longer references nonexistent grid APIs.
**Tests**:
- Typecheck run focused on splash modules passes.
- Unit tests for `TerminalBoot` config parsing and rendering safety.
- Unit tests for `TextExplosion` movement delta behavior.
- Unit tests for `QuantumParticles` respawn condition and `SpyVsSpy` scanline path.
**Status**: Complete

## Stage 3: Exact Effect Config Fidelity
**Goal**: Ensure source card config keys/values are honored by corresponding effects with source-compatible semantics.
**Success Criteria**:
- All cards with `effectConfig` have their configured fields consumed by effect implementations.
- Key mismatches are removed (e.g., source key names work directly or via explicit compatibility adapters).
- High-impact parity gaps are fixed (`starfield`, `ascii_morph`, `text_explosion`, `spotlight`, `sound_bars`, `raindrops`, `old_film`, `pixel_zoom`).
**Tests**:
- Table-driven unit tests per effect verifying representative config fields change behavior.
- Regression test validating every `effectConfig` field in `splash-cards.ts` is either consumed or intentionally ignored with documented rationale.
**Status**: Complete

## Stage 4: Exact Source Data Fidelity (Messages/Cards/Art)
**Goal**: Align splash datasets to source fidelity while preserving web portability.
**Success Criteria**:
- `splash-messages.ts` exactly matches source message set (count/content/duplicates/unicode preserved).
- Card set strategy is made explicit and implemented:
  - Source-fidelity canonical set matches `card_definitions.py`.
  - Any web-only/extended cards are separated from canonical source set and not used in fidelity mode by default.
- ASCII art mappings remain source-accurate for all canonical card references.
**Tests**:
- Deterministic parity test for message count/content hash.
- Deterministic parity test for canonical card names/effect mapping against a checked-in source snapshot.
- Unit test: every canonical card references valid effect and ascii keys.
**Status**: Complete

## Stage 5: UX/Accessibility/Behavior Parity Hardening
**Goal**: Fix dismiss/reduced-motion/theming behavior to match requirements and avoid regressions.
**Success Criteria**:
- Auto-dismiss uses the same fade-out path as click/key dismiss (no abrupt unmount).
- `prefers-reduced-motion: reduce` renders static HTML-only splash (no canvas animation loop).
- Overlay colors/styles use theme-aware CSS variables where required.
- Escape/click dismissal remains functional and deterministic.
**Tests**:
- Integration test: auto-dismiss performs fade then unmount.
- Integration test: reduced-motion mode does not animate canvas.
- Integration test: light/dark theme sanity check for overlay readability.
- Existing frontend test suite passes with no splash-related regressions.
**Status**: Complete

## Issue Coverage Map
- Issue 1 (terminal_boot runtime crash): Stage 2
- Issue 2 (strict login trigger semantics): Stage 1
- Issue 3 (effectConfig not consumed): Stage 3
- Issue 4 (TextExplosion timing/invalid props): Stage 2
- Issue 5 (auto-dismiss skips fade path): Stage 5
- Issue 6 (QuantumParticles alive-count bug): Stage 2
- Issue 7 (SpyVsSpy nonexistent API): Stage 2
- Issue 8 (reduced-motion + theme adaptation gaps): Stage 5
- Issue 9 (message fidelity mismatch): Stage 4
