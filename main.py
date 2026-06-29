from fastapi import FastAPI, Header, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import time
import base64

app = FastAPI()

# -----------------------------
# CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Assignment Values
# -----------------------------
TOTAL_ORDERS = 46
RATE_LIMIT = 20
WINDOW = 10  # seconds

# -----------------------------
# Fixed Order Catalog
# -----------------------------
orders_catalog = [
    {
        "id": i,
        "item": f"Order-{i}"
    }
    for i in range(1, TOTAL_ORDERS + 1)
]

# -----------------------------
# Stores
# -----------------------------
idempotency_store = {}
client_requests = {}

# -----------------------------
# Request Model
# -----------------------------
class Order(BaseModel):
    item: str = "Sample Order"

# -----------------------------
# Rate Limiting Middleware
# -----------------------------
@app.middleware("http")
async def rate_limit(request: Request, call_next):

    # Don't rate limit CORS preflight
    if request.method == "OPTIONS":
        return await call_next(request)

    # Only rate-limit /orders endpoints
    if request.url.path.startswith("/orders"):

        client_id = request.headers.get("X-Client-Id", "anonymous")

        now = time.time()

        history = client_requests.get(client_id, [])

        history = [t for t in history if now - t < WINDOW]

        if len(history) >= RATE_LIMIT:
            response = Response(status_code=429)
            response.headers["Retry-After"] = str(WINDOW)
            return response

        history.append(now)

        client_requests[client_id] = history

    response = await call_next(request)

    return response

# -----------------------------
# POST /orders
# -----------------------------
@app.post("/orders", status_code=201)
def create_order(
    order: Order,
    idempotency_key: str = Header(..., alias="Idempotency-Key")
):

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    new_order = {
        "id": str(uuid.uuid4()),
        "item": order.item
    }

    idempotency_store[idempotency_key] = new_order

    return new_order

# -----------------------------
# GET /orders
# -----------------------------
@app.get("/orders")
def get_orders(
    limit: int = 10,
    cursor: str | None = None
):

    start = 0

    if cursor:
        try:
            start = int(base64.b64decode(cursor).decode())
        except Exception:
            start = 0

    end = min(start + limit, TOTAL_ORDERS)

    items = orders_catalog[start:end]

    next_cursor = None

    if end < TOTAL_ORDERS:
        next_cursor = base64.b64encode(
            str(end).encode()
        ).decode()

    return {
        "items": items,
        "next_cursor": next_cursor
    }

# -----------------------------
# Root
# -----------------------------
@app.get("/")
def root():
    return {
        "message": "Orders API is running"
    }
