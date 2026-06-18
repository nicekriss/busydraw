# Changelog

## v0.10-dev
- Added Busy tags for selected parents/components: furniture, wall, window, door, fixture, and custom.
- Added selected-component dimensions that use each parent/Empty object's visible child bbox, so BlenderKit assets can be dimensioned as one component.
- Added tag-component dimensions to generate dimensions for all top-level objects with the active Busy tag.
- Added active-parent component dimensions: total parent outer dimensions plus smaller child-component internal dimensions along the parent's main axis.
- Added tag dimension visibility controls to hide, show, or delete only the dimensions belonging to the active tag.
- Added selected-component dimension hiding for local cleanup when one parent/component's dimensions get crowded.
- Changed component dimension placement to default to the scene-center side, so dimensions for furniture near a wall tend to stay inside the room instead of outside the wall.
- Updated generated sheets to identify v0.10-dev.

## v0.9-dev
- Added output view presets: Core, Plan + ISO, Elevations, and All.
- Added a Quick Test render operator that applies draft output settings and renders the selected sheet in one step.
- Added buttons to open the generated HTML sheet and output folder from the Busy Layout panel.
- Updated generated sheets to identify v0.9-dev and keep image backgrounds explicitly white.
- Added a section cut option to cut only objects taller than the cut plane, so low furniture can remain visible in plan views.
- Changed two-object dimensions to default to nearest bounding-box faces instead of object origins, with Auto/X/Y axis controls.
- Converted the numbered Busy Layout panel sections into foldouts so the growing option set stays manageable.
- Added group-to-active dimensions for multi-part assets: select all furniture parts, select the wall last, then dimension the furniture group's bbox to the active object.
- Parent/Empty objects now use their visible child meshes for bbox dimension calculations, so a BlenderKit parent can be selected as one component.

## v0.8-dev
- Added PNG border-background post-processing so forced white background is reliable even when Blender renders a gray world/background.
- In Real Scale mode, ISO view now defaults to Auto Fit to avoid extreme close-up/cropping.
- HTML sheet cards can now show per-view scale labels, so ISO can display `Auto Fit` while plan/elevations display `1:50`.
- Added `Real Scale safe margin mm` so dimension lines and border strokes can breathe without manually changing viewport size.
- Added a Fine dimension style button for thinner lines, smaller ticks, and less heavy dimension text.
- Added fast white background mode using transparent PNG output so test renders avoid the slow per-pixel cleanup path.
- Added Draft and Final render preset buttons.
- Changed Fine dimension style to recreate the bounding-box dimensions immediately so the visual change is obvious.
- Changed fast white background mode from transparent PNG to RGB white PNG so standalone image previews do not appear black.

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
