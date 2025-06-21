# Data models for bike scraper
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime

@dataclass
class BikeSpecification:
    """Model for bike specifications"""
    frame_material: Optional[str] = None
    frame_size: Optional[str] = None
    wheel_size: Optional[str] = None
    tire_size: Optional[str] = None
    gears: Optional[str] = None
    drivetrain: Optional[str] = None
    brakes: Optional[str] = None
    suspension: Optional[str] = None
    weight: Optional[str] = None
    max_weight_capacity: Optional[str] = None
    
@dataclass
class BikeImage:
    """Model for bike images"""
    url: str
    alt_text: Optional[str] = None
    caption: Optional[str] = None
    is_primary: bool = False

@dataclass
class BikePrice:
    """Model for bike pricing information"""
    price: Optional[float] = None
    currency: str = "USD"
    original_price: Optional[float] = None
    discount_percentage: Optional[float] = None
    is_on_sale: bool = False

@dataclass
class BikeAvailability:
    """Model for bike availability information"""
    in_stock: Optional[bool] = None
    stock_level: Optional[str] = None
    available_sizes: List[str] = field(default_factory=list)
    available_colors: List[str] = field(default_factory=list)
    estimated_delivery: Optional[str] = None

@dataclass
class BikeReview:
    """Model for bike reviews"""
    rating: Optional[float] = None
    review_count: Optional[int] = None
    review_summary: Optional[str] = None

@dataclass
class Bike:
    """Main model for bike information"""
    # Basic information
    manufacturer: str
    model: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    year: Optional[int] = None
    sku: Optional[str] = None
    
    # Pricing
    pricing: BikePrice = field(default_factory=BikePrice)
    
    # Specifications
    specifications: BikeSpecification = field(default_factory=BikeSpecification)
    
    # Availability
    availability: BikeAvailability = field(default_factory=BikeAvailability)
    
    # Reviews
    reviews: BikeReview = field(default_factory=BikeReview)
    
    # Images
    images: List[BikeImage] = field(default_factory=list)
    
    # Description and details
    description: Optional[str] = None
    short_description: Optional[str] = None
    features: List[str] = field(default_factory=list)
    
    # Metadata
    url: Optional[str] = None
    scraped_at: datetime = field(default_factory=datetime.now)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert bike object to dictionary for export"""
        return {
            # Basic info
            'manufacturer': self.manufacturer,
            'model': self.model,
            'category': self.category,
            'subcategory': self.subcategory,
            'year': self.year,
            'sku': self.sku,
            
            # Pricing
            'price': self.pricing.price,
            'currency': self.pricing.currency,
            'original_price': self.pricing.original_price,
            'discount_percentage': self.pricing.discount_percentage,
            'is_on_sale': self.pricing.is_on_sale,
            
            # Specifications
            'frame_material': self.specifications.frame_material,
            'frame_size': self.specifications.frame_size,
            'wheel_size': self.specifications.wheel_size,
            'tire_size': self.specifications.tire_size,
            'gears': self.specifications.gears,
            'drivetrain': self.specifications.drivetrain,
            'brakes': self.specifications.brakes,
            'suspension': self.specifications.suspension,
            'weight': self.specifications.weight,
            'max_weight_capacity': self.specifications.max_weight_capacity,
            
            # Availability
            'in_stock': self.availability.in_stock,
            'stock_level': self.availability.stock_level,
            'available_sizes': ', '.join(self.availability.available_sizes),
            'available_colors': ', '.join(self.availability.available_colors),
            'estimated_delivery': self.availability.estimated_delivery,
            
            # Reviews
            'rating': self.reviews.rating,
            'review_count': self.reviews.review_count,
            'review_summary': self.reviews.review_summary,
            
            # Images
            'primary_image': self.images[0].url if self.images else None,
            'image_count': len(self.images),
            'all_images': ', '.join([img.url for img in self.images]),
            
            # Description
            'description': self.description,
            'short_description': self.short_description,
            'features': ', '.join(self.features),
            
            # Metadata
            'url': self.url,
            'scraped_at': self.scraped_at.isoformat()
        }
    
    def __str__(self) -> str:
        return f"{self.manufacturer} {self.model} - {self.category}"
