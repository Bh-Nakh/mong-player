// NoAdPlayer 샤프닝 — 언샤프 마스크 (3x3 가우시안과의 차이를 더함).

//!PARAM noad_sharpen
//!TYPE float
//!MINIMUM 0.0
//!MAXIMUM 3.0
0.5

//!HOOK SCALED
//!BIND HOOKED
//!DESC NoAd sharpen
vec4 hook() {
    vec4 c = HOOKED_tex(HOOKED_pos);
    vec2 d = HOOKED_pt;
    vec4 b = c * 4.0
           + (HOOKED_tex(HOOKED_pos + vec2(d.x, 0.0)) + HOOKED_tex(HOOKED_pos - vec2(d.x, 0.0))
            + HOOKED_tex(HOOKED_pos + vec2(0.0, d.y)) + HOOKED_tex(HOOKED_pos - vec2(0.0, d.y))) * 2.0
           + HOOKED_tex(HOOKED_pos + d) + HOOKED_tex(HOOKED_pos - d)
           + HOOKED_tex(HOOKED_pos + vec2(d.x, -d.y)) + HOOKED_tex(HOOKED_pos - vec2(d.x, -d.y));
    b /= 16.0;
    return clamp(c + (c - b) * noad_sharpen, 0.0, 1.0);
}
