from collections.abc import Callable
from typing import override

from tilemap_parser import AnimationPlayer, CollisionRunner, SpriteAnimationSet, load_character_collision

from src.core.effects import ParticleConsumerPartial
from src.entity.base import CollidableAnimationEntity
from src.entity.enemies.base import GroundCheck, HorizontalGroundedEnemy
from src.settings import ANIMATION_PATH, CHARACTER_COLLISION_PATH

MUSHROOM_SPEED = 100
MUSHROOM_GRAVITY = 800
MUSHROOM_MAX_FALL_SPEED = 600
TARGET_CHASE_RANGE = 200


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

        self.collision_shape = load_character_collision(self.collision_path).shape  # pyright: ignore

        sprite_animation_set = SpriteAnimationSet.load(self.animation_path)
        self.animation_states: dict[str, AnimationPlayer] = {
            "idle": AnimationPlayer(sprite_animation_set, "idle"),
            "attack": AnimationPlayer(sprite_animation_set, "attack"),
            "run": AnimationPlayer(sprite_animation_set, "run"),
            "attack_with_stun": AnimationPlayer(sprite_animation_set, "attack_with_stun"),
            "hurt": AnimationPlayer(sprite_animation_set, "hurt"),
            "dead": AnimationPlayer(sprite_animation_set, "dead"),
            "stunned": AnimationPlayer(sprite_animation_set, "stunned"),
        }
        self.current_state = "idle"

    def can_stun(self):
        return self.stun_time == 0 and self.current_state != "stunned"

    def stun(self):
        self.stun_time = 2
        self.current_state = "stunned"
        self.vx = 0

    @override
    def get_state(self) -> str:
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
