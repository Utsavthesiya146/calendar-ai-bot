import streamlit as st
import os
from datetime import datetime, timedelta
from ai_agent import CalendarAIAgent

# Configure page
st.set_page_config(
    page_title="Calendar AI Assistant",
    page_icon="📅",
    layout="wide"
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "ai_agent" not in st.session_state:
    try:
        st.session_state.ai_agent = CalendarAIAgent()
    except Exception as e:
        st.error(f"Failed to initialize AI agent: {str(e)}")
        st.error("Please ensure OPENAI_API_KEY environment variable is set and Google Calendar credentials are valid.")
        st.stop()

# App header
st.title("📅 Calendar AI Assistant")
st.markdown("Your intelligent assistant for booking appointments and managing your Google Calendar")

# Sidebar with instructions
with st.sidebar:
    st.header("How to Use")
    st.markdown("""
    **Examples of what you can ask:**
    
    📝 **Booking appointments:**
    - "Book a meeting tomorrow at 2 PM"
    - "Schedule a dentist appointment next Friday"
    - "I need a 30-minute slot this afternoon"
    
    🔍 **Checking availability:**
    - "Am I free tomorrow at 3 PM?"
    - "What time slots are available on Monday?"
    - "Show me my schedule for next week"
    
    📋 **Getting information:**
    - "What meetings do I have today?"
    - "Show my upcoming appointments"
    """)
    
    # Display current date/time
    st.markdown("---")
    st.markdown(f"**Today:** {datetime.now().strftime('%A, %B %d, %Y')}")
    st.markdown(f"**Time:** {datetime.now().strftime('%I:%M %p')}")

# Main chat interface
st.header("💬 Chat with your Calendar Assistant")

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask me about your calendar or to book an appointment..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Get AI response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Process the message with the AI agent
                result = st.session_state.ai_agent.process_message(
                    prompt, 
                    st.session_state.messages[:-1]  # Exclude the current message
                )
                
                if result["success"]:
                    response = result["response"]
                    
                    # Display any function call results
                    if result.get("function_calls"):
                        for func_call in result["function_calls"]:
                            func_result = func_call["result"]
                            
                            # Special handling for time slot suggestions
                            if func_call["function"] == "suggest_time_slots" and func_result.get("success"):
                                slots = func_result.get("slots", [])
                                if slots:
                                    st.markdown("**Available Time Slots:**")
                                    for i, slot in enumerate(slots, 1):
                                        start_dt = datetime.fromisoformat(slot['start'])
                                        end_dt = datetime.fromisoformat(slot['end'])
                                        
                                        col1, col2 = st.columns([3, 1])
                                        with col1:
                                            st.markdown(f"**{i}.** {start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}")
                                        with col2:
                                            if st.button(f"Book #{i}", key=f"book_{i}_{len(st.session_state.messages)}"):
                                                # Auto-book this slot
                                                book_prompt = f"Book an appointment from {slot['start']} to {slot['end']}"
                                                st.session_state.messages.append({"role": "user", "content": book_prompt})
                                                
                                                book_result = st.session_state.ai_agent.process_message(
                                                    book_prompt,
                                                    st.session_state.messages[:-1]
                                                )
                                                
                                                if book_result["success"]:
                                                    st.session_state.messages.append({
                                                        "role": "assistant", 
                                                        "content": book_result["response"]
                                                    })
                                                    st.rerun()
                            
                            # Special handling for upcoming events
                            elif func_call["function"] == "get_upcoming_events" and func_result.get("success"):
                                events = func_result.get("events", [])
                                if events:
                                    st.markdown("**Upcoming Events:**")
                                    for event in events:
                                        start_time = event['start']
                                        if 'T' in start_time:
                                            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00')).replace(tzinfo=None)
                                            time_str = start_dt.strftime('%m/%d/%Y %I:%M %p')
                                        else:
                                            time_str = start_time
                                        
                                        st.markdown(f"• **{event['summary']}** - {time_str}")
                            
                            # Special handling for successful booking
                            elif func_call["function"] == "create_appointment" and func_result.get("success"):
                                event = func_result.get("event", {})
                                st.success("✅ Appointment booked successfully!")
                                if event:
                                    start_dt = datetime.fromisoformat(event['start'].replace('Z', '+00:00')).replace(tzinfo=None)
                                    end_dt = datetime.fromisoformat(event['end'].replace('Z', '+00:00')).replace(tzinfo=None)
                                    
                                    st.info(f"""
                                    **Event Details:**
                                    - **Title:** {event['summary']}
                                    - **Date:** {start_dt.strftime('%A, %B %d, %Y')}
                                    - **Time:** {start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}
                                    - **Event ID:** {event['id']}
                                    """)
                    
                    # Display the main response
                    st.markdown(response)
                    
                else:
                    st.error(f"Error: {result.get('error', 'Unknown error occurred')}")
                    response = result["response"]
                    st.markdown(response)
                
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                response = "I apologize, but I encountered an error. Please try again."
                st.markdown(response)
    
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>Calendar AI Assistant - Powered by OpenAI GPT-4o and Google Calendar API</div>", 
    unsafe_allow_html=True
)

# Quick action buttons
st.markdown("### Quick Actions")
col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("📅 Check Today's Schedule"):
        today = datetime.now().strftime('%Y-%m-%d')
        quick_prompt = f"What's on my schedule for today ({today})?"
        st.session_state.messages.append({"role": "user", "content": quick_prompt})
        st.rerun()

with col2:
    if st.button("🔍 Find Tomorrow's Slots"):
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        quick_prompt = f"What time slots are available tomorrow ({tomorrow})?"
        st.session_state.messages.append({"role": "user", "content": quick_prompt})
        st.rerun()

with col3:
    if st.button("📋 Upcoming Events"):
        quick_prompt = "Show me my upcoming appointments"
        st.session_state.messages.append({"role": "user", "content": quick_prompt})
        st.rerun()

with col4:
    if st.button("🆕 Book New Meeting"):
        quick_prompt = "I want to schedule a new meeting"
        st.session_state.messages.append({"role": "user", "content": quick_prompt})
        st.rerun()

# Clear chat button
if st.sidebar.button("🗑️ Clear Chat History"):
    st.session_state.messages = []
    st.rerun()

# Environment variables check
with st.sidebar:
    st.markdown("---")
    st.markdown("**System Status:**")
    
    # Check OpenAI API Key
    if os.environ.get("OPENAI_API_KEY"):
        st.success("✅ OpenAI API Key configured")
    else:
        st.error("❌ OpenAI API Key missing")
    
    # Check Google Calendar credentials
    if os.path.exists("credentials.json"):
        st.success("✅ Google Calendar credentials found")
    else:
        st.error("❌ Google Calendar credentials missing")
