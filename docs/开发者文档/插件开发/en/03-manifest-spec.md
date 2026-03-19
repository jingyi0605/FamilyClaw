# 03 Manifest Spec

Minimum fields:

- `id`
- `name`
- `version`
- `api_version`
- `types`
- `permissions`
- `entrypoints`
- `capabilities`

For config forms, readable copy and locale keys can now coexist.

Keep the plain-text fallback fields such as:

- `title`
- `label`
- `help_text`

If the plugin also wants to use its own locale resources, add the matching key fields:

- `config_specs[].title_key`
- `config_specs[].description_key`
- `config_specs[].config_schema.fields[].label_key`
- `config_specs[].config_schema.fields[].description_key`
- `config_specs[].config_schema.fields[].enum_options[].label_key`
- `config_specs[].ui_schema.sections[].title_key`
- `config_specs[].ui_schema.sections[].description_key`
- `config_specs[].ui_schema.widgets[].placeholder_key`
- `config_specs[].ui_schema.widgets[].help_text_key`
- `config_specs[].ui_schema.submit_text_key`

The host resolves locale keys through household plugin locales first, then falls back to the readable plain-text copy instead of showing the raw key.

Locale rules to keep straight:

- `locale-pack` is the plugin type for full locale bundles.
- normal plugins may also declare `locales` for their own labels, config copy, card titles, and action text.
- same-`locale_id` messages are merged by message key instead of replacing the whole locale bundle.
- merge priority remains `builtin > official > third_party`.

Supported normal types:

- `integration`
- `action`
- `agent-skill`
- `channel`
- `region-provider`
- `ai-provider`
- `locale-pack`
- `theme-pack`

Supported exclusive slots:

- `memory_engine`
- `memory_provider`
- `context_engine`

For `ai-provider`, the current rule is concrete:

- `entrypoints.ai_provider` is required
- `capabilities.ai_provider` is the provider declaration
- builtin AI providers must be real plugins with real manifests

The host keeps governance and the unified gateway.

`ai-provider` plugins own:

- provider declaration
- field schema
- driver entrypoint
- protocol adaptation
- streaming
- vendor-specific behavior

For `integration` plugins, the current host-facing manifest boundary also includes:

- `instance_model`
- `refresh_mode`
- `supports_discovery`
- `supports_actions`
- `supports_cards`
- `entity_types`
- `default_cache_ttl_seconds`
- `max_stale_seconds`

If the plugin should create a default instance automatically after enablement, also declare:

- `auto_create_default_instance`
- `default_instance_display_name`
- `default_instance_config`

If the plugin renders one card per device or per instance, use:

- `dashboard_cards[].card_key` for fixed cards
- `dashboard_cards[].card_key_prefix` for dynamic cards
