# M2U Export Helper

A lightweight Maya tool for validating and exporting Unreal-ready FBX assets.

> Validate first. Export cleaner.

## Overview

M2U Export Helper is a portfolio-focused Maya pipeline tool built for validating and exporting single Unreal-ready FBX assets directly from Autodesk Maya.

The goal of the tool is to help catch common asset issues before export, reduce manual checking, and provide a cleaner artist-facing workflow through validation, export gating, and JSON reporting.

It is designed for practical use by individual artists, students, small teams, and studios that want a simple Maya shelf-based validation/export helper.

## What the tool does

M2U Export Helper lets you:

- validate one selected Maya asset before export
- separate issues into **blocking errors** and **non-blocking warnings**
- export the asset as FBX only when blocking checks pass
- generate JSON validation and export reports
- launch the tool from a custom Maya shelf button
- optionally use an icon-supported shelf button

## Validation coverage

### Blocking checks

These checks stop export when they fail:

- Mesh Presence Check
- Name Check
- Freeze Transform Check
- Polycount Check

### Non-blocking checks

These checks do not stop export, but are shown as warnings or informational results:

- Scene Unit Check
- Pivot Check
- History Check
- Asset Scale Check

## Main features

- single-asset validation
- Unreal-ready FBX export workflow
- blocking vs non-blocking validation logic
- Maya UI workflow
- JSON validation report
- privacy-safer JSON export report
- custom shelf creation
- icon-supported shelf button
- cleaner UI path handling

## Included files

Recommended package structure:

```text

M2U_installer.py
M2U_icon.png
README.md

```

## Installation

Open **Autodesk Maya**.

Go to **Script Editor** and switch to the **Python** tab.

Run:

```python

import maya.cmds as cmds
p = cmds.fileDialog2(fileMode=1, caption="Select installer", fileFilter="Python Files (*.py)")
if p:
    exec(open(p[0], encoding="utf-8").read(), globals())
    install_and_launch_from_path(p[0])

```

When the file picker opens, select:

```text

M2U_installer.py

```

After that:

- the UI will open
- a custom shelf button will be created
- the tool can be launched later from the shelf

## Daily use

1. Open Maya
2. Click the **M2U Export** shelf button
3. Select one asset
4. Choose an export folder
5. Click **Validate Selected**
6. Review blocking issues and warnings
7. Click **Export Selected** if the asset passes blocking checks

## Export behavior

The tool exports only when all blocking checks pass.

Warnings do not stop export, but they are still shown in the UI and written to the report output.

## Output files

When export runs, the tool creates:

- `your_asset_name.fbx`
- `maya_unreal_v2_3_3_validation_report.json`
- `maya_unreal_v2_3_3_export_report.json`

## Privacy note

The UI is designed to avoid exposing full local file paths during normal use.

The export report is written in a more privacy-conscious format and avoids storing full local output paths.

Note that validation data may still include Maya object path information when needed for technical reporting.

## Notes

- The tool is designed for **one selected asset at a time**
- The tool runs inside **Autodesk Maya**
- FBX export requires Maya's **fbxmaya** plugin
- If the icon file is missing, the shelf button falls back to a text-only button

## Troubleshooting

### Shelf button does not appear

Run the installer again and make sure you selected the correct installer file.

### Shelf button appears but no icon is shown

Make sure `M2U_icon.png` is in the same folder as the installer script.

### Export does not happen

Run **Validate Selected** first and check whether the asset has blocking failures.

### Mesh test fails on empty groups or locators

This is expected. The tool only exports transforms that contain mesh shapes.

## Source and download

This project is published publicly on GitHub so users can view the code and download the tool.

Please download the tool from my **official GitHub page**.

If you want to share the tool with someone else, please send them to the official GitHub repository instead of re-uploading the files elsewhere.

## License / usage terms

This project is publicly visible and source-available on GitHub.

You may:

- use the tool for personal, educational, and internal production use
- use the tool inside a studio or company pipeline, including adding it to employee shelves or internal workstations
- review the source code for learning and evaluation
- download the tool from my official GitHub page

You may **not**:

- re-upload, mirror, redistribute, or republish the script, icon, package, or modified versions on other websites, repositories, drives, or marketplaces
- sell the tool, bundle it into a paid package, or include it in a commercial asset/tool pack
- use this code, in whole or in part, as the base for another tool, product, or commercial/internal tool release
- copy, adapt, fork, or repurpose the source code to create your own separate tool or derivative release
- remove attribution and present the tool or code as your own work

If someone wants to use the tool, they must download it from my **official GitHub page**.

For any use outside the permissions listed above, direct permission is required from the author.

## Portfolio note

This project is part of my technical art / pipeline tooling portfolio and is intended to demonstrate practical Maya tool development, validation system design, and artist-facing workflow polish.
