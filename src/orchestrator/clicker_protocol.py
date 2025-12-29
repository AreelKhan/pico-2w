from __future__ import annotations

import base64


def encode_bins(bins: list[int]) -> str:
    n = len(bins)
    nbytes = (n + 7) // 8
    buf = bytearray(nbytes)
    for i, b in enumerate(bins):
        if b:
            byte_i = i // 8
            bit = 7 - (i % 8)
            buf[byte_i] |= 1 << bit
    return base64.b64encode(bytes(buf)).decode("ascii")


def expected_run_seconds(*, n_bins: int, bin_ms: int) -> float:
    return (n_bins * bin_ms) / 1000.0
