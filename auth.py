import streamlit as st
import extra_streamlit_components as stx
import datetime
import time
from database import conn

# Initialize the Cookie Manager (cached so it doesn't reload constantly)
@st.cache_resource(experimental_allow_widgets=True)
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
    
    # Custom CSS for the beautiful floating card UI
    st.markdown("""
    <style>
    .login-card {
        background-color: #ffffff;
        padding: 40px;
        border-radius: 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08);
        border: 1px solid #e5e7eb;
        text-align: center;
        margin-top: 5vh;
    }
    .login-header {
        font-size: 32px;
        font-weight: 800;
        color: #111827;
        margin-bottom: 8px;
        letter-spacing: -0.02em;
    }
    .login-sub {
        color: #6b7280;
        font-size: 15px;
        margin-bottom: 32px;
    }
    /* Hide the default Streamlit Form border to blend perfectly with our card */
    div[data-testid="stForm"] {
        border: none !important;
        padding: 0 !important;
        background-color: transparent !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Center the login card using columns
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.container():
            st.markdown('<div class="login-card">', unsafe_allow_html=True)
            st.markdown('<div class="login-header">🛡️ Admin Access</div>', unsafe_allow_html=True)
            st.markdown('<div class="login-sub">Secure Ground Operations Portal</div>', unsafe_allow_html=True)
            
            with st.form("enterprise_login", clear_on_submit=False):
                u = st.text_input("Username", placeholder="Enter your admin username")
                p = st.text_input("Password", type="password", placeholder="••••••••")
                
                keep_logged_in = st.checkbox("Keep me logged in for 30 days", value=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                submitted = st.form_submit_button("Authenticate", use_container_width=True, type="primary")
                
                if submitted:
                    if u and p:
                        res = conn.query("SELECT * FROM admins WHERE username = :u AND password = :p", params={"u": u, "p": p}, ttl=0)
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
                            st.error("❌ Invalid credentials. Please try again.")
                    else:
                        st.warning("⚠️ Please provide both username and password.")
            
            st.markdown('</div>', unsafe_allow_html=True)
