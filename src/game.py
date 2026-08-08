import sys

import pygame

from src.settings import MAPS_PATH
from src.shared.signals import dashorb
from src.world import World


class Game:
    WIDTH = 1280
    HEIGHT = 720
    FPS = 60
    TITLE = "Pygame"
    BG = (46, 62, 48)

    def __init__(self) -> None:
        self.running = True
        self._init()
        self.world = World(MAPS_PATH / "1.json", self.WIDTH, self.HEIGHT)
        dashorb.connect(self.world.consume_particles)

    def _init(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption(self.TITLE)
        self.clock = pygame.time.Clock()

    def handle_event(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

    def render(self) -> None:
        self.screen.fill(self.BG)
        self.world.render(self.screen)
        pygame.display.flip()

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(self.FPS) / 1000.0
            self.handle_event()
            self.world.update(dt)
            self.render()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()
