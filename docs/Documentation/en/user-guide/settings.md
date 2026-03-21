---
title: Settings
docId: en-3.5
version: v0.1
status: draft
order: 350
outline: deep
---

# Settings

## Page status

- **Status**: The H5 settings page is available. The entry is `/pages/settings/index`, protected by login and family context.
- **Structure**: top navigation plus multiple section cards. Some settings lead to subpages such as AI Settings.

![fc-doc-20260320T000409.webp](../../使用指南/assets/fc-doc-20260320T000409.webp)

## Main sections already implemented

- **Appearance and themes**: choose built-in themes or plugin-provided themes. If a theme is unavailable, the page shows a disabled warning. When you switch themes, the new theme takes effect and is saved immediately.
- **Language and time zone**: choose the default family language and time zone. This affects time display and translation resources, and the page may need a refresh afterward.
- **Devices and integrations**: create instances for connected plugins. The instance-name field now stays empty by default, and each plugin can declare its own suggested placeholder. The system only renders that suggestion instead of silently saving the plugin name as your final instance name.
- **Notifications and accessibility**: this area is still mostly placeholder content in the current version.
- **AI Settings shortcut**: a direct entry into the AI configuration subpage.

## AI Settings subpage (`/pages/settings/ai/index`)

- **AI assistants**: create or edit the family butler and other assistant roles. Model provider configuration must be completed first.
- **Provider Profiles**: plugin-driven provider forms with fields such as `base_url`, `secret_ref`, and `model_name`, plus enable and disable support.
- **Routes**: choose primary and fallback models for abilities such as `text` and `qa_generation`, then configure timeout and retry behavior.
- **Initialization progress hints**: if setup is incomplete, the page shows which steps are still missing.

### Local model providers

The current built-in local provider plugins include:

- `Ollama`
- `LM Studio`
- `LocalAI`

There are also many mainstream public cloud AI providers, with support for multiple provider coding plans.

The easiest order is:

1. choose the provider plugin first
2. fill in the local service address
3. if your local service uses an API key, fill in that key as well
4. let the page refresh the model list automatically
5. choose a model from the list, or type a custom model name manually if needed

Those local providers are handled as local-only by default and are not automatically treated as remote-provider privacy levels.

![fc-doc-20260320T000538.webp](../../使用指南/assets/fc-doc-20260320T000538.webp)

## Family context

- The top of the page shows the current family. After switching families, language, theme, and time zone settings change with that family context.
- If the family is not initialized or is disabled, the settings page shows a warning and guides you back to the setup flow.

## Common issues

- **Theme is missing or invalid**: the related theme plugin may be disabled or uninstalled. Switch to another available theme.
- **Language or time zone did not take effect**: refresh the page or log in again, then confirm that the current family context is the one you intended to change.
- **Why is the instance-name field empty when I create an integration?**: this is now the default behavior. The placeholder suggestion comes from the plugin when available; otherwise the page falls back to a generic hint. The final name still must be confirmed and entered by the user.
- **Cannot save AI provider configuration**: check the required fields and secret values, or confirm the related plugin is enabled.

## Completion standard

- A user can switch theme, language, and time zone, then enter AI Settings to finish model and route configuration.
- When a theme is unavailable or a family is not initialized, the user can follow the page warning and take the right next step.
