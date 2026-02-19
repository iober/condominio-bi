import json
import os
import uuid
import requests
import streamlit as st
import streamlit.components.v1 as components
from google_auth_oauthlib.flow import Flow

SESSIONS_FILE = "sessions.json"

def _get_redirect_uri() -> str:
    try:
        return st.secrets["REDIRECT_URI"]
    except Exception:
        return "http://localhost:8501"
COOKIE_NAME   = "bi_sid"
COOKIE_DAYS   = 30
SESSION_PARAM = "sid"

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.readonly",
]


# ==========================
# SESSÕES NO SERVIDOR
# ==========================
_sessions_memory: dict = {}

def _load_sessions():
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE) as f:
                data = json.load(f)
                _sessions_memory.update(data)
        except Exception:
            pass
    return _sessions_memory

def _save_sessions(sessions: dict):
    _sessions_memory.clear()
    _sessions_memory.update(sessions)
    try:
        with open(SESSIONS_FILE, "w") as f:
            json.dump(sessions, f)
    except Exception:
        pass


# ==========================
# COOKIE VIA JAVASCRIPT
# ==========================
def inject_cookie_reader():
    """
    Injeta JS que lê o localStorage e redireciona com ?sid=TOKEN se não estiver na URL.
    """
    if st.query_params.get(SESSION_PARAM):
        return
    js = f"""
    <script>
    (function() {{
        try {{
            var sid = window.parent.localStorage.getItem('{COOKIE_NAME}');
            if (sid) {{
                var url = new URL(window.parent.location.href);
                if (!url.searchParams.get('{SESSION_PARAM}')) {{
                    url.searchParams.set('{SESSION_PARAM}', sid);
                    window.parent.location.href = url.toString();
                }}
            }}
        }} catch(e) {{}}
    }})();
    </script>
    """
    components.html(js, height=0, scrolling=False)


def _set_cookie_js(token: str):
    js = f"""
    <script>
    (function() {{
        try {{
            window.parent.localStorage.setItem('{COOKIE_NAME}', '{token}');
        }} catch(e) {{}}
    }})();
    </script>
    """
    components.html(js, height=0, scrolling=False)


def _delete_cookie_js():
    js = f"""
    <script>
    (function() {{
        try {{
            window.parent.localStorage.removeItem('{COOKIE_NAME}');
        }} catch(e) {{}}
    }})();
    </script>
    """
    components.html(js, height=0, scrolling=False)


def _get_flow() -> Flow:
    redirect_uri = _get_redirect_uri()

    # Permite HTTP apenas em desenvolvimento local
    if redirect_uri.startswith("http://"):
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    else:
        os.environ.pop("OAUTHLIB_INSECURE_TRANSPORT", None)

    try:
        with open("credentials.json") as f:
            raw = json.load(f)
    except FileNotFoundError:
        raw = json.loads(st.secrets["GOOGLE_CREDENTIALS"])

    # Suporta tanto "installed" quanto "web"
    cred = raw.get("web") or raw.get("installed")

    config = {
        "web": {
            "client_id": cred["client_id"],
            "client_secret": cred["client_secret"],
            "auth_uri": cred["auth_uri"],
            "token_uri": cred["token_uri"],
            "redirect_uris": [redirect_uri],
        }
    }
    return Flow.from_client_config(config, scopes=SCOPES, redirect_uri=redirect_uri)


def get_auth_url() -> str:
    flow = _get_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="select_account",
    )
    st.session_state["oauth_state"] = state
    return auth_url


def handle_callback() -> bool:
    if "code" not in st.query_params:
        return False
    try:
        flow = _get_flow()
        flow.fetch_token(code=st.query_params["code"])
        user_resp = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {flow.credentials.token}"},
            timeout=10,
        )
        user_info = user_resp.json()

        # Criar sessão no servidor
        token = str(uuid.uuid4())
        sessions = _load_sessions()
        sessions[token] = {
            "user_info": user_info,
            "gmail_token": flow.credentials.to_json(),
        }
        _save_sessions(sessions)

        st.session_state["user"] = user_info
        st.session_state["gmail_token"] = flow.credentials.to_json()
        st.session_state["authenticated"] = True
        st.session_state["_sid"] = token

        # Colocar sid na URL e gravar cookie
        st.query_params.clear()
        st.query_params[SESSION_PARAM] = token
        return True
    except Exception as e:
        st.session_state["login_error"] = str(e)
        st.query_params.clear()
        return False


def is_authenticated() -> bool:
    if st.session_state.get("authenticated", False):
        return True
    sid = st.query_params.get(SESSION_PARAM, "")
    if sid:
        sessions = _load_sessions()
        if sid in sessions:
            session_data = sessions[sid]
            if isinstance(session_data, dict) and "user_info" in session_data:
                st.session_state["user"] = session_data["user_info"]
                st.session_state["gmail_token"] = session_data.get("gmail_token")
            else:
                st.session_state["user"] = session_data
            st.session_state["authenticated"] = True
            return True
        st.query_params.clear()
    return False


def logout():
    sid = st.query_params.get(SESSION_PARAM, "") or st.session_state.get("_sid", "")
    if sid:
        sessions = _load_sessions()
        sessions.pop(sid, None)
        _save_sessions(sessions)
    st.session_state.clear()
    _delete_cookie_js()
    st.query_params.clear()
    st.rerun()


def show_login_page():
    st.markdown("""
    <style>
    .login-box {
        max-width: 420px;
        margin: 80px auto 0 auto;
        padding: 48px 40px;
        border-radius: 16px;
        background: #1e1e2e;
        box-shadow: 0 4px 32px rgba(0,0,0,0.4);
        text-align: center;
    }
    .login-title {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 4px;
    }
    .login-sub {
        color: #888;
        margin-bottom: 32px;
        font-size: 0.95rem;
    }
    .google-btn {
        display: inline-flex;
        align-items: center;
        gap: 12px;
        background: #fff;
        color: #333;
        font-size: 1rem;
        font-weight: 500;
        padding: 12px 28px;
        border-radius: 8px;
        text-decoration: none;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        transition: box-shadow 0.2s;
    }
    .google-btn:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.3); }
    </style>
    """, unsafe_allow_html=True)

    auth_url = get_auth_url()

    # SVG do logo Google
    google_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 48 48">
        <path fill="#EA4335" d="M24 9.5c3.1 0 5.6 1.1 7.6 2.9l5.6-5.6C33.5 3.5 29.1 1.5 24 1.5 14.9 1.5 7.2 7.2 4.2 15.1l6.6 5.1C12.3 13.9 17.6 9.5 24 9.5z"/>
        <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v8.5h12.7c-.6 3-2.3 5.5-4.8 7.2l7.4 5.7c4.3-4 6.7-9.9 6.7-16.9z"/>
        <path fill="#FBBC05" d="M10.8 28.8A14.5 14.5 0 0 1 9.5 24c0-1.7.3-3.3.8-4.8L3.7 14C2.3 16.9 1.5 20.3 1.5 24c0 3.7.8 7.1 2.2 10.1l6.6-5.1-.5-.2z"/>
        <path fill="#34A853" d="M24 46.5c5.1 0 9.5-1.7 12.7-4.6l-7.4-5.7c-1.8 1.2-4.1 1.9-5.3 1.9-6.4 0-11.7-4.4-13.2-10.2l-6.6 5.1C7.2 40.8 14.9 46.5 24 46.5z"/>
    </svg>"""

    st.markdown(f"""
    <div class="login-box">
        <div class="login-title">🏢 BI Condomínio</div>
        <div class="login-sub">Faça login para acessar o dashboard</div>
        <a class="google-btn" href="{auth_url}">
            {google_svg}
            Entrar com Google
        </a>
    </div>
    """, unsafe_allow_html=True)

    if "login_error" in st.session_state:
        st.error(f"Erro no login: {st.session_state.pop('login_error')}")

    st.stop()
