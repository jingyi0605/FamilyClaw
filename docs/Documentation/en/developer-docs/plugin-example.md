---
title: Example Plugin
docId: en-4.8
version: v0.1
status: active
order: 480
outline: deep
---

# Example Plugin

For your first plugin, do not start with high-risk control logic or a complex protocol. Start by studying the real built-in plugins already in the repository.

## Example 1: `health-basic-reader`

Location:

- `apps/api-server/app/plugins/builtin/health_basic/`

Good for learning:

- what the smallest `integration` plugin looks like
- how to declare a `schedule` trigger
- how to provide dashboard cards

Important manifest parts:

- `types: ["integration"]`
- `entrypoints.integration`
- `capabilities.integration`
- `dashboard_cards`

This is the best first reference because it does not require discovery and does not carry complex action execution logic.

## Example 2: `builtin.provider.chatgpt`

Location:

- `apps/api-server/app/plugins/builtin/ai_provider_chatgpt/manifest.json`

Good for learning:

- how to design `ai-provider` field schemas
- how to declare runtime capability
- how to express the capability boundary for an OpenAI-compatible provider
- how to add provider-side protocol selection without mutating the shared OpenAI driver contract
- how to normalize a user-entered site root into a usable `/v1` API base in the provider layer

This kind of plugin is not the best place to learn business logic. It is the best place to learn the division of labor: the host governs, the plugin adapts.

## Example 3: `channel-feishu`

Location:

- `apps/api-server/app/plugins/builtin/channel_feishu/manifest.json`

Good for learning:

- how to write `config_specs`
- how to describe forms with `ui_schema`
- how to declare channel binding capabilities

If you want to build a communication channel integration, this example is much more useful than a blank README.

## Example 4: `builtin.theme.chun-he-jing-ming`

Location:

- `apps/api-server/app/plugins/builtin/theme_chun_he_jing_ming_pack/`

Good for learning:

- how a `theme-pack` resource plugin is declared
- how to write `tokens_resource`, `platform_targets`, and `resource_source`

## Recommended order for a first plugin

1. choose a simple type first, preferably `integration` or `theme-pack`
2. get the manifest correct first
3. then write the smallest possible entry function
4. then connect configuration
5. then validate it inside the host

## Skeleton for a minimal `integration` plugin

```text
my_demo_plugin/
├── __init__.py
├── manifest.json
├── integration.py
├── README.md
└── tests/
```

Your `manifest.json` should include at least:

```json
{
  "id": "my-demo-plugin",
  "name": "My Demo Plugin",
  "version": "0.1.0",
  "api_version": 1,
  "types": ["integration"],
  "permissions": ["device.read"],
  "risk_level": "low",
  "triggers": ["manual"],
  "entrypoints": {
    "integration": "my_demo_plugin.integration.sync"
  },
  "capabilities": {
    "integration": {
      "domains": ["demo"],
      "instance_model": "single_instance",
      "refresh_mode": "polling",
      "supports_discovery": false,
      "supports_actions": false,
      "supports_cards": false,
      "entity_types": ["demo.entity"]
    }
  }
}
```

## What to verify first

- whether the host can discover the plugin
- whether the plugin appears in the plugin state page
- whether configuration can be saved
- whether the execution entry really runs
- whether disable state blocks it consistently

## Bad first-plugin choices

- high-risk action plugins
- channels that require complex auth and callback flows
- plugins that need broad host-context write access

Your first plugin should teach you structure, not show off complexity.
