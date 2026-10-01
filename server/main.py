import random
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
from mock_data import inventory_items, orders, demand_forecasts, backlog_items, spending_summary, monthly_spending, category_spending, recent_transactions, purchase_orders, restocking_orders, tasks

app = FastAPI(title="Factory Inventory Management System")

# Quarter mapping for date filtering
QUARTER_MAP = {
    'Q1-2025': ['2025-01', '2025-02', '2025-03'],
    'Q2-2025': ['2025-04', '2025-05', '2025-06'],
    'Q3-2025': ['2025-07', '2025-08', '2025-09'],
    'Q4-2025': ['2025-10', '2025-11', '2025-12']
}

def filter_by_month(items: list, month: Optional[str]) -> list:
    """Filter items by month/quarter based on order_date field"""
    if not month or month == 'all':
        return items

    if month.startswith('Q'):
        # Handle quarters
        if month in QUARTER_MAP:
            months = QUARTER_MAP[month]
            return [item for item in items if any(m in item.get('order_date', '') for m in months)]
    else:
        # Direct month match
        return [item for item in items if month in item.get('order_date', '')]

    return items

def apply_filters(items: list, warehouse: Optional[str] = None, category: Optional[str] = None,
                 status: Optional[str] = None) -> list:
    """Apply common filters to a list of items"""
    filtered = items

    if warehouse and warehouse != 'all':
        filtered = [item for item in filtered if item.get('warehouse') == warehouse]

    if category and category != 'all':
        filtered = [item for item in filtered if item.get('category', '').lower() == category.lower()]

    if status and status != 'all':
        filtered = [item for item in filtered if item.get('status', '').lower() == status.lower()]

    return filtered

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class InventoryItem(BaseModel):
    id: str
    sku: str
    name: str
    category: str
    warehouse: str
    quantity_on_hand: int
    reorder_point: int
    unit_cost: float
    location: str
    last_updated: str

class Order(BaseModel):
    id: str
    order_number: str
    customer: str
    items: List[dict]
    status: str
    order_date: str
    expected_delivery: str
    total_value: float
    actual_delivery: Optional[str] = None
    warehouse: Optional[str] = None
    category: Optional[str] = None

class DemandForecast(BaseModel):
    id: str
    item_sku: str
    item_name: str
    current_demand: int
    forecasted_demand: int
    trend: str
    period: str

class BacklogItem(BaseModel):
    id: str
    order_id: str
    item_sku: str
    item_name: str
    quantity_needed: int
    quantity_available: int
    days_delayed: int
    priority: str
    has_purchase_order: Optional[bool] = False

class PurchaseOrder(BaseModel):
    id: str
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    status: str
    created_date: str
    notes: Optional[str] = None

class CreatePurchaseOrderRequest(BaseModel):
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    notes: Optional[str] = None

class RestockingRecommendation(BaseModel):
    sku: str
    item_name: str
    category: str
    warehouse: str
    quantity_on_hand: int
    reorder_point: int
    forecasted_demand: int
    trend: str
    recommended_quantity: int
    unit_cost: float
    line_total: float
    urgency_score: float
    urgency_reason: str

class RestockingRecommendationsResponse(BaseModel):
    budget: float
    total_cost: float
    remaining_budget: float
    items: List[RestockingRecommendation]

class RestockingOrderItem(BaseModel):
    sku: str
    item_name: str
    quantity: int
    unit_cost: float
    line_total: float

class RestockingOrder(BaseModel):
    id: str
    order_number: str
    supplier_name: str
    items: List[RestockingOrderItem]
    item_count: int
    total_cost: float
    budget_requested: float
    order_date: str
    lead_time_days: int
    expected_delivery_date: str
    status: str

class CreateRestockingOrderRequest(BaseModel):
    budget: float

class Task(BaseModel):
    id: str
    title: str
    priority: str
    dueDate: str
    status: str

class CreateTaskRequest(BaseModel):
    title: str
    priority: str
    dueDate: str

MOCK_SUPPLIERS = [
    "Acme Industrial Supply",
    "Global Parts Co.",
    "Northbridge Components",
    "Pioneer Manufacturing"
]

def compute_restocking_recommendations(budget: float) -> RestockingRecommendationsResponse:
    """Rank demand-forecast items by urgency (stock shortfall + demand growth)
    and greedily fill the given budget, allowing a partial fill on the item
    where the budget runs out so lower-ranked, cheaper items can still use
    any leftover budget."""
    inventory_by_sku = {item["sku"]: item for item in inventory_items}

    candidates = []
    for forecast in demand_forecasts:
        item = inventory_by_sku.get(forecast["item_sku"])
        if not item:
            continue

        recommended_quantity = max(0, forecast["forecasted_demand"] - item["quantity_on_hand"])
        if recommended_quantity == 0:
            continue

        reorder_point = item["reorder_point"]
        shortfall_ratio = max(0.0, (reorder_point - item["quantity_on_hand"]) / reorder_point) if reorder_point else 0.0

        current_demand = forecast["current_demand"]
        growth_ratio = max(0.0, (forecast["forecasted_demand"] - current_demand) / current_demand) if current_demand else 0.0

        urgency_score = round(0.6 * shortfall_ratio + 0.4 * growth_ratio, 4)

        if shortfall_ratio > 0 and growth_ratio > 0:
            urgency_reason = "Below reorder point, demand increasing"
        elif shortfall_ratio > 0:
            urgency_reason = "Below reorder point"
        elif growth_ratio > 0:
            urgency_reason = "Demand increasing"
        else:
            urgency_reason = "Restock recommended"

        candidates.append({
            "sku": item["sku"],
            "item_name": item["name"],
            "category": item["category"],
            "warehouse": item["warehouse"],
            "quantity_on_hand": item["quantity_on_hand"],
            "reorder_point": reorder_point,
            "forecasted_demand": forecast["forecasted_demand"],
            "trend": forecast["trend"],
            "recommended_quantity": recommended_quantity,
            "unit_cost": item["unit_cost"],
            "urgency_score": urgency_score,
            "urgency_reason": urgency_reason,
            "shortfall": reorder_point - item["quantity_on_hand"]
        })

    # Highest urgency first; ties broken by larger raw shortfall, then SKU
    candidates.sort(key=lambda c: (-c["urgency_score"], -c["shortfall"], c["sku"]))

    remaining_budget = max(0.0, budget)
    selected = []

    for candidate in candidates:
        full_line_cost = round(candidate["recommended_quantity"] * candidate["unit_cost"], 2)

        if full_line_cost <= remaining_budget:
            quantity = candidate["recommended_quantity"]
        else:
            quantity = int(remaining_budget // candidate["unit_cost"]) if candidate["unit_cost"] > 0 else 0

        if quantity <= 0:
            continue

        line_total = round(quantity * candidate["unit_cost"], 2)
        remaining_budget = round(remaining_budget - line_total, 2)

        selected.append(RestockingRecommendation(
            sku=candidate["sku"],
            item_name=candidate["item_name"],
            category=candidate["category"],
            warehouse=candidate["warehouse"],
            quantity_on_hand=candidate["quantity_on_hand"],
            reorder_point=candidate["reorder_point"],
            forecasted_demand=candidate["forecasted_demand"],
            trend=candidate["trend"],
            recommended_quantity=quantity,
            unit_cost=candidate["unit_cost"],
            line_total=line_total,
            urgency_score=candidate["urgency_score"],
            urgency_reason=candidate["urgency_reason"]
        ))

    total_cost = round(sum(item.line_total for item in selected), 2)

    return RestockingRecommendationsResponse(
        budget=budget,
        total_cost=total_cost,
        remaining_budget=round(max(0.0, budget) - total_cost, 2),
        items=selected
    )

# API endpoints
@app.get("/")
def root():
    return {"message": "Factory Inventory Management System API", "version": "1.0.0"}

@app.get("/api/inventory", response_model=List[InventoryItem])
def get_inventory(
    warehouse: Optional[str] = None,
    category: Optional[str] = None
):
    """Get all inventory items with optional filtering"""
    return apply_filters(inventory_items, warehouse, category)

@app.get("/api/inventory/{item_id}", response_model=InventoryItem)
def get_inventory_item(item_id: str):
    """Get a specific inventory item"""
    item = next((item for item in inventory_items if item["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.get("/api/orders", response_model=List[Order])
def get_orders(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get all orders with optional filtering"""
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)
    return filtered_orders

@app.get("/api/orders/{order_id}", response_model=Order)
def get_order(order_id: str):
    """Get a specific order"""
    order = next((order for order in orders if order["id"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.get("/api/demand", response_model=List[DemandForecast])
def get_demand_forecasts():
    """Get demand forecasts"""
    return demand_forecasts

@app.get("/api/backlog", response_model=List[BacklogItem])
def get_backlog():
    """Get backlog items with purchase order status"""
    # Add has_purchase_order flag to each backlog item
    result = []
    for item in backlog_items:
        item_dict = dict(item)
        # Check if this backlog item has a purchase order
        has_po = any(po["backlog_item_id"] == item["id"] for po in purchase_orders)
        item_dict["has_purchase_order"] = has_po
        result.append(item_dict)
    return result

@app.post("/api/purchase-orders", response_model=PurchaseOrder, status_code=201)
def create_purchase_order(request: CreatePurchaseOrderRequest):
    """Create a purchase order for a backlog item"""
    backlog_item = next((item for item in backlog_items if item["id"] == request.backlog_item_id), None)
    if not backlog_item:
        raise HTTPException(status_code=404, detail="Backlog item not found")

    if any(po["backlog_item_id"] == request.backlog_item_id for po in purchase_orders):
        raise HTTPException(status_code=400, detail="A purchase order already exists for this backlog item")

    purchase_order = PurchaseOrder(
        id=str(len(purchase_orders) + 1),
        backlog_item_id=request.backlog_item_id,
        supplier_name=request.supplier_name,
        quantity=request.quantity,
        unit_cost=request.unit_cost,
        expected_delivery_date=request.expected_delivery_date,
        status="Pending",
        created_date=datetime.now().isoformat(),
        notes=request.notes
    )

    purchase_orders.append(purchase_order.model_dump())
    return purchase_order

@app.get("/api/purchase-orders/{backlog_item_id}", response_model=PurchaseOrder)
def get_purchase_order_by_backlog_item(backlog_item_id: str):
    """Get the purchase order associated with a backlog item"""
    purchase_order = next((po for po in purchase_orders if po["backlog_item_id"] == backlog_item_id), None)
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return purchase_order

@app.get("/api/dashboard/summary")
def get_dashboard_summary(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get summary statistics for dashboard with optional filtering"""
    # Filter inventory
    filtered_inventory = apply_filters(inventory_items, warehouse, category)

    # Filter orders
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)

    total_inventory_value = sum(item["quantity_on_hand"] * item["unit_cost"] for item in filtered_inventory)
    low_stock_items = len([item for item in filtered_inventory if item["quantity_on_hand"] <= item["reorder_point"]])
    pending_orders = len([order for order in filtered_orders if order["status"] in ["Processing", "Backordered"]])
    total_backlog_items = len(backlog_items)

    return {
        "total_inventory_value": round(total_inventory_value, 2),
        "low_stock_items": low_stock_items,
        "pending_orders": pending_orders,
        "total_backlog_items": total_backlog_items,
        "total_orders_value": sum(order["total_value"] for order in filtered_orders)
    }

@app.get("/api/spending/summary")
def get_spending_summary():
    """Get spending summary statistics"""
    return spending_summary

@app.get("/api/spending/monthly")
def get_monthly_spending():
    """Get monthly spending breakdown"""
    return monthly_spending

@app.get("/api/spending/categories")
def get_category_spending():
    """Get spending by category"""
    return category_spending

@app.get("/api/spending/transactions")
def get_recent_transactions():
    """Get recent transactions"""
    return recent_transactions

@app.get("/api/reports/quarterly")
def get_quarterly_reports():
    """Get quarterly performance reports"""
    # Calculate quarterly statistics from orders
    quarters = {}

    for order in orders:
        order_date = order.get('order_date', '')
        # Determine quarter
        if '2025-01' in order_date or '2025-02' in order_date or '2025-03' in order_date:
            quarter = 'Q1-2025'
        elif '2025-04' in order_date or '2025-05' in order_date or '2025-06' in order_date:
            quarter = 'Q2-2025'
        elif '2025-07' in order_date or '2025-08' in order_date or '2025-09' in order_date:
            quarter = 'Q3-2025'
        elif '2025-10' in order_date or '2025-11' in order_date or '2025-12' in order_date:
            quarter = 'Q4-2025'
        else:
            continue

        if quarter not in quarters:
            quarters[quarter] = {
                'quarter': quarter,
                'total_orders': 0,
                'total_revenue': 0,
                'delivered_orders': 0,
                'avg_order_value': 0
            }

        quarters[quarter]['total_orders'] += 1
        quarters[quarter]['total_revenue'] += order.get('total_value', 0)
        if order.get('status') == 'Delivered':
            quarters[quarter]['delivered_orders'] += 1

    # Calculate averages and fulfillment rate
    result = []
    for q, data in quarters.items():
        if data['total_orders'] > 0:
            data['avg_order_value'] = round(data['total_revenue'] / data['total_orders'], 2)
            data['fulfillment_rate'] = round((data['delivered_orders'] / data['total_orders']) * 100, 1)
        result.append(data)

    # Sort by quarter
    result.sort(key=lambda x: x['quarter'])
    return result

@app.get("/api/reports/monthly-trends")
def get_monthly_trends():
    """Get month-over-month trends"""
    months = {}

    for order in orders:
        order_date = order.get('order_date', '')
        if not order_date:
            continue

        # Extract month (format: YYYY-MM-DD)
        month = order_date[:7]  # Gets YYYY-MM

        if month not in months:
            months[month] = {
                'month': month,
                'order_count': 0,
                'revenue': 0,
                'delivered_count': 0
            }

        months[month]['order_count'] += 1
        months[month]['revenue'] += order.get('total_value', 0)
        if order.get('status') == 'Delivered':
            months[month]['delivered_count'] += 1

    # Convert to list and sort
    result = list(months.values())
    result.sort(key=lambda x: x['month'])
    return result

@app.get("/api/restocking/recommendations", response_model=RestockingRecommendationsResponse)
def get_restocking_recommendations(budget: float = Query(..., ge=0)):
    """Get urgency-ranked restock recommendations that fit within the given budget"""
    return compute_restocking_recommendations(budget)

@app.post("/api/restocking/orders", response_model=RestockingOrder, status_code=201)
def create_restocking_order(request: CreateRestockingOrderRequest):
    """Submit a restocking order for the items recommended at the given budget"""
    if request.budget <= 0:
        raise HTTPException(status_code=400, detail="Budget must be greater than 0")

    recommendations = compute_restocking_recommendations(request.budget)
    if not recommendations.items:
        raise HTTPException(status_code=400, detail="No items to order for the given budget")

    order_date = datetime.now()
    lead_time_days = random.randint(5, 14)
    expected_delivery_date = order_date + timedelta(days=lead_time_days)

    order_items = [
        RestockingOrderItem(
            sku=item.sku,
            item_name=item.item_name,
            quantity=item.recommended_quantity,
            unit_cost=item.unit_cost,
            line_total=item.line_total
        )
        for item in recommendations.items
    ]

    order = RestockingOrder(
        id=str(len(restocking_orders) + 1),
        order_number=f"RO-2025-{len(restocking_orders) + 1:04d}",
        supplier_name=random.choice(MOCK_SUPPLIERS),
        items=order_items,
        item_count=len(order_items),
        total_cost=recommendations.total_cost,
        budget_requested=request.budget,
        order_date=order_date.isoformat(),
        lead_time_days=lead_time_days,
        expected_delivery_date=expected_delivery_date.isoformat(),
        status="Processing"
    )

    restocking_orders.append(order.model_dump())
    return order

@app.get("/api/restocking/orders", response_model=List[RestockingOrder])
def get_restocking_orders():
    """Get all submitted restocking orders, newest first"""
    return sorted(restocking_orders, key=lambda o: o["order_date"], reverse=True)

@app.get("/api/tasks", response_model=List[Task])
def get_tasks():
    """Get all tasks"""
    return tasks

@app.post("/api/tasks", response_model=Task, status_code=201)
def create_task(request: CreateTaskRequest):
    """Create a new task"""
    task = Task(
        id=str(len(tasks) + 1),
        title=request.title,
        priority=request.priority,
        dueDate=request.dueDate,
        status="pending"
    )
    tasks.append(task.model_dump())
    return task

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str):
    """Delete a task"""
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    tasks.remove(task)
    return {"message": "Task deleted"}

@app.patch("/api/tasks/{task_id}", response_model=Task)
def toggle_task(task_id: str):
    """Toggle a task's status between pending and completed"""
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task["status"] = "completed" if task["status"] == "pending" else "pending"
    return task

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
