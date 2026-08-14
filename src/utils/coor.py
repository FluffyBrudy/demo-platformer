import pygame
from pygame.typing import RectLike


def align_bottom_right(dest: RectLike, src_size: tuple[int, int]) -> tuple[int, int]:
    dest_rect = pygame.Rect(dest)
    return (
        dest_rect.right - src_size[0],
        dest_rect.bottom - src_size[1],
    )
