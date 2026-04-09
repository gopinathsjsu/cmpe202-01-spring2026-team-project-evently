"use client";

import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Serve marker assets from /public so iconUrl is always a real string (Turbopack
// can omit .src on imported PNGs, which triggers "iconUrl not set").
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: string })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl: "/leaflet/marker-icon.png",
  iconRetinaUrl: "/leaflet/marker-icon-2x.png",
  shadowUrl: "/leaflet/marker-shadow.png",
});

export type EventLocationMapProps = {
  latitude: number;
  longitude: number;
  /** Shown in the marker popup */
  popupTitle: string;
  /** One-line address for “Open in OpenStreetMap” link */
  mapsQuery: string;
};

function isValidLatLng(lat: number, lng: number): boolean {
  return (
    Number.isFinite(lat) &&
    Number.isFinite(lng) &&
    lat >= -90 &&
    lat <= 90 &&
    lng >= -180 &&
    lng <= 180
  );
}

export function EventLocationMap({
  latitude,
  longitude,
  popupTitle,
  mapsQuery,
}: EventLocationMapProps) {
  if (!isValidLatLng(latitude, longitude)) {
    return (
      <div className="flex aspect-video items-center justify-center rounded-xl bg-zinc-200 text-sm text-zinc-500 dark:bg-zinc-800">
        Map unavailable for this location.
      </div>
    );
  }

  const position: [number, number] = [latitude, longitude];
  const osmUrl = `https://www.openstreetmap.org/?mlat=${latitude}&mlon=${longitude}#map=16/${latitude}/${longitude}`;

  return (
    <div
      className="aspect-video w-full overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800"
      role="region"
      aria-label="Interactive map of the event venue"
    >
      <MapContainer
        center={position}
        zoom={15}
        className="z-0 h-full w-full min-h-[220px] [&_.leaflet-control-attribution]:text-[10px] [&_.leaflet-control-zoom]:rounded-md [&_.leaflet-control-zoom]:border [&_.leaflet-control-zoom]:border-zinc-200 [&_.leaflet-control-zoom_a]:bg-white [&_.leaflet-control-zoom_a]:text-zinc-800 dark:[&_.leaflet-control-zoom]:border-zinc-700 dark:[&_.leaflet-control-zoom_a]:bg-zinc-900 dark:[&_.leaflet-control-zoom_a]:text-zinc-200"
        scrollWheelZoom
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Marker position={position}>
          <Popup>
            <div className="min-w-[160px] text-sm">
              <p className="font-medium text-zinc-900">{popupTitle}</p>
              <p className="mt-1 text-xs text-zinc-600">{mapsQuery}</p>
              <a
                href={osmUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-block text-xs font-medium text-blue-600 underline"
              >
                Open in OpenStreetMap
              </a>
            </div>
          </Popup>
        </Marker>
      </MapContainer>
    </div>
  );
}
