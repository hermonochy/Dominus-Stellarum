from . import config

bottom_bar_height: float = float(config.BOTTOM_BAR_HEIGHT)
bar_dragging: bool = False


def clamp_bar_height(value: float, screen_height: int) -> float:
    max_height = screen_height * 0.45
    return max(
        float(config.BOTTOM_BAR_MIN_HEIGHT),
        min(max_height, value),
    )