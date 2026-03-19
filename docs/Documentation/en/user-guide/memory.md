---
title: Memory
docId: en-3.4
version: v0.1
status: draft
order: 340
outline: deep
---

# Memory

## Page status

- **Status**: The H5 memory page is available. The entry is `/pages/memories/index`, and it is protected by login and family context.
- **Data source**: the backend `/api/v1/memories` related APIs. Memory items include revision history, visibility, and status.

## What you can do

- Filter by type: all, fact, event, preference, or relationship.
- Search: keyword search works on titles and content.
- View details: click an item in the left list to open the detail panel on the right, including all revisions.
- Review state and visibility:
  - visibility: public, family, private, or sensitive
  - status: active, pending confirmation, invalid, or deleted
- Revise and operate on memory:
  - Correct: submit a revision and create a new version.
  - Invalidate: keep the history but mark the current version invalid.
  - Delete: logical delete only, while history remains.

![fc-doc-20260320T000342.webp](../../使用指南/assets/fc-doc-20260320T000342.webp)

## How to use it

1. Open the memory page and wait for the list to finish loading. Confirm the family context in the upper-right corner is correct.
2. Use the top filters to switch memory type, or search by keyword.
3. Click a memory item in the left list. The right side shows details and revision history:
   - **Current version** shows title, summary, visibility, and status.
   - **Revision history** is shown in reverse time order, with changed fields and reasons.
4. If you need to revise something:
   - Choose **Correct** and submit the new title, content, or visibility.
   - Choose **Invalidate** or **Delete** and provide a reason before submitting.
5. After submission, the list refreshes. If the action fails, check the warning for permission or network problems.

## Permissions and notes

- The current member must have the right permission to revise or delete memory. If not, the page returns an error.
- Memory items with `sensitive` or `private` visibility are not visible or editable for non-authorized members.
- Delete is a logical delete. Historical versions remain available for audit.

## Common issues

- **The list is empty**: on a fresh environment, there may simply be no memory yet. Normal conversations and events generate memory over time.
- **Revision failed or permission denied**: confirm the current member role and family context. If needed, ask an administrator.
- **Time looks wrong**: if the browser time zone and the family time zone do not match, displayed times may look offset. Adjust the time zone in Settings first.

## Completion standard

- A user can filter, search, inspect, revise, and delete memory.
- The user understands the meaning of visibility and status and knows what to check when permissions are insufficient.
