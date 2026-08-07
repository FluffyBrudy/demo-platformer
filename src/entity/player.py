from typing import Literal, no_type_check

import pygame
from pygame import Surface
from tilemap_parser import (
    AnimationPlayer,
    CollisionRunner,
    ICollidableSprite,
    SpriteAnimationSet,
    load_character_collision,
)

from src.settings import ANIMATION_PATH, CHARACTER_COLLISION_PATH

INPUT_DELAY_THRESHOLD = 0.15

RUN_SPEED = 150.0
GROUND_ACCEL = 2200.0
GROUND_DECEL = 2600.0
AIR_ACCEL = 1000.0


def move_toward(current: float, target: float, by: float) -> float:
    if current < target:
        return min(current + by, target)
    return max(current - by, target)


TPlayerStates = Literal["idle", "jump", "run", "slide", "wallslide"]


class Player(ICollidableSprite):
    collision_path = CHARACTER_COLLISION_PATH / "player.collision.json"
    animation_path = ANIMATION_PATH / "player.anim.json"

    @no_type_check
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.on_ground = False
        self.collision_shape = load_character_collision(self.collision_path).shape

        self.jump_triggered = False
        self.input_x = 0
        self.prev_input = 0
        self.flipped = False

        sprite_animation_set = SpriteAnimationSet.load(self.animation_path)
        self.animation_states: dict[TPlayerStates, AnimationPlayer] = {
            "idle": AnimationPlayer(sprite_animation_set, "idle"),
            "jump": AnimationPlayer(sprite_animation_set, "jump"),
            "run": AnimationPlayer(sprite_animation_set, "run"),
            "slide": AnimationPlayer(sprite_animation_set, "slide"),
            "wallslide": AnimationPlayer(sprite_animation_set, "wallslide"),
        }
        self.current_state: TPlayerStates = "idle"

    def trigger_jump(self):
        self.jump_triggered: bool = True

    def update(self, dt: float, runner: CollisionRunner):
        keys = pygame.key.get_pressed()
        movement_x = keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]
        self.jump_triggered = False

        if keys[pygame.K_SPACE]:
            self.jump_triggered = True
        if movement_x:
            if movement_x < 0:
                self.flipped = True
            else:
                self.flipped = False
            self.input_x = movement_x * (0.5 if self.vy > 0.01 else 1)
        else:
            self.input_x = 0

        if self.jump_triggered and self.on_ground:
            self.vy = runner.jump_strength
        if not self.on_ground:
            self.vy = min(self.vy + runner.gravity * dt, runner.max_fall_speed)

        accel = GROUND_ACCEL if self.on_ground else AIR_ACCEL
        if self.input_x:
            self.vx = move_toward(self.vx, self.input_x * RUN_SPEED, accel * dt)
        else:
            decel = GROUND_DECEL if self.on_ground else AIR_ACCEL
            self.vx = move_toward(self.vx, 0.0, decel * dt)
        state = self.get_state()
        if self.current_state != state:
            self.current_state = state
            self.animation_states[state].reset()
        self.animation_states[self.current_state].update(dt * 1000)

    def get_state(self) -> TPlayerStates:
        if not self.on_ground:
            return "jump"
        if abs(self.vx) > 0.001:
            return "run"
        return "idle"

    def buffer_input(self, dt: float):
        pass

    def render(self, surface: Surface, offset: tuple[float, float]):
        current_frame = self.animation_states[self.current_state].get_current_image()
        if current_frame is None:
            return

        if self.flipped:
            current_frame = pygame.transform.flip(current_frame, True, False)
        surface.blit(current_frame, (self.x - offset[0], self.y - offset[1]))
