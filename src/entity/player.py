from typing import Literal, override

import pygame
from tilemap_parser import (
    AnimationPlayer,
    SpriteAnimationSet,
    get_shape_aabb,
    load_character_collision,
)

from src.entity.base import CollidableAnimationEntity
from src.settings import ANIMATION_PATH, CHARACTER_COLLISION_PATH

RUN_SPEED = 150.0
GROUND_ACCEL = 2200.0
GROUND_DECEL = 2600.0
AIR_ACCEL = 1000.0
JUMP_STRENGTH = -400
MAX_FALL_SPEED = 600
GRAVITY = 800


def move_toward(current: float, target: float, by: float) -> float:
    if current < target:
        return min(current + by, target)
    return max(current - by, target)


TPlayerStates = Literal["idle", "jump", "run", "slide", "wallslide"]


class Player(CollidableAnimationEntity):
    collision_path = CHARACTER_COLLISION_PATH / "player.collision.json"
    animation_path = ANIMATION_PATH / "player.anim.json"
    blend_flags = pygame.BLEND_RGBA_MAX

    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.on_ground = False
        self.collision_shape = load_character_collision(self.collision_path).shape  # pyright: ignore
        self.shape_aabb = get_shape_aabb(self.x, self.y, self.collision_shape)

        self.input_x = 0
        self.flipped = False
        self.jump_triggered = False

        sprite_animation_set = SpriteAnimationSet.load(self.animation_path)
        self.animation_states: dict[str, AnimationPlayer] = {
            "idle": AnimationPlayer(sprite_animation_set, "idle"),
            "jump": AnimationPlayer(sprite_animation_set, "jump"),
            "run": AnimationPlayer(sprite_animation_set, "run"),
            "slide": AnimationPlayer(sprite_animation_set, "slide"),
            "wallslide": AnimationPlayer(sprite_animation_set, "wallslide"),
        }
        self.current_state = "idle"

    @override
    def update_physics(self, dt: float):
        keys = pygame.key.get_pressed()
        movement_x = keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]
        self.jump_triggered = keys[pygame.K_SPACE]
        if movement_x:
            self.flipped = movement_x < 0
            self.input_x = movement_x * (0.5 if self.vy > 0.01 else 1.0)
        else:
            self.input_x = 0.0

        self.vertical_movement(dt)
        self.horizontal_movement(dt)

    def vertical_movement(self, dt: float):
        _, t, r, b = self.shape_aabb
        if self.jump_triggered and self.on_ground:
            self.vy = JUMP_STRENGTH
            self.on_ground = False
            self.emit({"x": r, "y": (t + b) * 0.5, "name": "dashorb", "direction": -1, "count": 20})

        if not self.on_ground:
            self.vy = min(
                self.vy + GRAVITY * dt,
                MAX_FALL_SPEED,
            )

    def horizontal_movement(self, dt: float):
        target_vx = self.input_x * RUN_SPEED
        if self.input_x != 0:
            accel = GROUND_ACCEL if self.on_ground else AIR_ACCEL
            self.vx = move_toward(self.vx, target_vx, accel * dt)
        else:
            decel = GROUND_DECEL if self.on_ground else AIR_ACCEL
            self.vx = move_toward(self.vx, 0.0, decel * dt)

        l, _, r, b = self.shape_aabb
        if self.on_ground:
            if self.vx < 0:
                self.emit({"x": r, "y": b, "name": "dashorb", "direction": 0, "count": 1})
            elif self.vx > 0:
                self.emit({"x": l, "y": b, "name": "dashorb", "direction": 180, "count": 1})

    @override
    def get_state(self) -> TPlayerStates:
        if not self.on_ground:
            return "jump"
        if abs(self.vx) > 0.001:
            return "run"
        return "idle"
