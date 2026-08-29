'use client';

import { useEffect, useRef, useCallback } from 'react';
import { MapContainer, TileLayer, ImageOverlay, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet-draw/dist/leaflet.draw.css';
import 'leaflet-draw';

// Fix Leaflet's default icon URLs broken by Webpack/Next.js bundling
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

interface DrawControlProps {
  onPolygonDrawn: (geometry: any, bounds: L.LatLngBounds) => void;
}

function DrawControl({ onPolygonDrawn }: DrawControlProps) {
  const map = useMap();
  const drawnItems = useRef(new L.FeatureGroup());

  const handleDrawn = useCallback(
    (geometry: any, bounds: L.LatLngBounds) => {
      onPolygonDrawn(geometry, bounds);
    },
    [onPolygonDrawn]
  );

  useEffect(() => {
    map.addLayer(drawnItems.current);

    const drawControl = new (L.Control as any).Draw({
      draw: {
        polygon: {
          allowIntersection: false,
          shapeOptions: { color: '#22c55e', fillColor: '#22c55e', fillOpacity: 0.18, weight: 2 },
        },
        rectangle: {
          shapeOptions: { color: '#22c55e', fillColor: '#22c55e', fillOpacity: 0.18, weight: 2 },
        },
        circle: false,
        circlemarker: false,
        marker: false,
        polyline: false,
      },
      edit: { featureGroup: drawnItems.current },
    });

    map.addControl(drawControl);

    const onCreate = (e: any) => {
      drawnItems.current.clearLayers();
      drawnItems.current.addLayer(e.layer);
      const geojson = e.layer.toGeoJSON();
      const bounds = e.layer.getBounds() as L.LatLngBounds;
      handleDrawn(geojson.geometry, bounds);
    };

    map.on(L.Draw.Event.CREATED, onCreate);

    return () => {
      map.off(L.Draw.Event.CREATED, onCreate);
      map.removeControl(drawControl);
      map.removeLayer(drawnItems.current);
    };
  }, [map, handleDrawn]);

  return null;
}

interface SatelliteMapDrawProps {
  onPolygonDrawn: (geometry: any, bounds: L.LatLngBounds) => void;
  heatmapDataUrl?: string;
  heatmapBounds?: [[number, number], [number, number]];
  center?: [number, number];
  zoom?: number;
}

export default function SatelliteMapDraw({
  onPolygonDrawn,
  heatmapDataUrl,
  heatmapBounds,
  center = [26.57, 93.84],
  zoom = 13,
}: SatelliteMapDrawProps) {
  return (
    <MapContainer
      center={center}
      zoom={zoom}
      style={{ height: '420px', width: '100%', borderRadius: '12px' }}
      className="z-0"
    >
      {/* Esri imagery keeps the imagery and attribution provider aligned. */}
      <TileLayer
        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        attribution="Tiles &copy; Esri"
        maxZoom={20}
      />
      <TileLayer
        url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
        attribution="Labels &copy; Esri"
        maxZoom={20}
        pane="overlayPane"
      />

      <DrawControl onPolygonDrawn={onPolygonDrawn} />

      {heatmapDataUrl && heatmapBounds && (
        <ImageOverlay
          url={heatmapDataUrl}
          bounds={heatmapBounds}
          opacity={0.72}
          zIndex={400}
        />
      )}
    </MapContainer>
  );
}
