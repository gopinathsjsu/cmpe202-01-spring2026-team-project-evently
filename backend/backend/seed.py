"""Seed the database with sample events.

Usage:
    source .env && uv run python -m backend.seed
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

from pymongo.asynchronous.mongo_client import AsyncMongoClient

logger = logging.getLogger(__name__)

SAMPLE_EVENTS: list[dict[str, Any]] = [
    {
        "id": 1,
        "title": "Summer Music Festival 2026",
        "about": "Three days of live music across five stages featuring top artists from around the world. Food trucks, art installations, and a vibrant community atmosphere.",
        "organizer_user_id": 1,
        "price": 0.0,
        "total_capacity": 5000,
        "start_time": datetime(2026, 6, 20, 12, 0),
        "end_time": datetime(2026, 6, 22, 23, 0),
        "category": "Music",
        "schedule": [
            {"start_time": datetime(2026, 6, 20, 12, 0), "description": "Gates open"},
            {
                "start_time": datetime(2026, 6, 20, 14, 0),
                "description": "Opening act on Main Stage",
            },
            {
                "start_time": datetime(2026, 6, 20, 20, 0),
                "description": "Headliner performance",
            },
        ],
        "location": {
            "longitude": -73.9654,
            "latitude": 40.7829,
            "venue_name": "Central Park",
            "address": "Central Park West",
            "city": "New York",
            "state": "NY",
            "zip_code": "10024",
        },
    },
    {
        "id": 2,
        "title": "Tech Conference 2026",
        "about": "A premier technology conference featuring keynotes from industry leaders, hands-on workshops, and networking opportunities for developers and entrepreneurs.",
        "organizer_user_id": 2,
        "price": 0.0,
        "total_capacity": 2000,
        "start_time": datetime(2026, 7, 10, 9, 0),
        "end_time": datetime(2026, 7, 12, 17, 0),
        "category": "Conference",
        "schedule": [
            {
                "start_time": datetime(2026, 7, 10, 9, 0),
                "description": "Registration and breakfast",
            },
            {
                "start_time": datetime(2026, 7, 10, 10, 0),
                "description": "Opening keynote",
            },
            {
                "start_time": datetime(2026, 7, 10, 14, 0),
                "description": "Afternoon workshops",
            },
        ],
        "location": {
            "longitude": -122.4000,
            "latitude": 37.7850,
            "venue_name": None,
            "address": "747 Howard St",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": "94103",
        },
    },
    {
        "id": 3,
        "title": "Art Gallery Opening",
        "about": "Exclusive opening night for a contemporary art exhibition showcasing works by emerging artists. Wine and hors d'oeuvres provided.",
        "organizer_user_id": 3,
        "price": 0.0,
        "total_capacity": 300,
        "start_time": datetime(2026, 5, 15, 18, 0),
        "end_time": datetime(2026, 5, 15, 22, 0),
        "category": "Other",
        "schedule": [
            {
                "start_time": datetime(2026, 5, 15, 18, 0),
                "description": "Doors open with welcome drinks",
            },
            {
                "start_time": datetime(2026, 5, 15, 19, 0),
                "description": "Artist talk and Q&A",
            },
        ],
        "location": {
            "longitude": -73.9580,
            "latitude": 40.7614,
            "venue_name": "Brooklyn Museum",
            "address": "200 Eastern Pkwy",
            "city": "Brooklyn",
            "state": "NY",
            "zip_code": "11238",
        },
    },
    {
        "id": 4,
        "title": "Morning Yoga Session",
        "about": "Start your day with a peaceful outdoor yoga session suitable for all skill levels. Mats provided. Led by certified instructor Maria Chen.",
        "organizer_user_id": 4,
        "price": 0.0,
        "total_capacity": 100,
        "start_time": datetime(2026, 4, 5, 7, 0),
        "end_time": datetime(2026, 4, 5, 8, 30),
        "category": "Sports",
        "schedule": [
            {
                "start_time": datetime(2026, 4, 5, 7, 0),
                "description": "Warm-up and stretching",
            },
            {"start_time": datetime(2026, 4, 5, 7, 30), "description": "Flow sequence"},
            {
                "start_time": datetime(2026, 4, 5, 8, 15),
                "description": "Cool-down and meditation",
            },
        ],
        "location": {
            "longitude": -118.4965,
            "latitude": 34.0259,
            "venue_name": "Riverside Park",
            "address": "1500 Riverside Dr",
            "city": "Los Angeles",
            "state": "CA",
            "zip_code": "90039",
        },
    },
    {
        "id": 5,
        "title": "Startup Networking Mixer",
        "about": "Connect with fellow founders, investors, and tech professionals in a casual setting. Lightning pitches, open bar, and plenty of time to mingle.",
        "organizer_user_id": 2,
        "price": 0.0,
        "total_capacity": 150,
        "start_time": datetime(2026, 5, 20, 18, 0),
        "end_time": datetime(2026, 5, 20, 21, 0),
        "category": "Conference",
        "schedule": [
            {
                "start_time": datetime(2026, 5, 20, 18, 0),
                "description": "Doors open and networking",
            },
            {
                "start_time": datetime(2026, 5, 20, 19, 0),
                "description": "Lightning pitch round",
            },
            {
                "start_time": datetime(2026, 5, 20, 20, 0),
                "description": "Open networking",
            },
        ],
        "location": {
            "longitude": -74.0060,
            "latitude": 40.7128,
            "venue_name": "WeWork Manhattan",
            "address": "154 W 14th St",
            "city": "New York",
            "state": "NY",
            "zip_code": "10011",
        },
    },
    {
        "id": 6,
        "title": "Comedy Night Live",
        "about": "An evening of stand-up comedy featuring five of the best up-and-coming comedians. Two-drink minimum. Ages 21+.",
        "organizer_user_id": 5,
        "price": 0.0,
        "total_capacity": 250,
        "start_time": datetime(2026, 4, 18, 20, 0),
        "end_time": datetime(2026, 4, 18, 23, 0),
        "category": "Comedy",
        "schedule": [
            {
                "start_time": datetime(2026, 4, 18, 20, 0),
                "description": "Doors and bar open",
            },
            {
                "start_time": datetime(2026, 4, 18, 20, 30),
                "description": "Host introduction",
            },
            {
                "start_time": datetime(2026, 4, 18, 20, 45),
                "description": "First comedian",
            },
        ],
        "location": {
            "longitude": -74.0001,
            "latitude": 40.7264,
            "venue_name": "Comedy Cellar",
            "address": "117 MacDougal St",
            "city": "New York",
            "state": "NY",
            "zip_code": "10012",
        },
    },
    {
        "id": 7,
        "title": "Food & Wine Festival",
        "about": "Sample dishes from 40+ local restaurants paired with wines from boutique vineyards. Live cooking demonstrations and celebrity chef meet-and-greets.",
        "organizer_user_id": 6,
        "price": 75.0,
        "total_capacity": 3000,
        "start_time": datetime(2026, 8, 8, 11, 0),
        "end_time": datetime(2026, 8, 8, 20, 0),
        "category": "Festival",
        "schedule": [
            {
                "start_time": datetime(2026, 8, 8, 11, 0),
                "description": "Festival gates open",
            },
            {
                "start_time": datetime(2026, 8, 8, 13, 0),
                "description": "Live cooking demo: Chef Alex",
            },
            {
                "start_time": datetime(2026, 8, 8, 16, 0),
                "description": "Wine tasting masterclass",
            },
        ],
        "location": {
            "longitude": -122.3321,
            "latitude": 47.6062,
            "venue_name": "Pike Place Market Grounds",
            "address": "85 Pike St",
            "city": "Seattle",
            "state": "WA",
            "zip_code": "98101",
        },
    },
    {
        "id": 8,
        "title": "Photography Workshop",
        "about": "Learn portrait and landscape photography techniques from a professional photographer. Bring your own camera. All skill levels welcome.",
        "organizer_user_id": 7,
        "price": 45.0,
        "total_capacity": 30,
        "start_time": datetime(2026, 5, 3, 10, 0),
        "end_time": datetime(2026, 5, 3, 16, 0),
        "category": "Workshop",
        "schedule": [
            {
                "start_time": datetime(2026, 5, 3, 10, 0),
                "description": "Introduction and camera settings",
            },
            {
                "start_time": datetime(2026, 5, 3, 12, 0),
                "description": "Outdoor shooting session",
            },
            {
                "start_time": datetime(2026, 5, 3, 14, 0),
                "description": "Editing and post-processing",
            },
        ],
        "location": {
            "longitude": -122.4194,
            "latitude": 37.7749,
            "venue_name": "SF Art Institute",
            "address": "800 Chestnut St",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": "94133",
        },
    },
    {
        "id": 9,
        "title": "Jazz in the Park",
        "about": "An afternoon of smooth jazz performed by the Bay Area Jazz Ensemble. Bring a blanket and a picnic. Family-friendly event.",
        "organizer_user_id": 1,
        "price": 0.0,
        "total_capacity": 800,
        "start_time": datetime(2026, 6, 7, 14, 0),
        "end_time": datetime(2026, 6, 7, 18, 0),
        "category": "Music",
        "schedule": [
            {"start_time": datetime(2026, 6, 7, 14, 0), "description": "Opening set"},
            {
                "start_time": datetime(2026, 6, 7, 16, 0),
                "description": "Featured artist performance",
            },
        ],
        "location": {
            "longitude": -122.4269,
            "latitude": 37.7694,
            "venue_name": "Golden Gate Park",
            "address": "501 Stanyan St",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": "94117",
        },
    },
    {
        "id": 10,
        "title": "Marathon Training Run",
        "about": "Group training run for the upcoming city marathon. 10-mile route along the waterfront. All paces welcome. Water stations provided.",
        "organizer_user_id": 4,
        "price": 0.0,
        "total_capacity": 500,
        "start_time": datetime(2026, 3, 22, 6, 30),
        "end_time": datetime(2026, 3, 22, 10, 0),
        "category": "Sports",
        "schedule": [
            {
                "start_time": datetime(2026, 3, 22, 6, 30),
                "description": "Warm-up and group stretch",
            },
            {"start_time": datetime(2026, 3, 22, 7, 0), "description": "Run starts"},
        ],
        "location": {
            "longitude": -122.3893,
            "latitude": 37.7983,
            "venue_name": "Embarcadero",
            "address": "Pier 39",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": "94133",
        },
    },
    {
        "id": 11,
        "title": "Indie Film Screening",
        "about": "Premiere screening of three award-winning independent short films followed by a panel discussion with the directors.",
        "organizer_user_id": 3,
        "price": 15.0,
        "total_capacity": 200,
        "start_time": datetime(2026, 4, 25, 19, 0),
        "end_time": datetime(2026, 4, 25, 22, 30),
        "category": "Other",
        "schedule": [
            {
                "start_time": datetime(2026, 4, 25, 19, 0),
                "description": "Welcome and introduction",
            },
            {
                "start_time": datetime(2026, 4, 25, 19, 15),
                "description": "Screening begins",
            },
            {
                "start_time": datetime(2026, 4, 25, 21, 30),
                "description": "Director panel Q&A",
            },
        ],
        "location": {
            "longitude": -118.3287,
            "latitude": 34.0928,
            "venue_name": "The Egyptian Theatre",
            "address": "6712 Hollywood Blvd",
            "city": "Los Angeles",
            "state": "CA",
            "zip_code": "90028",
        },
    },
    {
        "id": 12,
        "title": "Salsa Dance Night",
        "about": "Hot salsa dancing night with a live Latin band. Beginner lesson at 8 PM, open dancing at 9. No partner needed!",
        "organizer_user_id": 5,
        "price": 20.0,
        "total_capacity": 400,
        "start_time": datetime(2026, 5, 9, 20, 0),
        "end_time": datetime(2026, 5, 10, 1, 0),
        "category": "Music",
        "schedule": [
            {
                "start_time": datetime(2026, 5, 9, 20, 0),
                "description": "Beginner salsa lesson",
            },
            {
                "start_time": datetime(2026, 5, 9, 21, 0),
                "description": "Live band and open floor",
            },
        ],
        "location": {
            "longitude": -80.1918,
            "latitude": 25.7617,
            "venue_name": "Mango's Tropical Cafe",
            "address": "900 Ocean Dr",
            "city": "Miami",
            "state": "FL",
            "zip_code": "33139",
        },
    },
    {
        "id": 13,
        "title": "Hackathon: Build for Good",
        "about": "48-hour hackathon focused on building tech solutions for nonprofits. Prizes, mentors, and free meals included. Teams of 2-5.",
        "organizer_user_id": 2,
        "price": 0.0,
        "total_capacity": 200,
        "start_time": datetime(2026, 9, 12, 18, 0),
        "end_time": datetime(2026, 9, 14, 18, 0),
        "category": "Conference",
        "schedule": [
            {
                "start_time": datetime(2026, 9, 12, 18, 0),
                "description": "Kickoff and team formation",
            },
            {
                "start_time": datetime(2026, 9, 13, 9, 0),
                "description": "Hacking continues",
            },
            {
                "start_time": datetime(2026, 9, 14, 15, 0),
                "description": "Demos and judging",
            },
        ],
        "location": {
            "longitude": -122.0084,
            "latitude": 37.3382,
            "venue_name": "San Jose Convention Center",
            "address": "150 W San Carlos St",
            "city": "San Jose",
            "state": "CA",
            "zip_code": "95113",
        },
    },
    {
        "id": 14,
        "title": "Shakespeare in the Park",
        "about": "Free outdoor performance of A Midsummer Night's Dream by the City Theater Company. Bring blankets and lawn chairs.",
        "organizer_user_id": 3,
        "price": 0.0,
        "total_capacity": 600,
        "start_time": datetime(2026, 7, 4, 19, 0),
        "end_time": datetime(2026, 7, 4, 21, 30),
        "category": "Theater",
        "schedule": [
            {
                "start_time": datetime(2026, 7, 4, 19, 0),
                "description": "Pre-show entertainment",
            },
            {
                "start_time": datetime(2026, 7, 4, 19, 30),
                "description": "Performance begins",
            },
        ],
        "location": {
            "longitude": -87.6298,
            "latitude": 41.8781,
            "venue_name": "Millennium Park",
            "address": "201 E Randolph St",
            "city": "Chicago",
            "state": "IL",
            "zip_code": "60602",
        },
    },
    {
        "id": 15,
        "title": "Ceramics Workshop",
        "about": "Hands-on pottery workshop. Learn wheel throwing and hand building techniques. All materials included. Take home your creation!",
        "organizer_user_id": 7,
        "price": 65.0,
        "total_capacity": 20,
        "start_time": datetime(2026, 4, 12, 10, 0),
        "end_time": datetime(2026, 4, 12, 14, 0),
        "category": "Workshop",
        "schedule": [
            {
                "start_time": datetime(2026, 4, 12, 10, 0),
                "description": "Introduction to clay and tools",
            },
            {
                "start_time": datetime(2026, 4, 12, 11, 0),
                "description": "Wheel throwing practice",
            },
            {
                "start_time": datetime(2026, 4, 12, 13, 0),
                "description": "Glazing and finishing",
            },
        ],
        "location": {
            "longitude": -122.2711,
            "latitude": 37.8044,
            "venue_name": "Oakland Clay Studio",
            "address": "620 16th St",
            "city": "Oakland",
            "state": "CA",
            "zip_code": "94612",
        },
    },
    {
        "id": 16,
        "title": "Outdoor Rock Climbing",
        "about": "Guided outdoor climbing at Castle Rock State Park. Gear provided. Must be 16+ and in reasonable physical condition.",
        "organizer_user_id": 4,
        "price": 55.0,
        "total_capacity": 25,
        "start_time": datetime(2026, 5, 17, 8, 0),
        "end_time": datetime(2026, 5, 17, 15, 0),
        "category": "Sports",
        "schedule": [
            {
                "start_time": datetime(2026, 5, 17, 8, 0),
                "description": "Meet and safety briefing",
            },
            {
                "start_time": datetime(2026, 5, 17, 9, 0),
                "description": "Climbing session 1",
            },
            {"start_time": datetime(2026, 5, 17, 12, 0), "description": "Lunch break"},
            {
                "start_time": datetime(2026, 5, 17, 13, 0),
                "description": "Climbing session 2",
            },
        ],
        "location": {
            "longitude": -122.0975,
            "latitude": 37.2306,
            "venue_name": "Castle Rock State Park",
            "address": "15000 Skyline Blvd",
            "city": "Los Gatos",
            "state": "CA",
            "zip_code": "95033",
        },
    },
    {
        "id": 17,
        "title": "Electronic Music Night",
        "about": "Underground electronic music event featuring four DJs spinning house, techno, and drum & bass. Full bar and light show.",
        "organizer_user_id": 1,
        "price": 30.0,
        "total_capacity": 500,
        "start_time": datetime(2026, 6, 28, 22, 0),
        "end_time": datetime(2026, 6, 29, 4, 0),
        "category": "Music",
        "schedule": [
            {
                "start_time": datetime(2026, 6, 28, 22, 0),
                "description": "Doors open, DJ 1",
            },
            {
                "start_time": datetime(2026, 6, 29, 0, 0),
                "description": "Headliner DJ set",
            },
            {"start_time": datetime(2026, 6, 29, 2, 0), "description": "Closing set"},
        ],
        "location": {
            "longitude": -122.4194,
            "latitude": 37.7749,
            "venue_name": "The Midway",
            "address": "900 Marin St",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": "94124",
        },
    },
    {
        "id": 18,
        "title": "Book Club Meetup",
        "about": "Monthly book club meeting discussing 'Project Hail Mary' by Andy Weir. New members always welcome. Coffee provided.",
        "organizer_user_id": 6,
        "price": 0.0,
        "total_capacity": 40,
        "start_time": datetime(2026, 4, 1, 18, 30),
        "end_time": datetime(2026, 4, 1, 20, 30),
        "category": "Other",
        "schedule": [
            {
                "start_time": datetime(2026, 4, 1, 18, 30),
                "description": "Arrival and coffee",
            },
            {
                "start_time": datetime(2026, 4, 1, 19, 0),
                "description": "Discussion begins",
            },
        ],
        "location": {
            "longitude": -122.4089,
            "latitude": 37.7855,
            "venue_name": "City Lights Bookstore",
            "address": "261 Columbus Ave",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": "94133",
        },
    },
    {
        "id": 19,
        "title": "Charity 5K Run",
        "about": "Annual charity run benefiting local children's hospitals. Walk or run! Medals for all finishers. Post-race brunch included.",
        "organizer_user_id": 4,
        "price": 35.0,
        "total_capacity": 1000,
        "start_time": datetime(2026, 10, 3, 8, 0),
        "end_time": datetime(2026, 10, 3, 12, 0),
        "category": "Sports",
        "schedule": [
            {
                "start_time": datetime(2026, 10, 3, 8, 0),
                "description": "Check-in and bib pickup",
            },
            {"start_time": datetime(2026, 10, 3, 9, 0), "description": "Race start"},
            {
                "start_time": datetime(2026, 10, 3, 10, 30),
                "description": "Awards and brunch",
            },
        ],
        "location": {
            "longitude": -71.0589,
            "latitude": 42.3601,
            "venue_name": "Boston Common",
            "address": "139 Tremont St",
            "city": "Boston",
            "state": "MA",
            "zip_code": "02111",
        },
    },
    {
        "id": 20,
        "title": "AI & Machine Learning Summit",
        "about": "Deep dive into the latest advances in artificial intelligence and machine learning. Research paper presentations, demos, and workshops.",
        "organizer_user_id": 2,
        "price": 150.0,
        "total_capacity": 800,
        "start_time": datetime(2026, 8, 20, 9, 0),
        "end_time": datetime(2026, 8, 21, 17, 0),
        "category": "Conference",
        "schedule": [
            {"start_time": datetime(2026, 8, 20, 9, 0), "description": "Registration"},
            {
                "start_time": datetime(2026, 8, 20, 10, 0),
                "description": "Keynote: The Future of AI",
            },
            {
                "start_time": datetime(2026, 8, 20, 14, 0),
                "description": "Hands-on ML workshop",
            },
            {
                "start_time": datetime(2026, 8, 21, 9, 0),
                "description": "Day 2: Research presentations",
            },
        ],
        "location": {
            "longitude": -122.0084,
            "latitude": 37.3382,
            "venue_name": "San Jose Convention Center",
            "address": "150 W San Carlos St",
            "city": "San Jose",
            "state": "CA",
            "zip_code": "95113",
        },
    },
    {
        "id": 21,
        "title": "Open Mic Night",
        "about": "Showcase your talent! Singers, poets, comedians, and musicians all welcome. Sign up at the door. Free entry for performers.",
        "organizer_user_id": 5,
        "price": 10.0,
        "total_capacity": 150,
        "start_time": datetime(2026, 3, 28, 19, 0),
        "end_time": datetime(2026, 3, 28, 23, 0),
        "category": "Music",
        "schedule": [
            {
                "start_time": datetime(2026, 3, 28, 19, 0),
                "description": "Sign-up and sound check",
            },
            {
                "start_time": datetime(2026, 3, 28, 19, 30),
                "description": "Performances begin",
            },
        ],
        "location": {
            "longitude": -122.4194,
            "latitude": 37.7749,
            "venue_name": "The Chapel",
            "address": "777 Valencia St",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": "94110",
        },
    },
    {
        "id": 22,
        "title": "Farmers Market Grand Opening",
        "about": "Grand opening of the new downtown farmers market. Fresh produce, artisan goods, live music, and free samples from 30+ vendors.",
        "organizer_user_id": 6,
        "price": 0.0,
        "total_capacity": 2000,
        "start_time": datetime(2026, 4, 19, 8, 0),
        "end_time": datetime(2026, 4, 19, 14, 0),
        "category": "Festival",
        "schedule": [
            {"start_time": datetime(2026, 4, 19, 8, 0), "description": "Market opens"},
            {
                "start_time": datetime(2026, 4, 19, 10, 0),
                "description": "Live acoustic music",
            },
            {
                "start_time": datetime(2026, 4, 19, 12, 0),
                "description": "Cooking demonstration",
            },
        ],
        "location": {
            "longitude": -122.4098,
            "latitude": 37.7956,
            "venue_name": "Ferry Building",
            "address": "1 Ferry Building",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": "94111",
        },
    },
    {
        "id": 23,
        "title": "Improv Comedy Show",
        "about": "Fast-paced improvisational comedy based entirely on audience suggestions. Interactive, unpredictable, and guaranteed to make you laugh.",
        "organizer_user_id": 5,
        "price": 25.0,
        "total_capacity": 180,
        "start_time": datetime(2026, 5, 30, 20, 0),
        "end_time": datetime(2026, 5, 30, 22, 0),
        "category": "Comedy",
        "schedule": [
            {"start_time": datetime(2026, 5, 30, 20, 0), "description": "Doors open"},
            {"start_time": datetime(2026, 5, 30, 20, 30), "description": "Show begins"},
        ],
        "location": {
            "longitude": -87.6298,
            "latitude": 41.8781,
            "venue_name": "Second City",
            "address": "1616 N Wells St",
            "city": "Chicago",
            "state": "IL",
            "zip_code": "60614",
        },
    },
    {
        "id": 24,
        "title": "Blockchain & Web3 Workshop",
        "about": "Hands-on workshop covering smart contract development, DeFi protocols, and building dApps. Laptop required. Intermediate level.",
        "organizer_user_id": 2,
        "price": 80.0,
        "total_capacity": 50,
        "start_time": datetime(2026, 7, 18, 9, 0),
        "end_time": datetime(2026, 7, 18, 17, 0),
        "category": "Workshop",
        "schedule": [
            {
                "start_time": datetime(2026, 7, 18, 9, 0),
                "description": "Setup and intro to Solidity",
            },
            {"start_time": datetime(2026, 7, 18, 12, 0), "description": "Lunch break"},
            {
                "start_time": datetime(2026, 7, 18, 13, 0),
                "description": "Build and deploy a dApp",
            },
        ],
        "location": {
            "longitude": -122.4194,
            "latitude": 37.7749,
            "venue_name": "Galvanize SF",
            "address": "44 Tehama St",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": "94105",
        },
    },
]

ONLINE_EVENT_IDS = {2, 5, 13, 20, 24}

SAMPLE_ATTENDANCE: list[dict[str, Any]] = [
    {"event_id": eid, "user_id": uid, "status": "going", "checked_in_at": None}
    for eid, uid_count in [
        (1, 320),
        (2, 124),
        (3, 85),
        (4, 45),
        (5, 56),
        (6, 234),
        (7, 150),
        (8, 18),
        (9, 90),
        (10, 75),
        (11, 42),
        (12, 110),
        (13, 60),
        (14, 200),
        (15, 12),
        (16, 20),
        (17, 180),
        (18, 25),
        (19, 300),
        (20, 95),
        (21, 70),
        (22, 400),
        (23, 100),
        (24, 35),
    ]
    for uid in range(1, uid_count + 1)
]

SAMPLE_FAVORITES: list[dict[str, Any]] = [
    {"event_id": eid, "user_id": uid}
    for eid, uid_count in [
        (1, 50),
        (2, 30),
        (6, 80),
        (7, 45),
        (14, 60),
        (17, 40),
    ]
    for uid in range(1, uid_count + 1)
]


async def seed() -> None:
    logging.basicConfig(
        format="[%(levelname)s][%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )

    url = os.getenv("DATABASE_URL", "")
    if not url:
        logger.error("DATABASE_URL environment variable is not set.")
        return

    client: AsyncMongoClient[dict[str, Any]]
    async with AsyncMongoClient(url) as client:
        db: Any = client["evently"]

        for coll_name in ("events", "attendance", "event_favorites"):
            existing = await db[coll_name].count_documents({})
            if existing > 0:
                logger.info("Dropping %d docs from '%s'...", existing, coll_name)
                await db[coll_name].delete_many({})

        enriched = []
        for evt in SAMPLE_EVENTS:
            enriched.append(
                {
                    **evt,
                    "is_online": evt["id"] in ONLINE_EVENT_IDS,
                    "image_url": None,
                }
            )

        await db["events"].insert_many(enriched)
        await db["attendance"].insert_many(SAMPLE_ATTENDANCE)
        await db["event_favorites"].insert_many(SAMPLE_FAVORITES)

        ev_count = await db["events"].count_documents({})
        at_count = await db["attendance"].count_documents({})
        fv_count = await db["event_favorites"].count_documents({})
        logger.info(
            "Seeded %d events, %d attendance records, %d favorites.",
            ev_count,
            at_count,
            fv_count,
        )


if __name__ == "__main__":
    asyncio.run(seed())
