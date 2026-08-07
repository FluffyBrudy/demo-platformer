# Mist / fog field work — problem & journey

Temp notes: what the problem was, why we ended up here, and what we learned.

## The problem

The platformer runs on `tilemap-parser`, whose particle system was built around the
spawn → live → die pipeline. That model is great for two of the three things games need:

- **burst** — fire an explosion once (`emit_burst`)
- **emitter** — steady streams of short-lived particles (rain, embers, smoke) via `spawn_rate`

But we wanted **mist**: a permanent atmosphere layer that just _exists_ and moves. Forcing
fog through `spawn_rate` produces the worst of both worlds: thousands of birth/death
events per minute, and every birth is an alpha "pop" — the classic "I can tell it's
particles" tell. The pipeline had no concept of a persistent, pre-filled field, so the
game had to fight the API.

## The journey

### 1. `wrap` mode (parser)

The core fix: particles with `wrap=True` never die — exiting the emission area
toroidally re-enters on the opposite side, exact offset preserved. Combined with
`spawn_rate=0` + a one-time fill burst, fog becomes "fill once, then only move".
Nothing is born, nothing dies. Verified: count perfectly stable, no alpha pops,
max per-frame alpha delta at fixed pixels ≤ ~3 over 300 frames.

### 2. Three layered fields (game)

One field reads flat and uniform. Three parallel fields — far (largest, slowest,
faintest), mid (main volume), near (smallest, fastest, ground band) — read as depth.
Near layer emitted only over the lower 65% of the screen. Tuned counts: 120/160/150.

### 3. Streak artifact (game)

Wrap preserves each sheet's y-offset forever, so same-speed sheets drift as coherent
rows/vertical wisps. First fix: a game-side sine "wobble" (per-sheet phase drift).
Later measurement showed the layered speed spread alone decorrelates the field (and
the wobble's measured benefit was partly seed noise) — the wobble was removed.

### 4. The unbounded-progress bug (parser)

Under wrap, `life` keeps ticking past zero, so `progress` grew forever → sheet sizes
ballooned ~5× in a long session (and FPS degraded). Fixed by clamping `progress` to
[0, 1]: sizes now grow once (0.9 → 1.2×) and plateau.

### 5. 60 FPS + the white-screen bug (game)

Mist was the dominant render cost (~15 ms of ~21 ms). Fix: draw all layers at
`zoom=0.5` into a half-resolution buffer, then upscale once → ~13 ms render, solid 60.
Output is pixel-identical (fog's linear falloff round-trips exactly through bilinear
scaling).
White screen on the first attempt: `pygame.transform.smoothscale(src, size, dest)`
corrupts the alpha channel on display surfaces (opaque fog everywhere). Fix: scale to
a new surface, then a normal alpha blit.

### 6. The API gap (parser)

The field pattern existed but was invisible: webdocs never mentioned `wrap`, and its
performance advice actively recommended the expensive path. Density required manual
count math (count × size² / area). So we shipped:

- `ParticleSystemConfig.count_for_coverage(coverage, w, h)` — density as a
  dimensionless number; shape-aware fill area (circle emitters use their disc)
- `ParticleSystem.emit_field(coverage, x, y, w, h)` — fill once; validates the
  field contract (wrap + spawn_rate=0) and errors naming the exact fields to fix
- Webdocs: "Persistent fields" + "Layered fields" sections with the depth rule
  table and a copy-paste layered-fog recipe; `examples/particles/src/field.py`
- Perlin noise discussed for drift quality — deferred (game-side follow-up, not
  engine machinery, per AGENTS.txt)

### 7. Game migrated to the recipe (game + parser bug found)

Game's `_load_mist` rewritten to mirror the docs recipe: one shared base config,
per-layer overrides of only size/speed/alpha/coverage, wobble dropped.
The migration instantly exposed a real parser bug: `from_dict` clamped `spawn_rate`
to ≥ 1, destroying `spawn_rate=0` on config roundtrip — the docs recipe would have
broken for anyone. Fixed (`max(0, ...)`) with a regression test.

## Where we landed

- Game: 3 layers, wrap fields, coverage-driven density (4.4 / 2.67 / 1.85 → 120/160/150
  sheets), half-res rendering, 60 FPS, no birth/death, max frame alpha delta ~2-4.
- Parser: `wrap`, `fog` shape, `fade_peak_alpha`, `count_for_coverage` / `fill_area` /
  `emit_field`, spawn_rate-0 roundtrip fixed; 565 tests pass.
- Docs: three-mode mental model (burst / emitter / field) + layered fog recipe.

## Key lessons

- Continuous media is a third particle mode, not a spawn-rate variant. Birth/death
  churn is a feature for rain, a bug for fog.
- Layer first, wobble later: speed/size spread across layers does most of the
  structure-dissolving work at config level.
- Roundtrip (to_dict/from_dict) is a real API contract — clamps and defaults there
  silently break valid configs.
- Measure before trusting a "fix": the wobble's measured benefit was partly seed noise.
- `smoothscale(src, size, dest)` on display surfaces = broken alpha; always scale +
  blit.

code:

```python
import sys

import pygame
from tilemap_parser import (
    Camera,
    CollisionRunner,
    ParticleSystem,
    ParticleSystemConfig,
    PhysicsWorld,
    TileLayerRenderer,
    TilemapData,
    load_map,
    load_tileset_collision,
)

from src.entity.player import Player
from src.settings import MAPS_PATH, TILESET_COLLISION_PATH


class Game:
    WIDTH = 1280
    HEIGHT = 720
    FPS = 60
    TITLE = "Pygame"
    BG_COLOR = (30, 30, 30)

    def __init__(self) -> None:
        self.running = True
        self._init()
        self._init_game()
        self.load_world()

    def _init(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption(self.TITLE)
        self.clock = pygame.time.Clock()

    def _init_game(self):
        self.camera = Camera(*self.screen.get_size(), "deadzone")
        self.player = Player(100, 150)

        self.camera.follow(self.player)

    def load_world(self):
        map_data = load_map(MAPS_PATH / "1.json")
        collision_tileset = load_tileset_collision(TILESET_COLLISION_PATH / "tiles.collision.json")
        if collision_tileset is None:
            raise ValueError("Unable to load collision tileset")

        world = PhysicsWorld.from_map(map_data, collision_tileset, use_gids=True)
        self.runner = CollisionRunner.from_world(world, game_type="platformer")
        self.renderer = TileLayerRenderer(map_data)

        self._load_mist(map_data)

    def _load_mist(self, map_data: TilemapData):
        node = next(node for node in map_data.particle_emitters if node.name == "mist")
        # Shared base config (webdocs "layered fog" recipe); each layer is a
        # copy that differs only in size, speed, alpha and coverage.
        base = ParticleSystemConfig.from_dict(node.config.to_dict(), name="mist")
        base.particle_shape = "fog"  # flat soft square: tiles like a haze sheet
        base.emission_shape = "rect"
        base.wrap = True  # never spawn/die: the field already exists, it moves
        base.spawn_rate = 0  # filled once below, then immortal
        base.speed_min, base.speed_max = 6.0, 10.0  # overwritten per layer
        base.direction = 0  # wind blows right
        base.spread = 30  # slight vertical wander around the wind
        base.gravity_x, base.gravity_y = 0.0, 0.0
        base.start_color_r, base.start_color_g, base.start_color_b = 200, 50, 80
        base.end_color_r, base.end_color_g, base.end_color_b = 190, 30, 70
        base.alpha_fade = "none"  # constant alpha: no pops, ever
        base.start_scale, base.end_scale = 0.9, 1.2  # slow growth, low contrast
        base.max_particles = 500  # headroom cap; emit_field clamps to this
        base.lifetime_min, base.lifetime_max = 60, 120  # unused while wrap=True
        base.rotation_speed = 0.0  # no effect on "fog" (symmetric shape)

        # Screen-space emitters: padded so sheets leave the visible screen
        # before they wrap.
        mist_rect = pygame.Rect(-160, -90, self.WIDTH + 320, self.HEIGHT + 180)
        ground_rect = pygame.Rect(-160, int(self.HEIGHT * 0.35), self.WIDTH + 320, int(self.HEIGHT * 0.65) + 90)

        # (name, size_min, size_max, speed_min, speed_max, alpha, coverage, rect)
        # Coverage = density dial; tuned so counts land at 120/160/150.
        layers = [
            ("far", 90, 140, 3.0, 6.0, 10, 4.4, mist_rect),
            ("mid", 60, 95, 5.0, 9.0, 16, 2.67, mist_rect),
            ("near", 40, 65, 8.0, 14.0, 10, 1.85, ground_rect),
        ]

        self.mist_layers: list[tuple[ParticleSystem, pygame.Rect]] = []
        # Fog is a soft blur anyway: render at half resolution and upscale,
        # so 430 large sheet blits cost a quarter of their full-res area.
        self._mist_buffer = pygame.Surface((self.WIDTH // 2, self.HEIGHT // 2), pygame.SRCALPHA)
        for name, size_min, size_max, speed_min, speed_max, alpha, coverage, rect in layers:
            cfg = ParticleSystemConfig.from_dict(base.to_dict(), name=name)
            cfg.particle_size_min, cfg.particle_size_max = size_min, size_max
            cfg.speed_min, cfg.speed_max = speed_min, speed_max
            cfg.start_color_a = cfg.end_color_a = alpha
            # apply render scale BEFORE anything spawns
            cfg.apply_render_scale(map_data.render_scale)
            # construct + fill the field once (density from coverage)
            system = ParticleSystem(cfg)
            system.emit_field(coverage, *rect)
            self.mist_layers.append((system, rect))

    def handle_event(self) -> None:
        self.player_movement = 0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

    def update(self, dt: float) -> None:
        self.player.update(dt)
        self.runner.move_platformer(
            self.player, None, None, dt, self.player.input_x, jump_pressed=self.player.jump_triggered
        )
        for system, rect in self.mist_layers:
            system.update(dt, *rect)

    def render(self) -> None:
        self.screen.fill((0, 0, 0))
        self.renderer.render(self.screen, self.camera.offset)
        self.player.render(self.screen, self.camera.offset)
        self._mist_buffer.fill((0, 0, 0, 0))
        for system, _rect in self.mist_layers:
            system.draw(self._mist_buffer, 0, 0, 0.5)
        # Two-step scale+blit: smoothscale(src, size, dest) corrupts alpha
        # on display surfaces (opaque fog everywhere), so scale to a new
        # surface and let a normal alpha blit composite it.
        scaled = pygame.transform.smoothscale(self._mist_buffer, self.screen.get_size())
        self.screen.blit(scaled, (0, 0))
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
```
