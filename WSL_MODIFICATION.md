# WSL2 Custom Kernel — Steps & Recovery

## Why this is needed

The candleLight USB-to-CAN adapter (delivered with the Hunter SE) uses the
`gs_usb` Linux kernel driver. The default Microsoft WSL2 kernel does not
include this driver. A one-time custom kernel build is required.

---

## Before you start — backup .wslconfig

> 🖥️ **PowerShell — no Admin required**

```powershell
Copy-Item "$env:USERPROFILE\.wslconfig" "$env:USERPROFILE\.wslconfig.bak" -ErrorAction SilentlyContinue
Write-Host "Backed up to $env:USERPROFILE\.wslconfig.bak"
```

If `.wslconfig` doesn't exist yet, that's fine — nothing to back up.

---

## Steps

### Step 1 — Run the kernel build script (~15 minutes)

> 🐧 **WSL2 terminal — with sudo**

```bash
sudo bash setup/04_build_wsl2_kernel.sh
```

What it does:
- Installs build tools (`build-essential`, `flex`, `bison`, etc.)
- Clones Microsoft's WSL2 kernel source at your exact running version
- Enables `CONFIG_CAN_GS_USB=y` (and related CAN flags)
- Compiles the kernel using all available CPU cores
- Copies `bzImage` to `C:\Users\jhuessy\wsl2-kernel\bzImage`
- Adds a `kernel=` line to `C:\Users\jhuessy\.wslconfig`

### Step 2 — Shut down WSL2

> 🖥️ **PowerShell — no Admin required**

```powershell
wsl --shutdown
```

### Step 3 — Reopen WSL2

Close and reopen your WSL2 terminal. The new kernel loads automatically.

### Step 4 — Verify the driver loaded

> 🐧 **WSL2 terminal — with sudo**

```bash
sudo modprobe gs_usb && echo "gs_usb OK"
uname -r   # version should look the same as before
```

### Step 5 — Bring up the CAN interface

> 🐧 **WSL2 terminal — with sudo**

```bash
sudo bash setup/02_setup_can_interface.sh
```

---

## Recovery — if WSL2 won't start after the reboot

This means the custom kernel failed to boot. Fix takes 30 seconds:

### Option A — Comment out the kernel line (recommended)

> 🖥️ **Windows — open Notepad or any text editor (no Admin required)**

Open the file:
```
C:\Users\jhuessy\.wslconfig
```

Find the line that looks like:
```ini
[wsl2]
kernel=C:\\Users\\jhuessy\\wsl2-kernel\\bzImage
```

Comment it out:
```ini
[wsl2]
# kernel=C:\\Users\\jhuessy\\wsl2-kernel\\bzImage
```

Save the file, then:

> 🖥️ **PowerShell — no Admin required**

```powershell
wsl --shutdown
```

Reopen WSL2 — it will boot the original Microsoft kernel as before.

### Option B — Restore from backup

> 🖥️ **PowerShell — no Admin required**

```powershell
Copy-Item "$env:USERPROFILE\.wslconfig.bak" "$env:USERPROFILE\.wslconfig" -Force
wsl --shutdown
```

Then reopen WSL2.

### Option C — Delete .wslconfig entirely

If you didn't have a `.wslconfig` before this:

> 🖥️ **PowerShell — no Admin required**

```powershell
Remove-Item "$env:USERPROFILE\.wslconfig"
wsl --shutdown
```

---

## Recovery — if the build script fails mid-way

The `.wslconfig` is only updated at the **end** of the script, so if it fails
partway through your existing WSL2 setup is unaffected. Just re-run:

> 🐧 **WSL2 terminal — with sudo**

```bash
sudo bash setup/04_build_wsl2_kernel.sh
```

The script skips the `git clone` step if the source is already present.

---

## Reverting permanently (uninstall custom kernel)

> 🖥️ **PowerShell — no Admin required**

```powershell
notepad "$env:USERPROFILE\.wslconfig"   # remove or comment out the kernel= line
wsl --shutdown
```

> 🐧 **WSL2 terminal — no sudo needed**

```bash
rm -rf ~/wsl2-kernel
```

> 🖥️ **PowerShell — no Admin required**

```powershell
Remove-Item -Recurse "$env:USERPROFILE\wsl2-kernel"
```

---

## Summary

| File changed | What changed | How to revert |
|---|---|---|
| `C:\Users\jhuessy\.wslconfig` | `kernel=` line added | Comment out or delete the line |
| `C:\Users\jhuessy\wsl2-kernel\bzImage` | New file | Delete the file |
| WSL2 distro / Ubuntu packages | Nothing | N/A |
| Windows | Nothing | N/A |
