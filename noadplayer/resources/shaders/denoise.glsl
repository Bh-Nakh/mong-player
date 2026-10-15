// NoAdPlayer 노이즈 제거 — 5x5 양방향(bilateral) 필터. 화면 크기로 늘린 뒤(SCALED) 처리.

//!PARAM noad_denoise
//!TYPE float
//!MINIMUM 0.0
//!MAXIMUM 0.5
0.08

//!HOOK SCALED
//!BIND HOOKED
//!DESC NoAd denoise
vec4 hook() {
    vec4 c = HOOKED_tex(HOOKED_pos);
    vec4 sum = vec4(0.0);
    float wsum = 0.0;
    float inv_r = 1.0 / max(noad_denoise * noad_denoise, 1e-6);
    for (int y = -2; y <= 2; y++) {
        for (int x = -2; x <= 2; x++) {
            vec4 s = HOOKED_tex(HOOKED_pos + vec2(x, y) * HOOKED_pt);
            vec3 d = s.rgb - c.rgb;
            float w = exp(-float(x * x + y * y) / 4.5 - dot(d, d) * inv_r);
            sum += s * w;
            wsum += w;
        }
    }
    return sum / wsum;
}
