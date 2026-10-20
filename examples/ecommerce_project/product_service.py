#!/usr/bin/env python3
"""
Product Management API
Comprehensive e-commerce product catalog and inventory management system
"""
from fastapi import FastAPI, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship
from typing import List, Optional, Dict
from datetime import datetime
from decimal import Decimal
import enum

Base = declarative_base()

# Enums
class ProductStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONTINUED = "discontinued"
    COMING_SOON = "coming_soon"

class CategoryType(str, enum.Enum):
    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    BOOKS = "books"
    HOME = "home"
    SPORTS = "sports"
    BEAUTY = "beauty"

# Database Models
class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category_type = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    products = relationship("Product", back_populates="category")
    subcategories = relationship("Category", remote_side=[id])

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    short_description = Column(String(500))
    sku = Column(String(50), unique=True, nullable=False)
    barcode = Column(String(100), unique=True, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    cost_price = Column(Numeric(10, 2), nullable=True)
    weight = Column(Numeric(8, 3), nullable=True)
    dimensions = Column(String(100), nullable=True)  # Format: "L x W x H"
    status = Column(String, default=ProductStatus.ACTIVE.value)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    brand = Column(String(100), nullable=True)
    manufacturer = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    category = relationship("Category", back_populates="products")
    inventory = relationship("Inventory", back_populates="product", uselist=False)
    images = relationship("ProductImage", back_populates="product")
    reviews = relationship("ProductReview", back_populates="product")

class Inventory(Base):
    __tablename__ = "inventory"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, unique=True)
    quantity_available = Column(Integer, default=0)
    quantity_reserved = Column(Integer, default=0)
    reorder_level = Column(Integer, default=10)
    max_stock_level = Column(Integer, default=1000)
    last_restocked = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    product = relationship("Product", back_populates="inventory")

class ProductImage(Base):
    __tablename__ = "product_images"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    image_url = Column(String(500), nullable=False)
    alt_text = Column(String(200))
    is_primary = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    product = relationship("Product", back_populates="images")

class ProductReview(Base):
    __tablename__ = "product_reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    user_id = Column(Integer, nullable=False)  # Reference to user from auth service
    rating = Column(Integer, nullable=False)  # 1-5 stars
    title = Column(String(200))
    comment = Column(Text)
    is_verified_purchase = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    product = relationship("Product", back_populates="reviews")

# Pydantic Models
class CategoryCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    category_type: CategoryType

class CategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    parent_id: Optional[int]
    category_type: str
    is_active: bool
    created_at: datetime

class ProductCreate(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    short_description: Optional[str] = Field(None, max_length=500)
    sku: str = Field(..., max_length=50)
    barcode: Optional[str] = Field(None, max_length=100)
    price: Decimal = Field(..., gt=0)
    cost_price: Optional[Decimal] = Field(None, gt=0)
    weight: Optional[Decimal] = None
    dimensions: Optional[str] = None
    status: ProductStatus = ProductStatus.ACTIVE
    category_id: int
    brand: Optional[str] = None
    manufacturer: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    status: Optional[ProductStatus] = None
    category_id: Optional[int] = None

class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    short_description: Optional[str]
    sku: str
    price: Decimal
    status: str
    category_id: int
    brand: Optional[str]
    created_at: datetime
    inventory_quantity: Optional[int] = None

class InventoryUpdate(BaseModel):
    quantity_available: Optional[int] = None
    reorder_level: Optional[int] = None
    max_stock_level: Optional[int] = None

class ProductSearchFilters(BaseModel):
    category_id: Optional[int] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    status: Optional[ProductStatus] = None
    brand: Optional[str] = None
    in_stock_only: Optional[bool] = False

# Service Classes
class CategoryService:
    """Category management service"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_category(self, category_data: CategoryCreate) -> CategoryResponse:
        """Create a new product category"""
        # Check if category name already exists
        existing = self.db.query(Category).filter(Category.name == category_data.name).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category name already exists"
            )
        
        new_category = Category(**category_data.dict())
        self.db.add(new_category)
        self.db.commit()
        self.db.refresh(new_category)
        
        return CategoryResponse(
            id=new_category.id,
            name=new_category.name,
            description=new_category.description,
            parent_id=new_category.parent_id,
            category_type=new_category.category_type,
            is_active=new_category.is_active,
            created_at=new_category.created_at
        )
    
    def get_categories(self, include_inactive: bool = False) -> List[CategoryResponse]:
        """Get all categories"""
        query = self.db.query(Category)
        if not include_inactive:
            query = query.filter(Category.is_active == True)
        
        categories = query.all()
        return [CategoryResponse(
            id=cat.id,
            name=cat.name,
            description=cat.description,
            parent_id=cat.parent_id,
            category_type=cat.category_type,
            is_active=cat.is_active,
            created_at=cat.created_at
        ) for cat in categories]

class InventoryService:
    """Inventory management service"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def update_inventory(self, product_id: int, inventory_data: InventoryUpdate) -> dict:
        """Update product inventory"""
        inventory = self.db.query(Inventory).filter(Inventory.product_id == product_id).first()
        if not inventory:
            # Create inventory record if it doesn't exist
            inventory = Inventory(product_id=product_id)
            self.db.add(inventory)
        
        # Update fields
        for field, value in inventory_data.dict(exclude_unset=True).items():
            setattr(inventory, field, value)
        
        inventory.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(inventory)
        
        return {
            "product_id": inventory.product_id,
            "quantity_available": inventory.quantity_available,
            "quantity_reserved": inventory.quantity_reserved,
            "reorder_level": inventory.reorder_level,
            "needs_restock": inventory.quantity_available <= inventory.reorder_level
        }
    
    def reserve_inventory(self, product_id: int, quantity: int) -> bool:
        """Reserve inventory for an order"""
        inventory = self.db.query(Inventory).filter(Inventory.product_id == product_id).first()
        if not inventory or inventory.quantity_available < quantity:
            return False
        
        inventory.quantity_available -= quantity
        inventory.quantity_reserved += quantity
        self.db.commit()
        return True
    
    def release_inventory(self, product_id: int, quantity: int) -> bool:
        """Release reserved inventory (e.g., order cancelled)"""
        inventory = self.db.query(Inventory).filter(Inventory.product_id == product_id).first()
        if not inventory or inventory.quantity_reserved < quantity:
            return False
        
        inventory.quantity_available += quantity
        inventory.quantity_reserved -= quantity
        self.db.commit()
        return True

class ProductService:
    """Product management service"""
    
    def __init__(self, db: Session):
        self.db = db
        self.inventory_service = InventoryService(db)
    
    def create_product(self, product_data: ProductCreate) -> ProductResponse:
        """Create a new product"""
        # Check if SKU already exists
        existing = self.db.query(Product).filter(Product.sku == product_data.sku).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SKU already exists"
            )
        
        # Verify category exists
        category = self.db.query(Category).filter(Category.id == product_data.category_id).first()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
        
        new_product = Product(**product_data.dict())
        self.db.add(new_product)
        self.db.commit()
        self.db.refresh(new_product)
        
        # Create initial inventory record
        inventory = Inventory(product_id=new_product.id)
        self.db.add(inventory)
        self.db.commit()
        
        return self._product_to_response(new_product)
    
    def get_product(self, product_id: int) -> ProductResponse:
        """Get a single product by ID"""
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        return self._product_to_response(product)
    
    def search_products(self, filters: ProductSearchFilters, skip: int = 0, limit: int = 100) -> List[ProductResponse]:
        """Search products with filters"""
        query = self.db.query(Product)
        
        if filters.category_id:
            query = query.filter(Product.category_id == filters.category_id)
        if filters.min_price:
            query = query.filter(Product.price >= filters.min_price)
        if filters.max_price:
            query = query.filter(Product.price <= filters.max_price)
        if filters.status:
            query = query.filter(Product.status == filters.status.value)
        if filters.brand:
            query = query.filter(Product.brand.ilike(f"%{filters.brand}%"))
        if filters.in_stock_only:
            query = query.join(Inventory).filter(Inventory.quantity_available > 0)
        
        products = query.offset(skip).limit(limit).all()
        return [self._product_to_response(product) for product in products]
    
    def update_product(self, product_id: int, product_data: ProductUpdate) -> ProductResponse:
        """Update a product"""
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        
        # Update fields
        for field, value in product_data.dict(exclude_unset=True).items():
            setattr(product, field, value)
        
        product.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(product)
        
        return self._product_to_response(product)
    
    def _product_to_response(self, product: Product) -> ProductResponse:
        """Convert Product model to response"""
        inventory_quantity = None
        if product.inventory:
            inventory_quantity = product.inventory.quantity_available
        
        return ProductResponse(
            id=product.id,
            name=product.name,
            description=product.description,
            short_description=product.short_description,
            sku=product.sku,
            price=product.price,
            status=product.status,
            category_id=product.category_id,
            brand=product.brand,
            created_at=product.created_at,
            inventory_quantity=inventory_quantity
        )

# FastAPI Routes
app = FastAPI(title="Product Management API", version="1.0.0")

@app.post("/categories", response_model=CategoryResponse)
async def create_category(category_data: CategoryCreate, db: Session = Depends(get_db)):
    """Create a new product category"""
    service = CategoryService(db)
    return service.create_category(category_data)

@app.get("/categories", response_model=List[CategoryResponse])
async def get_categories(include_inactive: bool = False, db: Session = Depends(get_db)):
    """Get all product categories"""
    service = CategoryService(db)
    return service.get_categories(include_inactive)

@app.post("/products", response_model=ProductResponse)
async def create_product(product_data: ProductCreate, db: Session = Depends(get_db)):
    """Create a new product"""
    service = ProductService(db)
    return service.create_product(product_data)

@app.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    """Get a product by ID"""
    service = ProductService(db)
    return service.get_product(product_id)

@app.get("/products", response_model=List[ProductResponse])
async def search_products(
    category_id: Optional[int] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    status: Optional[ProductStatus] = None,
    brand: Optional[str] = None,
    in_stock_only: bool = False,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Search products with filters"""
    filters = ProductSearchFilters(
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
        status=status,
        brand=brand,
        in_stock_only=in_stock_only
    )
    service = ProductService(db)
    return service.search_products(filters, skip, limit)

@app.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(product_id: int, product_data: ProductUpdate, db: Session = Depends(get_db)):
    """Update a product"""
    service = ProductService(db)
    return service.update_product(product_id, product_data)

@app.put("/inventory/{product_id}")
async def update_inventory(product_id: int, inventory_data: InventoryUpdate, db: Session = Depends(get_db)):
    """Update product inventory"""
    service = InventoryService(db)
    return service.update_inventory(product_id, inventory_data)

@app.post("/inventory/{product_id}/reserve")
async def reserve_inventory(product_id: int, quantity: int, db: Session = Depends(get_db)):
    """Reserve inventory for an order"""
    service = InventoryService(db)
    success = service.reserve_inventory(product_id, quantity)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient inventory"
        )
    return {"message": "Inventory reserved successfully"}

@app.post("/inventory/{product_id}/release")
async def release_inventory(product_id: int, quantity: int, db: Session = Depends(get_db)):
    """Release reserved inventory"""
    service = InventoryService(db)
    success = service.release_inventory(product_id, quantity)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid release request"
        )
    return {"message": "Inventory released successfully"}

def get_db():
    """Database dependency - placeholder"""
    pass
