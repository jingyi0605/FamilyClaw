---
title: Field Specification
docId: en-4.6
version: v0.1
status: draft
order: 460
outline: deep
---

# Field Specification

## Minimal required manifest fields

- `id`
- `name`
- `version`
- `api_version`
- `types`
- `permissions`
- `entrypoints`
- `capabilities`

## Add these when configuration is needed

- `config_specs`
- `locales`

## Current key points

- `enum_options` and `option_source` are mutually exclusive
- `depends_on` and `clear_on_dependency_change` express field linkage
- User-facing text should keep readable fallback text even when dictionary keys exist

## Completion standard

- Plugin authors know which fields are hard requirements and which are extensions.
