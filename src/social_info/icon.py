from PIL import Image, ImageDraw, ImageFont


def social_icon(size=64):
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((2, 2, size - 2, size - 2), radius=size // 4, fill="#e74c3c")
    try:
        font = ImageFont.truetype("arial.ttf", int(size * 0.62))
    except OSError:
        font = ImageFont.load_default()
    draw.text((size / 2, size / 2), "S", font=font, fill="white", anchor="mm")
    return image
