"""
Tests for purchase order API endpoints.

Note: Backlog item IDs are partitioned across tests (one id per test) since
purchase orders are stored in a shared in-memory list for the whole test
session and each backlog item may only have one purchase order.
"""
import pytest


class TestCreatePurchaseOrder:
    """Test suite for creating purchase orders."""

    def test_create_purchase_order_returns_201_and_shape(self, client):
        """Test creating a purchase order returns the expected response shape."""
        response = client.post("/api/purchase-orders", json={
            "backlog_item_id": "1",
            "supplier_name": "Acme Industrial Supply",
            "quantity": 350,
            "unit_cost": 12.5,
            "expected_delivery_date": "2025-11-01",
            "notes": "Rush order"
        })
        assert response.status_code == 201

        data = response.json()
        for field in [
            "id", "backlog_item_id", "supplier_name", "quantity", "unit_cost",
            "expected_delivery_date", "status", "created_date", "notes"
        ]:
            assert field in data

        assert data["backlog_item_id"] == "1"
        assert data["supplier_name"] == "Acme Industrial Supply"
        assert data["quantity"] == 350
        assert data["status"] == "Pending"

    def test_create_purchase_order_without_notes_succeeds(self, client):
        """Test that notes is optional when creating a purchase order."""
        response = client.post("/api/purchase-orders", json={
            "backlog_item_id": "2",
            "supplier_name": "Global Parts Co.",
            "quantity": 10,
            "unit_cost": 450.0,
            "expected_delivery_date": "2025-11-05"
        })
        assert response.status_code == 201
        assert response.json()["notes"] is None

    def test_create_purchase_order_for_nonexistent_backlog_item_returns_404(self, client):
        """Test that creating a PO for a nonexistent backlog item returns 404."""
        response = client.post("/api/purchase-orders", json={
            "backlog_item_id": "nonexistent-item-999",
            "supplier_name": "Pioneer Manufacturing",
            "quantity": 50,
            "unit_cost": 20.0,
            "expected_delivery_date": "2025-11-10"
        })
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_create_duplicate_purchase_order_returns_400(self, client):
        """Test that a backlog item cannot have more than one purchase order."""
        first_response = client.post("/api/purchase-orders", json={
            "backlog_item_id": "3",
            "supplier_name": "Northbridge Components",
            "quantity": 80,
            "unit_cost": 35.0,
            "expected_delivery_date": "2025-11-15"
        })
        assert first_response.status_code == 201

        second_response = client.post("/api/purchase-orders", json={
            "backlog_item_id": "3",
            "supplier_name": "Northbridge Components",
            "quantity": 80,
            "unit_cost": 35.0,
            "expected_delivery_date": "2025-11-15"
        })
        assert second_response.status_code == 400

        data = second_response.json()
        assert "detail" in data

    def test_create_purchase_order_missing_field_returns_422(self, client):
        """Test that omitting a required field returns a validation error."""
        response = client.post("/api/purchase-orders", json={
            "backlog_item_id": "4",
            "supplier_name": "Pioneer Manufacturing"
        })
        assert response.status_code == 422


class TestGetPurchaseOrderByBacklogItem:
    """Test suite for retrieving a purchase order by backlog item id."""

    def test_get_purchase_order_by_backlog_item_returns_200_and_shape(self, client):
        """Test retrieving a purchase order created for a backlog item."""
        create_response = client.post("/api/purchase-orders", json={
            "backlog_item_id": "4",
            "supplier_name": "Pioneer Manufacturing",
            "quantity": 175,
            "unit_cost": 8.75,
            "expected_delivery_date": "2025-11-20"
        })
        assert create_response.status_code == 201
        created_order = create_response.json()

        get_response = client.get("/api/purchase-orders/4")
        assert get_response.status_code == 200

        data = get_response.json()
        assert data["id"] == created_order["id"]
        assert data["backlog_item_id"] == "4"

    def test_get_purchase_order_for_item_without_po_returns_404(self, client):
        """Test that fetching a PO for a backlog item without one returns 404."""
        response = client.get("/api/purchase-orders/nonexistent-item-888")
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()
