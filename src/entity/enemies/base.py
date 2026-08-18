from abc import ABC
from collections.abc import Callable
from random import choice, randint, random

from tilemap_parser import CollisionResult, CollisionRunner
from tilemap_parser.runtime.collision import should_collide

from src.core.effects import ParticleConsumerPartial
from src.entity.base import CollidableAnimationEntity

GroundCheck = Callable[["HorizontalGroundedEnemy"], bool]


class HorizontalGroundedEnemy(CollidableAnimationEntity, ABC):
    speed: float
    gravity: float
    max_fall_speed: float
    target_chase_range: float

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
        self.runner = runner
        self.ground_check = ground_check
        self.emit = emit
        self.target = target

        self.flipped = True
        self.walking = 0
        self.direction = -1

    @property
    def size(self) -> tuple[int, int]:
        frame = self.animation_states[self.current_state].get_current_image()
        if frame is None:
            raise TypeError("Unable to load frame size")
        return frame.size

    def handle_movement_x(self, res: CollisionResult, _dt: float):
        if not self.walking:
            if random() < 0.01:
                self.walking = randint(int(self.speed * 0.8), int(self.speed))
            else:
                self.vx = 0
                return
        if res.hit_wall_x or (self.on_ground and not self.ground_check(self)):
            self.direction = -self.direction
            self.flipped = not self.flipped
        self.vx = self.direction * self.speed
