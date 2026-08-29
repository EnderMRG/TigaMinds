'use client';

import { Fragment, useEffect } from 'react';
import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip, Popup, Marker, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const RISK_COLORS: Record<string, string> = {
  LOW: '#22c55e',
  MEDIUM: '#f59e0b',
  HIGH: '#ef4444',
};

const HAZARD_COLORS: Record<string, string> = {
  low: '#22c55e',
  moderate: '#f59e0b',
  severe: '#ef4444',
};

interface Segment {
  coordinates: [number, number][];  // [lng, lat] pairs
  risk_level: string;
  risk_score: number;
  rainfall_intensity: number;
  hazard_type?: string | null;
  hazard_description?: string | null;
  severity?: string | null;
  corridor_name?: string | null;
}

interface RouteMapProps {
  origin: { lat: number; lng: number; name: string };
  destination: { lat: number; lng: number; name: string };
  segments: Segment[];
  alternateGeometry?: { type: string; coordinates: [number, number][] };
}

function AutoFit({ origin, destination }: { origin: RouteMapProps['origin']; destination: RouteMapProps['destination'] }) {
  const map = useMap();
  useEffect(() => {
    try {
      const bounds = L.latLngBounds([
        [origin.lat, origin.lng],
        [destination.lat, destination.lng],
      ]);
      map.fitBounds(bounds, { padding: [40, 40] });
    } catch {}
  }, [map, origin, destination]);
  return null;
}

export default function RouteMap({ origin, destination, segments, alternateGeometry }: RouteMapProps) {
  return (
    <MapContainer
      center={[origin.lat, origin.lng]}
      zoom={7}
      style={{ height: '100%', width: '100%', borderRadius: '12px' }}
      className="z-0"
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org">OpenStreetMap</a> contributors'
        maxZoom={19}
      />

      <AutoFit origin={origin} destination={destination} />

      {/* Color-coded route segments */}
      {segments.map((seg, i) => {
        const latLngs = seg.coordinates.map(([lng, lat]): [number, number] => [lat, lng]);
        const midpoint = latLngs[Math.floor(latLngs.length / 2)];
        return (
          <Fragment key={i}>
            <Polyline
              positions={latLngs}
              pathOptions={{
                color: RISK_COLORS[seg.risk_level] || '#888',
                weight: 5,
                opacity: 0.85,
              }}
            >
              <Tooltip sticky>
                <div className="text-xs font-medium">
                  <div>Risk: <strong>{seg.risk_level}</strong> ({(seg.risk_score * 100).toFixed(0)}%)</div>
                  <div>Rainfall: {(seg.rainfall_intensity * 100).toFixed(0)}%</div>
                </div>
              </Tooltip>
            </Polyline>
            {seg.hazard_type && midpoint && (
              <Marker
                position={midpoint}
                icon={L.divIcon({
                  className: 'hazard-marker',
                  html: `<span style="display:flex;width:24px;height:24px;align-items:center;justify-content:center;border-radius:50%;background:${HAZARD_COLORS[seg.severity || 'moderate'] || HAZARD_COLORS.moderate};border:2px solid white;color:white;font-weight:700;font-size:14px;box-shadow:0 1px 4px #0008">!</span>`,
                  iconSize: [24, 24],
                  iconAnchor: [12, 12],
                })}
              >
                <Popup>
                  <div className="text-xs max-w-[220px]">
                    <strong className="capitalize">{seg.hazard_type.replace('_', ' ')} risk</strong>
                    <p className="mt-1">{seg.hazard_description}</p>
                    <p className="mt-1 capitalize">Severity: {seg.severity || 'moderate'}</p>
                    {seg.corridor_name && <p className="mt-1 text-gray-500">{seg.corridor_name}</p>}
                  </div>
                </Popup>
              </Marker>
            )}
          </Fragment>
        );
      })}

      {/* Alternate route (dashed blue if present) */}
      {alternateGeometry && (
        <Polyline
          positions={(alternateGeometry.coordinates as [number, number][]).map(([lng, lat]): [number, number] => [lat, lng])}
          pathOptions={{ color: '#3b82f6', weight: 3, dashArray: '8 6', opacity: 0.65 }}
        >
          <Tooltip>Alternate Route (Lower Risk)</Tooltip>
        </Polyline>
      )}

      {/* Origin marker */}
      <CircleMarker
        center={[origin.lat, origin.lng]}
        radius={10}
        pathOptions={{ color: '#22c55e', fillColor: '#22c55e', fillOpacity: 1 }}
      >
        <Tooltip permanent direction="top" offset={[0, -10]}>
          <span className="text-xs font-semibold">🌿 {origin.name}</span>
        </Tooltip>
      </CircleMarker>

      {/* Destination marker */}
      <CircleMarker
        center={[destination.lat, destination.lng]}
        radius={10}
        pathOptions={{ color: '#8b5cf6', fillColor: '#8b5cf6', fillOpacity: 1 }}
      >
        <Tooltip permanent direction="top" offset={[0, -10]}>
          <span className="text-xs font-semibold">🏛️ {destination.name}</span>
        </Tooltip>
      </CircleMarker>
    </MapContainer>
  );
}
