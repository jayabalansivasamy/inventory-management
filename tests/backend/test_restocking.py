"""
Tests for restocking API endpoints.
"""
from datetime import datetime

import pytest


class TestRestockingRecommendations:
    """Test suite for the restocking recommendations endpoint."""

    def test_get_recommendations_returns_200_and_shape(self, client):
        """Test getting recommendations returns the expected response shape."""
        response = client.get("/api/restocking/recommendations?budget=5000")
        assert response.status_code == 200

        data = response.json()
        assert "budget" in data
        assert "total_cost" in data
        assert "remaining_budget" in data
        assert "items" in data
        assert isinstance(data["items"], list)

        if data["items"]:
            first_item = data["items"][0]
            for field in [
                "sku", "item_name", "category", "warehouse", "quantity_on_hand",
                "reorder_point", "forecasted_demand", "trend", "recommended_quantity",
                "unit_cost", "line_total", "urgency_score", "urgency_reason"
            ]:
                assert field in first_item

    def test_recommendations_respect_budget_cap(self, client):
        """Test that total cost never exceeds the given budget."""
        for budget in [0, 500, 5000, 100000]:
            response = client.get(f"/api/restocking/recommendations?budget={budget}")
            assert response.status_code == 200

            data = response.json()
            assert data["total_cost"] <= budget + 0.01

    def test_recommendations_zero_budget_returns_empty(self, client):
        """Test that a zero budget produces no recommendations."""
        response = client.get("/api/restocking/recommendations?budget=0")
        assert response.status_code == 200

        data = response.json()
        assert data["items"] == []
        assert data["total_cost"] == 0

    def test_recommendations_higher_budget_includes_more_or_equal_items(self, client):
        """Test that a higher budget never recommends fewer items."""
        low_response = client.get("/api/restocking/recommendations?budget=1000")
        high_response = client.get("/api/restocking/recommendations?budget=100000")

        low_count = len(low_response.json()["items"])
        high_count = len(high_response.json()["items"])

        assert high_count >= low_count

    def test_recommendations_items_sorted_by_urgency_desc(self, client):
        """Test that recommended items are sorted by urgency score descending."""
        response = client.get("/api/restocking/recommendations?budget=100000")
        data = response.json()

        scores = [item["urgency_score"] for item in data["items"]]
        assert scores == sorted(scores, reverse=True)

    def test_recommendations_quantity_never_exceeds_forecast_gap(self, client):
        """Test that recommended quantity never exceeds the forecast gap."""
        response = client.get("/api/restocking/recommendations?budget=100000")
        data = response.json()

        for item in data["items"]:
            forecast_gap = item["forecasted_demand"] - item["quantity_on_hand"]
            assert item["recommended_quantity"] <= max(0, forecast_gap)

    def test_missing_budget_param_returns_422(self, client):
        """Test that omitting the required budget param returns a validation error."""
        response = client.get("/api/restocking/recommendations")
        assert response.status_code == 422

    def test_negative_budget_rejected(self, client):
        """Test that a negative budget is rejected."""
        response = client.get("/api/restocking/recommendations?budget=-100")
        assert response.status_code == 422


class TestCreateRestockingOrder:
    """Test suite for submitting a restocking order."""

    def test_create_order_returns_201_and_shape(self, client):
        """Test creating an order returns the expected response shape."""
        response = client.post("/api/restocking/orders", json={"budget": 5000})
        assert response.status_code == 201

        data = response.json()
        for field in [
            "id", "order_number", "supplier_name", "items", "item_count",
            "total_cost", "budget_requested", "order_date", "lead_time_days",
            "expected_delivery_date", "status"
        ]:
            assert field in data

        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0
        assert data["item_count"] == len(data["items"])
        assert data["status"] == "Processing"

    def test_create_order_lead_time_in_expected_range(self, client):
        """Test that the generated lead time is within the expected 5-14 day range."""
        response = client.post("/api/restocking/orders", json={"budget": 5000})
        data = response.json()

        assert 5 <= data["lead_time_days"] <= 14

    def test_create_order_expected_delivery_matches_lead_time(self, client):
        """Test that expected_delivery_date equals order_date plus lead_time_days."""
        response = client.post("/api/restocking/orders", json={"budget": 5000})
        data = response.json()

        order_date = datetime.fromisoformat(data["order_date"])
        expected_delivery = datetime.fromisoformat(data["expected_delivery_date"])

        assert (expected_delivery - order_date).days == data["lead_time_days"]

    def test_create_order_persists_to_list(self, client):
        """Test that a created order appears in the submitted orders list."""
        create_response = client.post("/api/restocking/orders", json={"budget": 5000})
        created_order = create_response.json()

        list_response = client.get("/api/restocking/orders")
        order_ids = [order["id"] for order in list_response.json()]

        assert created_order["id"] in order_ids

    def test_create_order_zero_budget_returns_400(self, client):
        """Test that a zero budget is rejected when placing an order."""
        response = client.post("/api/restocking/orders", json={"budget": 0})
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data

    def test_create_order_total_cost_matches_items_sum(self, client):
        """Test that total_cost equals the sum of each item's line total."""
        response = client.post("/api/restocking/orders", json={"budget": 5000})
        data = response.json()

        calculated_total = sum(item["line_total"] for item in data["items"])
        assert abs(data["total_cost"] - calculated_total) < 0.01


class TestGetRestockingOrders:
    """Test suite for listing submitted restocking orders."""

    def test_get_orders_returns_200_and_list(self, client):
        """Test getting all restocking orders."""
        response = client.get("/api/restocking/orders")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_orders_includes_previously_created_order(self, client):
        """Test that a newly created order is included in the orders list."""
        create_response = client.post("/api/restocking/orders", json={"budget": 5000})
        created_order = create_response.json()

        list_response = client.get("/api/restocking/orders")
        order_numbers = [order["order_number"] for order in list_response.json()]

        assert created_order["order_number"] in order_numbers
