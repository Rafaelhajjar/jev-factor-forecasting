"""Linear-algebra validation, not evidence of forecasting accuracy."""

import numpy as np
import pytest

from jev_factor.pca_basis_audit import compare_rotations


def test_sign_alignment_recovers_identical_ordered_basis():
    q, _ = np.linalg.qr(np.random.default_rng(45).normal(size=(9, 3)))
    basis = q.T
    r = np.array([-1, 1, -1])[:, None] * basis
    result = compare_rotations(basis, r)
    assert result["same_up_to_component_signs"]
    assert result["same_retained_subspace"]
    assert result["signs_to_align_R_with_Python"] == [-1, 1, -1]


def test_degenerate_subspace_rotation_is_not_mislabeled_a_sign_flip():
    basis = np.eye(3)[:2]
    rotation = np.array([[0.8, -0.6], [0.6, 0.8]])
    result = compare_rotations(basis, rotation @ basis)
    assert result["same_retained_subspace"]
    assert not result["same_up_to_component_signs"]
    assert result["signs_to_align_R_with_Python"] is None


def test_different_retained_subspace_is_detected():
    result = compare_rotations(np.eye(3)[:2], np.eye(3)[[0, 2]])
    assert not result["same_retained_subspace"]
    assert not result["same_up_to_component_signs"]


@pytest.mark.parametrize("candidate", [np.ones(3), np.eye(3) * 2, np.eye(3) * np.nan])
def test_invalid_rotation_is_rejected(candidate):
    with pytest.raises(ValueError):
        compare_rotations(np.eye(3), candidate)
