# Busy Layout MVP

Blender add-on prototype for generating SketchUp LayOut-style drawing sheets from 3D models.

## Current version

v0.10-dev

## Features

- Orthographic cameras for top plan, front, right, left, back, and ISO views
- Per-view zoom-out controls based on Orthographic Scale
- Forced white drawing background
- Temporary shadeless/emission white material rendering
- Freestyle outline rendering
- Temporary Boolean section cut
- Simple XY dimension helpers
- PNG view export
- HTML drawing sheet for browser PDF export
- Real scale mode with 1:10, 1:20, 1:30, 1:50, 1:75, 1:100, 1:150, 1:200, and custom scale denominator presets
- Meter and millimeter model unit options
- Adjustable viewport width/height in millimeters for scale calculation
- v0.7.1 fixes forced white render background handling when an existing Blender world uses nodes
- v0.8-dev adds output PNG background cleanup and keeps ISO on Auto Fit by default during Real Scale rendering
- v0.9-dev adds view presets, quick test rendering, and one-click sheet/output folder opening
- v0.10-dev adds SketchUp-like Busy tags and parent/component bbox dimension helpers

## Install

During development, use the linked `busy_layout_mvp` package as a Blender add-on. Release downloads are published separately when a version is ready.

## v0.7 Real Scale

`Auto Fit` keeps the previous v0.6 behavior and uses the per-view zoom-out controls.

`Real Scale` calculates each orthographic camera's `camera.data.ortho_scale` from:

- selected scale denominator, such as `1:50`
- viewport width/height in millimeters
- model unit, either meter or millimeter
- render aspect ratio

Example: with model unit `Meter`, scale `1:50`, and viewport `180mm x 120mm`, the vertical world height is `120mm * 50 = 6000mm = 6m`, so the camera orthographic scale is at least about `6.0`.

The v0.7 scale feature is an MVP control for Blender orthographic views, not a complete CAD scale/layout engine. If `Real Scale margin factor` is set above `1.0`, the view is intentionally wider than the printed scale and the sheet label adds `adjusted`.

## Roadmap

- v0.11: sheet viewport layout controls
- v1.0: title block templates and collection-based line styles
