import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class CalendarService:
    def __init__(self):
        """Initialize the Google Calendar service using service account credentials."""
        try:
            # Load service account credentials
            credentials = service_account.Credentials.from_service_account_file(
                'credentials.json',
                scopes=['https://www.googleapis.com/auth/calendar']
            )
            
            # Build the Calendar API service
            self.service = build('calendar', 'v3', credentials=credentials)
            
            # Get the primary calendar ID (we'll use the service account's calendar)
            self.calendar_id = 'primary'
            
        except Exception as e:
            raise Exception(f"Failed to initialize Calendar service: {str(e)}")
    
    def get_calendar_list(self) -> List[Dict]:
        """Get list of available calendars."""
        try:
            calendar_list = self.service.calendarList().list().execute()
            return calendar_list.get('items', [])
        except HttpError as e:
            raise Exception(f"Failed to get calendar list: {str(e)}")
    
    def check_availability(self, start_time: str, end_time: str) -> bool:
        """
        Check if a time slot is available.
        
        Args:
            start_time: ISO format datetime string (e.g., '2024-01-15T10:00:00')
            end_time: ISO format datetime string (e.g., '2024-01-15T11:00:00')
            
        Returns:
            True if slot is available, False if there are conflicts
        """
        try:
            # Convert to RFC3339 format for Google Calendar API
            time_min = start_time + 'Z' if not start_time.endswith('Z') else start_time
            time_max = end_time + 'Z' if not end_time.endswith('Z') else end_time
            
            # Query for events in the time range
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # If there are any events in this time range, it's not available
            return len(events) == 0
            
        except HttpError as e:
            raise Exception(f"Failed to check availability: {str(e)}")
    
    def get_busy_times(self, date: str) -> List[Dict]:
        """
        Get all busy times for a specific date.
        
        Args:
            date: Date string in YYYY-MM-DD format
            
        Returns:
            List of busy time slots with start and end times
        """
        try:
            # Set time range for the entire day
            time_min = f"{date}T00:00:00Z"
            time_max = f"{date}T23:59:59Z"
            
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            busy_times = []
            
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                
                busy_times.append({
                    'start': start,
                    'end': end,
                    'summary': event.get('summary', 'Busy')
                })
            
            return busy_times
            
        except HttpError as e:
            raise Exception(f"Failed to get busy times: {str(e)}")
    
    def suggest_time_slots(self, date: str, duration_minutes: int = 60, 
                          preferred_start_hour: int = 9, preferred_end_hour: int = 17) -> List[Dict]:
        """
        Suggest available time slots for a given date.
        
        Args:
            date: Date string in YYYY-MM-DD format
            duration_minutes: Duration of the appointment in minutes
            preferred_start_hour: Earliest hour to consider (24-hour format)
            preferred_end_hour: Latest hour to consider (24-hour format)
            
        Returns:
            List of available time slots
        """
        try:
            busy_times = self.get_busy_times(date)
            available_slots = []
            
            # Create datetime objects for the day's boundaries
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            start_of_day = date_obj.replace(hour=preferred_start_hour, minute=0, second=0, microsecond=0)
            end_of_day = date_obj.replace(hour=preferred_end_hour, minute=0, second=0, microsecond=0)
            
            # Convert busy times to datetime objects
            busy_periods = []
            for busy in busy_times:
                try:
                    if 'T' in busy['start']:  # datetime format
                        start = datetime.fromisoformat(busy['start'].replace('Z', '+00:00')).replace(tzinfo=None)
                        end = datetime.fromisoformat(busy['end'].replace('Z', '+00:00')).replace(tzinfo=None)
                    else:  # all-day event
                        continue  # Skip all-day events for now
                    
                    busy_periods.append((start, end))
                except Exception:
                    continue  # Skip malformed entries
            
            # Sort busy periods by start time
            busy_periods.sort(key=lambda x: x[0])
            
            # Find available slots
            current_time = start_of_day
            slot_duration = timedelta(minutes=duration_minutes)
            
            for busy_start, busy_end in busy_periods:
                # Check if there's a gap before this busy period
                if current_time + slot_duration <= busy_start:
                    available_slots.append({
                        'start': current_time.strftime('%Y-%m-%dT%H:%M:%S'),
                        'end': (current_time + slot_duration).strftime('%Y-%m-%dT%H:%M:%S'),
                        'duration_minutes': duration_minutes
                    })
                
                # Move current time to after this busy period
                current_time = max(current_time, busy_end)
            
            # Check for availability after the last busy period
            if current_time + slot_duration <= end_of_day:
                available_slots.append({
                    'start': current_time.strftime('%Y-%m-%dT%H:%M:%S'),
                    'end': (current_time + slot_duration).strftime('%Y-%m-%dT%H:%M:%S'),
                    'duration_minutes': duration_minutes
                })
            
            # Limit to first 5 suggestions
            return available_slots[:5]
            
        except Exception as e:
            raise Exception(f"Failed to suggest time slots: {str(e)}")
    
    def create_event(self, summary: str, start_time: str, end_time: str, 
                    description: str = "", attendee_email: str = "") -> Dict:
        """
        Create a new calendar event.
        
        Args:
            summary: Event title
            start_time: Start time in ISO format
            end_time: End time in ISO format
            description: Event description
            attendee_email: Email of attendee (optional)
            
        Returns:
            Created event details
        """
        try:
            # Prepare event data
            event = {
                'summary': summary,
                'description': description,
                'start': {
                    'dateTime': start_time + 'Z' if not start_time.endswith('Z') else start_time,
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time + 'Z' if not end_time.endswith('Z') else end_time,
                    'timeZone': 'UTC',
                },
            }
            
            # Add attendee if provided
            if attendee_email:
                event['attendees'] = [{'email': attendee_email}]
            
            # Create the event
            created_event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()
            
            return {
                'id': created_event['id'],
                'summary': created_event['summary'],
                'start': created_event['start']['dateTime'],
                'end': created_event['end']['dateTime'],
                'html_link': created_event.get('htmlLink', ''),
                'status': created_event['status']
            }
            
        except HttpError as e:
            raise Exception(f"Failed to create event: {str(e)}")
    
    def get_events(self, max_results: int = 10) -> List[Dict]:
        """
        Get upcoming events from the calendar.
        
        Args:
            max_results: Maximum number of events to return
            
        Returns:
            List of upcoming events
        """
        try:
            # Get current time in RFC3339 format
            now = datetime.utcnow().isoformat() + 'Z'
            
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            formatted_events = []
            
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                
                formatted_events.append({
                    'id': event['id'],
                    'summary': event.get('summary', 'No Title'),
                    'start': start,
                    'end': end,
                    'description': event.get('description', ''),
                    'status': event.get('status', 'confirmed')
                })
            
            return formatted_events
            
        except HttpError as e:
            raise Exception(f"Failed to get events: {str(e)}")
