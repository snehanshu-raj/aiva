import React, { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, Polyline, Tooltip } from 'react-leaflet';
import { X, Navigation } from 'lucide-react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default Leaflet markers in React
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

// Custom icon for current location
const currentLocationIcon = new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});

// Custom icon for captures (Red)
const captureIcon = new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});

// Haversine formula to calculate distance between two points in meters
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371e3; // Earth radius in meters
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180;
    const Δφ = (lat2 - lat1) * Math.PI / 180;
    const Δλ = (lon2 - lon1) * Math.PI / 180;

    const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
        Math.cos(φ1) * Math.cos(φ2) *
        Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    return R * c;
}

// Component to recenter map when location changes
function RecenterMap({ lat, lng }) {
    const map = useMap();
    useEffect(() => {
        if (lat && lng) {
            map.setView([lat, lng], map.getZoom());
        }
    }, [lat, lng, map]);
    return null;
}

const MapGallery = ({ captures, currentLocation, onClose }) => {
    // Default center (will be overridden if location exists)
    const defaultCenter = [51.505, -0.09];

    const center = currentLocation
        ? [currentLocation.coords.latitude, currentLocation.coords.longitude]
        : (captures.length > 0 && captures[0].location
            ? [captures[0].location.latitude, captures[0].location.longitude]
            : defaultCenter);

    // Calculate nearest capture
    const nearestData = useMemo(() => {
        if (!currentLocation || captures.length === 0) return null;

        let minDistance = Infinity;
        let nearest = null;

        captures.forEach(capture => {
            if (capture.location && capture.location.latitude && capture.location.longitude) {
                const dist = calculateDistance(
                    currentLocation.coords.latitude,
                    currentLocation.coords.longitude,
                    capture.location.latitude,
                    capture.location.longitude
                );
                if (dist < minDistance) {
                    minDistance = dist;
                    nearest = capture;
                }
            }
        });

        return nearest ? { capture: nearest, distance: minDistance } : null;
    }, [currentLocation, captures]);

    return (
        <div className="map-gallery-overlay">
            <button className="close-map-btn" onClick={onClose}>
                <X size={24} />
            </button>

            <MapContainer center={center} zoom={13} scrollWheelZoom={true} style={{ height: '100%', width: '100%' }}>
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                {/* Current Location Marker */}
                {currentLocation && (
                    <>
                        <Marker
                            position={[currentLocation.coords.latitude, currentLocation.coords.longitude]}
                            icon={currentLocationIcon}
                        >
                            <Popup>
                                <div className="map-popup-content">
                                    <h3>You are here</h3>
                                    <p>Current Location</p>
                                </div>
                            </Popup>
                        </Marker>
                        <RecenterMap lat={currentLocation.coords.latitude} lng={currentLocation.coords.longitude} />
                    </>
                )}

                {/* Capture Markers */}
                {captures.map((capture) => {
                    if (!capture.location || !capture.location.latitude || !capture.location.longitude) return null;

                    return (
                        <Marker
                            key={capture.frame_id}
                            position={[capture.location.latitude, capture.location.longitude]}
                            icon={captureIcon}
                        >
                            <Popup>
                                <div className="map-popup-content">
                                    <img
                                        src={`/captures/${capture.filename}`}
                                        alt={capture.description}
                                        className="popup-image"
                                    />
                                    <p className="popup-desc">{capture.description}</p>
                                    <p className="popup-date">{new Date(capture.timestamp).toLocaleString()}</p>
                                    <a
                                        href={`https://www.google.com/maps/dir/?api=1&destination=${capture.location.latitude},${capture.location.longitude}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="navigate-btn"
                                        style={{
                                            display: 'inline-block',
                                            marginTop: '8px',
                                            padding: '6px 12px',
                                            background: '#2A81CB',
                                            color: 'white',
                                            textDecoration: 'none',
                                            borderRadius: '4px',
                                            fontSize: '12px',
                                            fontWeight: 'bold'
                                        }}
                                    >
                                        Navigate Here
                                    </a>
                                </div>
                            </Popup>
                        </Marker>
                    );
                })}

                {/* Nearest Neighbor Line */}
                {currentLocation && nearestData && (
                    <Polyline
                        positions={[
                            [currentLocation.coords.latitude, currentLocation.coords.longitude],
                            [nearestData.capture.location.latitude, nearestData.capture.location.longitude]
                        ]}
                        pathOptions={{ color: '#00f3ff', dashArray: '10, 10', weight: 3, opacity: 0.8 }}
                    >
                        <Tooltip permanent direction="center" offset={[0, 0]} className="distance-tooltip">
                            {nearestData.distance < 1000
                                ? `${Math.round(nearestData.distance)}m`
                                : `${(nearestData.distance / 1000).toFixed(1)}km`}
                        </Tooltip>
                    </Polyline>
                )}
            </MapContainer>

            <div className="map-legend">
                <div className="legend-item">
                    <Navigation size={16} fill="#2A81CB" color="#2A81CB" />
                    <span>You</span>
                </div>
                <div className="legend-item">
                    <div className="red-dot"></div>
                    <span>Captures</span>
                </div>
                {nearestData && (
                    <div className="legend-item">
                        <div style={{ width: 20, height: 3, background: '#00f3ff', borderStyle: 'dashed' }}></div>
                        <span>Nearest</span>
                    </div>
                )}
            </div>
        </div>
    );
};

export default MapGallery;
