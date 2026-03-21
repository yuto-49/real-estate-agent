import type { Property } from '../utils/types'

interface PropertyCardProps {
  property: Property
  onSelect?: (property: Property) => void
}

export default function PropertyCard({ property, onSelect }: PropertyCardProps) {
  return (
    <div className="property-card" onClick={() => onSelect?.(property)}>
      <h3>{property.address}</h3>
      <div className="property-details">
        <span className="price">${property.asking_price?.toLocaleString()}</span>
        {property.bedrooms && <span>{property.bedrooms} bed</span>}
        {property.bathrooms && <span>{property.bathrooms} bath</span>}
        {property.sqft && <span>{property.sqft.toLocaleString()} sqft</span>}
        {property.property_type && <span className="type">{property.property_type}</span>}
      </div>
      <div className="property-status">
        <span className={`status ${property.status}`}>{property.status}</span>
      </div>
    </div>
  )
}
