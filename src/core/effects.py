from typing import TypedDict

from tilemap_parser import ParticleSystem


class ParticleConsumer(TypedDict):
    x: float
    y: float
    name: str


class ParticleConsumerPartial(ParticleConsumer, total=False):
    count: int
    direction: float
    width: int
    height: int
    offset: tuple[int, int]


def particle_consumer(
    particle_lookup: dict[str, ParticleSystem],
    config: ParticleConsumerPartial,
):
    """This is mutable, ensure that direction is always included whoever consumes"""
    x = config["x"]
    y = config["y"]
    name = config["name"]
    count = config.get("count", 5)
    direction = config.get("direction", 0.0)
    width = config.get("width", 1)
    height = config.get("height", 1)

    particle_lookup[name].config.direction = direction
    particle_lookup[name].emit_burst(count, x, y, width, height)
