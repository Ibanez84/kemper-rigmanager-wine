# Kemper Rig Manager on Linux (Wine / Bottles)

Patches that let **Kemper Rig Manager 4.3.13** (Windows 64-bit) run in Wine on Linux with a
working USB connection to a Kemper Profiler: detection, syncing rigs/snapshots/performances,
auditioning from Rig Exchange, the live editor and backups. No Windows VM needed.

> **Unofficial.** Not made, supported or endorsed by Kemper. Use at your own risk.
> **Never update the Profiler's OS through Rig Manager under Wine.** Update it the official
> way, with a USB stick on the amp, which needs no PC. Don't let a firmware flash depend on
> a homemade USB layer.

Tested with:

| | |
|---|---|
| Amp | Profiler Toaster (MK1), OS 14.2.2 (and OS 13.0.5 with Rig Manager 3.10.13) |
| Rig Manager | 4.3.13 and 3.10.13, Windows 64-bit |
| Linux | Fedora-based (Bazzite), Bottles (Flatpak) |
| Wine | Soda 11.0-10 runner; patches made against Wine 11.0 |

Only tested with one Toaster MK1. Stage, Player and MK2 may behave differently. Reports welcome.

The Profiler's USB audio is class-compliant and already works natively on Linux; this is only
about Rig Manager.

## Why Rig Manager didn't work in Wine

Rig Manager talks to the Profiler through Windows' **WinUSB** driver and finds the amp through
the Windows device and USB hub APIs. Wine's `winusb.dll` was only stubs, and its USB driver had
no hub for Rig Manager to look at, so it never saw the amp. The patches add:

1. **powrprof**: three missing power functions Rig Manager imports at startup.
2. **setupapi**: `CM_Get_Parent`, `CM_Get_DevNode_Registry_PropertyW`, `SPDRP_ADDRESS` and
   `SetupGetThreadLogToken`, used to walk from the WinUSB device to its hub and port.
3. **wineusb.sys**: a virtual USB hub (hub interface, node-connection and descriptor IOCTLs),
   the USB device interface and WinUSB `DeviceInterfaceGUIDs` registration, and private IOCTLs
   for control, bulk/interrupt read/write, reset and abort.
4. **winusb.dll**: a real WinUSB implementation on top of those IOCTLs.
5. **win32u**: `WM_PARENTNOTIFY`'s wParam is sign-extended like on Windows. Without it Rig
   Manager's editor throws an `OverflowException`.

### Technical notes

- **WinUsb functions Rig Manager 4.3.13 imports:** Initialize, Free, QueryInterfaceSettings,
  QueryDeviceInformation, Get/SetCurrentAlternateSetting, GetAssociatedInterface,
  ControlTransfer, ReadPipe, WritePipe, ResetPipe, AbortPipe, GetOverlappedResult, and the five
  isochronous functions (Register/UnregisterIsochBuffer, Read/WriteIsochPipe,
  GetCurrentFrameNumber).
- **Isochronous:** exported as stubs only. Rig Manager never calls them during sync, auditioning
  or editing (a Wine stub call would raise an exception); they only need to exist for the DLL
  to load.
- **Overlapped I/O:** winusb.dll passes the caller's `OVERLAPPED` straight to `DeviceIoControl`.
  wineusb.sys returns `STATUS_PENDING` and completes the IRP when the libusb transfer finishes.
  `WinUsb_GetOverlappedResult` is `GetOverlappedResult` on the device handle. Without an
  `OVERLAPPED`, the call waits on a private event.
- **Timeouts:** Rig Manager doesn't import `WinUsb_SetPipePolicy`, so no WinUSB pipe timeouts
  are used; its timeouts are its own waits. `SetPipePolicy`/`SetPowerPolicy` are accepted and
  ignored.
- **Abort/reset:** `AbortPipe` and `ResetPipe` become `URB_FUNCTION_ABORT_PIPE` and
  `URB_FUNCTION_SYNC_RESET_PIPE_AND_CLEAR_STALL`. Closing a handle cancels its pending transfers.
- **Speed:** `QueryDeviceInformation(DEVICE_SPEED)` returns 1 for full-speed devices, as native
  WinUSB does.
- **Not implemented:** switching alternate settings, associated interfaces, the descriptor
  parsing helpers.

## Install (Bottles Flatpak)

Paths below are Bottles' default Flatpak data folder. `<runners>` means
`~/.var/app/com.usebottles.bottles/data/bottles/runners`, `<bottles>` means
`~/.var/app/com.usebottles.bottles/data/bottles/bottles`.

### 1. USB permission (udev rule)

```sh
sudo cp udev/70-kemper.rules /etc/udev/rules.d/
sudo udevadm control --reload
sudo udevadm trigger
```

Then unplug and replug the Profiler's USB cable. The rule only gives the logged-in user access
to Kemper's USB vendor ID (133e):

```
SUBSYSTEM=="usb", ATTRS{idVendor}=="133e", TAG+="uaccess"
```

### 2. A separate runner for Rig Manager

In Bottles, go to **Preferences → Runners** and install **soda-11.0-10**. Then make a copy that
only the Rig Manager bottle will use, so your other bottles are untouched:

```sh
cd <runners>
cp -a soda-11.0-10 soda-11.0-10-kemper
```

Copy the patched DLLs into the copy (back up the originals first):

```sh
W=<runners>/soda-11.0-10-kemper/lib/wine/x86_64-windows
mkdir -p ~/soda-originals
cp $W/{setupapi.dll,wineusb.sys,winusb.dll,powrprof.dll} ~/soda-originals/
cp prebuilt/soda-11.0-10/* $W/
rm $W/SHA256SUMS
```

Apply the win32u fix (checks the file is Soda 11.0-10's and keeps a `.orig` backup):

```sh
python3 tools/patch-soda-win32u.py <runners>/soda-11.0-10-kemper/lib/wine/x86_64-unix/win32u.so
```

Don't copy a vanilla Wine `user32.dll` or `win32u` into the Soda runner. Soda's win32u has extra
system calls, and mixing them breaks every message box.

### 3. The bottle

1. In Bottles, create a new bottle, type **Application**, for example named `KemperRM`.
2. In the bottle's settings, set **Runner** to `soda-11.0-10-kemper` and the Windows version to
   **Windows 10**.
3. Install .NET 4.8 and the VC++ 2022 runtime. I used winetricks inside the Bottles Flatpak:

   ```sh
   flatpak run --command=sh com.usebottles.bottles -c '
   R=$HOME/.var/app/com.usebottles.bottles/data/bottles/runners/soda-11.0-10-kemper
   export WINEPREFIX=$HOME/.var/app/com.usebottles.bottles/data/bottles/bottles/KemperRM
   export WINE=$R/bin/wine WINESERVER=$R/bin/wineserver PATH=$R/bin:$PATH WINEDEBUG=-all
   winetricks -q --force remove_mono dotnet48 vcrun2022'
   ```

   This takes a while. Bottles' own dependency installer (`dotnet48`, `vcredist2022`) may work
   too, but I haven't tested it.
4. Optional: I set Wine's audio driver to ALSA (`wine reg add "HKCU\Software\Wine\Drivers" /v
   Audio /d alsa /f`). I haven't tested whether that's required.

### 4. Rig Manager

Download the Windows 64-bit Rig Manager installer from Kemper, copy it into the bottle's
`drive_c`, and install it silently:

```sh
cp "<downloaded installer>.msi" <bottles>/KemperRM/drive_c/rm.msi
flatpak run --command=bottles-cli com.usebottles.bottles shell -b KemperRM \
    -i 'msiexec /i C:\rm.msi /qn'
```

An error about `DiInstallDevice` from Kemper's driver helper during setup is harmless. The MSI
still installs the WinUSB INF the patched Wine needs.

Start Rig Manager from Bottles (add `C:\Program Files\Kemper Amps\Rig Manager\Rig Manager.exe`
as a program) and connect the Profiler.

## Troubleshooting

- **0 rigs / "GetFileList Timeout" after a crash:** close Rig Manager and power-cycle the
  Profiler.
- **Amp not detected:** check the udev rule and replug; check the bottle really uses the
  `-kemper` runner.
- **Crashes after changing display scaling:** keep the bottle's DPI at 96. 108 crashed Rig
  Manager (GDI+ out of memory in a tree view animation), 120 broke the rig editor panel.
- **Small or serif fonts:** the bottle has no Segoe UI. A `FontSubstitutes` entry mapping
  "Segoe UI" and "Segoe UI Semibold" to Arial fixes it.
- **Never replace runner files while Rig Manager runs.** Close it and run `wineserver -k` first,
  or the mapped DLLs get corrupted.
- An `unsupported CLEAR_FEATURE` line in Wine's log is harmless.

## Building from source

The patches in `patches/` apply to Wine's `wine-11.0` tag:

```sh
git clone https://gitlab.winehq.org/wine/wine.git && cd wine
git checkout wine-11.0
git am /path/to/patches/*.patch
mkdir build64 && cd build64
../configure --enable-win64
make dlls/powrprof/all dlls/setupapi/all dlls/wineusb.sys/all dlls/winusb/all dlls/win32u/all
```

The results are `dlls/<name>/x86_64-windows/<name>.dll` (and `wineusb.sys`). For the Soda
runner, use only these four and patch win32u with `tools/patch-soda-win32u.py`. Patch 5 is the
source version of that fix, for vanilla Wine.

`prebuilt/soda-11.0-10/` holds the four DLLs built from these patches, the exact files in my
working runner. `SHA256SUMS` lists their checksums.

## License

LGPL-2.1-or-later, the same as Wine (see `LICENSE`). Feel free to reuse, adapt and upstream it.

These patches were developed with the help of Claude Code (Anthropic's AI coding assistant).
