import type { EventCategory, EventCreatePayload, EventScheduleEntry } from "@/lib/types";

export interface CreateEventFormValues {
  title: string;
  category: EventCategory;
  startISO: string;
  endISO: string;
  venueName: string;
  address: string;
  city: string;
  state: string;
  zipCode: string;
  latitude: number;
  longitude: number;
}

export function buildCreateEventPayload(
  values: CreateEventFormValues,
): EventCreatePayload {
  return {
    title: values.title.trim(),
    about: "",
    price: 0,
    total_capacity: 100,
    start_time: values.startISO,
    end_time: values.endISO,
    category: values.category,
    is_online: false,
    image_url: null,
    schedule: [] as EventScheduleEntry[],
    location: {
      longitude: values.longitude,
      latitude: values.latitude,
      venue_name: values.venueName.trim() || null,
      address: values.address.trim(),
      city: values.city.trim(),
      state: values.state.trim(),
      zip_code: values.zipCode.trim(),
    },
  };
}
