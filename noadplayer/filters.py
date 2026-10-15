"""화질 필터 → mpv. 모두 GPU 에서 처리해 하드웨어 디코딩(nvdec 등)을 그대로 유지한다.

- 밝기·대비·채도·감마·색조, 회전: mpv 속성
- 샤프닝·블러·노이즈 제거·반전: 직접 작성한 GLSL 셰이더 (resources/shaders)
  FFmpeg 필터(CPU)를 쓰면 디코딩을 복사 모드로 바꿔야 하는데, 필터를 끈 뒤 mpv 가
  직접 디코딩(nvdec)으로 돌아오지 못하는 문제가 있어(2026-10-08 시험) 셰이더로 바꿨다.
"""
import os
from dataclasses import asdict, dataclass

from .paths import RESOURCES

SHADERS = os.path.join(RESOURCES, "shaders")
COLOR_KEYS = ("brightness", "contrast", "saturation", "gamma", "hue")
DENOISE_STRENGTH = {1: 0.04, 2: 0.08, 3: 0.14}


@dataclass
class Filters:
    brightness: int = 0      # -100 ~ 100
    contrast: int = 0
    saturation: int = 0
    gamma: int = 0
    hue: int = 0
    sharpen: int = 0         # 0 ~ 10
    blur: int = 0            # 0 ~ 10
    denoise: int = 0         # 0 끔, 1 약, 2 중, 3 강
    rotate: int = 0          # 0 / 90 / 180 / 270
    hflip: bool = False
    vflip: bool = False

    def shaders(self):
        """→ ([셰이더 파일], {옵션}) — 순서: 노이즈 제거 → 샤프닝 → 블러 → 반전"""
        files, opts = [], {}
        if self.denoise:
            files.append("denoise.glsl")
            opts["noad_denoise"] = DENOISE_STRENGTH[self.denoise]
        if self.sharpen:
            files.append("sharpen.glsl")
            opts["noad_sharpen"] = self.sharpen * 0.25
        if self.blur:
            files.append("blur.glsl")
            opts["noad_blur"] = self.blur * 0.5
        if self.hflip or self.vflip:
            files.append("flip.glsl")
            opts["noad_hflip"] = 1.0 if self.hflip else 0.0
            opts["noad_vflip"] = 1.0 if self.vflip else 0.0
        return [os.path.join(SHADERS, f) for f in files], opts

    def is_default(self):
        return self == Filters()

    def as_dict(self):
        return asdict(self)


def apply(player, f: Filters):
    for k in COLOR_KEYS:
        setattr(player, k, getattr(f, k))
    player.video_rotate = f.rotate
    files, opts = f.shaders()
    player.command("change-list", "glsl-shader-opts", "clr", "")
    for k, v in opts.items():
        player.command("change-list", "glsl-shader-opts", "add", f"{k}={v:g}")
    player.command("change-list", "glsl-shaders", "clr", "")
    for path in files:
        player.command("change-list", "glsl-shaders", "append", path)
