"""Draws the postcard. You never need to edit this file.

Makes three files for each permit you render:
  <name>-front.png   the picture side
  <name>-back.png    the message-and-address side
  <name>.pdf         both sides, one page each, at print size

Nothing here talks to the internet and nothing is mailed. These are
pictures you look at.
"""

import os

from PIL import Image, ImageDraw, ImageFont

DPI = 300                       # print resolution
MARGIN_IN = 0.25                # safe margin from the trim edge, inches

# Ubuntu's standard fonts, which is what GitHub's runners have.
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def load_font(size: int, bold: bool = False):
    """Get a font at the size we want, or fall back to a plain one."""
    path = FONT_BOLD if bold else FONT_REGULAR
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def hex_to_rgb(value: str, fallback=(31, 78, 121)) -> tuple:
    """Turn '#1F4E79' into the numbers Pillow wants."""
    text = str(value or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    if len(text) != 6:
        return fallback
    try:
        return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return fallback


def parse_size(value: str) -> tuple:
    """Turn '6x4' into pixel width and height at print resolution."""
    try:
        wide, tall = str(value).lower().split("x")
        wide, tall = float(wide), float(tall)
    except (ValueError, AttributeError):
        wide, tall = 6.0, 4.0
    # Keep it inside sane postcard territory.
    wide = min(max(wide, 3.0), 12.0)
    tall = min(max(tall, 3.0), 12.0)
    return int(wide * DPI), int(tall * DPI)


def wrap(draw, text: str, font, max_width: int, max_lines: int = 99) -> list:
    """Break text into lines that fit the width we have."""
    words = str(text or "").split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
            if len(lines) == max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    # If we ran out of room, show that there was more.
    if len(lines) == max_lines and len(" ".join(lines)) < len(str(text or "")):
        lines[-1] = lines[-1].rstrip(",.;: ") + "..."
    return lines


def fit_font(draw, text: str, max_width: int, start_size: int, bold=False):
    """Shrink a font until the text fits on one line. Never truncates."""
    size = start_size
    while size > 8:
        font = load_font(size, bold)
        if draw.textlength(str(text or ""), font=font) <= max_width:
            return font
        size -= 2
    return load_font(8, bold)


def fit_block(draw, text, max_width, start_size, max_lines, bold=False):
    """Shrink a font until the text fits in the number of lines we allow.

    Company names in this trade get long ("...Residential Technology
    Systems of Greater Richmond"). Smaller type beats an ellipsis when
    the words are somebody's actual business name.
    """
    size = start_size
    while size > 10:
        font = load_font(size, bold)
        if len(wrap(draw, text, font, max_width, 99)) <= max_lines:
            return font
        size -= 2
    return load_font(10, bold)


def block_height(draw, text, font, max_width, line_gap=1.35, max_lines=99):
    """How tall this text will be once wrapped, so we can centre it."""
    lines = wrap(draw, text, font, max_width, max_lines)
    return len(lines) * int(font.size * line_gap)


def draw_block(draw, text, font, box, fill, line_gap=1.35, max_lines=99):
    """Write wrapped text into a box. Returns the y we finished at."""
    left, top, right = box
    lines = wrap(draw, text, font, right - left, max_lines)
    line_height = int(font.size * line_gap)
    for i, line in enumerate(lines):
        draw.text((left, top + i * line_height), line, font=font, fill=fill)
    return top + len(lines) * line_height


def paste_logo(card, logo_path, box):
    """Drop the logo into a box, keeping its shape. True if it worked."""
    left, top, max_w, max_h = box
    if not logo_path or not os.path.exists(logo_path):
        return False
    try:
        logo = Image.open(logo_path)
    except Exception:
        return False

    logo = logo.convert("RGBA")
    scale = min(max_w / logo.width, max_h / logo.height)
    if scale <= 0:
        return False
    new_size = (max(1, int(logo.width * scale)), max(1, int(logo.height * scale)))
    logo = logo.resize(new_size, Image.LANCZOS)
    # Centre it inside the space it was given.
    offset = (int(left + (max_w - logo.width) / 2),
              int(top + (max_h - logo.height) / 2))
    card.paste(logo, offset, logo)
    return True


def render_front(pick, company, accent, size, logo_path):
    """The picture side: your brand, and why this card showed up."""
    width, height = size
    margin = int(MARGIN_IN * DPI)
    card = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(card)

    # A band of colour across the top, with the logo sitting on it.
    band_height = int(height * 0.34)
    draw.rectangle([0, 0, width, band_height], fill=accent)

    logo_box = (margin, int(margin * 0.8),
                width - 2 * margin, band_height - int(margin * 1.6))
    if not paste_logo(card, logo_path, logo_box):
        name_font = fit_block(draw, company.get("name", ""),
                              width - 2 * margin, int(height * 0.075), 2,
                              bold=True)
        lines = wrap(draw, company.get("name", ""), name_font,
                     width - 2 * margin, 2)
        y = int((band_height - len(lines) * name_font.size * 1.25) / 2)
        for line in lines:
            line_w = draw.textlength(line, font=name_font)
            draw.text(((width - line_w) / 2, y), line,
                      font=name_font, fill="white")
            y += int(name_font.size * 1.25)

    # Work out how tall the middle block is, then centre it in the space
    # between the colour band and the footer, so a short message from
    # Claude doesn't leave a hole in the card.
    text_width = width - 2 * margin
    headline_font = fit_block(draw, pick.get("headline", "A project near you"),
                              text_width, int(height * 0.062), 2, bold=True)
    body_font = load_font(int(height * 0.036))
    rule_gap = int(margin * 1.1) + 6

    head_h = block_height(draw, pick.get("headline", "A project near you"),
                          headline_font, text_width, 1.2, 2)
    body_h = block_height(draw, pick.get("front_message", ""), body_font,
                          text_width, 1.4, 3)

    # Reserve the footer: company name, then the details line under it.
    name_font = fit_font(draw, company.get("name", ""), text_width,
                         int(height * 0.036), bold=True)
    details = "  ".join(bit for bit in (
        company.get("tagline", ""), company.get("phone", ""),
        company.get("website", "")) if bit)
    detail_font = fit_font(draw, details, text_width, int(height * 0.028))
    footer_h = int(name_font.size * 1.35) + int(detail_font.size * 1.3)
    footer_top = height - margin - footer_h

    area_top, area_bottom = band_height, footer_top
    total = head_h + rule_gap + body_h
    y = max(area_top + int(margin * 0.6),
            area_top + int((area_bottom - area_top - total) / 2))

    y = draw_block(draw, pick.get("headline", "A project near you"),
                   headline_font, (margin, y, width - margin),
                   (25, 25, 25), 1.2, max_lines=2)
    y += int(margin * 0.5)
    draw.line([(margin, y), (width - margin, y)], fill=accent, width=6)
    y += int(margin * 0.6)
    draw_block(draw, pick.get("front_message", ""), body_font,
               (margin, y, width - margin), (60, 60, 60), 1.4, max_lines=3)

    # Footer: who this is from. Both lines are shrunk to fit rather than
    # cut off, because a truncated phone number is worse than small type.
    draw.text((margin, footer_top), company.get("name", ""),
              font=name_font, fill=accent)
    if details:
        draw.text((margin, footer_top + int(name_font.size * 1.35)),
                  details, font=detail_font, fill=(120, 120, 120))
    return card


def render_back(pick, company, services, accent, size, permit):
    """The message-and-address side, laid out like a real postcard."""
    width, height = size
    margin = int(MARGIN_IN * DPI)
    card = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(card)

    split = int(width * 0.52)          # message left, address right
    draw.line([(split, margin), (split, height - margin)],
              fill=(205, 205, 205), width=3)

    # ---- left: the pitch --------------------------------------------
    left = margin
    right = split - int(margin * 0.7)
    y = margin

    head_font = load_font(int(height * 0.040), bold=True)
    y = draw_block(draw, pick.get("back_headline", "About your project"),
                   head_font, (left, y, right), accent, 1.25, max_lines=2)
    y += int(margin * 0.35)

    body_font = load_font(int(height * 0.030))
    y = draw_block(draw, pick.get("back_message", ""), body_font,
                   (left, y, right), (45, 45, 45), 1.45, max_lines=9)
    y += int(margin * 0.45)

    # A few of the services, so the card says what we actually do.
    if services:
        small = load_font(int(height * 0.026))
        for service in services[:4]:
            if y > height - margin - small.size * 3:
                break
            draw.ellipse([left + 4, y + small.size * 0.35,
                          left + 14, y + small.size * 0.35 + 10], fill=accent)
            # Two lines per bullet: a service cut off mid-word reads as
            # a bug on a card meant to look printed.
            y = draw_block(draw, service, small,
                           (left + 28, y, right), (70, 70, 70), 1.3,
                           max_lines=2)
            y += int(small.size * 0.35)

    # ---- right: stamp, address, source ------------------------------
    rx = split + int(margin * 0.7)

    stamp_w, stamp_h = int(width * 0.10), int(height * 0.15)
    stamp_x = width - margin - stamp_w
    draw.rectangle([stamp_x, margin, stamp_x + stamp_w, margin + stamp_h],
                   outline=(180, 180, 180), width=3)
    stamp_font = load_font(int(height * 0.019))
    draw.text((stamp_x + 12, margin + stamp_h / 2 - stamp_font.size),
              "PLACE\nSTAMP", font=stamp_font, fill=(170, 170, 170))

    # Return address, small, top left of the right half.
    ret_font = load_font(int(height * 0.023))
    ret = [company.get("name", ""), company.get("location", ""),
           company.get("website", "")]
    ry = margin
    for line in [r for r in ret if r]:
        got = wrap(draw, line, ret_font, stamp_x - rx - 20, 1)
        if got:
            draw.text((rx, ry), got[0], font=ret_font, fill=(120, 120, 120))
        ry += int(ret_font.size * 1.35)

    # The recipient block, where a real mailer would print the address.
    addr_font = load_font(int(height * 0.032), bold=True)
    addr_y = int(height * 0.52)
    draw.text((rx, addr_y - int(addr_font.size * 1.6)), "CURRENT RESIDENT",
              font=load_font(int(height * 0.024)), fill=(150, 150, 150))
    # Lay it out the way an address actually reads: street on its own
    # line, then the city/zip line under it.
    street = permit.get("street") or permit.get("address") or "Address not stated"
    locality = " ".join(bit for bit in (permit.get("city", ""),
                                        permit.get("zip", "")) if bit)
    ay = draw_block(draw, street, addr_font, (rx, addr_y, width - margin),
                    (25, 25, 25), 1.3, max_lines=2)
    if locality:
        draw.text((rx, ay + 6), locality, font=addr_font, fill=(25, 25, 25))

    # Provenance, so the room can see where this came from.
    note_font = load_font(int(height * 0.020))
    note = f"Permit filed {permit.get('date') or 'date not stated'}"
    if permit.get("place"):
        note += f" - {permit['place']}"
    draw.text((rx, height - margin - note_font.size), note,
              font=note_font, fill=(160, 160, 160))

    # PREVIEW stripe, so nobody mistakes this for something that mailed.
    tag_font = load_font(int(height * 0.022), bold=True)
    tag = "PREVIEW ONLY - NOT MAILED"
    tag_w = draw.textlength(tag, font=tag_font)
    draw.rectangle([left - 6, height - margin - tag_font.size - 8,
                    left + tag_w + 14, height - margin + 8],
                   fill=(240, 240, 240))
    draw.text((left + 4, height - margin - tag_font.size - 2), tag,
              font=tag_font, fill=(150, 150, 150))
    return card


def render(pick, permit, config, out_dir, stem):
    """Draw both sides and save the PNGs and the PDF. Returns the paths."""
    settings = config.get("postcard") or {}
    company = config.get("company") or {}
    accent = hex_to_rgb(settings.get("accent_color"))
    size = parse_size(settings.get("size", "6x4"))

    os.makedirs(out_dir, exist_ok=True)
    front = render_front(pick, company, accent, size,
                         config.get("logo_path"))
    back = render_back(pick, company, config.get("services") or [],
                       accent, size, permit)

    front_path = os.path.join(out_dir, f"{stem}-front.png")
    back_path = os.path.join(out_dir, f"{stem}-back.png")
    pdf_path = os.path.join(out_dir, f"{stem}.pdf")

    front.save(front_path, "PNG", dpi=(DPI, DPI))
    back.save(back_path, "PNG", dpi=(DPI, DPI))
    front.save(pdf_path, "PDF", resolution=DPI, save_all=True,
               append_images=[back])
    return front_path, back_path, pdf_path
