---
title: Xiaomi Speaker Integration
docId: en-3.7
version: v0.1
status: draft
order: 370
outline: deep
---

# Xiaomi Speaker Integration

If you want to connect a Xiaomi speaker that already runs the `open-xiaoai` client to FamilyClaw, keep the workflow simple:

1. flash the speaker first
2. point the speaker client to the FamilyClaw machine on port `4399`
3. create the integration in FamilyClaw, sync the speaker into the family, then configure the response prefixes

## Before you start

- FamilyClaw is already running and reachable from the same LAN as the Xiaomi speaker.
- The machine hosting FamilyClaw is exposing port `4399` to the local network.
- You can sign in to FamilyClaw and manage the current household.
- The Xiaomi speaker has already been flashed with a system that can run the `open-xiaoai` client.

## Part 1: Flash the Xiaomi speaker

Do not rewrite the flashing steps here. Use the official `open-xiaoai` flashing guide directly:

- Flashing guide:
  [open-xiaoai flashing guide](https://github.com/idootop/open-xiaoai/blob/main/docs/flash.md)

Two details matter before you start:

- The current guide only applies to `XiaoAi Speaker Pro (LX06)` and `Xiaomi Smart Speaker Pro (OH2P)`.
- The USB cable must support data transfer, not charging only.

After flashing, the official guide also shows how to log in through SSH. If SSH does not work, stop there. There is no point pretending the client step is ready.

## Part 2: Start the Xiaomi speaker client

For the client side, follow the `open-xiaoai` Rust client guide, but change the `SERVER` address to the LAN IP of the machine running this project and keep port `4399`.

- Client guide:
  [open-xiaoai client guide](https://github.com/idootop/open-xiaoai/blob/main/packages/client-rust/README.md)

### 1. Sign in to the speaker with SSH

```bash
ssh -o HostKeyAlgorithms=+ssh-rsa root@YOUR_SPEAKER_IP
```

### 2. Create the client directory

```bash
mkdir -p /data/open-xiaoai
```

### 3. Write the FamilyClaw server address

Replace the IP below with the real LAN IP of the machine hosting FamilyClaw:

```bash
echo 'ws://192.168.31.100:4399' > /data/open-xiaoai/server.txt
```

Do not guess here. This is not the speaker IP, and it is not the random browser URL you happen to use for the web UI. It must be the address that the speaker can actually reach on the LAN.

If you run FamilyClaw through Docker, a NAS package, or any other container setup, also verify this:

- port `4399` is published from the host machine
- the firewall or router is not blocking LAN access

### 4. Start the client

The easiest path is still the official bootstrap script:

```bash
curl -sSfL https://gitee.com/idootop/artifacts/releases/download/open-xiaoai-client/init.sh | sh
```

If you prefer to start the binary manually, it still has to connect to the same address:

```bash
/data/open-xiaoai/client ws://192.168.31.100:4399
```

### 5. Enable auto start if needed

The official client guide also provides a startup script. Use that if you want the speaker to reconnect automatically after reboot. Once that is done, reboot the speaker and check FamilyClaw again to see whether the gateway has been discovered.

## Part 3: Add the speaker in FamilyClaw and configure response prefixes

### Step 1: Create a formal `Xiaomi Speaker Gateway` instance

Open:

`Settings -> Devices & Integrations`

Then follow this sequence:

1. click `Add devices by instance`
2. choose the `Xiaomi Speaker Gateway` plugin from the catalog
3. give the instance a name such as `Living Room Xiaomi Gateway`
4. pick the gateway that FamilyClaw has already discovered
5. click `Create instance`

Two details matter here:

- If FamilyClaw has discovered only one available gateway, the UI usually binds it automatically.
- If the `Discovered gateways` area is still empty, the speaker client is not really connected yet. Go back and recheck the IP, port `4399`, and LAN reachability first.

### Step 2: Sync the discovered speakers into the household

After the instance is created, stay on the same `Settings -> Devices & Integrations` page and do this:

1. select the `Xiaomi Speaker Gateway` instance you just created
2. click `Sync all devices`
3. or click `Sync selected devices` if you only want a subset

Only after that sync finishes does the speaker become a formal household device instead of just a discovered candidate.

### Step 3: Configure the response prefixes in device details

Do not stay in the integration page for device-level settings. That page is for integration setup and sync, not for per-device behavior.

Go here instead:

`Family -> Devices`

Find the Xiaomi speaker you just synced, open its device detail dialog, and switch to the `Voice Takeover` tab.

This tab has two important fields:

- `Take over all voice requests`
  If enabled, every voice request on that speaker is handed to FamilyClaw directly and prefixes are no longer used for matching.
- `Response prefixes`
  If full takeover is disabled, only requests that start with these prefixes are forwarded to FamilyClaw.

The Chinese UI and product notes sometimes call these values "response words", but the formal field name in the current product is `Response prefixes`. Same thing, less confusion.

### How to fill the response prefixes

For example:

```text
please
help me
assistant
```

The rules are simple:

- one prefix per line is fine, and comma-separated input also works
- keep at least one prefix, otherwise you are asking for accidental triggers
- if `Take over all voice requests` is enabled, the prefixes no longer apply

## Common checks

### FamilyClaw does not show any discovered gateway

Check the obvious things first:

- `server.txt` really points to the FamilyClaw machine on port `4399`
- the speaker and FamilyClaw are on the same LAN
- port `4399` is reachable from the LAN
- the client process is actually running

### The instance exists, but no speaker can be synced

That is usually one of these:

- the instance is bound to the wrong gateway
- the speaker client started once, but is not staying connected to FamilyClaw

### The response prefixes do not work

Do not jump to superstition. Check the configuration first:

- `Take over all voice requests` may already be enabled, which makes prefixes irrelevant
- `Response prefixes` may contain only blank lines, duplicate values, or whitespace
- your actual spoken sentence may not start with the prefixes you configured

## Related pages

- [Settings](./settings.md)
- [Family](./households.md)
- [open-xiaoai flashing guide](https://github.com/idootop/open-xiaoai/blob/main/docs/flash.md)
- [open-xiaoai client guide](https://github.com/idootop/open-xiaoai/blob/main/packages/client-rust/README.md)
