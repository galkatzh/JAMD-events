#!/usr/bin/env python3
"""
Scrape calendar events from jamd.ac.il calendar AJAX endpoint
"""

import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import csv
import re

def fetch_month_calendar(year, month):
    """Fetch calendar data for a specific month"""
    
    url = "https://www.jamd.ac.il/calendar-of-events-page"
    
    # Format month as YYYY-MM
    month_str = f"{year}-{month:02d}"
    
    params = {
        'page': '0',
        'view_name': 'calendar_event',
        'view_display_id': 'block_calendar_secondary',
        'view_args': month_str,
        'view_path': 'node/8289',
        'view_base_path': 'calendar-node-field-event-date/month',
        'view_dom_id': '43a9961c501d60faa3159e34295a5dcb',
        'pager_element': '0',
        'mini': month_str,
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching {month_str}: {e}")
        return None

def extract_events_from_html(html_content):
    """Extract event information from the HTML calendar"""
    
    events = []
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all event items
    event_divs = soup.find_all('div', class_='view-item-calendar_event')
    
    for event_div in event_divs:
        event_data = {}
        
        # Extract title
        title_link = event_div.find('div', class_='views-field-title')
        if title_link:
            link = title_link.find('a')
            if link:
                event_data['title'] = link.get_text(strip=True)
                event_data['url'] = 'https://www.jamd.ac.il' + link.get('href', '')
        
        # Extract date/time
        date_field = event_div.find('div', class_='views-field-field-event-date-1')
        if date_field:
            date_span = date_field.find('span', class_='date-display-single')
            if date_span:
                event_data['date_display'] = date_span.get_text(strip=True)
                # Try to parse the datetime from the content attribute
                datetime_str = date_span.get('content', '')
                if datetime_str:
                    try:
                        event_data['datetime'] = date_parser.parse(datetime_str).isoformat()
                    except:
                        event_data['datetime'] = datetime_str
        
        # Extract location
        location_field = event_div.find('div', class_='views-field-field-event-location')
        if location_field:
            location_content = location_field.find('div', class_='field-content')
            if location_content:
                event_data['location'] = location_content.get_text(strip=True)
        
        if event_data.get('title'):
            events.append(event_data)
    
    return events

def scrape_calendar(start_year, start_month, end_year, end_month):
    """Scrape calendar events across multiple months"""
    
    all_events = []
    current_date = datetime(start_year, start_month, 1)
    end_date = datetime(end_year, end_month, 1)
    
    while current_date <= end_date:
        print(f"Fetching {current_date.strftime('%Y-%m')}...")
        
        json_response = fetch_month_calendar(current_date.year, current_date.month)
        
        if json_response:
            # The response is an array of commands
            for command in json_response:
                if command.get('command') == 'insert':
                    html_data = command.get('data', '')
                    events = extract_events_from_html(html_data)
                    all_events.extend(events)
                    print(f"  Found {len(events)} events")
        
        # Move to next month
        if current_date.month == 12:
            current_date = datetime(current_date.year + 1, 1, 1)
        else:
            current_date = datetime(current_date.year, current_date.month + 1, 1)
    
    return all_events

def save_to_csv(events, filename='calendar_events.csv'):
    """Save events to CSV file"""
    
    if not events:
        print("No events to save")
        return
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['title', 'datetime', 'date_display', 'location', 'url']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        writer.writeheader()
        for event in events:
            writer.writerow({
                'title': event.get('title', ''),
                'datetime': event.get('datetime', ''),
                'date_display': event.get('date_display', ''),
                'location': event.get('location', ''),
                'url': event.get('url', '')
            })
    
    print(f"\nSaved {len(events)} events to {filename}")

def save_to_json(events, filename='calendar_events.json'):
    """Save events to JSON file"""
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
    
    print(f"Saved {len(events)} events to {filename}")

def format_ics_datetime(dt_string):
    """Convert ISO datetime string to ICS format (YYYYMMDDTHHMMSS)"""
    try:
        dt = date_parser.parse(dt_string)
        # Convert to UTC
        if dt.tzinfo is not None:
            dt = dt.astimezone(datetime.now().astimezone().tzinfo)
        return dt.strftime('%Y%m%dT%H%M%S')
    except:
        return None

def sanitize_ics_text(text):
    """Sanitize text for ICS format by escaping special characters"""
    if not text:
        return ''
    # Escape special characters
    text = text.replace('\\', '\\\\')
    text = text.replace(',', '\\,')
    text = text.replace(';', '\\;')
    text = text.replace('\n', '\\n')
    return text

def save_to_ics(events, filename='calendar_events.ics'):
    """Save events to ICS (iCalendar) file"""
    
    if not events:
        print("No events to save")
        return
    
    ics_lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//JAMD Calendar Scraper//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'X-WR-CALNAME:JAMD Events',
        'X-WR-TIMEZONE:Asia/Jerusalem',
    ]
    
    for idx, event in enumerate(events):
        title = sanitize_ics_text(event.get('title', 'No Title'))
        location = sanitize_ics_text(event.get('location', ''))
        url = event.get('url', '')
        
        # Parse datetime
        datetime_str = event.get('datetime')
        if not datetime_str:
            continue
            
        dtstart = format_ics_datetime(datetime_str)
        if not dtstart:
            continue
        
        # Default duration: 1 hour
        try:
            dt = date_parser.parse(datetime_str)
            dt_end = dt + timedelta(hours=1)
            dtend = format_ics_datetime(dt_end.isoformat())
        except:
            dtend = None
        
        # Generate unique ID
        uid = f"event-{idx}-{dtstart}@jamd.ac.il"
        
        # Create timestamp for DTSTAMP
        dtstamp = datetime.now().astimezone().strftime('%Y%m%dT%H%M%SZ')
        
        # Build event
        ics_lines.extend([
            'BEGIN:VEVENT',
            f'UID:{uid}',
            f'DTSTAMP:{dtstamp}',
            f'DTSTART:{dtstart}',
        ])
        
        if dtend:
            ics_lines.append(f'DTEND:{dtend}')
        
        ics_lines.extend([
            f'SUMMARY:{title}',
            f'DESCRIPTION:{sanitize_ics_text(event.get("date_display", ""))}',
        ])
        
        if location:
            ics_lines.append(f'LOCATION:{location}')
        
        if url:
            ics_lines.append(f'URL:{url}')
        
        ics_lines.extend([
            'STATUS:CONFIRMED',
            'END:VEVENT',
        ])
    
    ics_lines.append('END:VCALENDAR')
    
    # Write to file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\r\n'.join(ics_lines))
    
    print(f"Saved {len(events)} events to {filename}")

if __name__ == '__main__':
    # Scrape calendar from current date for one year ahead
    today = datetime.now()
    end_date = today + timedelta(days=365)
    
    print(f"Scraping calendar from {today.strftime('%Y-%m')} to {end_date.strftime('%Y-%m')}")
    
    events = scrape_calendar(
        start_year=today.year, 
        start_month=today.month,
        end_year=end_date.year,
        end_month=end_date.month
    )
    
    print(f"\nTotal events found: {len(events)}")
    
    # Save to CSV, JSON, and ICS formats
    save_to_csv(events)
    save_to_json(events)
    save_to_ics(events)
    
    # Print first few events as preview
    print("\nPreview of events:")
    for event in events[:3]:
        print(f"\n- {event.get('title')}")
        print(f"  Date: {event.get('date_display')}")
        print(f"  Location: {event.get('location')}")
        print(f"  URL: {event.get('url')}")
