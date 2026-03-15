# Godot 4 Speed Prototype

Minimal third-person movement prototype focused on very high-speed traversal.

## Folder structure

```text
prototype/
├── project.godot
├── README.md
├── scenes/
│   ├── Main.tscn
│   └── Player.tscn
└── scripts/
    └── player.gd
```

## Scene setup

- `scenes/Main.tscn`
  - `Main (Node3D)`
  - `Sun (DirectionalLight3D)`
  - `Ground (StaticBody3D)` with collision + mesh
  - `Player` instance from `Player.tscn`
  - `Building_A`, `Building_B`, `Building_C` (`StaticBody3D` cubes)
- `scenes/Player.tscn`
  - `Player (CharacterBody3D)` with `scripts/player.gd`
  - `CollisionShape3D` (capsule)
  - `BodyMesh` (capsule mesh)
  - `Camera3D` (third-person follow camera)
  - `CanvasLayer/StaminaBar` (minimal stamina feedback)

## Controls

- `WASD`: Move (camera-relative)
- `Shift`: Sprint
- `E`: Hold for speed mode (drains stamina)

## How to run

1. Install/open **Godot 4.x**.
2. Import project at `prototype/project.godot`.
3. Press **Play** (or run `Main.tscn`).

## Tuning

Adjust movement and camera values in `scripts/player.gd` exported variables:

- `walk_speed`
- `sprint_multiplier`
- `speed_mode_multiplier`
- `acceleration`, `rotation_speed`
- `stamina_*`
- `base_fov`, `max_fov_bonus`
- `camera_offset`, `camera_look_at_offset`
