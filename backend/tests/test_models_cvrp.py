"""Validation on the CVRP request model."""

import pytest
from pydantic import ValidationError

from app.models.cvrp import WASTE_TYPES, CVRPRequest


def test_defaults():
    request = CVRPRequest()
    assert request.waste_type == "DI"
    assert request.load_unit == "kg"
    assert request.n_vehicles == 5
    assert request.edge_modifications == []


@pytest.mark.parametrize("waste_type", WASTE_TYPES)
def test_every_waste_type_is_accepted(waste_type):
    assert CVRPRequest(waste_type=waste_type).waste_type == waste_type


@pytest.mark.parametrize(
    "kwargs",
    [
        {"waste_type": "XX"},
        {"load_unit": "tonnes"},
        {"n_vehicles": 0},
        {"n_vehicles": 51},
        {"max_runtime": 121},
        {"waste_per_centroid": 0},
    ],
)
def test_bad_values_are_rejected(kwargs):
    with pytest.raises(ValidationError):
        CVRPRequest(**kwargs)
