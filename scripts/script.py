import re
from pathlib import Path

from PIL import Image


def extract_number(path: Path) -> float:
    """Extracts the first sequence of digits from a filename for natural sorting."""
    match = re.search(r"\d+", path.name)
    return int(match.group()) if match else float("inf")


def make_spritesheets(entity_path: Path) -> Image.Image:
    """
    Packs an entire entity (e.g. player) into a single master sprite sheet.
    Each action directory represents a distinct row.
    """
    if not entity_path.exists():
        raise FileNotFoundError(f"{entity_path} does not exist")

    img_container = []
    cols = 0

    for action_dir in sorted(entity_path.iterdir()):
        if not action_dir.is_dir():
            continue

        valid_files = []

        for file in action_dir.iterdir():
            if file.is_file() and file.suffix.lower() == ".png":
                valid_files.append(file)
            elif file.is_dir():
                for sub_file in file.iterdir():
                    if sub_file.is_file() and sub_file.suffix.lower() == ".png":
                        valid_files.append(sub_file)

        if not valid_files:
            continue

        valid_files.sort(key=extract_number)

        sub_container = [Image.open(f) for f in valid_files]

        cols = max(len(sub_container), cols)
        img_container.append(sub_container)

    if not img_container:
        raise ValueError(f"No valid action directories containing PNGs found in {entity_path}")

    rows = len(img_container)

    w, h = img_container[0][0].size

    blank_canvas = Image.new("RGBA", (w * cols, h * rows), (0, 0, 0, 0))

    for r_idx, row_images in enumerate(img_container):
        for c_idx, img in enumerate(row_images):
            x = c_idx * w
            y = r_idx * h
            rgba_img = img.convert("RGBA")
            blank_canvas.paste(rgba_img, (x, y), rgba_img)

    return blank_canvas


if __name__ == "__main__":
    player_dir = Path("assets/data/images/entities/player")
    master_sheet = make_spritesheets(player_dir)

    master_sheet.save(f"{player_dir.stem}_sheet.png")
    print(f"Generated single sheet: {master_sheet.width}x{master_sheet.height}")
