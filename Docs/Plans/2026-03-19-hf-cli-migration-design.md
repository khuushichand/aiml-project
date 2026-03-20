# Hugging Face CLI Migration Design

**Date:** 2026-03-19

## Goal

Replace outdated `huggingface-cli` references with the current `hf` CLI across repo-facing guidance and user-facing runtime help text, while keeping Python package and import names unchanged.

## Problem

The repository currently documents and surfaces `huggingface-cli` commands in multiple setup guides, READMEs, and error messages. Hugging Face now documents `hf` as the supported CLI interface. Leaving the old command in place makes setup instructions stale and increases the chance that users follow outdated guidance during model download workflows.

## Decision

Standardize on `hf` for all repo-local command examples and prose references that describe the CLI.

Also modernize adjacent installation guidance where it is part of the same workflow:

- Prefer `pip install -U "huggingface_hub"` for this repo's Python and virtualenv-oriented setup guides.
- Use `hf download ...` in shell examples.
- Mention `hf auth login` where gated or private repo access is relevant.
- Preserve `huggingface-hub` and `huggingface_hub` when referring to the Python package or imports.

## Why This Approach

- It aligns the repository with current upstream Hugging Face documentation.
- It keeps setup guidance consistent with the repo's Python-first environment instructions.
- It limits behavior changes to user-facing text, docs, and tests instead of widening scope into download implementation code.

## Scope

### Runtime Text

- Update user-facing help and error messages that currently instruct users to run `huggingface-cli`.
- Update matching unit tests that assert on those messages.

### Documentation

- Update command examples from `huggingface-cli download` to `hf download`.
- Update nearby prose that says to use `huggingface-cli`.
- Refresh adjacent install snippets so they prefer `pip install -U "huggingface_hub"` where the doc is already describing CLI setup.
- Add brief authentication guidance when the workflow may involve gated repos.

### Verification

- Confirm no `huggingface-cli` or `huggingface_cli` references remain in the repository after the migration.
- Run targeted tests for the touched runtime string change.
- Run Bandit on the touched Python files because user-facing code text changes still touch runtime Python modules.

## Non-Goals

- No change to actual model download implementation logic.
- No rename of Python package references such as `huggingface-hub` or `huggingface_hub`.
- No broad rewrite of unrelated Hugging Face documentation that does not mention the legacy CLI.
