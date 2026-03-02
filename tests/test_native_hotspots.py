from qa_snapshot_native import compress_payload, frame_sha1, smallest_hit, sort_rects_by_area


def test_frame_sha1_is_deterministic():
    data = b"quantum-hotspot-test"
    assert frame_sha1(data) == frame_sha1(data)


def test_compress_payload_roundtrip_shape():
    data = (b"abc123" * 2000)
    compressed = compress_payload(data)
    assert isinstance(compressed, bytes)
    assert len(compressed) > 0
    assert len(compressed) < len(data)


def test_smallest_hit_selects_most_specific_rect():
    rects = [
        ((0, 0, 100, 100), "root"),
        ((10, 10, 40, 40), "container"),
        ((20, 20, 10, 10), "leaf"),
    ]
    assert smallest_hit(rects, 25, 25) == "leaf"
    assert smallest_hit(rects, 12, 12) == "container"
    assert smallest_hit(rects, 101, 101) is None


def test_sort_rects_by_area_orders_small_to_large():
    rects = [
        ((0, 0, 50, 50), "a"),
        ((0, 0, 10, 10), "b"),
        ((0, 0, 30, 30), "c"),
    ]
    ordered = sort_rects_by_area(rects)
    assert [item[1] for item in ordered] == ["b", "c", "a"]
