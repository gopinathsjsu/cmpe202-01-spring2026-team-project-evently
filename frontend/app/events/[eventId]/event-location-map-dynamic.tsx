"use client";

import dynamic from "next/dynamic";
import type { EventLocationMapProps } from "./event-location-map";

const EventLocationMapLazy = dynamic(
  () => import("./event-location-map").then((m) => m.EventLocationMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex aspect-video items-center justify-center rounded-xl bg-zinc-200 text-sm text-zinc-400 dark:bg-zinc-800">
        Loading map…
      </div>
    ),
  },
);

export function EventLocationMapDynamic(props: EventLocationMapProps) {
  return <EventLocationMapLazy {...props} />;
}
