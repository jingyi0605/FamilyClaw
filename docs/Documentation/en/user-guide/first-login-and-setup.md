---
title: First Login and Initialization
docId: en-3.0
version: v0.1
status: draft
order: 300
outline: deep
---

# First Login and Initialization

## When to use this page

- You are entering the system for the first time after a new deployment.
- You need to run the initialization wizard for a new family.

## Login entry

1. Open the deployed address in your browser. The default address is `http://<host>:8080`.
2. If you are not logged in, Guard redirects you to the login page.
3. For the very first login, the default account is `user` and the password is `user`. After initialization finishes, the system creates a new account and password for you, and the original `user` account is disabled.

![fc-doc-20260319T231835.webp](../../使用指南/assets/fc-doc-20260319T231835.webp)

## Initialization wizard flow

The wizard entry is `/pages/setup/index`. Guard redirects here automatically when the current family has not finished initialization.

![fc-doc-20260319T234131.webp](../../使用指南/assets/fc-doc-20260319T234131.webp)

1. **Family profile (`family_profile`)**
   - Fill in the family name, time zone, language, and region details such as country, province, city, and district.

![fc-doc-20260319T234213.webp](../../使用指南/assets/fc-doc-20260319T234213.webp)

2. **First member (`first_member`)**
   - Enter the member name or nickname and choose the role, which defaults to administrator.
   - The page can generate a username automatically.
   - You also need to set a password.

![fc-doc-20260319T234248.webp](../../使用指南/assets/fc-doc-20260319T234248.webp)

3. **Provider setup (`provider_setup`)**
   - Select an installed AI provider adapter such as ChatGPT or another OpenAI-compatible gateway.
   - Fill in fields such as `base_url`, `secret_ref`, `model_name`, privacy level, and timeout.
   - The ChatGPT provider now supports both `Responses` and `Chat Completions`. In `Auto` mode it tries `Responses` first and falls back to the legacy compatibility route when needed.
   - If you only enter a site root such as `https://example.com`, the driver automatically expands it to `https://example.com/v1` before making API calls.
   - If you move on and later realize you picked the wrong platform, go back to this step and reopen the provider selector card. Saving again replaces the current default AI service for the household.

![fc-doc-20260319T234425.webp](../../使用指南/assets/fc-doc-20260319T234425.webp)

Many AI providers are supported, including local options such as Ollama, LM Studio, and LocalAI.

![fc-doc-20260319T234413.webp](../../使用指南/assets/fc-doc-20260319T234413.webp)

4. **First butler agent (`first_butler_agent`)**
   - Through an LLM-guided conversation, you define the identity, personality, and service focus of the family butler.
   - You can adjust it later in Settings.

![fc-doc-20260319T234556.webp](../../使用指南/assets/fc-doc-20260319T234556.webp)

5. **Finish (`finish`)**
   - After all steps are completed, the system redirects you to the dashboard automatically.

![fc-doc-20260319T234658.webp](../../使用指南/assets/fc-doc-20260319T234658.webp)

## Re-entering the wizard

- If you leave halfway through, logging in again continues the wizard from the current progress.
- If FamilyClaw determines that initialization is already complete, it redirects you back to the dashboard automatically.
- Even after AI setup is done, returning to the provider step still lets you edit the current values or choose another platform. You do not need to delete the family and start over.

## Common issues

- **Cannot enter the wizard or get stuck in a redirect loop**: clear the browser cache and try again, then confirm the backend health endpoint `/api/v1/healthz` is normal.
- **Provider form is missing fields**: make sure your `base_url` and API key are correct. If you use the ChatGPT provider, also verify that the protocol mode matches your gateway. If a provider still looks unusable, report it through GitHub issues.
- **Still shown as uninitialized after finishing**: check whether the current family context switched successfully. If needed, log in again.

## Completion standard

- You finish family profile, first member, model provider, and first butler creation.
- After logging in, you can enter the dashboard without being redirected back to the wizard.
