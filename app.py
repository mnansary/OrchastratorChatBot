# FILE: streamlit_app.py

import streamlit as st
import requests
import json
import time

# --- Configuration ---
API_BASE_URL = "http://localhost:9000"
CHAT_ENDPOINT = f"{API_BASE_URL}/chat/stream"
LOGIN_API_URL = "https://api.bengalmeat.com/auth/customer-login"

# --- Page Setup ---
st.set_page_config(
    page_title="Bengal Meat Assistant",
    page_icon="🥩",
    layout="centered"
)

# --- Helper Functions ---

@st.cache_data(ttl=3600)
def fetch_stores() -> dict:
    """Fetches store locations from the public company API."""
    try:
        response = requests.get("https://api.bengalmeat.com/store/storelistopen/1?is_visible=1")
        response.raise_for_status()
        stores = response.json().get('data', [])
        # Filter out any test stores
        return {
            f"{store['name']} ({store.get('CITY', 'N/A')})": store['id'] 
            for store in stores if "test" not in store.get("name", "").lower()
        }
    except Exception as e:
        st.error(f"Could not fetch store list. Using fallback. Error: {e}")
        return {"Mohammadpur Butcher Shop": 37, "Gulshan-2 GB": 67} # Sensible fallback

def reset_session():
    """Clears the session state to start a new chat."""
    keys_to_clear = [key for key in st.session_state.keys() if key != 'stores']
    for key in keys_to_clear:
        del st.session_state[key]
    # Re-initialize essential state
    st.session_state.stage = "setup"
    st.session_state.messages = []
    st.session_state.session_id = None
    st.rerun()

# --- UI Sections ---

def render_setup_page():
    """Renders the initial screen for store selection and login."""
    st.image("https://bengalmeat.com/wp-content/uploads/2023/11/logo.png", width=200)
    st.title("Welcome to Bengal Meat's Chat Assistant!")
    st.markdown("Please select your nearest store and log in to begin.")

    if 'stores' not in st.session_state:
        st.session_state.stores = fetch_stores()

    selected_store_name = st.selectbox(
        "Choose your store",
        options=list(st.session_state.stores.keys()),
        key="selected_store_name"
    )
    
    login_tab, guest_tab = st.tabs(["Login", "Continue as Guest"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            login_button = st.form_submit_button("Login and Start Chat")

            if login_button:
                store_id = st.session_state.stores[selected_store_name]
                with st.spinner("Logging in and preparing your personalized session..."):
                    try:
                        response = requests.post(LOGIN_API_URL, json={"email": email, "password": password})
                        response.raise_for_status()
                        login_data = response.json()
                        
                        # Use .get() for safer dictionary access
                        if login_data.get("statusCode") == 201 and login_data.get("data"):
                            user_data = login_data["data"].get("user", {})
                            st.session_state.session_meta = {
                                "store_id": store_id,
                                "user_id": user_data.get("id"),
                                "access_token": login_data["data"].get("accessToken"),
                                "refresh_token": login_data["data"].get("refreshToken"),
                            }
                            st.session_state.stage = 'chat'
                            st.rerun() # --- CHANGE: Automatically transition to chat ---
                        else:
                            st.error(f"Login failed: {login_data.get('message', 'Unknown error')}")
                    except requests.RequestException as e:
                        st.error(f"Login connection failed. Please check the server. Error: {e}")

    with guest_tab:
        if st.button("Continue as Guest and Start Chat"):
            store_id = st.session_state.stores[selected_store_name]
            st.session_state.session_meta = {
                "store_id": store_id,
                "user_id": None, "access_token": None, "refresh_token": None
            }
            st.session_state.stage = 'chat'
            st.rerun() # --- CHANGE: Automatically transition to chat ---

def render_chat_page():
    """Renders the main chat interface and handles API communication."""
    st.title("🥩 Chat with Meaty")
    st.button("End Session & Start Over", on_click=reset_session)
    st.markdown("---")

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Handle chat input from the user
    if prompt := st.chat_input("Ask about products, offers, or your orders..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Prepare request payload for an existing session
        payload = {"query": prompt, "session_id": st.session_state.session_id}
        
        # Display streaming response
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""
            tool_call_in_progress = False
            
            try:
                with requests.post(CHAT_ENDPOINT, json=payload, stream=True) as r:
                    r.raise_for_status()
                    for line in r.iter_lines():
                        if line:
                            event = json.loads(line.decode('utf-8'))
                            
                            # --- CHANGE: Handle different event types from the backend ---
                            event_type = event.get("type")
                            
                            if event_type == "tool_call":
                                tool_name = event.get("tool_name", "a tool")
                                placeholder.markdown(f"*(Searching for information using {tool_name}...)*")
                                tool_call_in_progress = True
                                
                            elif event_type == "answer_chunk":
                                if tool_call_in_progress:
                                    # Clear the "thinking" message when the first text chunk arrives
                                    full_response = ""
                                    tool_call_in_progress = False
                                
                                full_response += event["content"]
                                placeholder.markdown(full_response + "▌")
                                
                            elif event_type == "error":
                                st.error(event.get('content', 'An unknown error occurred.'))
                                break
                
                placeholder.markdown(full_response)
            except requests.RequestException as e:
                st.error(f"Failed to get response from chat service: {e}")
                full_response = "Sorry, I'm having trouble connecting right now."
            
            if full_response:
                st.session_state.messages.append({"role": "assistant", "content": full_response})

    # Initial session setup and welcome message
    if not st.session_state.get("session_id"):
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""
            with st.spinner("Meaty is preparing your session..."):
                try:
                    payload = {"session_meta": st.session_state.session_meta}
                    with requests.post(CHAT_ENDPOINT, json=payload, stream=True) as r:
                        r.raise_for_status()
                        for line in r.iter_lines():
                            if line:
                                event = json.loads(line.decode('utf-8'))
                                if event["type"] == "session_id":
                                    st.session_state.session_id = event["id"]
                                elif event["type"] == "welcome_message":
                                    full_response += event["content"]
                                    placeholder.markdown(full_response + "▌")
                                elif event["type"] == "error":
                                     st.error(event['content'])
                                     break
                    placeholder.markdown(full_response)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                except requests.RequestException as e:
                    st.error(f"Could not initialize chat session: {e}")


# --- Main Application Logic ---
if "stage" not in st.session_state:
    st.session_state.stage = "setup"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = None

if st.session_state.stage == "setup":
    render_setup_page()
else:
    render_chat_page()