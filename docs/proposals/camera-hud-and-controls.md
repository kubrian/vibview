# Proposal: Camera HUD and Keyboard Controls

> Display live camera parameters as a viewport overlay and provide keyboard-driven camera manipulation with configurable step sizes.

---

## Problem

The camera is currently a "black box" — users can manipulate it interactively (mouse drag/scroll/pan), but:

1. **No feedback on current state.** There is no way to see the numerical azimuth, elevation, distance, or field of view of the camera. Reproducing a specific viewpoint requires trial and error.
2. **No keyboard controls.** All camera motion is mouse-driven. Users who prefer keyboard navigation or need fine-grained, repeatable adjustments have no path.
3. **No config-grounded initial view.** The camera position is auto-computed from the structure size (distance via fill-factor formula, orientation at a default quaternion). There is no way to set `azimuth`, `elevation`, or `distance` in the YAML config to start at a pre-defined perspective.

Batch export is off the table (proposal withdrawn), but without reproducible camera state, even single-mode export produces unpredictable framing.

## Diagnosis

- `CameraController` uses `ArcballCamera` (quaternion-based orientation). There is no property or method that exposes azimuth/elevation, nor any keyboard event handler on the camera.
- `VibviewWindow.keyPressEvent` handles only `F11` (fullscreen) and `R` (reset). No other keyboard paths exist.
- `CameraConfig` has `fov`, `fill_factor`, `min_distance`, `default_window_size`, and axis-sub-view settings but no pose parameters (`azimuth`, `elevation`, `distance`, `center`).
- The `Structures` center of mass is used as the camera center on init, but this isn't configurable.
- There is no viewport text overlay infrastructure.
- The camera's quaternion can be decomposed into azimuth/elevation for display purposes, but `ArcballCamera` does not expose these natively.

## Proposed solution

### 1. Camera HUD (heads-up display)

A semi-transparent text overlay in the bottom-left (or configurable corner) of the main viewport showing the current camera state:

```
Camera         Fine
──────────────
azimuth    127.3°
elevation   24.1°
distance    12.74 Å
fov         45.0°
center     (0.0, 0.0, 0.0)
```

- Updated on every frame draw (via `canvas.events.draw`).
- Toggle visibility with the **`D`** key (mnemonic: "display" / "debug").
- Also toggleable via config key `camera.show_hud: bool` (default `false`).
- Text uses a `vispy.scene.visuals.Text` node attached to the canvas scene, positioned in viewport-relative coordinates via a transform.
- Font size, color, and opacity configurable under a `camera.hud_*` namespace.

Interaction with the HUD toggled on:

- The HUD is non-interactive (pass-through) — clicks pass through to the 3D scene.
- When visible and the camera changes (mouse drag, scroll, key press), the displayed values update in real time.

### 2. Keyboard camera controls

Arrow and modifier keys mapped to camera motion:

| Keys                    | Action                       | Coarse step | Fine step     |
| ----------------------- | ---------------------------- | ----------- | ------------- |
| `←` / `→`               | Rotate azimuth               | ±15°        | ±2°           |
| `↑` / `↓`               | Rotate elevation             | ±15°        | ±2°           |
| `Ctrl`+`←` / `Ctrl`+`→` | Translate X                  | ±1 Å        | ±0.1 Å        |
| `Ctrl`+`↑` / `Ctrl`+`↓` | Translate Y                  | ±1 Å        | ±0.1 Å        |
| `+` / `-`               | Zoom in/out (scale distance) | ×1.1 / ÷1.1 | ×1.02 / ÷1.02 |
| `Shift` (hold)          | Switch to fine step sizes    | —           | —             |

- Arrow keys are always active when the viewport has focus.
- Shift acts as a precision modifier: held while pressing an arrow key to use the fine step size.
- Zoom keys (`+`/`-`) scale the camera distance, keeping the center fixed.
- All step sizes are configurable in the YAML config (`camera.arrow_step_*`).

Implementation approach for keyboard rotation:

- On each arrow key event, construct a small delta quaternion (rotation around the camera-local up/right axes) and compose it with the current camera quaternion.
- For translation, offset `camera.center` by the camera-local right/up vectors scaled by the step size.
- For zoom, multiply `camera.distance` by the zoom factor.

This keeps `ArcballCamera` as the camera type and avoids a switch to `TurntableCamera`.

### 3. Config-driven initial camera state

Add new optional keys under the existing `camera:` section:

```yaml
camera:
  # --- existing keys (unchanged) ---
  fov: 45
  fill_factor: 0.75
  min_distance: 5.0
  default_window_size: [608, 608]

  # --- new pose keys (all optional, null = auto-compute) ---
  azimuth: null # initial azimuth angle in degrees
  elevation: null # initial elevation angle in degrees
  distance: null # initial camera distance in Å (null = auto from fill_factor)
  center: null # orbit center [x, y, z] in Å (null = center of mass)

  # --- new keyboard/gizmo step sizes ---
  keyboard_step_azimuth: 15.0
  keyboard_step_elevation: 15.0
  keyboard_step_translate: 1.0
  keyboard_step_fine_multiplier: 0.15 # coarse × this = fine step
  keyboard_zoom_factor: 1.1

  # --- new HUD options ---
  show_hud: false
  hud_font_size: 14
  hud_color: "#ffffff"
  hud_alpha: 0.8
```

When `azimuth`, `elevation`, and `distance` are all non-null, construct the initial camera quaternion from them and apply it after the usual auto-distance setup. The ordering: apply config values over the auto-computed base, so that unset fields still get sensible defaults.

### Data flow

```
Config → CameraController.__init__
           │
           ├── auto-compute distance (if null)
           ├── build quaternion from azimuth/elevation (if set)
           └── set camera.center (override if set)
                   │
                   ▼
            ArcballCamera ready
                   │
          ┌────────┴────────┐
          ▼                 ▼
   Keyboard events     Mouse events
   (VibviewWindow)     (vispy native)
          │                 │
          └────────┬────────┘
                   ▼
          CameraController.apply_delta()
                   │
          ┌────────┴────────┐
          ▼                 ▼
     Update camera      Update HUD
     quaternion         text overlay
```

### Implementation plan

1. **`CameraConfig`** — add the new optional fields (pose, steps, HUD). `None` defaults for pose fields, sensible defaults for step sizes. Validation in `__post_init__`.

2. **`CameraController`** — add methods:
   - `_build_quaternion(azimuth, elevation) → vispy.Quaternion` — construct a quaternion from Euler angles.
   - `_quaternion_to_ae(q) → (azimuth, elevation)` — decompose for HUD display.
   - `_key_rotate(delta_azimuth, delta_elevation)` — compose incremental rotation.
   - `_key_translate(dx, dy)` — offset center in camera-local XY plane.
   - `_key_zoom(factor)` — scale distance.

3. **`VibviewWindow.keyPressEvent`** — add cases for arrow keys, `+`/`-`, `D` (HUD toggle), `R` (reset, already exists). Route to `CameraController` methods via a new callback `on_camera_key`.

4. **HUD layer** — add a `vispy.scene.visuals.Text` grid to the main view scene. In `CameraController`, update text positions/strings each frame via `canvas.events.draw`. The HUD uses a `vispy.scene.transforms.STTransform` to pin to viewport coordinates.

5. **`defaults.yaml`** — add the new config keys with inline comments.

### Toggle behavior

| Key            | Action                  | Scope                       |
| -------------- | ----------------------- | --------------------------- |
| `D`            | Toggle HUD overlay      | Per-session (not persisted) |
| `Shift` (hold) | Fine movement modifier  | Momentary                   |
| `F`            | (reserved — future use) | —                           |

The HUD toggle is session-only; it does not write back to the config file. The `camera.show_hud` config key controls the initial HUD state on startup.

## Difficulties and considerations

### ArcballCamera vs TurntableCamera

ArcballCamera uses quaternions with no built-in azimuth/elevation concept. We decompose the quaternion for display and construct incremental rotations for input. This keeps the existing camera type and avoids regressions in mouse interaction behavior.

Decomposition: given a quaternion `q = (w, x, y, z)` representing camera orientation, extract the forward vector (`-z` column of the rotation matrix) and compute spherical angles:

```python
def _quaternion_to_ae(q):
    # rotation matrix from quaternion
    R = np.array(q.get_matrix(RotationMatrix3D))[:3, :3]
    forward = -R[:, 2]  # camera looks along -z
    azimuth = np.degrees(np.arctan2(forward[0], forward[1]))
    elevation = np.degrees(np.arcsin(forward[2] / np.linalg.norm(forward)))
    return azimuth, elevation
```

This gives display values that match what the user would expect from a turntable-style camera, even though the underlying rotation is stored as a quaternion.

### Keyboard focus

The vispy canvas typically captures keyboard focus. Arrow keys may need to be intercepted at the `VibviewWindow` level (before they reach vispy) or via vispy's own key-event system. Qt's `keyPressEvent` on the window works because the vispy canvas is embedded as a native widget that doesn't swallow arrow keys. Verify on Linux with PyQt6.

### HUD positioning and frame updates

The HUD text must be re-positioned on every canvas resize (viewport-relative coordinates). Connect to `canvas.events.resize` to update the `STTransform` offset. The text content updates on `canvas.events.draw` (which fires every frame), so the displayed values are always current.

### Step sizes and UX

15° coarse rotation is large enough to be useful for navigation but small enough for fine adjustment with Shift (2.25° with 0.15 multiplier). Translation steps of 1 Å / 0.15 Å match typical bond-length scales. Users can tune these in their config.

### No overlap with existing shortcuts

Current shortcuts: `F11` (fullscreen), `R` (reset). The new `D` key for HUD toggle and arrow key handling do not conflict. `+`/`-` may conflict with vispy's default zoom — this must be tested. If vispy swallows `+`/`-`, route them through `VibviewWindow.keyPressEvent` before passing to vispy, or use `Ctrl`+`+` / `Ctrl`+`-` as an alternative.

## Rationale

- Solves the root problem that motivated the withdrawn batch-export proposal: reproducible camera state.
- The HUD gives immediate feedback that makes the camera "transparent" — users can see and remember exact parameters.
- Keyboard controls provide a mouse-free navigation path that complements mouse drag/scroll.
- Config-driven initial state means users can define "bookmarked" camera positions in their YAML config for repeatable exports.
- All step sizes and visual parameters are tunable in config — no hardcoded magic numbers.
- No new dependencies — vispy `Text` visuals and Qt key events are already available.
