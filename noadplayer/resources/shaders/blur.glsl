// NoAdPlayer 블러 — 가우시안, 가로·세로 두 번에 나눠 처리.

//!PARAM noad_blur
//!TYPE float
//!MINIMUM 0.1
//!MAXIMUM 8.0
1.0

//!HOOK SCALED
//!BIND HOOKED
//!DESC NoAd blur (horizontal)
vec4 hook() {
    int r = int(ceil(noad_blur * 3.0));
    vec4 sum = vec4(0.0);
    float wsum = 0.0;
    for (int i = -r; i <= r; i++) {
        float w = exp(-float(i * i) / (2.0 * noad_blur * noad_blur));
        sum += HOOKED_tex(HOOKED_pos + vec2(float(i) * HOOKED_pt.x, 0.0)) * w;
        wsum += w;
    }
    return sum / wsum;
}

//!HOOK SCALED
//!BIND HOOKED
//!DESC NoAd blur (vertical)
vec4 hook() {
    int r = int(ceil(noad_blur * 3.0));
    vec4 sum = vec4(0.0);
    float wsum = 0.0;
    for (int i = -r; i <= r; i++) {
        float w = exp(-float(i * i) / (2.0 * noad_blur * noad_blur));
        sum += HOOKED_tex(HOOKED_pos + vec2(0.0, float(i) * HOOKED_pt.y)) * w;
        wsum += w;
    }
    return sum / wsum;
}
