from collections.abc import Callable
from random import choice, randint, random
from typing import Literal, override

from tilemap_parser import (
    AnimationPlayer,
    CollisionResult,
    CollisionRunner,
    ICollidableSprite,
    SpriteAnimationSet,
    load_character_collision,
)

from src.core.effects import ParticleConsumerPartial
from src.entity.base import CollidableAnimationEntity
from src.settings import ANIMATION_PATH, CHARACTER_COLLISION_PATH

TMushroomStates = Literal["idle", "run", "attack", "attack_with_stun", "hurt", "dead", "stunned"]


MUSHROOM_SPEED = 100
MUSHROOM_GRAVITY = 800
MUSHROOM_MAX_FALL_SPEED = 600
TARGET_CHASE_RANGE = 200

GroundCheck = Callable[["Mushroom"], bool]


class Mushroom(CollidableAnimationEntity):
    collision_path = CHARACTER_COLLISION_PATH / "mushroom.collision.json"
    animation_path = ANIMATION_PATH / "mushroom.anim.json"

    def __init__(
        self,
        x: float,
        y: float,
        runner: CollisionRunner,
        ground_check: GroundCheck,
        emit: Callable[[ParticleConsumerPartial], None],
        target: CollidableAnimationEntity | None = None,
    ) -> None:
        self.x, self.y = x, y
        self.vx, self.vy = choice([1, -1]) * 150, 0
        self.on_ground = False
        self.collision_shape = load_character_collision(self.collision_path).shape  # pyright: ignore
        self.runner = runner
        self.ground_check = ground_check
        self.emit = emit

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

        self.flipped = True
        self.walking = 0
        self.direction = -1
        self.stun_time = 0

        self.target = target

    @property
    def size(self) -> tuple[int, int]:
        frame = self.animation_states[self.current_state].get_current_image()
        if frame is None:
            raise TypeError("Unable to load frame size")
        return frame.size

    def can_stun(self):
        return self.stun_time == 0 and self.current_state != "stunned"

    def stun(self):
        self.stun_time = 2
        self.current_state = "stunned"
        self.vx = 0

    @override
    def get_state(self) -> TMushroomStates:
        if self.stun_time != 0:
            return "stunned"
        if self.walking:
            return "run"
        return "idle"

    def handle_target(self):
        if self.target is None:
            return
        tl, tt, tr, tb = self.target.shape_aabb
        sl, st, sr, sb = self.shape_aabb
        x_diff = (tl + tr) * 0.5 - (sl + sr) * 0.5
        if abs(x_diff) < TARGET_CHASE_RANGE:
            if abs(self.target.y - self.y) > max(tb - tt, sb - st):
                return
            if not self.ground_check(self):
                self.walking = 0
                return
            self.direction = -1 if x_diff < 0 else 1
            self.flipped = x_diff > 0
            self.walking = MUSHROOM_SPEED

    def handle_movement_x(self, res: CollisionResult, _dt: float):
        if not self.walking:
            if random() < 0.01:
                self.walking = randint(int(MUSHROOM_SPEED * 0.8), MUSHROOM_SPEED)
            else:
                self.vx = 0
                return
        if res.hit_wall_x or (self.on_ground and not self.ground_check(self)):
            self.direction = -self.direction
            self.flipped = not self.flipped
        self.vx = self.direction * MUSHROOM_SPEED

    @override
    def update_physics(self, dt: float):
        res = self.runner.move_grounded(self, None, None, dt)
        self.handle_target()
        if not res.on_ground:
            self.vy = min(self.vy + MUSHROOM_GRAVITY * dt, MUSHROOM_MAX_FALL_SPEED)
        else:
            self.vy = 0

        if self.stun_time == 0:
            self.handle_movement_x(res, dt)
            self.walking = max(self.walking - 1, 0)
        else:
            self.stun_time = max(self.stun_time - dt, 0)
