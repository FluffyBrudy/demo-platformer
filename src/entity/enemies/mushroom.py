from abc import abstractmethod
from random import choice, randint, random
from typing import Callable, Literal, cast

import pygame
from pygame.surface import Surface
from tilemap_parser import AnimationPlayer, CollisionResult, CollisionRunner, ICollidableSprite, SpriteAnimationSet

from src.settings import ANIMATION_PATH, CHARACTER_COLLISION_PATH
from src.shared.world_context import collision_cache

TMushroomStates = Literal["idle", "run", "attack", "attack_with_stun", "hurt", "dead", "stunned"]


MUSHROOM_SPEED = 100
MUSHROOM_GRAVITY = 800
MUSHROOM_MAX_FALL_SPEED = 600


class Mushroom(ICollidableSprite):
    collision_path = CHARACTER_COLLISION_PATH / "mushroom.collision.json"
    animation_path = ANIMATION_PATH / "mushroom.anim.json"
    check_ground_ahead: Callable[[ICollidableSprite, int], bool]
    runner: CollisionRunner

    def __init__(self, x: float, y: float, target: ICollidableSprite | None = None) -> None:
        if getattr(Mushroom, "check_ground_ahead", None) is None:
            raise ValueError("Initialize check_ground_ahead callback")
        if getattr(Mushroom, "runner", None) is None:
            raise ValueError("Initialize runner attribute")

        self.x, self.y = x, y
        self.vx, self.vy = choice([1, -1]) * 150, 0
        self.on_ground = False
        self.collision_shape = collision_cache.get_character_collision(self.collision_path).shape  # pyright: ignore

        sprite_animation_set = SpriteAnimationSet.load(self.animation_path)
        self.animation_states: dict[TMushroomStates, AnimationPlayer] = {
            "idle": AnimationPlayer(sprite_animation_set, "idle"),
            "attack": AnimationPlayer(sprite_animation_set, "attack"),
            "run": AnimationPlayer(sprite_animation_set, "run"),
            "attack_with_stun": AnimationPlayer(sprite_animation_set, "attack_with_stun"),
            "hurt": AnimationPlayer(sprite_animation_set, "hurt"),
            "dead": AnimationPlayer(sprite_animation_set, "dead"),
            "stunned": AnimationPlayer(sprite_animation_set, "stunned"),
        }
        self.current_state: TMushroomStates = "idle"

        self.flipped = True
        self.walking = 0
        self.direction = -1
        self.walking = 0

        self.stun_time = 0

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

    def get_state(self) -> TMushroomStates:
        if self.stun_time != 0:
            return "stunned"
        if self.walking:
            return "run"
        return "idle"

    def update_animation(self, dt: float):
        state = self.get_state()
        if self.current_state != state:
            self.current_state = state
            self.animation_states[state].reset()
        self.animation_states[self.current_state].update(dt * 1000)

    def handle_movement_x(self, res: CollisionResult, dt: float):
        if not self.walking:
            if random() < 0.01:
                self.walking = randint(int(MUSHROOM_SPEED * 0.8), MUSHROOM_SPEED)
            else:
                self.vx = 0
                return
        if res.hit_wall_x or (self.on_ground and not self.check_ground_ahead(self, self.direction)):
            self.direction = -self.direction
            self.flipped = not self.flipped
        self.vx = self.direction * MUSHROOM_SPEED

    def update(self, dt: float):
        res = self.runner.move_grounded(self, None, None, dt)

        if not res.on_ground:
            self.vy = min(self.vy + MUSHROOM_GRAVITY * dt, MUSHROOM_MAX_FALL_SPEED)
        else:
            self.vy = 0

        if self.stun_time == 0:
            self.handle_movement_x(res, dt)
            self.walking = max(self.walking - 1, 0)
        else:
            self.stun_time = max(self.stun_time - dt, 0)
        self.update_animation(dt)

    def render(self, surface: Surface, offset: tuple[float, float]):
        frame = self.animation_states[self.current_state].get_current_image()
        if frame is None:
            return
        if self.flipped:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (self.x - offset[0], self.y - offset[1]))
