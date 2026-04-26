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

export interface FullUserDetail extends UserDetail {
  email: string;
  phone_number: string | null;
  roles: string[];
}

export interface ActivityItem {
  event_id: number;
  event_title: string;
  event_image_url: string | null;
  event_end_time: string | null;
  action: "attended" | "created" | "registered";
  date: string;
}

export interface ActivityResponse {
  items: ActivityItem[];
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

export interface MyEventItem {
  id: number;
  title: string;
  start_time: string;
  end_time: string;
  category: string;
  is_online: boolean;
  image_url: string | null;
  location_summary: string;
  price: number;
  status: string | null;
  attending_count: number;
}

export interface MyEventsResponse {
  created: MyEventItem[];
  registered: MyEventItem[];
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

export type AttendeeStatus = "going" | "checked_in";

export interface EventAttendeeItem {
  user_id: number;
  first_name: string;
  last_name: string;
  email: string;
  profile_photo_url: string | null;
  status: AttendeeStatus;
  checked_in_at: string | null;
}

export interface EventAttendeesResponse {
  event_id: number;
  event_title: string;
  total_capacity: number;
  going_count: number;
  checked_in_count: number;
  attendees: EventAttendeeItem[];
}

export interface CheckInResponse {
  event_id: number;
  user_id: number;
  status: "checked_in";
  checked_in_at: string;
}

export interface UndoCheckInResponse {
  event_id: number;
  user_id: number;
  status: "going";
}

export interface RemoveAttendeeResponse {
  event_id: number;
  user_id: number;
  status: "cancelled";
  in_calendar: false;
  google_synced: boolean;
}
