export interface Location {
  longitude: number;
  latitude: number;
  venue_name: string | null;
  address: string;
  city: string;
  state: string;
  zip_code: string;
}

export interface EventScheduleEntry {
  start_time: string;
  description: string;
}

export type EventCategory =
  | "Music"
  | "Business"
  | "Arts"
  | "Food"
  | "Sports"
  | "Education"
  | "Theater"
  | "Comedy"
  | "Festival"
  | "Conference"
  | "Workshop"
  | "Other";

export interface UserProfile {
  bio: string | null;
  location: string | null;
  website: string | null;
  twitter_handle: string | null;
  instagram_handle: string | null;
  facebook_handle: string | null;
  linkedin_handle: string | null;
  interests: string[];
}

export interface UserDetail {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  profile_photo_url: string | null;
  profile: UserProfile;
  events_created_count: number;
  events_attended_count: number;
}

export interface EventDetail {
  id: number;
  title: string;
  about: string;
  organizer_user_id: number;
  price: number;
  total_capacity: number;
  start_time: string;
  end_time: string;
  category: EventCategory;
  is_online: boolean;
  image_url: string | null;
  schedule: EventScheduleEntry[];
  location: Location;
  attending_count: number;
  favorites_count: number;
}

export type EventStatus = "pending" | "approved" | "rejected";

export interface PendingEventListItem {
  id: number;
  title: string;
  category: EventCategory;
  start_time: string;
  end_time: string;
  price: number;
  is_online: boolean;
  location: { venue_name: string | null; city: string; state: string };
  organizer_user_id: number;
  total_capacity: number;
  about: string;
  status: EventStatus;
}

export interface EventCreatePayload {
  title: string;
  about: string;
  price: number;
  total_capacity: number;
  start_time: string;
  end_time: string;
  category: EventCategory;
  is_online: boolean;
  image_url: string | null;
  schedule: EventScheduleEntry[];
  location: Location;
}
