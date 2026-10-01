"""
Tests for tasks API endpoints.
"""
import pytest


class TestTasksEndpoints:
    """Test suite for task-related endpoints."""

    def test_get_all_tasks_returns_200_and_list(self, client):
        """Test getting all tasks returns a list."""
        response = client.get("/api/tasks")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_task_returns_201_and_shape(self, client):
        """Test creating a task returns the expected response shape."""
        response = client.post("/api/tasks", json={
            "title": "Reorder circuit boards",
            "priority": "high",
            "dueDate": "2025-10-15"
        })
        assert response.status_code == 201

        data = response.json()
        for field in ["id", "title", "priority", "dueDate", "status"]:
            assert field in data

        assert data["title"] == "Reorder circuit boards"
        assert data["priority"] == "high"
        assert data["dueDate"] == "2025-10-15"
        assert data["status"] == "pending"

    def test_created_task_appears_in_list(self, client):
        """Test that a newly created task appears in the full task list."""
        create_response = client.post("/api/tasks", json={
            "title": "Follow up with supplier",
            "priority": "medium",
            "dueDate": "2025-11-01"
        })
        created_task = create_response.json()

        list_response = client.get("/api/tasks")
        task_ids = [task["id"] for task in list_response.json()]

        assert created_task["id"] in task_ids

    def test_create_task_missing_field_returns_422(self, client):
        """Test that omitting a required field returns a validation error."""
        response = client.post("/api/tasks", json={
            "title": "Missing priority and due date"
        })
        assert response.status_code == 422

    def test_toggle_task_status_marks_completed(self, client):
        """Test that toggling a pending task marks it completed."""
        create_response = client.post("/api/tasks", json={
            "title": "Audit warehouse stock",
            "priority": "low",
            "dueDate": "2025-12-01"
        })
        task_id = create_response.json()["id"]

        toggle_response = client.patch(f"/api/tasks/{task_id}")
        assert toggle_response.status_code == 200
        assert toggle_response.json()["status"] == "completed"

    def test_toggle_task_status_twice_returns_to_pending(self, client):
        """Test that toggling a completed task marks it pending again."""
        create_response = client.post("/api/tasks", json={
            "title": "Review supplier contracts",
            "priority": "medium",
            "dueDate": "2025-12-05"
        })
        task_id = create_response.json()["id"]

        client.patch(f"/api/tasks/{task_id}")
        second_toggle = client.patch(f"/api/tasks/{task_id}")

        assert second_toggle.status_code == 200
        assert second_toggle.json()["status"] == "pending"

    def test_toggle_nonexistent_task_returns_404(self, client):
        """Test that toggling a task that doesn't exist returns 404."""
        response = client.patch("/api/tasks/nonexistent-task-999")
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_delete_task_removes_it_from_list(self, client):
        """Test that deleting a task removes it from the task list."""
        create_response = client.post("/api/tasks", json={
            "title": "Schedule maintenance",
            "priority": "low",
            "dueDate": "2025-12-10"
        })
        task_id = create_response.json()["id"]

        delete_response = client.delete(f"/api/tasks/{task_id}")
        assert delete_response.status_code == 200

        list_response = client.get("/api/tasks")
        task_ids = [task["id"] for task in list_response.json()]
        assert task_id not in task_ids

    def test_delete_nonexistent_task_returns_404(self, client):
        """Test that deleting a task that doesn't exist returns 404."""
        response = client.delete("/api/tasks/nonexistent-task-999")
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()
