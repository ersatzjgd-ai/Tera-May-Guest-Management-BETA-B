import streamlit as st
import extra_streamlit_components as stx
import datetime
import time
from database import conn

# Initialize the Cookie Manager (cached so it doesn't reload constantly)
@st.cache_resource
def get_manager():
    return stx.CookieManager(key="auth_manager")

cookie_manager = get_manager()

def check_login_state():
    """Checks session state and cookies to keep the user logged in."""
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user = None
    
    # If not manually logged in this session, check for the 30-day cookie
    if not st.session_state.logged_in:
        token = cookie_manager.get(cookie="admin_session")
        if token:
            st.session_state.logged_in = True
            st.session_state.user = token

def logout():
    """Clears the session and deletes the cookie."""
    st.session_state.logged_in = False
    st.session_state.user = None
    cookie_manager.delete("admin_session")
    time.sleep(0.2) # Brief pause to allow cookie deletion to register
    st.rerun()

def render_login():
    """Renders the Enterprise-Grade Login UI."""
    
    # Enterprise Minimalist CSS
    st.markdown("""
    <style>
    div[data-testid="stForm"] {
        background-color: #ffffff !important;
        padding: 40px 35px !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.04) !important;
        border: 1px solid #e2e8f0 !important;
        margin-top: 8vh !important;
    }
    
    /* Clean, professional title */
    .enterprise-title {
        font-size: 20px;
        font-weight: 600;
        color: #0f172a;
        margin-bottom: 24px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        text-align: center;
        border-bottom: 1px solid #f1f5f9;
        padding-bottom: 16px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Center the login card using columns
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.form("enterprise_login", clear_on_submit=False):
            st.markdown('<div class="enterprise-title">System Sign-In</div>', unsafe_allow_html=True)
            
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            
            st.markdown("<div style='height: 5px;'></div>", unsafe_allow_html=True)
            keep_logged_in = st.checkbox("Keep me logged in", value=True)
            
            st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")
            
            if submitted:
                if u and p:
                    # Broken into two lines to prevent editor truncation
                    query_str = "SELECT * FROM admins WHERE username = :u AND password = :p"
                    res = conn.query(query_str, params={"u": u, "p": p}, ttl=0)
                    
                    if not res.empty:
                        st.session_state.logged_in = True
                        st.session_state.user = u
                        
                        # If checked, set the cookie to expire in 30 days
                        if keep_logged_in:
                            expire_date = datetime.datetime.now() + datetime.timedelta(days=30)
                            cookie_manager.set("admin_session", u, expires_at=expire_date)
                            time.sleep(0.2) # Allow cookie to set before rerunning
                        
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")
                else:
                    st.warning("Please provide both username and password.")
