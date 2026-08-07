import sys

import pygame
from tilemap_parser import (
    Camera,
    CollisionRunner,
    PhysicsWorld,
    TileLayerRenderer,
    load_map,
    load_tileset_collision,
)

from src.core.effects import Spotlight
from src.entity.player import Player
from src.settings import MAPS_PATH, TILESET_COLLISION_PATH


class Game:
    WIDTH = 1280
    HEIGHT = 720
    FPS = 60
    TITLE = "Pygame"
    BG = (46, 62, 48)

    def __init__(self) -> None:
        self.running = True
        self._init()
        self.load_world()

        # intensity controls how dark our screen is
        self.spotlight = Spotlight(200, 0.1, self.WIDTH, self.HEIGHT, self.player)

    def _init(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption(self.TITLE)
        self.clock = pygame.time.Clock()

    def load_world(self):
        map_data = load_map(MAPS_PATH / "1.json")
        collision_tileset = load_tileset_collision(TILESET_COLLISION_PATH / "tiles.collision.json")
        if collision_tileset is None:
            raise ValueError("Unable to load collision tileset")

        world = PhysicsWorld.from_map(map_data, collision_tileset, use_gids=True)
        self.runner = CollisionRunner.from_world(world, game_type="platformer")
        self.runner.horizontal_speed = 150
        self.renderer = TileLayerRenderer(map_data)

        tile_w, tile_h = map_data.tile_size
        ccount, rcount = map_data.map_size
        r = map_data.render_scale
        self.camera = Camera(*self.screen.get_size())
        self.player = Player(100, 150)
        self.camera.bounds = (0, 0, tile_w * ccount * r, tile_h * rcount * r)  # pyright: ignore
        self.camera.follow(self.player)
        self.camera.lerp_speed = 5.0

    def handle_event(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

    def update(self, dt: float) -> None:
        self.camera.update(dt)
        self.player.update(dt, self.runner)
        self.runner.move_platformer(self.player, None, None, dt, velocity=(self.player.vx, self.player.vy))
        print(dt)

    def render(self) -> None:
        self.screen.fill(self.BG)
        self.renderer.render(self.screen, self.camera.offset)
        self.player.render(self.screen, self.camera.offset)
        self.spotlight.render(self.screen, self.camera.offset)
        pygame.display.flip()

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(self.FPS) / 1000.0
            self.handle_event()
            self.update(dt)
            self.render()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()
