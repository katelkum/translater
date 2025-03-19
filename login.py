import streamlit as st
import json
from pathlib import Path

def load_credentials() -> dict:
    """Load credentials from the JSON file."""
    credentials_file = Path(__file__).parent / "credentials.json"
    
    # Create default credentials if file doesn't exist
    if not credentials_file.exists():
        default_credentials = {"users": []}
        with open(credentials_file, "w") as f:
            json.dump(default_credentials, f, indent=4)
    
    # Load credentials
    with open(credentials_file) as f:
        return json.load(f)

def save_credentials(credentials: dict) -> None:
    """Save credentials to the JSON file."""
    credentials_file = Path(__file__).parent / "credentials.json"
    with open(credentials_file, "w") as f:
        json.dump(credentials, f, indent=4)

def check_credentials(username: str, password: str) -> bool:
    """Verify user credentials."""
    credentials = load_credentials()
    return any(
        user["username"] == username and user["password"] == password
        for user in credentials["users"]
    )

def register_user(username: str, password: str) -> bool:
    """Register a new user."""
    credentials = load_credentials()
    
    # Check if username already exists
    if any(user["username"] == username for user in credentials["users"]):
        return False  # Username already exists
    
    # Add new user
    credentials["users"].append({"username": username, "password": password})
    save_credentials(credentials)
    return True

def show_login_page():
    """Display the login and registration page."""
    st.title("🔐 Login or Sign Up")
    
    # Initialize session state
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    # Tabs for login and sign-up
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.subheader("Login")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                if check_credentials(username, password):
                    st.session_state.authenticated = True
                    st.success("Login successful! Please wait...")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
    
    with tab2:
        st.subheader("Sign Up")
        with st.form("signup_form"):
            new_username = st.text_input("New Username")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            submit = st.form_submit_button("Sign Up")
            
            if submit:
                if new_password != confirm_password:
                    st.error("Passwords do not match!")
                elif register_user(new_username, new_password):
                    st.success("Registration successful! You can now log in.")
                else:
                    st.error("Username already exists. Please choose a different one.")
