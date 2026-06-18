# Busy Layout Dev Install

Use this when testing small add-on changes often.

Instead of installing a downloaded `.py` file every time, Blender can load the add-on directly from this Git working tree.

## Current Local Setup

This machine is set up for Blender `5.1` with a Windows junction:

```text
C:\Users\크리스\AppData\Roaming\Blender Foundation\Blender\5.1\scripts\addons\busy_layout_mvp
-> C:\Users\크리스\OneDrive\문서\blenderdraw\busy_layout_mvp
```

The previous single-file install was moved to:

```text
busy_layout_mvp_v07.py.disabled-backup
```

## Daily Test Loop

1. Pull or receive the latest repository changes.
2. In Blender, run `F3 > Reload Scripts`.
3. If Busy Layout is not enabled yet, use `Edit > Preferences > Add-ons` and enable `Busy Layout MVP` with module name `busy_layout_mvp`.
4. Test from the `N` sidebar > `Busy Layout`.

After the dev reload button is visible in the Busy Layout panel, you can usually press `Dev Reload Scripts` instead of using `F3`.

No delete/reinstall cycle is needed while this link is active.

## Recreate The Link

From this repository:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_blender_dev_link.ps1 -BlenderVersion 5.1
```

Change `5.1` if testing in another Blender version.
