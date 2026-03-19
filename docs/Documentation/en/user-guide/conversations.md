---
title: Conversations
docId: en-3.3
version: v0.1
status: active
order: 330
outline: deep
---

# Conversations / Assistant

## Page status

- **Status**: The H5 conversation page is already available. It is not a placeholder page.
- **Entry**: `/pages/assistant/index`
- **Access conditions**:
  - you must be logged in
  - you must already be inside a family
  - the current family must have at least one enabled AI assistant that supports conversations
- **Current main workspace**: the `Personal` tab is available now, while `Public` and `Moments` are still marked as coming soon.

This page already supports the main conversation flow, including:

- session list
- creating a new session
- switching AI assistants
- real-time message sending and receiving
- suggested questions
- proposal confirmation inside the conversation
- action confirmation and undo inside the conversation
- the context side panel

So this is not a future placeholder. It is already a usable primary page, even though a few extended tabs and details are still unfinished.

![fc-doc-20260320T000734.webp](../../使用指南/assets/fc-doc-20260320T000734.webp)

## What you can do here

### 1. Create a new session and manage history

After entering the page, you can start a new conversation immediately or switch back to an earlier session and continue.

Current support includes:

- clicking the `New Chat` button in the top-right corner to create a new session
- expanding the session list from the session title area
- reviewing the title, latest message preview, and recent activity time for each session
- opening an earlier session and continuing from that context

If this is your first time here and you do not have any sessions yet, the page gives you a direct entry to create one. You do not need extra setup first.

![fc-doc-20260320T000759.webp](../../使用指南/assets/fc-doc-20260320T000759.webp)

### 2. Switch between different AI assistants

If your family has multiple assistants that support conversation, this page lets you switch the current assistant.

The top area shows assistant information such as:

- assistant name
- assistant type
- current availability

When multiple assistants are available, you can click the avatar area to switch. After switching, the page starts a new session for the new assistant so different assistant contexts do not get mixed together.

One detail matters here: not every configured assistant appears in the switch list. Only assistants that are currently enabled and support conversation are shown as options.

This is important because **the conversation is bound to the currently selected assistant**. If you switch assistants and expect the page to keep using the exact context of the previous assistant, that is not how the current page works.

### 3. Send messages and receive real-time replies

This is the core ability of the page.

You can:

- type a question in the input box
- press `Enter` to send directly
- press `Shift + Enter` for a new line
- wait for the assistant to return the reply in real time

The page uses a real-time connection for replies, so the usual behavior is:

- your own message appears in the session first
- the assistant message enters a generating state
- content streams in and then finishes

### 4. Use suggested questions to move faster

The page automatically fetches a group of suggested questions that fit the current family and the current assistant.

Those suggestions appear in two places:

- the quick question area inside the context panel
- follow-up suggestion buttons under some assistant replies

You can click them directly when:

- you do not know how to start
- you want to test the assistant quickly
- you want to continue around the current topic

That helps new users a lot because you do not need to learn any special prompt format first.

![fc-doc-20260320T000904.webp](../../使用指南/assets/fc-doc-20260320T000904.webp)

### 5. Open the current conversation context

The page has a `Details` entry in the upper-right corner. Opening it shows the context panel on the right.

The panel currently shows:

- current family
- current assistant
- number of pending actions
- recent memories
- recent action records
- quick question buttons

If recent facts were extracted from the conversation, the memory area prefers showing those facts first. If not, the page falls back to suggested questions.

This panel is not for manual system configuration. It is there to help you quickly understand:

- which family the assistant is serving right now
- which recent context the assistant is using
- whether there are pending actions or proposals waiting for you

![fc-doc-20260320T000844.webp](../../使用指南/assets/fc-doc-20260320T000844.webp)

### 6. Confirm or dismiss proposals inside the conversation

The conversation page already supports proposal-style interaction.

When the assistant decides something should not be executed automatically and needs your confirmation first, it shows a proposal card under the message. You can handle it directly inside the conversation instead of leaving the page.

The currently supported proposal types include, but are not limited to:

- scheduled task creation
- scheduled task update
- scheduled task pause
- scheduled task resume
- scheduled task deletion
- reminder creation
- configuration apply
- memory write suggestions

Typical actions are:

- click the primary button to confirm
- click the secondary button to ignore it for now

If a scheduled-task proposal is still missing key information, the confirm button stays restricted instead of pretending the action is ready.

![fc-doc-20260320T001006.webp](../../使用指南/assets/fc-doc-20260320T001006.webp)

### 7. Confirm actions, review results, and undo when needed

Besides proposals, the page also supports action records.

In simple terms:

- **Proposal**: the system asks first whether you want to do it
- **Action**: the system is ready to execute it, or it already executed it, and now needs confirmation, result review, or undo

Actions may appear under different policies:

- confirm before execution
- notify only without blocking the main flow
- execute automatically but keep result and undo entry

What you can actually do on the page includes:

- confirm an action
- dismiss an action
- undo a completed action, but only when that action actually supports undo

That means the conversation page is no longer just a chat box. It already handles part of the approval and rollback flow inside the conversation itself.

![fc-doc-20260320T001108.webp](../../使用指南/assets/fc-doc-20260320T001108.webp)

### 8. Jump from a reply to related pages

After an assistant reply is completed, the page may show shortcut buttons under the message so you can continue with related work immediately.

Current jump targets include:

- the Family page
- the AI Settings page
- the Memory page

This is useful for cases such as:

- the assistant tells you to complete missing family data first
- the assistant says there is no available AI assistant and you need to open Settings
- the assistant mentions a memory item and you want to inspect it in the Memory page

> Screenshot placeholder: shortcut buttons under an assistant message

## Recommended order

If this is your first time using the page, the most stable order is:

1. Confirm that you selected the correct family and that the family already has at least one AI assistant configured.
2. Enter the `Personal` tab and click `New Chat`.
3. Click one suggested question first and confirm the assistant can reply normally.
4. Then type a real question yourself and see whether any proposal cards or action cards appear.
5. If needed, open the details panel and confirm the current context, recent memories, and recent actions.
6. If the assistant tells you to complete some configuration elsewhere, follow the shortcut buttons under the reply to the target page.

## Common issues

### Why do I see "no available assistant"?

That usually does not mean the conversation page is missing. It usually means the current family does not have any enabled assistant that supports conversations. Open the AI Settings page and confirm the assistant configuration.

### Why is the send button sometimes disabled?

The page depends on a real-time connection for sending and receiving. If the connection is not ready yet, if you just switched sessions, or if the network is unstable, the send button may stay disabled for a while.

### Why does switching assistants feel like starting over?

That is the real current design. After switching assistants, the page starts a new session for the new assistant so contexts do not get mixed.

### Why do some replies have no confirm or dismiss buttons?

Because proposals and actions only appear when the current reply actually generated them. The page does not show approval cards for every reply by default.

### Why can I open `Public` or `Moments` but not chat there?

Because those two tabs are still in the coming-soon state. The truly available workspace right now is `Personal`.

## Completion standard

- You understand that the conversation page is already a working page, not a migration placeholder.
- You know it can already handle session creation, session switching, real-time chat, suggestions, proposal confirmation, action undo, and context inspection.
- You also know the real unfinished parts are extended tabs such as `Public` and `Moments`, not the whole page.
