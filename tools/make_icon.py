"""앱 아이콘 생성 → noadplayer/resources/icon.ico, icon.png (Pillow 필요)."""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "noadplayer", "resources")
S = 1024                                     # 크게 그린 뒤 줄여서 계단 현상 제거


def draw():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    top, bottom = (92, 70, 230), (40, 24, 120)
    for y in range(S):
        t = y / (S - 1)
        gd.line([(0, y), (S, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([40, 40, S - 40, S - 40], radius=220, fill=255)
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)
    d.polygon([(330, 250), (330, 774), (780, 512)], fill=(255, 255, 255, 255))   # 재생 삼각형

    cx, cy, r = 760, 760, 190                                                    # 광고 금지 표시
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 255))
    d.ellipse([cx - r + 22, cy - r + 22, cx + r - 22, cy + r - 22], fill=(232, 52, 64, 255))
    try:
        font = ImageFont.truetype("arialbd.ttf", 150)
    except OSError:
        font = ImageFont.load_default()
    d.text((cx, cy + 4), "AD", font=font, fill=(255, 255, 255, 255), anchor="mm")
    off = int(r * 0.62)
    d.line([(cx - off, cy - off), (cx + off, cy + off)], fill=(255, 255, 255, 255), width=40)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    img = draw()
    img.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT, "icon.png"))
    img.save(os.path.join(OUT, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                                                   (128, 128), (256, 256)])
    print("완료:", OUT)


if __name__ == "__main__":
    main()
