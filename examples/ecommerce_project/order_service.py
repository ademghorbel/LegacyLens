#!/usr/bin/env python3
"""
Order Management Service
Complete e-commerce order processing, payment, and fulfillment system
"""
from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
import enum
import uuid

Base = declarative_base()

# Enums
class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class PaymentMethod(str, enum.Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PAYPAL = "paypal"
    BANK_TRANSFER = "bank_transfer"
    WALLET = "wallet"

class ShippingMethod(str, enum.Enum):
    STANDARD = "standard"
    EXPRESS = "express"
    OVERNIGHT = "overnight"
    PICKUP = "pickup"

# Database Models
class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, nullable=False)
    user_id = Column(Integer, nullable=False)  # Reference to user from auth service
    status = Column(String, default=OrderStatus.PENDING.value)
    
    # Pricing
    subtotal = Column(Numeric(12, 2), nullable=False)
    tax_amount = Column(Numeric(12, 2), default=0)
    shipping_cost = Column(Numeric(10, 2), default=0)
    discount_amount = Column(Numeric(10, 2), default=0)
    total_amount = Column(Numeric(12, 2), nullable=False)
    
    # Customer Information
    customer_email = Column(String(255), nullable=False)
    customer_phone = Column(String(20))
    
    # Shipping Information
    shipping_method = Column(String, default=ShippingMethod.STANDARD.value)
    shipping_address = Column(JSON)  # Stores address as JSON
    estimated_delivery = Column(DateTime)
    tracking_number = Column(String(100))
    
    # Billing Information
    billing_address = Column(JSON)  # Stores address as JSON
    
    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    confirmed_at = Column(DateTime)
    shipped_at = Column(DateTime)
    delivered_at = Column(DateTime)
    cancelled_at = Column(DateTime)
    
    # Relationships
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order")
    status_history = relationship("OrderStatusHistory", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, nullable=False)  # Reference to product from product service
    product_name = Column(String(200), nullable=False)  # Snapshot of product name
    product_sku = Column(String(50), nullable=False)  # Snapshot of SKU
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)  # Price at time of order
    total_price = Column(Numeric(12, 2), nullable=False)
    
    # Relationships
    order = relationship("Order", back_populates="items")

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    payment_number = Column(String(50), unique=True, nullable=False)
    method = Column(String, nullable=False)
    status = Column(String, default=PaymentStatus.PENDING.value)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="USD")
    
    # Payment Gateway Information
    gateway_transaction_id = Column(String(255))
    gateway_response = Column(JSON)  # Store gateway response as JSON
    
    # Card Information (if applicable, stored securely)
    card_last_four = Column(String(4))
    card_brand = Column(String(20))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    failed_at = Column(DateTime)
    refunded_at = Column(DateTime)
    
    # Relationships
    order = relationship("Order", back_populates="payments")

class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    previous_status = Column(String)
    new_status = Column(String, nullable=False)
    reason = Column(String(500))
    changed_by = Column(Integer)  # User ID who made the change
    changed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    order = relationship("Order", back_populates="status_history")

# Pydantic Models
class AddressModel(BaseModel):
    street_address: str
    city: str
    state: str
    postal_code: str
    country: str
    apartment: Optional[str] = None

class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)

class OrderCreate(BaseModel):
    user_id: int
    items: List[OrderItemCreate]
    customer_email: str
    customer_phone: Optional[str] = None
    shipping_address: AddressModel
    billing_address: Optional[AddressModel] = None
    shipping_method: ShippingMethod = ShippingMethod.STANDARD
    notes: Optional[str] = None

class PaymentCreate(BaseModel):
    order_id: int
    method: PaymentMethod
    amount: Decimal = Field(..., gt=0)
    card_token: Optional[str] = None  # Tokenized card information
    gateway_data: Optional[Dict[str, Any]] = None

class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    product_sku: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal

class PaymentResponse(BaseModel):
    id: int
    payment_number: str
    method: str
    status: str
    amount: Decimal
    currency: str
    card_last_four: Optional[str]
    card_brand: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]

class OrderResponse(BaseModel):
    id: int
    order_number: str
    user_id: int
    status: str
    subtotal: Decimal
    tax_amount: Decimal
    shipping_cost: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    customer_email: str
    shipping_method: str
    shipping_address: Dict[str, Any]
    estimated_delivery: Optional[datetime]
    tracking_number: Optional[str]
    created_at: datetime
    items: List[OrderItemResponse]
    payments: List[PaymentResponse]

class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    reason: Optional[str] = None
    tracking_number: Optional[str] = None

# Service Classes
class OrderNumberGenerator:
    """Generate unique order numbers"""
    
    @staticmethod
    def generate() -> str:
        """Generate a unique order number"""
        timestamp = datetime.now().strftime("%Y%m%d")
        unique_id = str(uuid.uuid4()).replace("-", "")[:8].upper()
        return f"ORD-{timestamp}-{unique_id}"

class PaymentNumberGenerator:
    """Generate unique payment numbers"""
    
    @staticmethod
    def generate() -> str:
        """Generate a unique payment number"""
        timestamp = datetime.now().strftime("%Y%m%d")
        unique_id = str(uuid.uuid4()).replace("-", "")[:8].upper()
        return f"PAY-{timestamp}-{unique_id}"

class PricingService:
    """Calculate order pricing including taxes and shipping"""
    
    def __init__(self):
        self.tax_rate = Decimal("0.08")  # 8% tax rate
        self.shipping_rates = {
            ShippingMethod.STANDARD: Decimal("5.99"),
            ShippingMethod.EXPRESS: Decimal("12.99"),
            ShippingMethod.OVERNIGHT: Decimal("24.99"),
            ShippingMethod.PICKUP: Decimal("0.00")
        }
    
    def calculate_order_totals(self, items_total: Decimal, shipping_method: ShippingMethod, 
                             discount_amount: Decimal = Decimal("0")) -> Dict[str, Decimal]:
        """Calculate order totals including tax and shipping"""
        subtotal = items_total
        shipping_cost = self.shipping_rates.get(shipping_method, Decimal("5.99"))
        taxable_amount = subtotal - discount_amount
        tax_amount = taxable_amount * self.tax_rate
        total_amount = subtotal + tax_amount + shipping_cost - discount_amount
        
        return {
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "shipping_cost": shipping_cost,
            "discount_amount": discount_amount,
            "total_amount": total_amount
        }

class PaymentGatewayService:
    """Mock payment gateway integration"""
    
    def process_payment(self, payment_data: PaymentCreate) -> Dict[str, Any]:
        """Process payment through gateway (mock implementation)"""
        # Mock payment processing logic
        import random
        success = random.choice([True, True, True, False])  # 75% success rate
        
        if success:
            return {
                "status": PaymentStatus.COMPLETED.value,
                "transaction_id": f"txn_{uuid.uuid4().hex[:16]}",
                "gateway_response": {
                    "response_code": "00",
                    "message": "Transaction approved",
                    "auth_code": f"AUTH{random.randint(100000, 999999)}"
                }
            }
        else:
            return {
                "status": PaymentStatus.FAILED.value,
                "transaction_id": None,
                "gateway_response": {
                    "response_code": "05",
                    "message": "Transaction declined",
                    "reason": "Insufficient funds"
                }
            }

class OrderService:
    """Main order management service"""
    
    def __init__(self, db: Session):
        self.db = db
        self.pricing_service = PricingService()
        self.payment_gateway = PaymentGatewayService()
    
    def create_order(self, order_data: OrderCreate) -> OrderResponse:
        """Create a new order"""
        # Generate order number
        order_number = OrderNumberGenerator.generate()
        
        # Calculate pricing
        items_total = self._calculate_items_total(order_data.items)
        pricing = self.pricing_service.calculate_order_totals(
            items_total, order_data.shipping_method
        )
        
        # Create order
        new_order = Order(
            order_number=order_number,
            user_id=order_data.user_id,
            subtotal=pricing["subtotal"],
            tax_amount=pricing["tax_amount"],
            shipping_cost=pricing["shipping_cost"],
            discount_amount=pricing["discount_amount"],
            total_amount=pricing["total_amount"],
            customer_email=order_data.customer_email,
            customer_phone=order_data.customer_phone,
            shipping_method=order_data.shipping_method.value,
            shipping_address=order_data.shipping_address.dict(),
            billing_address=order_data.billing_address.dict() if order_data.billing_address else order_data.shipping_address.dict(),
            notes=order_data.notes,
            estimated_delivery=self._calculate_estimated_delivery(order_data.shipping_method)
        )
        
        self.db.add(new_order)
        self.db.flush()  # Get the order ID
        
        # Create order items
        for item_data in order_data.items:
            # In a real implementation, you'd fetch product details from product service
            product_info = self._get_product_info(item_data.product_id)
            
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=item_data.product_id,
                product_name=product_info["name"],
                product_sku=product_info["sku"],
                quantity=item_data.quantity,
                unit_price=product_info["price"],
                total_price=product_info["price"] * item_data.quantity
            )
            self.db.add(order_item)
        
        # Add status history
        status_history = OrderStatusHistory(
            order_id=new_order.id,
            previous_status=None,
            new_status=OrderStatus.PENDING.value,
            reason="Order created",
            changed_by=order_data.user_id
        )
        self.db.add(status_history)
        
        self.db.commit()
        self.db.refresh(new_order)
        
        return self._order_to_response(new_order)
    
    def get_order(self, order_id: int, user_id: Optional[int] = None) -> OrderResponse:
        """Get order by ID"""
        query = self.db.query(Order).filter(Order.id == order_id)
        if user_id:
            query = query.filter(Order.user_id == user_id)
        
        order = query.first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        return self._order_to_response(order)
    
    def update_order_status(self, order_id: int, status_data: OrderStatusUpdate, 
                          changed_by: int) -> OrderResponse:
        """Update order status"""
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        previous_status = order.status
        order.status = status_data.status.value
        
        # Update timestamps based on status
        now = datetime.utcnow()
        if status_data.status == OrderStatus.CONFIRMED:
            order.confirmed_at = now
        elif status_data.status == OrderStatus.SHIPPED:
            order.shipped_at = now
            if status_data.tracking_number:
                order.tracking_number = status_data.tracking_number
        elif status_data.status == OrderStatus.DELIVERED:
            order.delivered_at = now
        elif status_data.status == OrderStatus.CANCELLED:
            order.cancelled_at = now
        
        # Add status history
        status_history = OrderStatusHistory(
            order_id=order.id,
            previous_status=previous_status,
            new_status=status_data.status.value,
            reason=status_data.reason,
            changed_by=changed_by
        )
        self.db.add(status_history)
        
        order.updated_at = now
        self.db.commit()
        self.db.refresh(order)
        
        return self._order_to_response(order)
    
    def process_payment(self, payment_data: PaymentCreate) -> PaymentResponse:
        """Process payment for an order"""
        order = self.db.query(Order).filter(Order.id == payment_data.order_id).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        # Generate payment number
        payment_number = PaymentNumberGenerator.generate()
        
        # Create payment record
        payment = Payment(
            order_id=payment_data.order_id,
            payment_number=payment_number,
            method=payment_data.method.value,
            amount=payment_data.amount,
            status=PaymentStatus.PROCESSING.value
        )
        
        self.db.add(payment)
        self.db.flush()
        
        # Process payment through gateway
        gateway_result = self.payment_gateway.process_payment(payment_data)
        
        # Update payment record
        payment.status = gateway_result["status"]
        payment.gateway_transaction_id = gateway_result.get("transaction_id")
        payment.gateway_response = gateway_result.get("gateway_response")
        
        if gateway_result["status"] == PaymentStatus.COMPLETED.value:
            payment.processed_at = datetime.utcnow()
            # Update order status
            order.status = OrderStatus.CONFIRMED.value
            order.confirmed_at = datetime.utcnow()
        elif gateway_result["status"] == PaymentStatus.FAILED.value:
            payment.failed_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(payment)
        
        return PaymentResponse(
            id=payment.id,
            payment_number=payment.payment_number,
            method=payment.method,
            status=payment.status,
            amount=payment.amount,
            currency=payment.currency,
            card_last_four=payment.card_last_four,
            card_brand=payment.card_brand,
            created_at=payment.created_at,
            processed_at=payment.processed_at
        )
    
    def _calculate_items_total(self, items: List[OrderItemCreate]) -> Decimal:
        """Calculate total price of all items"""
        total = Decimal("0")
        for item in items:
            product_info = self._get_product_info(item.product_id)
            total += product_info["price"] * item.quantity
        return total
    
    def _get_product_info(self, product_id: int) -> Dict[str, Any]:
        """Get product information (mock implementation)"""
        # In a real implementation, this would call the product service
        return {
            "id": product_id,
            "name": f"Product {product_id}",
            "sku": f"SKU-{product_id:06d}",
            "price": Decimal("29.99")
        }
    
    def _calculate_estimated_delivery(self, shipping_method: ShippingMethod) -> datetime:
        """Calculate estimated delivery date"""
        days = {
            ShippingMethod.STANDARD: 5,
            ShippingMethod.EXPRESS: 2,
            ShippingMethod.OVERNIGHT: 1,
            ShippingMethod.PICKUP: 0
        }
        return datetime.utcnow() + timedelta(days=days.get(shipping_method, 5))
    
    def _order_to_response(self, order: Order) -> OrderResponse:
        """Convert Order model to response"""
        items = [OrderItemResponse(
            id=item.id,
            product_id=item.product_id,
            product_name=item.product_name,
            product_sku=item.product_sku,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=item.total_price
        ) for item in order.items]
        
        payments = [PaymentResponse(
            id=payment.id,
            payment_number=payment.payment_number,
            method=payment.method,
            status=payment.status,
            amount=payment.amount,
            currency=payment.currency,
            card_last_four=payment.card_last_four,
            card_brand=payment.card_brand,
            created_at=payment.created_at,
            processed_at=payment.processed_at
        ) for payment in order.payments]
        
        return OrderResponse(
            id=order.id,
            order_number=order.order_number,
            user_id=order.user_id,
            status=order.status,
            subtotal=order.subtotal,
            tax_amount=order.tax_amount,
            shipping_cost=order.shipping_cost,
            discount_amount=order.discount_amount,
            total_amount=order.total_amount,
            customer_email=order.customer_email,
            shipping_method=order.shipping_method,
            shipping_address=order.shipping_address,
            estimated_delivery=order.estimated_delivery,
            tracking_number=order.tracking_number,
            created_at=order.created_at,
            items=items,
            payments=payments
        )

# FastAPI Routes
app = FastAPI(title="Order Management API", version="1.0.0")

@app.post("/orders", response_model=OrderResponse)
async def create_order(order_data: OrderCreate, db: Session = Depends(get_db)):
    """Create a new order"""
    service = OrderService(db)
    return service.create_order(order_data)

@app.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: int, user_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Get order by ID"""
    service = OrderService(db)
    return service.get_order(order_id, user_id)

@app.put("/orders/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: int,
    status_data: OrderStatusUpdate,
    changed_by: int,
    db: Session = Depends(get_db)
):
    """Update order status"""
    service = OrderService(db)
    return service.update_order_status(order_id, status_data, changed_by)

@app.post("/payments", response_model=PaymentResponse)
async def process_payment(payment_data: PaymentCreate, db: Session = Depends(get_db)):
    """Process payment for an order"""
    service = OrderService(db)
    return service.process_payment(payment_data)

@app.get("/orders/{order_id}/tracking")
async def get_tracking_info(order_id: int, db: Session = Depends(get_db)):
    """Get order tracking information"""
    service = OrderService(db)
    order = service.get_order(order_id)
    
    return {
        "order_number": order.order_number,
        "status": order.status,
        "tracking_number": order.tracking_number,
        "estimated_delivery": order.estimated_delivery,
        "shipping_method": order.shipping_method
    }

def get_db():
    """Database dependency - placeholder"""
    pass
