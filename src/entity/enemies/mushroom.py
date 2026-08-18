from collections.abc import Callable
from typing import override

from tilemap_parser import (
    AnimationPlayer,
    CollisionRunner,
    SpriteAnimationSet,
    get_shape_aabb,
    load_character_collision,
)
from tilemap_parser.runtime.collision import should_collide

from src.core.effects import ParticleConsumerPartial
from src.entity.base import CollidableAnimationEntity
from src.entity.enemies.base import GroundCheck, HorizontalGroundedEnemy
from src.settings import ANIMATION_PATH, CHARACTER_COLLISION_PATH

MUSHROOM_SPEED = 100
MUSHROOM_GRAVITY = 800
MUSHROOM_MAX_FALL_SPEED = 600
TARGET_CHASE_RANGE = 200
FEET_TOLERANCE = 8.0


class Mushroom(HorizontalGroundedEnemy):
    collision_path = CHARACTER_COLLISION_PATH / "mushroom.collision.json"
    animation_path = ANIMATION_PATH / "mushroom.anim.json"
    speed = MUSHROOM_SPEED
    gravity = MUSHROOM_GRAVITY
    max_fall_speed = MUSHROOM_MAX_FALL_SPEED
    target_chase_range = TARGET_CHASE_RANGE

    def __init__(
        self,
        x: float,
        y: float,
        runner: CollisionRunner,
        ground_check: GroundCheck,
        emit: Callable[[ParticleConsumerPartial], None],
        target: CollidableAnimationEntity | None = None,
    ) -> None:
        super().__init__(x, y, runner, ground_check, emit, target)

        collision = load_character_collision(self.collision_path)
        if collision is None:
            raise ValueError("Collision data not loaded")

        self.collision_shape = collision.shape  # pyright: ignore
        self.collision_mask = collision.collision_mask
        self.collision_layer = collision.collision_layer

        self.shape_aabb = get_shape_aabb(self.x, self.y, self.collision_shape)

        sprite_animation_set = SpriteAnimationSet.load(self.animation_path)
        self.animation_states: dict[str, AnimationPlayer] = {
            "idle": AnimationPlayer(sprite_animation_set, "idle"),
            "attack": AnimationPlayer(sprite_animation_set, "attack"),
            "run": AnimationPlayer(sprite_animation_set, "run"),
            "hurt": AnimationPlayer(sprite_animation_set, "hurt"),
            "dead": AnimationPlayer(sprite_animation_set, "dead"),
            "stunned": AnimationPlayer(sprite_animation_set, "stunned"),
        }
        self.current_state = "idle"
        self.stun_time = 0

        self.is_attacking = False

    def can_stun(self):
        falling = self.target is not None and self.target.vy >= 0
        return self.stun_time == 0 and self.current_state != "stunned" and falling

    def stun(self):
        self.stun_time = 2
        self.current_state = "stunned"
        self.is_attacking = False
        self.vx = 0

    def can_damage(self):
        return self.is_attacking and self.animation_states[self.current_state].frame_index > 3

    def handle_target(self):
        if self.target is None:
            return
        if not should_collide(self, self.target):  # pyright: ignore
            return
        if self.current_state == "stunned":
            return
        tl, _, tr, tb = self.target.shape_aabb
        sl, _, sr, sb = self.shape_aabb
        x_diff = (tl + tr) * 0.5 - (sl + sr) * 0.5

        y_fail = abs(sb - tb) > FEET_TOLERANCE
        if abs(x_diff) < min(tr - tl, sr - sl) and not y_fail:
            self.is_attacking = True
            self.walking = 0
        elif abs(x_diff) < self.target_chase_range:
            if y_fail:
                return
            if not self.ground_check(self):
                self.walking = 0
                return
            self.direction = -1 if x_diff < 0 else 1
            self.flipped = x_diff > 0
            self.walking = MUSHROOM_SPEED

    @override
    def get_state(self) -> str:
        if self.is_attacking:
            if self.animation_states[self.current_state].finished:
                self.is_attacking = False
                return "idle"
            return "attack"
        if self.stun_time != 0:
            return "stunned"
        if self.walking:
            return "run"
        return "idle"

    @override
    def update_physics(self, dt: float):
        res = self.runner.move_grounded(self, None, None, dt)
        self.handle_target()
        if not res.on_ground:
            self.vy = min(self.vy + self.gravity * dt, self.max_fall_speed)
        else:
            self.vy = 0

        if self.stun_time == 0:
            self.handle_movement_x(res, dt)
            self.walking = max(self.walking - 1, 0)
        else:
            self.stun_time = max(self.stun_time - dt, 0)
