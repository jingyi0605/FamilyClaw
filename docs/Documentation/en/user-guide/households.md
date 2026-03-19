---
title: Family
docId: en-3.2
version: v0.1
status: active
order: 320
outline: deep
---

# Family

## Page status

- **Status**: The H5 family page is available and already quite complete.
- **Entry**: `/pages/family`
- **Access conditions**: you must be logged in and have a current family selected.
- **Page structure**: there are five main tabs at the top:
  - `Overview`
  - `Rooms`
  - `Devices`
  - `Members`
  - `Relationships`

This is not just a display page. It reads family profile data, context summary, rooms, devices, members, member preferences, and member relationships, and it already lets you edit part of that data directly.

![fc-doc-20260319T234932.webp](../../使用指南/assets/fc-doc-20260319T234932.webp)

## What you can do here

### 1. Manage core family profile data

In the **Overview** tab, you can review and edit:

- family name
- time zone
- default language
- region information such as country, province, city, and district

You can also see the current family context summary, including:

- current family mode
- privacy mode
- whether guest mode, child protection, elder care, or fast voice access is enabled

If you just finished initialization, this is the main page for filling in missing profile details and correcting existing ones.

![fc-doc-20260319T235024.webp](../../使用指南/assets/fc-doc-20260319T235024.webp)

### 2. Add rooms and review room layout

In the **Rooms** tab, you can:

- review the current room list
- create a new room
- choose a room type
- set the room privacy level

When you create a room, the current form asks for:

- room name
- room type
- privacy level

The page also shows the device count and activity summary for each room so you can quickly judge whether the family structure is already captured properly.

At the moment, the **Edit room** button is still not fully open for editing, but room creation and room listing are already usable.

> Screenshot placeholder: room list and new room dialog

### 3. View and filter devices

In the **Devices** tab, you can:

- review the devices in the current family
- filter by room
- filter by device type
- filter by device state
- open the device detail dialog

The device page shows:

- device name
- assigned room
- device type
- current runtime state
- whether it is controllable
- whether it is enabled

If a device comes from an integration plugin, this page is often the fastest place to confirm:

- whether the device was synchronized at all
- whether it synced but has an abnormal state
- whether the room binding looks correct

![fc-doc-20260319T235653.webp](../../使用指南/assets/fc-doc-20260319T235653.webp)

### 4. Add, edit, and disable members

In the **Members** tab, you can manage members directly. This is already one of the most complete parts of the family page.

Supported actions include:

- adding a member
- editing member profile data
- setting nickname, gender, role, age group, birthday, and phone number
- assigning a guardian for a child
- enabling or disabling a member
- editing member preferences

Current member roles include:

- administrator
- adult
- child
- elder
- guest

The page also combines birthday, lunar birthday marker, guardian information, and member preferences so the member cards contain more complete context.

If you need to maintain family member data, this page is basically the main workbench.

![fc-doc-20260319T235413.webp](../../使用指南/assets/fc-doc-20260319T235413.webp)

### 5. Maintain relationships

In the **Relationships** tab, you can:

- review existing relationships
- view the relationship network visually
- add a relationship
- delete a relationship

The current model creates relationships as `source member -> relationship type -> target member`.

That matters for later features such as how the system understands kinship terms, care relationships, and family collaboration.

If your family includes children, elders, or any explicit guardian or care relationship, this tab is worth completing carefully.

![fc-doc-20260319T235316.webp](../../使用指南/assets/fc-doc-20260319T235316.webp)

## Recommended order

If this is your first time entering the family page, the recommended order is:

1. Start with **Overview** and confirm the family name, time zone, language, and region are correct.
2. Go to **Rooms** and add the main spaces in the family.
3. Move to **Members** and complete the family member profiles.
4. Then open **Relationships** and define guardian, parent, spouse, child, and similar relationships.
5. Finally, review **Devices** and confirm synchronized devices are mapped to the correct rooms.

## Common issues

### Some cards look empty after opening the family page

That usually does not mean the page is unfinished. It usually means some data has not been filled in yet or one of the related API calls failed. Check whether the page shows a partial load failure warning first.

### Why do I see devices on the devices tab but the room counts look wrong

Check whether the device is already bound to the correct room. The page shows what the backend currently returns. It does not invent room mappings for you.

### Why does a child member have to select a guardian

That is the current page rule, not a documentation rule. The child role requires a guardian relationship so the family structure data does not become incomplete.

### Why did another page not update immediately after I changed member data

The family page refreshes its own workspace data, but other pages refresh on their own timing.

## Completion standard

- You know the family page is already a working main page, not a migration placeholder.
- You know it can already manage family profile data, rooms, device views, members, and relationships.
- You also understand where the current partial gaps still are, so you do not mistake a local unfinished detail for a completely missing page.
