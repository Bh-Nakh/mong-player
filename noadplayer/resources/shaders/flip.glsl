// NoAdPlayer 반전 — noad_hflip / noad_vflip 이 1 이면 해당 방향으로 뒤집는다.

//!PARAM noad_hflip
//!TYPE float
//!MINIMUM 0.0
//!MAXIMUM 1.0
0.0

//!PARAM noad_vflip
//!TYPE float
//!MINIMUM 0.0
//!MAXIMUM 1.0
0.0

//!HOOK SCALED
//!BIND HOOKED
//!DESC NoAd flip
vec4 hook() {
    vec2 p = HOOKED_pos;
    if (noad_hflip > 0.5) p.x = 1.0 - p.x;
    if (noad_vflip > 0.5) p.y = 1.0 - p.y;
    return HOOKED_tex(p);
}
