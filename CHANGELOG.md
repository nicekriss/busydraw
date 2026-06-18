# Changelog

## v0.8-dev
- Added PNG border-background post-processing so forced white background is reliable even when Blender renders a gray world/background.
- In Real Scale mode, ISO view now defaults to Auto Fit to avoid extreme close-up/cropping.
- HTML sheet cards can now show per-view scale labels, so ISO can display `Auto Fit` while plan/elevations display `1:50`.
- Added `Real Scale safe margin mm` so dimension lines and border strokes can breathe without manually changing viewport size.
- Added a Fine dimension style button for thinner lines, smaller ticks, and less heavy dimension text.
- Added fast white background mode using transparent PNG output so test renders avoid the slow per-pixel cleanup path.
- Added Draft and Final render preset buttons.
- Changed Fine dimension style to recreate the bounding-box dimensions immediately so the visual change is obvious.

## v0.7.1
- Fixed forced white background rendering when the Blender scene world uses nodes.
- Made transparent background disabled while forced white background is enabled.
- Saved forced-white renders as RGB PNGs instead of RGBA PNGs.

## v0.7
- Added Auto Fit and Real Scale modes.
- Added drawing scale presets from 1:10 through 1:200 plus custom denominators.
- Added meter/millimeter model unit settings.
- Added viewport width/height controls for orthographic scale calculation.
- Updated camera setup and render operators to calculate `ortho_scale` from real scale settings.
- Updated HTML sheet scale labels and notes with scale mode, viewport size, and model unit.

## v0.6
- Added forced white background option.
- Changed temporary drawing material to emission white.
- Improved drawing render preset for black-background scenes.

## v0.5
- Added per-view zoom controls.
- Expanded zoom-out range.

## v0.4
- Added simple XY dimension tools.

## v0.3
- Added temporary section cut rendering.

## v0.2
- Added sheet metadata and more views.

## v0.1
- Initial camera and HTML sheet MVP.
