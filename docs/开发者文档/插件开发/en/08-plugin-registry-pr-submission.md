# 08 Plugin Registry PR Submission Guide

## Document Metadata

- Purpose: tell third-party developers how to submit a plugin registration PR without guessing what to prepare, how to submit it, or what reviewers will check.
- Current version: v1.0
- Related documents: `docs/开发者文档/插件开发/en/01-plugin-development-overview.md`, `docs/开发者文档/插件开发/en/06-build-a-runnable-plugin-walkthrough.md`, `docs/开发者文档/插件开发/en/07-plugin-testing-and-in-project-validation.md`, `specs/004.3-插件开发规范与注册表/design.md`
- Change log:
  - `2026-03-13`: created the first plugin registration PR submission guide.

This document answers one question only:

- your plugin is already built according to the rules, so how do you submit the registration PR

You do not need to understand how the backend parses the registry, and you do not need to design the registry format yourself.

Your job is simple: prepare the required material using the project template, then submit the PR.

## 1. Confirm You Are Actually Ready To Submit

Do not rush into registration before the plugin is really ready.

Before submitting a PR, at least pass these checks:

1. The plugin directory and `manifest.json` are already aligned with the spec.
2. The entrypoint paths in `manifest.json` resolve to real code.
3. The declared plugin types, permissions, and risk level are clearly written.
4. You have a readable plugin document that explains what the plugin does and how to verify it.
5. You already provide a plugin-owned dependency list such as `requirements.txt`.
6. The plugin does not depend on explicitly unsupported features such as auto-install or sandbox execution.

If these fail, do not submit a PR yet.

## 2. What You Need To Submit

Your registration PR should include at least 4 groups of material:

### 2.1 Plugin Source Repository URL

- it must be publicly reachable, or at least reachable by reviewers
- the repository must contain the real plugin code
- the repository must include `manifest.json`

### 2.2 Plugin Documentation URL

Using the repository `README.md` is usually the simplest option.

It should at least explain:

1. what the plugin does
2. which plugin capability types it supports
3. which permissions it requests
4. what its risk level is
5. how to run minimum verification
6. which Python dependencies it requires
7. what it explicitly does not do

### 2.3 Registry Entry File

The project will provide the registry directory and entry template.

Your job is to:

- add one plugin entry file based on the template
- keep the file name usually aligned with `plugin_id`
- make sure `plugin_id`, permissions, risk level, and plugin types match the plugin `manifest.json`

In plain words: do not invent your own format. Fill the provided template.

### 2.4 PR Description

The PR body should at least explain:

1. what problem the plugin solves
2. the plugin repository URL
3. the documentation URL
4. the risk level and why it matches
5. how you verified the plugin yourself

## 3. Recommended Submission Flow

Use this order. It causes the least pain:

1. clean up the plugin source repository first
2. verify that `manifest.json`, README, and minimum test notes are complete
3. verify that `requirements.txt` and minimum runner self-check notes are complete
4. fork the official registry repository, or modify the project branch specified by maintainers
5. add the registry entry file using the provided template
6. open the PR and clearly write the repository URL, docs URL, and risk notes
7. wait for review; if maintainers ask for missing material, add it directly instead of arguing vaguely in comments

## 4. Recommended PR Body Template

Your PR body should look at least like this:

```md
## Plugin Information

- plugin_id: `your-plugin-id`
- plugin name: `Your Plugin Name`
- plugin repository: `https://github.com/your-org/your-plugin-repo`
- plugin docs: `https://github.com/your-org/your-plugin-repo/blob/main/README.md`

## Capability Summary

- plugin types: `connector` / `memory-ingestor` / `action` / `agent-skill`
- declared permissions: `...`
- risk level: `low` / `medium` / `high`

## Self-Check Result

- [ ] `manifest.json` reviewed
- [ ] entrypoints are importable
- [ ] README is complete
- [ ] minimum verification steps are documented

## Extra Notes

- what this plugin explicitly does not do: `...`
- what reviewers should pay extra attention to: `...`
```

## 5. What Reviewers Will Focus On

You do not need to make the final decision, but you should know what reviewers will stop on.

The minimum review checklist for version one focuses on these points:

1. whether the registry entry matches `manifest.json`
2. whether the plugin repository is reachable and contains real code
3. whether the README clearly explains plugin purpose, permissions, and verification
4. whether the declared risk level matches the real plugin capability
5. if this is an action plugin, whether the risk and permission boundary is clearly written
6. whether the plugin secretly depends on remote install, remote execution, sandboxing, or signing systems that do not exist yet

## 6. What Will Be Rejected Directly

Do not expect a “merge first, fix later” pass for these cases:

- `plugin_id` does not match `manifest.json`
- the repository cannot be accessed, or it only contains empty description text with no real plugin code
- the README says almost nothing useful
- the declared risk level is obviously too low
- an action plugin does not clearly declare permission needs
- the registry entry does not follow the provided template
- the plugin clearly tries to cross the current boundary, such as requiring auto-install or remote execution

## 7. What You Actually Need To Remember

As a third-party developer, this step is really just two things:

1. build the plugin properly
2. submit complete registration material using the project template

How the registry is parsed internally and how the backend reads it later are maintainer concerns, not something you need to guess right now.
