# 11 Plugin Configuration Integration

Plugin configuration must go through:

- `manifest.config_specs`

Supported scopes:

- `plugin`
- `integration_instance`
- `device`
- `channel_account`

Secret field rules:

- never echo plaintext
- omitted means keep old value
- explicit clearing uses `clear_secret_fields`

Scope split matters:

- put shared provider defaults and shared secrets in `plugin`
- put per-instance bindings in `integration_instance`

Example:

- weather provider selection and API keys belong to `plugin`
- whether one weather instance binds to the household coordinate or a specific region node belongs to `integration_instance`
