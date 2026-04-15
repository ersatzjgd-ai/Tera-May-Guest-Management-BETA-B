import streamlit as st
import extra_streamlit_components as stx
import datetime
from database import conn

# Initialize the Cookie Manager
@st.cache_resource
def get_manager():
    return stx.CookieManager(key="auth_manager")

cookie_manager = get_manager()

def check_login_state():
    """Optimized login check to minimize reruns."""
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user = None
    
    # Only check cookies if we aren't already logged in for this session
    if not st.session_state.logged_in:
        try:
            # The .get() call is the 'handshake'. We wrap it in a try-block
            token = cookie_manager.get(cookie="admin_session")
            if token:
                st.session_state.logged_in = True
                st.session_state.user = token
        except:
            pass

def logout():
    """Direct logout without artificial delays."""
    st.session_state.logged_in = False
    st.session_state.user = None
    cookie_manager.delete("admin_session")
    st.rerun()

def render_login():
    """Refined Login UI."""
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
    .enterprise-title {
        font-size: 20px;
        font-weight: 600;
        color: #0f172a;
        margin-bottom: 24px;
        text-align: center;
        border-bottom: 1px solid #f1f5f9;
        padding-bottom: 16px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.form("enterprise_login"):
            st.markdown('<div class="enterprise-title">System Sign-In</div>', unsafe_allow_html=True)
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            keep_logged_in = st.checkbox("Keep me logged in", value=True)
            submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")
            
            if submitted:
                if u and p:
                    query = "SELECT * FROM admins WHERE username = :u AND password = :p"
                    res = conn.query(query, params={"u": u, "p": p}, ttl=0)
                    
                    if not res.empty:
                        st.session_state.logged_in = True
                        st.session_state.user = u
                        if keep_logged_in:
                            expiry = datetime.datetime.now() + datetime.timedelta(days=30)
                            cookie_manager.set("admin_session", u, expires_at=expiry)
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")
                else:
                    st.warning("Please provide credentials.")
