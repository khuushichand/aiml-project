Enhanced UX Review Prompt with User Personas

  Role: You are a Principal UX/HCI Designer with 15+ years of experience in healthcare IT systems, currently working at a large teaching hospital. You specialize in designing clinical decision support tools, EHR
  interfaces, and AI-assisted documentation systems.

  Context: Review the Chat Dictionaries workspace page - a terminology management system that allows users to define pattern-replacement pairs (literal strings or regex) that are applied to text before it reaches
  an AI model. This feature is particularly valuable in clinical settings for standardizing medical terminology, expanding abbreviations, and normalizing institution-specific jargon.

  ---
  User Personas

  Persona 1: Dr. Sarah Chen — Attending Physician (Internal Medicine)
  ┌───────────────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │     Attribute     │                                                                  Details                                                                   │
  ├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Age/Experience    │ 42, practicing 15 years                                                                                                                    │
  ├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Tech Proficiency  │ Moderate — comfortable with EHR, avoids "power user" features                                                                              │
  ├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Time Available    │ Extremely limited — 15-minute patient slots, documents between visits                                                                      │
  ├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Device Context    │ Desktop in clinic, tablet on rounds, occasionally phone                                                                                    │
  ├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Primary Use Cases │ Wants AI to understand her shorthand ("pt" → "patient", "hx" → "history"); needs department-specific drug abbreviations expanded correctly │
  ├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Pain Points       │ Frustrated when tools require multiple clicks; won't read help docs; abandons features that feel "technical"                               │
  ├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Goals             │ Set it up once and forget it; trust that substitutions are correct without constant checking                                               │
  ├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Quote             │ "I don't have time to learn a new system. If it doesn't work in 30 seconds, I'm going back to my old workflow."                            │
  └───────────────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
  ---
  Persona 2: Marcus Thompson — First-Year Resident (Emergency Medicine)
  ┌───────────────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │     Attribute     │                                                                              Details                                                                               │
  ├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Age/Experience    │ 27, just started residency                                                                                                                                         │
  ├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Tech Proficiency  │ High — grew up with technology, comfortable with regex basics                                                                                                      │
  ├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Time Available    │ Variable — sometimes slammed, sometimes waiting; willing to tinker during downtime                                                                                 │
  ├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Device Context    │ Primarily workstation-on-wheels in ED                                                                                                                              │
  ├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Primary Use Cases │ Building personal dictionaries for ED-specific terminology; experimenting with regex for medication dosing patterns; wants to share dictionaries with co-residents │
  ├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Pain Points       │ Makes mistakes and needs to understand what went wrong; wants to learn but documentation is often poor                                                             │
  ├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Goals             │ Master the tool to impress attendings; build efficient workflows early in career                                                                                   │
  ├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Quote             │ "Show me the advanced options. I'll figure it out, but give me good error messages when I mess up."                                                                │
  └───────────────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
  ---
  Persona 3: Jennifer Okafor — Medical Scribe
  ┌───────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │     Attribute     │                                                                                   Details                                                                                   │
  ├───────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Age/Experience    │ 24, scribing for 2 years while applying to PA school                                                                                                                        │
  ├───────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Tech Proficiency  │ High for documentation tools — this is her core job                                                                                                                         │
  ├───────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Time Available    │ Works alongside physicians in real-time; speed is critical                                                                                                                  │
  ├───────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Device Context    │ Laptop, sometimes standing, often in noisy environments                                                                                                                     │
  ├───────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Primary Use Cases │ Heavy user — maintains dictionaries for 6 different physicians she scribes for; each has unique abbreviation preferences; needs quick switching between active dictionaries │
  ├───────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Pain Points       │ Each physician uses different shorthand; bulk operations are essential; can't afford to activate wrong dictionary and corrupt notes                                         │
  ├───────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Goals             │ Zero errors in substitutions; fast dictionary switching; easy bulk import when onboarding new physician                                                                     │
  ├───────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Quote             │ "I need to switch between Dr. Chen's dictionary and Dr. Patel's in two clicks, max. And I need to KNOW which one is active."                                                │
  └───────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
  ---
  Persona 4: Robert "Bobby" Nguyen, RN — Charge Nurse (ICU)
  ┌───────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │     Attribute     │                                                                                    Details                                                                                    │
  ├───────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Age/Experience    │ 55, nursing for 30 years, charge nurse for 10                                                                                                                                 │
  ├───────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Tech Proficiency  │ Low-moderate — resistant to change, learned EHR reluctantly                                                                                                                   │
  ├───────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Time Available    │ Unpredictable — managing unit crises takes priority                                                                                                                           │
  ├───────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Device Context    │ Shared workstations, often logged in/out quickly                                                                                                                              │
  ├───────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Primary Use Cases │ Rarely creates dictionaries; uses pre-made ICU dictionary maintained by informatics team; needs to verify AI understood critical values correctly (vent settings, drip rates) │
  ├───────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Pain Points       │ Distrusts AI; needs absolute confidence substitutions are correct for safety-critical terms; font sizes are often too small                                                   │
  ├───────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Goals             │ Verify substitutions before trusting them; simple preview that shows exactly what changed                                                                                     │
  ├───────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Quote             │ "I've seen too many near-misses from computer errors. Show me proof this thing works before I trust it with my patients."                                                     │
  └───────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
  ---
  Current Functionality to Evaluate

  1. Dictionary Management — Create, edit, delete, activate/deactivate dictionaries
  2. Entry Management — Add pattern-replacement pairs with options for: regex vs. literal matching, probability (0-1), case sensitivity, max replacements, grouping
  3. Validation Tools — Schema validation, regex safety checks, template syntax validation
  4. Preview Tool — Test substitutions on sample text with token budget and iteration limits
  5. Import/Export — JSON and Markdown formats

  ---
  Evaluation Criteria (Mapped to Personas)
  ┌──────────────────────┬───────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │      Criterion       │   Persona Focus   │                                                                         Questions to Address                                                                          │
  ├──────────────────────┼───────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Error Prevention     │ Bobby, Jennifer   │ How well does the UI prevent mistakes that could cause incorrect medical terminology substitutions? Are destructive actions properly guarded? Is the active           │
  │                      │                   │ dictionary status unmistakably clear?                                                                                                                                 │
  ├──────────────────────┼───────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Cognitive Load       │ Dr. Chen, Bobby   │ Can a busy clinician quickly understand what each dictionary does? Is the information hierarchy clear? Can someone glance and know the system state?                  │
  ├──────────────────────┼───────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Learnability         │ Dr. Chen, Bobby   │ Could someone figure this out without training? Are advanced features (regex, probability) appropriately hidden from casual users?                                    │
  ├──────────────────────┼───────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Progressive          │ Dr. Chen vs.      │ Are basic features simple while advanced features accessible? Can Marcus find regex options without Bobby being overwhelmed?                                          │
  │ Disclosure           │ Marcus            │                                                                                                                                                                       │
  ├──────────────────────┼───────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Verification & Trust │ Bobby, Dr. Chen   │ Is it easy to verify substitutions work correctly before relying on them? Can users audit what happened? Is the preview unmistakably clear about what changed?        │
  ├──────────────────────┼───────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Efficiency           │ Jennifer, Marcus  │ How many clicks to accomplish common tasks? Are batch operations supported? Can Jennifer switch dictionaries quickly?                                                 │
  ├──────────────────────┼───────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Multi-Context        │ Jennifer          │ Can users manage multiple dictionaries for different contexts? Is it clear which dictionary applies where?                                                            │
  │ Support              │                   │                                                                                                                                                                       │
  ├──────────────────────┼───────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Accessibility        │ Bobby             │ Sufficient font sizes? Color contrast? Works with reading glasses? Keyboard navigable?                                                                                │
  ├──────────────────────┼───────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Error Recovery       │ Marcus            │ If regex is wrong, can the user understand what happened and fix it? Are error messages educational?                                                                  │
  ├──────────────────────┼───────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Terminology          │ Dr. Chen, Bobby   │ Is the UI language appropriate for non-technical clinical users? (Avoid: "regex", "schema", "iteration")                                                              │
  └──────────────────────┴───────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
  ---
  Scenarios to Evaluate
  ┌───────────────────┬─────────────────┬────────────────────────────────────────────────────────────────────────┐
  │     Scenario      │ Primary Persona │                                  Task                                  │
  ├───────────────────┼─────────────────┼────────────────────────────────────────────────────────────────────────┤
  │ First-time setup  │ Dr. Chen        │ Create first dictionary with 5 common abbreviations in under 3 minutes │
  ├───────────────────┼─────────────────┼────────────────────────────────────────────────────────────────────────┤
  │ Quick switch      │ Jennifer        │ Switch active dictionary between two physicians in under 5 seconds     │
  ├───────────────────┼─────────────────┼────────────────────────────────────────────────────────────────────────┤
  │ Verify before use │ Bobby           │ Test that "KCl 20 mEq" isn't being mangled before trusting AI output   │
  ├───────────────────┼─────────────────┼────────────────────────────────────────────────────────────────────────┤
  │ Debug regex error │ Marcus          │ Figure out why a pattern isn't matching and fix it                     │
  ├───────────────────┼─────────────────┼────────────────────────────────────────────────────────────────────────┤
  │ Bulk import       │ Jennifer        │ Import a colleague's dictionary and review entries before activating   │
  ├───────────────────┼─────────────────┼────────────────────────────────────────────────────────────────────────┤
  │ Audit trail       │ Bobby           │ Determine what substitutions were applied to a specific text           │
  └───────────────────┴─────────────────┴────────────────────────────────────────────────────────────────────────┘
  ---
  Deliverables Requested

  1. Heuristic Evaluation — Score against Nielsen's 10 heuristics (1-5 scale with justification), noting which personas are most affected
  2. Persona-Specific Issues — Top 3 usability problems for each persona
  3. Critical Safety Issues — Any patterns that could lead to patient safety incidents
  4. Quick Wins — 5 low-effort improvements with high impact (Small effort / High value)
  5. Recommended Redesigns — Wireframe suggestions for major structural changes, prioritized by persona impact
  6. Accessibility Audit — WCAG 2.1 AA compliance gaps, with special attention to Bobby's needs

  Output Format: Structured report with:
  - Severity ratings: Critical (patient safety) / High / Medium / Low
  - Effort estimates: Small (< 1 day) / Medium (1-3 days) / Large (> 3 days)
  - Persona impact tags for each finding