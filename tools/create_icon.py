from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    size = 1024
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((32, 32, 992, 992), radius=210, fill="#153F35")
    draw.rounded_rectangle((232, 174, 792, 850), radius=56, outline="#F3F1EA", width=64)
    draw.line((512, 206, 512, 818), fill="#F3F1EA", width=44)
    draw.rounded_rectangle((430, 302, 594, 720), radius=32, fill="#D97A32")
    draw.ellipse((530, 486, 566, 522), fill="#153F35")

    output = Path(__file__).resolve().parents[1] / "assets" / "PantaGateChecker.ico"
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(
        output,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Created {output}")


if __name__ == "__main__":
    main()