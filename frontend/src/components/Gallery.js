import React, { useEffect } from 'react';
import { motion } from 'framer-motion';
import { X, Calendar, Clock, MapPin, Trash2 } from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Fix for default Leaflet icons in React
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl: require('leaflet/dist/images/marker-icon.png'),
  shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

const Gallery = ({ captures, onClose, onDelete }) => {
  return (
    <motion.div
      className="gallery-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <div className="gallery-container">
        <div className="gallery-header">
          <h2>Captured Moments</h2>
          <button className="close-btn" onClick={onClose}>
            <X size={24} />
          </button>
        </div>

        {captures.length === 0 ? (
          <div className="empty-gallery">
            <p>No captures yet. Ask AIVA to describe something!</p>
          </div>
        ) : (
          <div className="gallery-grid">
            {captures.map((capture) => (
              <motion.div
                key={capture.filename} // Use filename as key
                className="gallery-item"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <div className="image-wrapper">
                  {/* Use backend URL for image */}
                  <img
                    src={`/captures/${capture.filename}`}
                    alt={capture.description}
                    onError={(e) => {
                      e.target.onerror = null;
                      e.target.src = 'https://via.placeholder.com/400x300?text=Image+Not+Found';
                    }}
                  />
                </div>
                <div className="content-wrapper">
                  <div className="content-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                    <p className="description">{capture.description}</p>
                    <button
                      className="delete-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (window.confirm('Delete this capture?')) {
                          onDelete(capture.frame_id || capture.filename.split('_')[0]);
                        }
                      }}
                      title="Delete capture"
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>

                  <div className="meta-info">
                    <span><Calendar size={14} /> {new Date(capture.timestamp).toLocaleDateString()}</span>
                    <span><Clock size={14} /> {new Date(capture.timestamp).toLocaleTimeString()}</span>
                  </div>

                  {capture.location && (
                    <div className="map-wrapper">
                      <div className="map-header" style={{ justifyContent: 'space-between' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <MapPin size={14} />
                          <span>Location</span>
                        </div>
                        <a
                          href={`https://www.google.com/maps/search/?api=1&query=${capture.location.latitude},${capture.location.longitude}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ fontSize: '0.8rem', color: '#4a9eff', textDecoration: 'none', fontWeight: 500 }}
                          onClick={(e) => e.stopPropagation()}
                        >
                          Open in Maps ↗
                        </a>
                      </div>
                      <MapContainer
                        center={[capture.location.latitude, capture.location.longitude]}
                        zoom={15}
                        scrollWheelZoom={false}
                        className="leaflet-map"
                      >
                        <TileLayer
                          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                        />
                        <Marker
                          position={[capture.location.latitude, capture.location.longitude]}
                          eventHandlers={{
                            click: () => {
                              window.open(`https://www.google.com/maps/search/?api=1&query=${capture.location.latitude},${capture.location.longitude}`, '_blank');
                            },
                          }}
                        >
                          <Popup>
                            Captured here<br />
                            <span style={{ fontSize: '0.8em', color: '#666' }}>Click marker to navigate</span>
                          </Popup>
                        </Marker>
                      </MapContainer>
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
};

export default Gallery;
