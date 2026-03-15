extends CharacterBody3D

@export var walk_speed: float = 12.0
@export var sprint_multiplier: float = 2.0
@export var speed_mode_multiplier: float = 4.0
@export var acceleration: float = 28.0
@export var rotation_speed: float = 8.0
@export var stamina_max: float = 5.0
@export var stamina_drain_per_second: float = 1.4
@export var stamina_recover_per_second: float = 0.9
@export var base_fov: float = 75.0
@export var max_fov_bonus: float = 35.0
@export var gravity: float = 30.0
@export var camera_offset: Vector3 = Vector3(0.0, 3.0, 7.0)
@export var camera_look_at_offset: Vector3 = Vector3(0.0, 1.0, 0.0)

var stamina: float = stamina_max

@onready var camera: Camera3D = $Camera3D
@onready var stamina_bar: ProgressBar = $CanvasLayer/StaminaBar

func _ready() -> void:
	camera.top_level = true
	stamina_bar.max_value = stamina_max
	stamina_bar.value = stamina
	_update_camera_follow()
	_update_camera_fov()

func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity.y -= gravity * delta
	else:
		velocity.y = 0.0

	var speed_mode_active := Input.is_action_pressed("speed_mode") and stamina > 0.0
	_update_stamina(delta, speed_mode_active)

	var input_dir := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var move_direction := _get_camera_relative_direction(input_dir)

	var speed_multiplier := 1.0
	if Input.is_action_pressed("sprint"):
		speed_multiplier *= sprint_multiplier
	if speed_mode_active:
		speed_multiplier *= speed_mode_multiplier

	var target_velocity := move_direction * walk_speed * speed_multiplier
	velocity.x = move_toward(velocity.x, target_velocity.x, acceleration * delta)
	velocity.z = move_toward(velocity.z, target_velocity.z, acceleration * delta)

	if move_direction.length_squared() > 0.0001:
		var target_yaw := atan2(move_direction.x, move_direction.z)
		rotation.y = lerp_angle(rotation.y, target_yaw, rotation_speed * delta)

	move_and_slide()

	_update_camera_follow()
	_update_camera_fov()
	stamina_bar.value = stamina

func _get_camera_relative_direction(input_dir: Vector2) -> Vector3:
	if input_dir.length_squared() == 0.0:
		return Vector3.ZERO

	var camera_forward := -camera.global_transform.basis.z
	var camera_right := camera.global_transform.basis.x
	camera_forward.y = 0.0
	camera_right.y = 0.0

	camera_forward = camera_forward.normalized()
	camera_right = camera_right.normalized()

	return (camera_right * input_dir.x + camera_forward * input_dir.y).normalized()

func _update_stamina(delta: float, speed_mode_active: bool) -> void:
	if speed_mode_active:
		stamina = max(stamina - stamina_drain_per_second * delta, 0.0)
	else:
		stamina = min(stamina + stamina_recover_per_second * delta, stamina_max)

func _update_camera_follow() -> void:
	camera.global_position = global_position + camera_offset
	camera.look_at(global_position + camera_look_at_offset, Vector3.UP)

func _update_camera_fov() -> void:
	var current_speed := Vector2(velocity.x, velocity.z).length()
	var max_speed := walk_speed * sprint_multiplier * speed_mode_multiplier
	var speed_ratio := clamp(current_speed / max_speed, 0.0, 1.0)
	camera.fov = lerp(base_fov, base_fov + max_fov_bonus, speed_ratio)
