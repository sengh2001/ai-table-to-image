from PIL import Image, ImageDraw, ImageFont
import textwrap
from typing import List, Optional, Tuple

# You can change font path to a system TTF or include a font file in the project.
try:
    DEFAULT_FONT = ImageFont.truetype("DejaVuSans.ttf", 14)
    HEADER_FONT = ImageFont.truetype("DejaVuSans-Bold.ttf", 16)
except IOError:
    DEFAULT_FONT = ImageFont.load_default()
    HEADER_FONT = DEFAULT_FONT

CELL_PADDING = 8
LINE_WIDTH = 1
ROW_HEIGHT_MIN = 28

def measure_text(text: str, font: ImageFont.ImageFont, max_width: int) -> Tuple[List[str], int]:
    """Wrap text into lines that fit max_width and return wrapped lines and height."""
    words = text.split()
    if not words:
        bbox = font.getbbox("Ag")
        height = bbox[3] - bbox[1]
        return [""], height

    def text_width(s: str) -> int:
        bbox = font.getbbox(s)
        return bbox[2] - bbox[0]

    def text_height(s: str) -> int:
        bbox = font.getbbox(s)
        return bbox[3] - bbox[1]

    lines = []
    line = ""
    for w in words:
        test = (line + " " + w).strip()
        w_width = text_width(test)
        if w_width + 2 * CELL_PADDING > max_width and line:
            lines.append(line)
            line = w
        else:
            line = test
    if line:
        lines.append(line)

    height = len(lines) * text_height("Ag") + 2 * CELL_PADDING
    return lines, height


def render_table_image(columns: List[str], rows: List[List[Optional[str]]], title: Optional[str]=None, max_width: int=1200) -> Image.Image:
    """
    Render a simple table to a PIL Image and return it.
    - columns: list of column header strings
    - rows: list of rows (each row is list of cell strings or None)
    """
    n_cols = max(1, len(columns))
    # Estimate column widths (equal distribution initially)
    col_width = max_width // n_cols
    # Measure header heights
    header_heights = []
    for col in columns:
        _, h = measure_text(col or "", HEADER_FONT, col_width)
        header_heights.append(h)
    header_height = max(header_heights) + 2

    # Measure each row height
    row_heights = []
    for r in rows:
        cell_heights = []
        for i, cell in enumerate(r):
            text = "" if cell is None else str(cell)
            _, h = measure_text(text, DEFAULT_FONT, col_width)
            cell_heights.append(max(h, ROW_HEIGHT_MIN))
        row_heights.append(max(cell_heights))

    # Title height
    title_height = 0
    if title:
        title_lines, th = measure_text(title, HEADER_FONT, max_width)
        title_height = th + 12

    total_height = title_height + header_height + sum(row_heights) + (len(rows)+2) * LINE_WIDTH + 20

    img = Image.new("RGB", (max_width, total_height), "white")
    draw = ImageDraw.Draw(img)

    y = 10
    if title:
        draw.text((10, y), title, font=HEADER_FONT, fill="black")
        y += title_height

    # draw header background
    draw.rectangle([0, y, max_width, y + header_height], fill=(245,245,245))
    # draw header text
    x = 0
    for i, col in enumerate(columns):
        left = x + CELL_PADDING
        top = y + CELL_PADDING
        # wrap header
        lines, _ = measure_text(col or "", HEADER_FONT, col_width)
        line_y = top
        for ln in lines:
            draw.text((left, line_y), ln, font=HEADER_FONT, fill="black")
            bbox = HEADER_FONT.getbbox("Ag")
            line_y += bbox[3] - bbox[1]

        # vertical grid line
        draw.line([x + col_width, y, x + col_width, total_height], fill="black", width=LINE_WIDTH)
        x += col_width
    # bottom of header
    y += header_height
    draw.line([0, y, max_width, y], fill="black", width=LINE_WIDTH)

    # draw rows
    for r_idx, row in enumerate(rows):
        x = 0
        row_h = row_heights[r_idx]
        for c_idx in range(n_cols):
            cell_text = ""
            if c_idx < len(row):
                cell_text = "" if row[c_idx] is None else str(row[c_idx])
            left = x + CELL_PADDING
            top = y + CELL_PADDING
            lines, _ = measure_text(cell_text, DEFAULT_FONT, col_width)
            line_y = top
            for ln in lines:
                draw.text((left, line_y), ln, font=DEFAULT_FONT, fill="black")
                lbbox = DEFAULT_FONT.getbbox("Ag")
                line_y += bbox[3] - bbox[1]

            # vertical line
            draw.line([x + col_width, y, x + col_width, y + row_h], fill="black", width=LINE_WIDTH)
            x += col_width
        # row bottom line
        draw.line([0, y + row_h, max_width, y + row_h], fill="black", width=LINE_WIDTH)
        y += row_h

    return img
