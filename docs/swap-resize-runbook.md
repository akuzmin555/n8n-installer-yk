# Swap resize runbook

This note documents the planned swap change for this server.

## Current state observed

- Swap is a file: `/swap.img`
- Current size: `8G`
- Current usage was almost full: about `7.9G / 8G`
- Filesystem for `/swap.img`: root filesystem `/`
- Backing device: `/dev/mapper/ubuntu--vg-ubuntu--lv`
- Root filesystem has more than `1T` free, so there is enough disk space.
- RAM pressure was not active at the time of checking:
  - `free -h` showed about `41G` available memory.
  - `vmstat 1` showed `si=0` and `so=0` after the first average line.

## Goal

Increase `/swap.img` from `8G` to `32G` without rebooting.

This gives more emergency headroom for memory spikes from LLM/RAG/container workloads. It does not make the system faster. If the system actively uses a large amount of swap, it can still become very slow because swap is stored on disk.

## Pre-checks

Run:

```bash
free -h
swapon --show
df -hT /swap.img
vmstat 1
```

In `vmstat 1`, ignore the first line after the header because it is an average since boot. Watch the next several lines:

- `si` and `so` should usually be `0` or very low.
- `wa` should be low.

Before running `swapoff`, make sure available RAM is comfortably larger than the currently used swap. For the observed state, about `8G` swap was used and available RAM was much higher, so this looked safe.

## Main commands

Run these commands one by one:

```bash
sudo swapoff /swap.img
sudo fallocate -l 32G /swap.img
sudo chmod 600 /swap.img
sudo mkswap /swap.img
sudo swapon /swap.img
swapon --show
free -h
```

Expected result:

- `swapon --show` lists `/swap.img`
- swap size is about `32G`
- swap usage may be low immediately after recreation

## If `swapoff` is slow

`swapoff /swap.img` can take time because Linux has to move swapped pages back into RAM.

Open another terminal and watch:

```bash
free -h
vmstat 1
```

If the machine remains responsive, wait.

## If `swapoff` fails

If `swapoff` fails with an error such as not enough memory:

1. Do not continue with `fallocate` or `mkswap`.
2. Check memory:

```bash
free -h
swapon --show
```

3. Stop or reduce memory-heavy services, then retry later.

If swap is still enabled in `swapon --show`, the old swap is still active.

## If swap was disabled but recreation failed

If `swapoff` succeeded but a later command failed, recreate and enable the old or new swap file.

For the planned `32G` size:

```bash
sudo fallocate -l 32G /swap.img
sudo chmod 600 /swap.img
sudo mkswap /swap.img
sudo swapon /swap.img
swapon --show
free -h
```

If you want to return to the old `8G` size instead:

```bash
sudo fallocate -l 8G /swap.img
sudo chmod 600 /swap.img
sudo mkswap /swap.img
sudo swapon /swap.img
swapon --show
free -h
```

## fstab check

The existing setup likely already uses `/swap.img`. Confirm with:

```bash
grep -n 'swap.img\| swap ' /etc/fstab
```

If `/etc/fstab` contains `/swap.img`, no fstab change is needed when only changing the file size.

## Reboot

A reboot is not required for this operation.

Rebooting would clear current swap usage, but it would also interrupt services. The planned procedure is designed to work online.
