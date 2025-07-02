import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from openai import OpenAI
from calendar_service import CalendarService

class CalendarAIAgent:
    def __init__(self):
        """Initialize the AI agent with OpenAI and Calendar service."""
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable must be set")
        
        self.client = OpenAI(api_key=self.openai_api_key)
        self.calendar_service = CalendarService()
        
        # Define available functions for the AI agent
        self.functions = [
            {
                "name": "check_availability",
                "description": "Check if a specific time slot is available for booking",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_time": {
                            "type": "string",
                            "description": "Start time in ISO format (YYYY-MM-DDTHH:MM:SS)"
                        },
                        "end_time": {
                            "type": "string",
                            "description": "End time in ISO format (YYYY-MM-DDTHH:MM:SS)"
                        }
                    },
                    "required": ["start_time", "end_time"]
                }
            },
            {
                "name": "suggest_time_slots",
                "description": "Get available time slots for a specific date",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "Date in YYYY-MM-DD format"
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Duration of appointment in minutes (default: 60)"
                        },
                        "preferred_start_hour": {
                            "type": "integer",
                            "description": "Preferred earliest hour (0-23, default: 9)"
                        },
                        "preferred_end_hour": {
                            "type": "integer",
                            "description": "Preferred latest hour (0-23, default: 17)"
                        }
                    },
                    "required": ["date"]
                }
            },
            {
                "name": "create_appointment",
                "description": "Create a new appointment/event in the calendar",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "Title/summary of the appointment"
                        },
                        "start_time": {
                            "type": "string",
                            "description": "Start time in ISO format (YYYY-MM-DDTHH:MM:SS)"
                        },
                        "end_time": {
                            "type": "string",
                            "description": "End time in ISO format (YYYY-MM-DDTHH:MM:SS)"
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of the appointment"
                        },
                        "attendee_email": {
                            "type": "string",
                            "description": "Email address of the attendee (optional)"
                        }
                    },
                    "required": ["summary", "start_time", "end_time"]
                }
            },
            {
                "name": "get_upcoming_events",
                "description": "Get list of upcoming events from the calendar",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of events to return (default: 10)"
                        }
                    },
                    "required": []
                }
            }
        ]
    
    def _execute_function(self, function_name: str, arguments: Dict) -> Dict:
        """Execute the specified function with given arguments."""
        try:
            if function_name == "check_availability":
                is_available = self.calendar_service.check_availability(
                    arguments["start_time"], 
                    arguments["end_time"]
                )
                return {
                    "success": True,
                    "available": is_available,
                    "message": f"Time slot is {'available' if is_available else 'not available'}"
                }
            
            elif function_name == "suggest_time_slots":
                slots = self.calendar_service.suggest_time_slots(
                    arguments["date"],
                    arguments.get("duration_minutes", 60),
                    arguments.get("preferred_start_hour", 9),
                    arguments.get("preferred_end_hour", 17)
                )
                return {
                    "success": True,
                    "slots": slots,
                    "message": f"Found {len(slots)} available time slots"
                }
            
            elif function_name == "create_appointment":
                event = self.calendar_service.create_event(
                    arguments["summary"],
                    arguments["start_time"],
                    arguments["end_time"],
                    arguments.get("description", ""),
                    arguments.get("attendee_email", "")
                )
                return {
                    "success": True,
                    "event": event,
                    "message": "Appointment created successfully"
                }
            
            elif function_name == "get_upcoming_events":
                events = self.calendar_service.get_events(
                    arguments.get("max_results", 10)
                )
                return {
                    "success": True,
                    "events": events,
                    "message": f"Retrieved {len(events)} upcoming events"
                }
            
            else:
                return {
                    "success": False,
                    "error": f"Unknown function: {function_name}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def process_message(self, user_message: str, conversation_history: List[Dict]) -> Dict:
        """
        Process user message and return AI response with potential function calls.
        
        Args:
            user_message: The user's input message
            conversation_history: List of previous messages in the conversation
            
        Returns:
            Dictionary containing AI response and any function results
        """
        try:
            # Prepare messages for OpenAI
            messages = [
                {
                    "role": "system",
                    "content": """You are a helpful AI assistant for booking appointments on Google Calendar. 
                    Your role is to help users schedule appointments by:
                    
                    1. Understanding their scheduling needs and preferences
                    2. Checking calendar availability
                    3. Suggesting suitable time slots
                    4. Confirming and creating appointments
                    5. Providing information about existing appointments
                    
                    Guidelines:
                    - Be conversational and friendly
                    - Ask clarifying questions when needed (date, time preferences, duration, purpose)
                    - Use function calls to interact with the calendar
                    - Always confirm details before creating appointments
                    - Handle errors gracefully and provide helpful alternatives
                    - Today's date is """ + datetime.now().strftime('%Y-%m-%d') + """
                    
                    When users mention times, try to be flexible with formats but always convert to ISO format for function calls.
                    Be proactive in suggesting alternatives if requested times are not available."""
                }
            ]
            
            # Add conversation history
            messages.extend(conversation_history)
            
            # Add current user message
            messages.append({"role": "user", "content": user_message})
            
            # Make initial request to OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                functions=self.functions,
                function_call="auto",
                temperature=0.7
            )
            
            message = response.choices[0].message
            function_results = []
            
            # Handle function calls
            if hasattr(message, 'function_call') and message.function_call:
                function_name = message.function_call.name
                function_args = json.loads(message.function_call.arguments)
                
                # Execute the function
                result = self._execute_function(function_name, function_args)
                function_results.append({
                    "function": function_name,
                    "arguments": function_args,
                    "result": result
                })
                
                # Send function result back to OpenAI for final response
                messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "function_call": {
                        "name": function_name,
                        "arguments": message.function_call.arguments
                    }
                })
                
                messages.append({
                    "role": "function",
                    "name": function_name,
                    "content": json.dumps(result)
                })
                
                # Get final response
                final_response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    temperature=0.7
                )
                
                final_content = final_response.choices[0].message.content
            else:
                final_content = message.content
            
            return {
                "success": True,
                "response": final_content,
                "function_calls": function_results,
                "raw_message": message
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response": f"I apologize, but I encountered an error: {str(e)}. Please try again."
            }
    
    def format_time_slots(self, slots: List[Dict]) -> str:
        """Format time slots for display in conversation."""
        if not slots:
            return "No available time slots found for the requested date."
        
        formatted = "Here are the available time slots:\n\n"
        for i, slot in enumerate(slots, 1):
            start_dt = datetime.fromisoformat(slot['start'])
            end_dt = datetime.fromisoformat(slot['end'])
            
            formatted += f"{i}. {start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}\n"
        
        return formatted
    
    def parse_date_time(self, date_time_str: str) -> Optional[datetime]:
        """Parse various date/time formats into datetime object."""
        # Common patterns to try
        patterns = [
            '%Y-%m-%d %H:%M',
            '%Y-%m-%dT%H:%M:%S',
            '%m/%d/%Y %H:%M',
            '%m-%d-%Y %H:%M',
            '%B %d, %Y %H:%M',
            '%Y-%m-%d',
        ]
        
        for pattern in patterns:
            try:
                return datetime.strptime(date_time_str, pattern)
            except ValueError:
                continue
        
        return None
