---
title: Plugin Development
docId: en-4.3
version: v0.1
status: active
order: 430
outline: deep
---

# Plugin Development

Plugin development is not "adding a patch point into the host." It is the current extension model in FamilyClaw.

If you do not remember the full rule set yet, remember these four lines first:

1. The host only keeps platform rules and unified standards.
2. Third-party integration, field mapping, and provider-specific behavior should go into plugins first.
3. Plugin output must already be standardized. The host should not need patch-style repair logic afterward.
4. Whether a plugin can execute is determined only by the unified enabled/disabled state, not by page-specific guesses.

## Read these pages first

Recommended order:

1. Read [Plugin Specification](./plugin-specification.md) first so you understand the host-plugin boundary.
2. Then read [Field Specification](./plugin-fields.md) so you write `manifest.json` and config schemas correctly.
3. Then read [Integration Flow](./plugin-integration.md) so you understand execution flow and integration endpoints.
4. Then read [Example Plugin](./plugin-example.md) and compare against real built-in plugins.
5. Finally, read [Plugin Submission](./plugin-submission.md) and use it as your delivery checklist.

These pages together form the current plugin development handbook inside the official docs site. You do not need to leave `docs/Documentation` to piece the rules together.

## Current supported plugin types

Based on `apps/api-server/app/modules/plugin/schemas.py`, the current supported types are:

- `integration`
- `action`
- `agent-skill`
- `channel`
- `locale-pack`
- `region-provider`
- `theme-pack`
- `ai-provider`

Exclusive slots:

- `memory_engine`
- `memory_provider`
- `context_engine`

## What should become a plugin

### Good plugin candidates

- third-party API integrations
- third-party device protocol adapters
- model provider integrations
- communication platform channels
- theme resources and locale resources
- region catalogs and region parsing

### What should not become a plugin

- host-owned data such as families, members, rooms, and permissions
- host-wide audit
- host-wide scheduling
- host-wide standard entity, card, and action semantics

## What already exists in the repository

Built-in plugins live under:

- `apps/api-server/app/plugins/builtin/`

Current examples include:

- AI providers such as `ai_provider_chatgpt`, `ai_provider_claude`, and `ai_provider_qwen`
- channels such as `channel_feishu`, `channel_discord`, and `channel_telegram`
- the `health_basic` integration
- theme packs such as `theme_chun_he_jing_ming_pack`
- locale packs such as `locale_zh_tw_pack`

These are not conceptual examples. They already exist in the repository now.

## Minimal development flow

### 1. Decide the type before you write code

Decide whether it is:

- `integration`
- `action`
- `channel`
- `ai-provider`
- or another supported type

If the type is wrong, the manifest, execution path, and config scope all go wrong with it.

### 2. Write `manifest.json` first

The host reads the manifest first and decides how your plugin is loaded.

At minimum, write:

- `id`
- `name`
- `version`
- `api_version`
- `types`
- `permissions`
- `risk_level`
- `entrypoints`
- `capabilities`

### 3. Then implement the entry code

Examples:

- an `integration` entry
- a `channel` entry
- an `ai_provider` entry

The code path must match the `manifest.json` declaration exactly.

Also keep one distinction clear:

- `apps/api-server/plugins-dev/<plugin>/` is the in-repo development location rule
- an external plugin repository may still use the `official_weather` style layout, where repository-level files stay at the root and the actual plugin package lives in a subdirectory

Do not force those two standards into one fake universal template.

### 4. Then connect configuration

If the plugin needs user-provided values, add:

- `config_specs`

Do not hide the config contract in code and expect the frontend to guess your fields.

If the setup flow itself needs real side effects, such as:

- logging in to a third-party account
- loading live device candidates
- surfacing a secondary verification URL

add one more hook:

- declare `entrypoints.config_preview`
- implement a preview function in the plugin
- let the UI call it explicitly from a button such as "Log in and load devices"
- return temporary setup state through `view.runtime_state`
- return renderable preview output through `view.preview_artifacts`

This is for runtime setup actions. It is not a replacement for persisted config fields, and it is not something you should hide inside `config/resolve`.

### Generic staged setup with `ui_schema.actions + runtime_sections`

For flows such as "log in and load devices", do not patch the host page. The plugin should declare the whole staged flow itself:

- declare a preview action in `ui_schema.actions`
- bind that action to one section through `section_id`
- expose post-action runtime output through `ui_schema.runtime_sections`
- use `candidate_select` when the user needs to choose one item and persist the result into a real config field such as `device_selector`
- keep all plugin-specific `label / description / help_text / placeholder / runtime` copy in the plugin's own `manifest + locales`; the host only performs generic rendering

That keeps the host generic. The host renders buttons, calls `config_preview`, shows runtime output, and writes selected values back into the config draft. It does not know what "Xiaomi login", "secondary verification", or "device binding" means.

### What `config_preview` should return now

The host now formally recognizes these preview fields:

- `field_errors`
- `runtime_state`
- `preview_artifacts`

For multi-step auth flows, there is now one more host-managed runtime contract inside `runtime_state`:

- `runtime_state.auth_session`

The host creates this session only for explicit preview actions, exposes a callback URL to the plugin, records callback payloads at a host-owned endpoint, and lets the frontend poll unified session status. The plugin should use it like this:

- on the first preview action, generate the provider verification URL from `auth_session.callback_url`
- store only the provider-specific resume payload in `auth_session.payload`
- after the host callback is received, consume `auth_session.callback_payload` and continue the login flow
- when the flow finishes, return an `auth_session` mutation with `completed`, `failed`, `expired`, or another terminal state

Do not make users manually paste a callback URL back into the form as the primary flow. That can exist only as a temporary debug fallback.

`preview_artifacts` is the host-rendered list for temporary setup output. The current kinds are:

- `image_url`: render an image such as a login QR code; this can be a remote URL or a directly renderable `data:image/...` URL
- `external_url`: render an external link
- `text`: render a temporary block of text

Minimal example:

```json
{
  "runtime_state": {
    "status": "waiting_scan",
    "message": "The QR code is ready. Please scan it."
  },
  "preview_artifacts": [
    {
      "key": "login-qr",
      "kind": "image_url",
      "label": "Login QR code",
      "url": "https://example.com/login-qr.png"
    },
    {
      "key": "login-tip",
      "kind": "text",
      "label": "Current status",
      "text": "The QR code is ready. Please scan it."
    }
  ]
}
```

Keep the boundary clean:

- `preview_artifacts` is for host rendering, not for pushing vendor protocol details back into the host
- `image_url` must point to an actual image resource; if an upstream service only gives you a landing page or H5 URL, the plugin must turn it into a real image before handing it to the host
- do not send platform-private fields such as `qr_code_url` or `weixin_login_status` to host pages
- persisted config still belongs to the normal save flow; preview artifacts are temporary only

### Read-only display widgets

If a field is only there to show text or a read-only summary, stop pretending it is an editable input.

You can now declare:

```json
{
  "widgets": {
    "login_hint": {
      "widget": "display"
    }
  }
}
```

`display` means:

- the host renders the field as a read-only block
- the UI does not show an input control for it
- it is suitable for static instructions or read-only values already present in the field/default

Do not abuse it:

- QR codes, temporary links, and transient text belong in `preview_artifacts`
- `display` is for field-level read-only content, not a replacement for `config_preview`

### 5. Validate it inside the host

At minimum, confirm:

- the plugin can be discovered
- the plugin state is visible
- configuration can be saved
- the execution entry really runs
- disable state blocks execution consistently

## What the host currently owns

- plugin registration and mounting
- enable/disable governance
- config value storage
- permissions, audit, and scheduling
- standard entity, card, and action semantics
- plugin marketplace and version governance

## What the plugin currently owns

- third-party platform integration
- mapping third-party fields into host-standard data
- plugin-local cache, deduplication, rate limiting, and vendor-specific logic
- producing final standardized DTOs

## Common mistakes during development

### 1. Putting host-owned data into a plugin

That is not faster implementation. That is a broken boundary.

### 2. Making the host patch plugin output at read time

If the host still needs `if plugin_type == ...` just to understand the result, your plugin output was never standardized.

### 3. Inventing your own scheduler

Scheduled tasks, background jobs, and retry policy belong to the host.

Plugins should declare capability, not register their own private cron layer.

### 4. Ignoring disable semantics

After a plugin is disabled:

- it cannot be newly used
- it cannot continue executing
- but it can still be viewed and configured

That rule must match the whole system.

## Generic `channel.send` delivery payload

The host no longer treats outbound channel delivery as `text + metadata` only.

The current unified payload now includes:

- `delivery.text`
- `delivery.attachments`
- `delivery.metadata`

`attachments` is a platform-neutral list. Each item should describe at least:

- `kind`: `image` / `video` / `audio` / `file`
- `file_name`
- `content_type`
- `source_path` or `source_url`
- `size_bytes`
- `metadata`

Keep the boundary clear:

- The host only forwards normalized attachment info. It does not understand vendor upload protocols.
- A plugin may support only the attachment kinds it declares. If a kind is unsupported, return a clear error instead of silently dropping it.
- Older text-only plugins can keep reading `delivery.text`. The extra `attachments` field is additive, not a host-side special case.

## Generic inbound media references

If a `channel` plugin downloads inbound media into its own private runtime directory, it should return host-consumable references instead of leaking vendor protocol fields.

Current practice is:

- Keep the downloaded file under the plugin `working_dir/media/` tree.
- Expose a normalized attachment list through `normalized_payload.attachments`.
- Mirror the same list under `normalized_payload.metadata.attachments` for consumers that only read metadata today.
- Put partial download failures under `normalized_payload.metadata.media_download_errors`.

Each inbound attachment should stay platform-neutral and follow the same shape as outbound attachments as much as possible:

- `kind`
- `file_name`
- `content_type`
- `source_path`
- `size_bytes`
- `metadata`

Boundary reminder:

- The host still does not understand vendor CDN tokens, decrypt parameters, or upload/download protocols.
- If media download fails, return a clear normalized error summary. Do not dump vendor-specific protocol blobs into host models.

## How the channel access page discovers third-party `channel` plugins

The settings page for communication platforms must now render from the registered plugin snapshot instead of a hardcoded Telegram/Discord list.
If the page still relies on a static platform array, third-party `channel` plugins will never show up. That is not a missing feature. That is the host breaking the plugin boundary.

The common rule is:

- Build the platform picker from `listRegisteredPlugins()`
- Show only enabled plugins whose `types` include `channel` and whose manifest declares `capabilities.channel.platform_code`
- Submit the real `plugin_id` when creating an account; never synthesize `channel-${platformCode}` in the UI
- Reuse host branding and logos for known platforms; for unknown platforms, fall back to `plugin.name` plus a generic icon instead of pretending everything is Telegram

This is host-wide behavior, not a Weixin special case. Today it is Weixin claw. Tomorrow it may be another third-party channel. The entry should keep working without more host patches.

## How a `channel` plugin declares account actions and status summaries

If a `channel` plugin needs account-level actions such as "start login", "refresh status", or "clear local state", do not make the frontend guess the buttons and do not hardcode action names in the host.

Declare them in the manifest through:

- `capabilities.channel.ui.account_actions`
- `capabilities.channel.ui.status_action_key`

Minimal example:

```json
{
  "types": ["channel", "action"],
  "entrypoints": {
    "channel": "plugin.channel.handle",
    "action": "plugin.action.execute"
  },
  "capabilities": {
    "channel": {
      "platform_code": "weixin-claw",
      "inbound_modes": ["polling"],
      "delivery_modes": ["reply"],
      "ui": {
        "status_action_key": "refresh-login-status",
        "account_actions": [
          {
            "key": "start-login",
            "action_name": "start_login",
            "label": "Start login",
            "variant": "primary"
          },
          {
            "key": "refresh-login-status",
            "action_name": "get_login_status",
            "label": "Refresh login status"
          }
        ]
      }
    }
  }
}
```

Keep the boundary strict:

- If a plugin declares `account_actions`, it must also declare the `action` type and `entrypoints.action`
- The host only understands action keys, action names, button labels, danger level, and confirmation text. It does not understand QR code semantics or platform login stages
- The account detail page should primarily read plugin state from `status_summary` in the action result
- If an action returns displayable artifacts such as a QR image or an external link, expose them through `artifacts` instead of leaking platform-specific fields into the host

Recommended action result fields are:

- `message`
- `status_summary`
- `artifacts`

`status_summary` is the platform-neutral summary object. `artifacts` is the platform-neutral display artifact list. The host only renders them.

## Keep setup forms friendly

If your plugin exposes many fields, do not dump everything into one long setup form.

The integrations modal now treats `ui_schema.sections` as a staged wizard, and you can mark a section as an optional advanced step:

```json
{
  "id": "advanced",
  "title": "Advanced troubleshooting",
  "mode": "advanced",
  "fields": ["request_timeout_ms", "enable_trace"]
}
```

Practical rules:

- omit `mode` for normal steps
- use `mode = "advanced"` for troubleshooting, overrides, selectors, and other non-essential inputs
- regular users can save after the basic steps, and only expand advanced sections when needed
- keep account/login and core behavior settings in the earlier sections

## Built-in plugins worth studying

- `apps/api-server/app/plugins/builtin/health_basic/manifest.json`
  Good for the smallest `integration` example and dashboard card declaration.
- `apps/api-server/app/plugins/builtin/ai_provider_chatgpt/manifest.json`
  Good for `ai-provider` schema and compatibility fields.
- `apps/api-server/app/plugins/builtin/channel_feishu/manifest.json`
  Good for channel config, UI schema, and binding capability.
- `apps/api-server/app/plugins/builtin/theme_chun_he_jing_ming_pack/manifest.json`
  Good for `theme-pack` resource declaration.

## When you should stop and rethink

If you notice yourself preparing to:

- add another domain-specific host service
- add another set of exceptions for one plugin type
- make the frontend or backend each add their own compatibility patch

stop first. The problem is probably not missing logic. The problem is that the boundary is already starting to rot.
