"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

type Props = { latitude: number; longitude: number };

export function EventLocationMap({ latitude, longitude }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const map = L.map(el).setView([latitude, longitude], 14);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);

    const icon = L.icon({
      iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
      iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
      shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
      iconSize: [25, 41],
      iconAnchor: [12, 41],
      shadowSize: [41, 41],
    });

    L.marker([latitude, longitude], { icon }).addTo(map);

    return () => {
      map.remove();
    };
  }, [latitude, longitude]);

  return <div ref={containerRef} className="z-0 mt-4 aspect-[16/9] w-full rounded-xl" />;
}
