from datetime import datetime, timedelta
import pytz
from icalendar import Calendar, Event as ICalEvent
from bs4 import BeautifulSoup
import json
import os
from typing import Dict, List
import uuid

EVENTS_FILE = 'tracked_events.json'
CALENDAR_FILE = 'events.ics'


import requests
from bs4 import BeautifulSoup
import time
from typing import List, Dict
import re
def extract_event_info(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all matching div elements
    events = soup.find_all('div', class_=['col', 'col-xs-12', 'col-lg-12'])
    
    events_data = []
    for event in events:
        # Extract title and link
        title_div = event.find('div', class_='views-field-title')
        if title_div:
            title_link = title_div.find('a')
            if title_link:
                title = title_link.text
                link = title_link.get('href')
            else:
                title = title_div.text.strip()
                link = None
        else:
            title = None
            link = None
            
        # Extract date
        date_div = event.find('div', class_='views-field-field-event-date')
        date = date_div.find('span', class_='date-display-single').text.strip() if date_div else None
        
        # Extract location
        location_div = event.find('div', class_='views-field-field-event-location')
        location = location_div.find('div', class_='field-content').text.strip() if location_div else None
        
        events_data.append({
            'title': title,
            'date': date,
            'location': location,
            'link': link
        })
    
    return events_data
def fetch_events_page(url: str = "https://www.jamd.ac.il/calendar-of-events-page") -> str:
    """Fetch the events page with retries."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Raise an exception for bad status codes
            return response.text
        except requests.RequestException as e:
            if attempt == max_retries - 1:  # Last attempt
                raise Exception(f"Failed to fetch events page after {max_retries} attempts: {e}")
            print(f"Attempt {attempt + 1} failed, retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)

def load_tracked_events() -> Dict:
    """Load previously tracked events from JSON file."""
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"events": {}}

def save_tracked_events(events_dict: Dict) -> None:
    """Save tracked events to JSON file."""
    with open(EVENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(events_dict, f, ensure_ascii=False, indent=2)

def parse_hebrew_date(date_str: str) -> datetime:
    """Convert Hebrew date string to datetime object."""
    hebrew_to_english_months = {
        'ינואר': 'January',
        'פברואר': 'February',
        'מרץ': 'March',
        'אפריל': 'April',
        'מאי': 'May',
        'יוני': 'June',
        'יולי': 'July',
        'אוגוסט': 'August',
        'ספטמבר': 'September',
        'אוקטובר': 'October',
        'נובמבר': 'November',
        'דצמבר': 'December'
    }
    
    day, month_str = date_str.split(' ', 1)
    month_str, time = month_str.replace(',', '').rsplit(' ', 1)
    month_str = hebrew_to_english_months.get(month_str, month_str)
    date_string = f"{day} {month_str} 2025 {time}"
    return datetime.strptime(date_string, "%d %B %Y %H:%M")

def create_event_key(event_data: Dict) -> str:
    """Create a unique key for an event based on title, date, and location."""
    return f"{event_data['title']}_{event_data['date']}_{event_data['location']}"

def is_event_in_past(event_date: datetime) -> bool:
    """Check if event has already passed."""
    israel_tz = pytz.timezone('Asia/Jerusalem')
    now = datetime.now(israel_tz)
    return event_date < now

def create_ical_event(event_data: Dict, event_uid: str) -> ICalEvent:
    """Create an iCalendar event from event data."""
    event = ICalEvent()
    
    # Parse start time
    start_time = parse_hebrew_date(event_data['date'])
    israel_tz = pytz.timezone('Asia/Jerusalem')
    start_time = israel_tz.localize(start_time)
    
    # Set end time (default 2 hours after start)
    end_time = start_time + timedelta(hours=2)
    
    event.add('summary', event_data['title'])
    event.add('dtstart', start_time)
    event.add('dtend', end_time)
    event.add('location', event_data['location'])
    event.add('description', f"Event Link: https://www.jamd.ac.il{event_data['link']}")
    event.add('uid', event_uid)
    event.add('dtstamp', datetime.now(israel_tz))
    
    return event

def load_or_create_calendar() -> Calendar:
    """Load existing calendar or create new one."""
    if os.path.exists(CALENDAR_FILE):
        with open(CALENDAR_FILE, 'rb') as f:
            return Calendar.from_ical(f.read())
    
    cal = Calendar()
    cal.add('prodid', '-//JAMD Events Calendar//EN')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    return cal

def cleanup_past_events(calendar: Calendar, tracked_events: Dict) -> tuple:
    """Remove past events from both iCalendar and tracking file."""
    events_to_remove = []
    new_calendar = Calendar()
    new_calendar.add('prodid', calendar['prodid'])
    new_calendar.add('version', calendar['version'])
    new_calendar.add('calscale', calendar['calscale'])
    new_calendar.add('method', calendar['method'])
    
    israel_tz = pytz.timezone('Asia/Jerusalem')
    
    # Check tracked events
    for event_key, event_info in tracked_events['events'].items():
        event_date = israel_tz.localize(datetime.fromisoformat(event_info['date']))
        if is_event_in_past(event_date):
            events_to_remove.append(event_key)
            print(f"Removing past event: {event_info['title']}")
    
    # Remove from tracking dictionary
    for event_key in events_to_remove:
        tracked_events['events'].pop(event_key)
    
    # Keep only future events in calendar
    for component in calendar.walk():
        if component.name == "VEVENT":
            event_start = component.get('dtstart').dt
            if not is_event_in_past(event_start):
                new_calendar.add_component(component)
    
    return new_calendar, tracked_events

def update_calendar_with_events(events_data: List[Dict]) -> None:
    """Updates iCalendar with new events and tracks them in JSON."""
    tracked_events = load_tracked_events()
    calendar = load_or_create_calendar()
    
    # Cleanup past events
    calendar, tracked_events = cleanup_past_events(calendar, tracked_events)
    
    # Process new events
    for event_data in events_data:
        event_key = create_event_key(event_data)
        
        # Skip if event already tracked
        if event_key in tracked_events['events']:
            print(f"Event already exists: {event_data['title']}")
            continue
        
        # Parse date for checking if event is in past
        event_date = parse_hebrew_date(event_data['date'])
        if is_event_in_past(event_date):
            print(f"Skipping past event: {event_data['title']}")
            continue
        
        # Create unique ID for event
        event_uid = str(uuid.uuid4())
        
        # Create and add calendar event
        ical_event = create_ical_event(event_data, event_uid)
        calendar.add_component(ical_event)
        
        # Track the event
        tracked_events['events'][event_key] = {
            'title': event_data['title'],
            'date': event_date.isoformat(),
            'location': event_data['location'],
            'link': event_data['link'],
            'uid': event_uid
        }
        print(f"Added new event: {event_data['title']}")
    
    # Save updated calendar and tracking data
    with open(CALENDAR_FILE, 'wb') as f:
        f.write(calendar.to_ical())
    save_tracked_events(tracked_events)

if __name__ == "__main__":
    try:
        # Your existing scraping code here
        html_content = fetch_events_page()
        
        events = extract_event_info(html_content)  # Using your existing extract_event_info function
        update_calendar_with_events(events)
        print("Calendar update completed successfully")
        print(f"Calendar file created/updated at: {os.path.abspath(CALENDAR_FILE)}")
    except Exception as e:
        print(f"Error during calendar update: {e}")
