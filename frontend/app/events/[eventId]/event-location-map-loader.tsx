"use client";

import dynamic from "next/dynamic";

const EventLocationMap = dynamic(
  () => import("./event-location-map").then((m) => m.EventLocationMap),
  { ssr: false },
);

export function EventLocationMapLoader(props: { latitude: number; longitude: number }) {
  return <EventLocationMap {...props} />;
}
