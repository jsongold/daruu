"""Tests for candidate_filter module.

TDD: these tests are written FIRST, before the implementation.
"""

import pytest

from app.services.vision_autofill.candidate_filter import (
    CandidateLabel,
    FieldWithCandidates,
    compute_distance_score,
    estimate_page_sizes,
    filter_candidates,
    to_ivb,
)


class TestToIvb:
    def test_to_ivb_basic(self):
        """A4サイズ(595x842)での基本変換"""
        assert to_ivb([0, 0, 595, 842], 595, 842) == (0, 0, 999, 999)
        assert to_ivb([297.5, 421, 0, 0], 595, 842) == (499, 499, 499, 499)

    def test_to_ivb_clamp(self):
        """はみ出し座標のクランプ"""
        assert to_ivb([-10, -10, 605, 852], 595, 842)[0] == 0

    def test_to_ivb_zero_dimensions(self):
        """幅・高さゼロのbboxでもクラッシュしない"""
        result = to_ivb([100, 100, 0, 0], 595, 842)
        assert len(result) == 4
        assert all(0 <= v <= 999 for v in result)

    def test_to_ivb_full_page(self):
        """ページ全体をカバーするbbox"""
        result = to_ivb([0, 0, 612, 792], 612, 792)
        assert result == (0, 0, 999, 999)


class TestComputeDistanceScore:
    def test_direction_left(self):
        """ラベルがフィールドの左にある場合"""
        score, direction = compute_distance_score(
            [200, 100, 150, 20],  # field
            [50, 100, 100, 15],  # label (左にある)
        )
        assert direction == "left"

    def test_direction_above(self):
        """ラベルがフィールドの上にある場合"""
        score, direction = compute_distance_score(
            [100, 200, 150, 20],  # field
            [100, 160, 100, 15],  # label (上にある)
        )
        assert direction == "above"

    def test_direction_right(self):
        """ラベルがフィールドの右にある場合"""
        score, direction = compute_distance_score(
            [50, 100, 100, 20],  # field
            [200, 100, 100, 15],  # label (右にある)
        )
        assert direction == "right"

    def test_direction_below(self):
        """ラベルがフィールドの下にある場合"""
        score, direction = compute_distance_score(
            [100, 100, 150, 20],  # field
            [100, 200, 100, 15],  # label (下にある)
        )
        assert direction == "below"

    def test_direction_overlap(self):
        """ラベルとフィールドが重なっている場合"""
        score, direction = compute_distance_score(
            [100, 100, 150, 20],  # field
            [120, 105, 100, 15],  # label (重なっている)
        )
        assert direction == "overlap"

    def test_vertical_alignment_bonus(self):
        """同じ行にあるラベルが優先される"""
        score_aligned, _ = compute_distance_score(
            [200, 100, 150, 20],  # field
            [50, 102, 100, 15],  # label (ほぼ同じy座標)
        )
        score_offset, _ = compute_distance_score(
            [200, 100, 150, 20],  # field
            [50, 60, 100, 15],  # label (y座標がずれている)
        )
        assert score_aligned < score_offset

    def test_left_preferred_over_right(self):
        """同距離の場合、左ラベルの方が右ラベルよりスコアが低い(=優先)"""
        score_left, dir_left = compute_distance_score(
            [300, 100, 100, 20],
            [150, 100, 100, 20],  # left
        )
        score_right, dir_right = compute_distance_score(
            [300, 100, 100, 20],
            [450, 100, 100, 20],  # right (same distance)
        )
        assert dir_left == "left"
        assert dir_right == "right"
        assert score_left < score_right

    def test_score_is_positive(self):
        """スコアは常に正の値"""
        score, _ = compute_distance_score(
            [200, 100, 150, 20],
            [50, 100, 100, 15],
        )
        assert score > 0


class TestEstimatePageSizes:
    def test_estimate_page_sizes_a4(self):
        """A4サイズの推定"""
        fields = [{"id": "Text1", "t": "text", "p": 1, "b": [500, 800, 80, 20]}]
        blocks = [{"s": "test", "p": 1, "b": [10, 10, 50, 15]}]
        sizes = estimate_page_sizes(fields, blocks)
        assert sizes[1] == (595, 842)

    def test_estimate_page_sizes_letter(self):
        """Letterサイズの推定"""
        fields = [{"id": "Text1", "t": "text", "p": 1, "b": [550, 750, 50, 30]}]
        blocks = [{"s": "test", "p": 1, "b": [10, 10, 50, 15]}]
        sizes = estimate_page_sizes(fields, blocks)
        assert sizes[1] == (612, 792)

    def test_estimate_page_sizes_unknown(self):
        """不明サイズ: max + 10%マージン"""
        fields = [{"id": "Text1", "t": "text", "p": 1, "b": [0, 0, 100, 100]}]
        blocks = []
        sizes = estimate_page_sizes(fields, blocks)
        w, h = sizes[1]
        assert w == 100 * 1.1
        assert h == 100 * 1.1

    def test_estimate_multi_page(self):
        """複数ページの推定"""
        fields = [
            {"id": "Text1", "t": "text", "p": 1, "b": [500, 800, 80, 20]},
            {"id": "Text2", "t": "text", "p": 2, "b": [550, 750, 50, 30]},
        ]
        blocks = []
        sizes = estimate_page_sizes(fields, blocks)
        assert 1 in sizes
        assert 2 in sizes


class TestFilterCandidates:
    def test_filter_returns_correct_count(self):
        """top_k=5の場合、最大5件の候補が返る"""
        fields = [{"id": "Text1", "t": "text", "p": 1, "b": [200, 100, 150, 20]}]
        blocks = [
            {"s": f"label{i}", "p": 1, "b": [50 + i * 20, 100, 40, 15]}
            for i in range(20)
        ]
        result = filter_candidates(fields, blocks, top_k=5)
        assert len(result) == 1
        assert len(result[0].candidates) == 5

    def test_filter_same_page_only(self):
        """異なるページのテキストブロックは候補に含まれない"""
        fields = [{"id": "Text1", "t": "text", "p": 1, "b": [200, 100, 150, 20]}]
        blocks = [
            {"s": "同ページ", "p": 1, "b": [50, 100, 60, 15]},
            {"s": "別ページ", "p": 2, "b": [50, 100, 60, 15]},
        ]
        result = filter_candidates(fields, blocks, top_k=5)
        assert len(result[0].candidates) == 1
        assert result[0].candidates[0].text == "同ページ"

    def test_filter_returns_field_with_candidates_type(self):
        """戻り値の型がFieldWithCandidatesであること"""
        fields = [{"id": "Text1", "t": "text", "p": 1, "b": [200, 100, 150, 20]}]
        blocks = [{"s": "label", "p": 1, "b": [50, 100, 60, 15]}]
        result = filter_candidates(fields, blocks)
        assert isinstance(result[0], FieldWithCandidates)
        assert isinstance(result[0].candidates[0], CandidateLabel)

    def test_filter_sorted_by_score(self):
        """候補はスコア昇順でソートされている"""
        fields = [{"id": "Text1", "t": "text", "p": 1, "b": [200, 100, 150, 20]}]
        blocks = [
            {"s": "near", "p": 1, "b": [150, 100, 40, 15]},
            {"s": "far", "p": 1, "b": [10, 10, 40, 15]},
        ]
        result = filter_candidates(fields, blocks, top_k=5)
        scores = [c.distance_score for c in result[0].candidates]
        assert scores == sorted(scores)

    def test_filter_default_top_k(self):
        """デフォルトtop_k=7"""
        fields = [{"id": "Text1", "t": "text", "p": 1, "b": [200, 100, 150, 20]}]
        blocks = [
            {"s": f"label{i}", "p": 1, "b": [50 + i * 20, 100, 40, 15]}
            for i in range(20)
        ]
        result = filter_candidates(fields, blocks)
        assert len(result[0].candidates) == 7

    def test_filter_with_provided_page_sizes(self):
        """page_sizesを明示的に渡した場合"""
        fields = [{"id": "Text1", "t": "text", "p": 1, "b": [200, 100, 150, 20]}]
        blocks = [{"s": "label", "p": 1, "b": [50, 100, 60, 15]}]
        page_sizes = {1: (595.0, 842.0)}
        result = filter_candidates(fields, blocks, page_sizes=page_sizes)
        assert len(result) == 1

    def test_filter_empty_blocks(self):
        """テキストブロックが空の場合、候補は空リスト"""
        fields = [{"id": "Text1", "t": "text", "p": 1, "b": [200, 100, 150, 20]}]
        result = filter_candidates(fields, [], top_k=5)
        assert len(result) == 1
        assert len(result[0].candidates) == 0

    def test_filter_ivb_coords_in_range(self):
        """候補のIVB座標が0-999の範囲内"""
        fields = [{"id": "Text1", "t": "text", "p": 1, "b": [200, 100, 150, 20]}]
        blocks = [{"s": "label", "p": 1, "b": [50, 100, 60, 15]}]
        result = filter_candidates(fields, blocks)
        for candidate in result[0].candidates:
            for v in candidate.bbox_ivb:
                assert 0 <= v <= 999
        for v in result[0].bbox_ivb:
            assert 0 <= v <= 999
