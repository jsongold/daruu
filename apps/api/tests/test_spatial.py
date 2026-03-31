"""Tests for spatial utility functions."""

from app.spatial import direction_score, is_decoration, score_to_confidence


class TestDirectionScore:
    def test_label_left_of_field(self):
        field = (0.5, 0.5, 0.1, 0.02)
        label = (0.3, 0.5, 0.1, 0.02)
        score, direction = direction_score(field, label)
        assert direction == "left"
        assert score > 0

    def test_label_above_field(self):
        field = (0.5, 0.5, 0.1, 0.02)
        label = (0.5, 0.3, 0.1, 0.02)
        score, direction = direction_score(field, label)
        assert direction == "above"
        assert score > 0

    def test_label_right_of_field(self):
        field = (0.3, 0.5, 0.1, 0.02)
        label = (0.5, 0.5, 0.1, 0.02)
        score, direction = direction_score(field, label)
        assert direction == "right"
        assert score > 0

    def test_label_below_field(self):
        field = (0.5, 0.3, 0.1, 0.02)
        label = (0.5, 0.5, 0.1, 0.02)
        score, direction = direction_score(field, label)
        assert direction == "below"
        assert score > 0

    def test_overlap(self):
        field = (0.5, 0.5, 0.1, 0.02)
        label = (0.55, 0.505, 0.05, 0.01)
        score, direction = direction_score(field, label)
        assert direction == "overlap"
        assert score == 0.0

    def test_left_scores_lower_than_right(self):
        field = (0.5, 0.5, 0.1, 0.02)
        label_left = (0.3, 0.5, 0.1, 0.02)
        label_right = (0.7, 0.5, 0.1, 0.02)
        score_left, _ = direction_score(field, label_left)
        score_right, _ = direction_score(field, label_right)
        assert score_left < score_right

    def test_same_row_alignment_bonus(self):
        field = (0.5, 0.5, 0.1, 0.02)
        label_aligned = (0.3, 0.5, 0.1, 0.02)
        label_offset = (0.3, 0.4, 0.1, 0.02)
        score_aligned, _ = direction_score(field, label_aligned)
        score_offset, _ = direction_score(field, label_offset)
        assert score_aligned < score_offset


class TestIsDecoration:
    def test_empty_string(self):
        assert is_decoration("") is True

    def test_whitespace_only(self):
        assert is_decoration("   ") is True

    def test_single_punctuation(self):
        assert is_decoration(".") is True
        assert is_decoration("-") is True
        assert is_decoration("*") is True

    def test_dots(self):
        assert is_decoration("...") is True
        assert is_decoration("....") is True

    def test_dashes(self):
        assert is_decoration("---") is True

    def test_underscores(self):
        assert is_decoration("___") is True

    def test_single_digit(self):
        assert is_decoration("1") is True
        assert is_decoration("99") is True

    def test_three_digits_not_decoration(self):
        assert is_decoration("123") is False

    def test_real_label(self):
        assert is_decoration("Name") is False
        assert is_decoration("Date of Birth") is False

    def test_short_label(self):
        assert is_decoration("No") is False
        assert is_decoration("ID") is False

    def test_cjk_label(self):
        assert is_decoration("氏名") is False


class TestScoreToConfidence:
    def test_overlap_returns_95(self):
        assert score_to_confidence(0.0) == 95

    def test_close_match_high_confidence(self):
        conf = score_to_confidence(0.05)
        assert 50 < conf <= 100

    def test_far_match_low_confidence(self):
        conf = score_to_confidence(0.5)
        assert conf < 10

    def test_very_far_returns_zero(self):
        conf = score_to_confidence(2.0)
        assert conf == 0

    def test_never_exceeds_100(self):
        assert score_to_confidence(-1.0) == 95

    def test_monotonically_decreasing(self):
        scores = [0.01, 0.05, 0.1, 0.2, 0.3, 0.5]
        confidences = [score_to_confidence(s) for s in scores]
        for i in range(len(confidences) - 1):
            assert confidences[i] >= confidences[i + 1]
