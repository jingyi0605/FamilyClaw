---
title: Xiaomi Speaker Integration
docId: en-3.7
version: v0.1
status: draft
order: 370
outline: deep
---

# Xiaomi Speaker Integration

If you want to connect a Xiaomi speaker that already runs the `open-xiaoai` client into FamilyClaw, do it in this order:

1. Flash the device first.
2. Point the client to port `4399` on the machine that runs FamilyClaw.
3. Create the integration in FamilyClaw, sync devices, and configure the wake prefixes.

## Before you start

- FamilyClaw is already running, and the speaker can reach the FamilyClaw machine through the local network.
- The FamilyClaw machine exposes port `4399` to the LAN.
- You can sign in to FamilyClaw, and the current account has household management permission.
- The speaker already runs a system image that can launch the `open-xiaoai` client.

## Part 1: Flash the Xiaomi speaker

Do not duplicate the flashing guide here. Follow the official `open-xiaoai` flashing document directly:

- Flashing guide:
  [open-xiaoai Flashing Guide](https://github.com/idootop/open-xiaoai/blob/main/docs/flash.md)

Two things matter before you continue:

- The current flashing guide applies only to `XiaoAi Speaker Pro (LX06)` and `Xiaomi Smart Speaker Pro (OH2P)`.
- The USB cable must support data transfer, not charging only.

After flashing, verify that SSH access works. If SSH itself is still broken, the later client steps are pointless.

## Part 2: Start the Xiaomi speaker client

Use the `open-xiaoai` Rust client guide as the base, but point `SERVER` to the LAN IP of the machine that runs FamilyClaw and keep the port fixed at `4399`.

- Client guide:
  [open-xiaoai Client Guide](https://github.com/idootop/open-xiaoai/blob/main/packages/client-rust/README.md)

### 1. Sign in to the speaker over SSH

```bash
ssh -o HostKeyAlgorithms=+ssh-rsa root@YOUR_SPEAKER_IP
```

### 2. Create the client directory

```bash
mkdir -p /data/open-xiaoai
```

### 3. Write the FamilyClaw server address

Replace the IP below with the real LAN IP of the machine that runs FamilyClaw:

```bash
echo 'ws://192.168.31.100:4399' > /data/open-xiaoai/server.txt
```

Do not confuse this address with the speaker IP or some browser URL you copied casually. The speaker must be able to reach this exact FamilyClaw host and port.

If you deploy through Docker, NAS, or any container setup, also verify:

- The host maps port `4399` out correctly.
- Firewall or router rules do not block LAN access.

### 4. Start the client

The easiest path is still the official startup script:

```bash
curl -sSfL https://gitee.com/idootop/artifacts/releases/download/open-xiaoai-client/init.sh | sh
```

If you run the binary manually, point it to the same address:

```bash
/data/open-xiaoai/client ws://192.168.31.100:4399
```

### 5. Enable auto-start if needed

The official client guide already documents the boot-time script. Configure it there, then reboot the speaker and return to FamilyClaw to confirm the gateway is discovered.

## Part 3: Add the speaker in FamilyClaw and set wake prefixes

### Step 1: Create a `XiaoAi Speaker Gateway` instance

Open:

`Settings -> Devices & Integrations`

Then do this:

1. Click `Add device by instance`.
2. Choose `XiaoAi Speaker Gateway` from the plugin list.
3. Enter an instance name such as `Living Room XiaoAi Gateway`.
4. Select the discovered gateway.
5. Click `Create Instance`.

Two details matter here:

- If the system discovers only one available gateway, the UI usually binds it automatically.
- If `Discovered Gateways` is still empty, the speaker client has not really connected yet. Recheck the IP, port `4399`, and LAN connectivity first.

### Step 2: Sync the discovered speakers into the household

Stay on `Settings -> Devices & Integrations` and continue:

1. Select the `XiaoAi Speaker Gateway` instance you just created.
2. Click `Sync All Devices`.
3. Or click `Sync Selected Devices` if you only want a subset.

After sync, the speaker becomes a managed household device instead of a half-connected discovery record.

### Step 3: Configure wake prefixes in the device detail page

Do not stay on the integration page. That page is for discovery and sync, not device-level management.

Go here instead:

`Family -> Devices`

Find the imported Xiaomi speaker, open its detail page, and enter the `Voice Takeover` tab.

Two settings live there:

- `Take over all voice commands`
  When enabled, every voice request from that speaker goes straight into FamilyClaw and prefixes stop mattering.
- `Wake prefixes`
  When full takeover is disabled, only utterances that start with these prefixes enter FamilyClaw.

The Chinese docs sometimes call this the "response word". The real field name in the current product is `Wake prefixes`.

### How to fill the wake prefixes

For example:

```text
please,help me,assistant
```

Rules are simple:

- Separate prefixes with commas.
- Keep at least one prefix unless you intentionally enable full takeover.
- If `Take over all voice commands` is already enabled, the prefixes no longer apply.

## Troubleshooting

### The discovered gateway does not show up

Check these first:

- `server.txt` really points to the FamilyClaw machine at port `4399`
- The speaker and the FamilyClaw machine are on the same LAN
- Port `4399` is open to the LAN
- The client process is truly running

### The gateway exists, but no devices sync

Usually it is one of these:

- The instance is bound to the wrong gateway
- The client started once but is not staying connected to FamilyClaw

### The wake prefixes do not work

Check the configuration before blaming anything mysterious:

- `Take over all voice commands` may already be enabled, which naturally disables prefix matching
- `Wake prefixes` may contain empty lines, duplicates, or whitespace-only values
- Your spoken phrase may not actually start with one of the configured prefixes

## Related docs

- [Settings](./settings.md)
- [Family](./households.md)
- [open-xiaoai Flashing Guide](https://github.com/idootop/open-xiaoai/blob/main/docs/flash.md)
- [open-xiaoai Client Guide](https://github.com/idootop/open-xiaoai/blob/main/packages/client-rust/README.md)
