
import os
import json
import tempfile
from pathlib import Path
import shutil
from git import Repo

try:
    from groq import Groq

    client = Groq(
        api_key=os.environ.get("GROQ_API_KEY")
    )

except Exception:
    client = None

from graphviz import Digraph


# ============================================================
# BACKEND FUNCTIONS
# ============================================================
def clone_repository(repo_url):
    temp_dir = tempfile.mkdtemp(prefix="code2arch_")

    try:
        Repo.clone_from(
            repo_url,
            temp_dir,
            depth=1
        )

        return temp_dir, None

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None, str(e)


def scan_repository(repo_path):
    files = []

    repo_path = Path(repo_path)

    for path in repo_path.rglob("*"):

        if not path.is_file():
            continue

        # Ignore unnecessary directories
        if any(part in IGNORE_DIRS for part in path.parts):
            continue

        # Only analyze supported file types
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue

        try:
            relative_path = path.relative_to(repo_path)

            files.append({
                "path": str(relative_path),
                "extension": path.suffix.lower(),
                "size": path.stat().st_size
            })

        except Exception:
            pass

    return files


def extract_code(repo_path, files):
    codebase = []

    for file_info in files:
        path = file_info["path"]

        content = read_file_content(
            repo_path,
            path
        )

        codebase.append({
            "path": path,
            "content": content
        })

    return codebase


def analyze_architecture(codebase):

    # Sirf important source files
    allowed_extensions = (
        ".py", ".js", ".jsx", ".ts", ".tsx",
        ".java", ".cpp", ".c", ".cs",
        ".go", ".php", ".rb",
        ".html", ".css", ".sql"
    )

    selected_files = []

    for item in codebase:
        path = item.get("path", "").lower()

        if path.endswith(allowed_extensions):
            selected_files.append(item)

    # Maximum 12 important files
    selected_files = selected_files[:12]

    code_text = ""

    # Very small limits
    MAX_FILE_CHARS = 2000
    MAX_TOTAL_CHARS = 12000

    for item in selected_files:

        path = item.get("path", "unknown")
        content = item.get("content", "")

        # Limit each file
        content = content[:MAX_FILE_CHARS]

        block = f"""
FILE: {path}
{content}
"""

        # Stop if total becomes too large
        if len(code_text) + len(block) > MAX_TOTAL_CHARS:
            break

        code_text += block

    system_prompt = """
You are a software architecture analyzer.

Analyze the provided repository code.

Return ONLY valid JSON:

{
  "project_type": "",
  "technologies": [],
  "components": [
    {
      "name": "",
      "type": "",
      "description": ""
    }
  ],
  "connections": [
    {
      "from": "",
      "to": "",
      "relationship": ""
    }
  ],
  "data_flow": [],
  "security_findings": []
}

Rules:
- Use only information supported by the code.
- Do not invent components.
- Detect technologies when clearly visible.
- Identify important frontend, backend, API, database and module components.
- Keep descriptions short.
- Keep the response concise.
- Return JSON only.
"""

    user_prompt = f"""
Analyze this repository:

{code_text}
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        temperature=0.1,
        max_tokens=2500
    )

    return response.choices[0].message.content


def parse_architecture_result(result):
    try:
        # Remove markdown code fences if AI adds them
        cleaned = result.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.replace("```json", "")
            cleaned = cleaned.replace("```", "")

        architecture = json.loads(cleaned)

        return architecture

    except json.JSONDecodeError as e:
        print("❌ Could not parse AI response as JSON")
        print("Error:", e)
        return None


def create_visual_architecture(architecture):
    
    if not isinstance(architecture, dict):
        raise TypeError(
            f"Architecture must be a dictionary, got {type(architecture)}"
        )

    components = architecture.get("components", [])
    connections = architecture.get("connections", [])

    dot = Digraph("RepoLensArchitecture", format="png")

    # Premium dark architecture diagram
    dot.attr(
        rankdir="TB",
        bgcolor="#080F1E",
        pad="0.5",
        nodesep="0.6",
        ranksep="0.8"
    )

    dot.attr(
        "node",
        shape="box",
        style="rounded,filled",
        fillcolor="#111C31",
        color="#3B82F6",
        fontcolor="#F1F5F9",
        fontname="Arial",
        fontsize="12",
        margin="0.22"
    )

    dot.attr(
        "edge",
        color="#22D3EE",
        penwidth="1.8",
        arrowsize="0.8",
        fontcolor="#8FA4BF",
        fontname="Arial",
        fontsize="9"
    )

    name_to_id = {}

    # --------------------------------------------------------
    # Components
    # --------------------------------------------------------

    for i, component in enumerate(components):

        name = component.get(
            "name",
            f"Component {i + 1}"
        )

        component_type = component.get(
            "type",
            "Component"
        )

        node_id = f"node_{i}"

        name_to_id[name] = node_id

        label = (
            f"{name}\\n"
            f"[{component_type}]"
        )

        dot.node(
            node_id,
            label=label
        )

    # --------------------------------------------------------
    # Connections
    # --------------------------------------------------------

    for connection in connections:

        source = connection.get("from", "")
        target = connection.get("to", "")
        relationship = connection.get(
            "relationship",
            ""
        )

        if source in name_to_id and target in name_to_id:

            dot.edge(
                name_to_id[source],
                name_to_id[target],
                xlabel=relationship
            )

    return dot





# ============================================================
# RepoLens AI — Premium Product UI
# Landing → Login/Signup → Dashboard → Analyzer

import streamlit as st
import traceback

st.set_page_config(
    page_title="RepoLens AI",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "page": "landing",
    "authenticated": False,
    "user": "",
    "users": {
        "demo@repolens.ai": {
            "name": "Demo User",
            "password": "demo123",
        }
    },
    "history": [],
    "architecture": None,
    "files": [],
    "repo_url": "",
    "tab": "overview",
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

BASE_DIR = Path(__file__).resolve().parent
LOGO = BASE_DIR / "assets" / "repolens_logo.png"

# ============================================================
# PREMIUM DESIGN SYSTEM
# ============================================================

st.markdown(
    """
<style>
/* ---------- APP ---------- */
.stApp {
    background:
        radial-gradient(circle at 8% 0%, rgba(59,130,246,.15), transparent 27%),
        radial-gradient(circle at 92% 7%, rgba(34,211,238,.11), transparent 24%),
        linear-gradient(180deg, #060B16 0%, #080F1E 45%, #070D19 100%);
    color: #F1F5F9;
}

.block-container {
    max-width: 1320px;
    padding-top: 1.25rem;
    padding-bottom: 5rem;
}

/* ---------- HEADER ---------- */
.topbar {
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding: 10px 4px 18px;
    border-bottom: 1px solid rgba(148,163,184,.10);
    margin-bottom: 28px;
}

.brand {
    display:flex;
    align-items:center;
    gap:12px;
    font-size:20px;
    font-weight:800;
    letter-spacing:-.4px;
}

.brand-mark {
    width:40px;
    height:40px;
    border-radius:12px;
    display:flex;
    align-items:center;
    justify-content:center;
    background:linear-gradient(135deg,#2563EB,#06B6D4);
    box-shadow:0 8px 30px rgba(37,99,235,.28);
    font-size:21px;
}

.brand-sub {
    color:#7186A3;
    font-size:11px;
    font-weight:600;
    letter-spacing:1.3px;
    margin-top:2px;
}

/* ---------- HERO ---------- */
.hero {
    position:relative;
    overflow:hidden;
    padding:72px 70px 68px;
    border:1px solid #1D304D;
    border-radius:30px;
    background:
        radial-gradient(circle at 82% 25%, rgba(34,211,238,.10), transparent 25%),
        radial-gradient(circle at 20% 90%, rgba(59,130,246,.12), transparent 30%),
        linear-gradient(135deg, rgba(17,28,49,.98), rgba(7,14,29,.97));
    box-shadow:
        0 35px 100px rgba(0,0,0,.42),
        inset 0 1px rgba(255,255,255,.035);
    margin: 12px 0 30px;
}

.hero:after {
    content:"";
    position:absolute;
    width:420px;
    height:420px;
    right:-190px;
    top:-220px;
    border-radius:50%;
    border:1px solid rgba(34,211,238,.10);
    box-shadow:0 0 0 50px rgba(34,211,238,.025),0 0 0 100px rgba(34,211,238,.018);
}

.badge {
    display:inline-flex;
    align-items:center;
    padding:9px 15px;
    border:1px solid #274568;
    border-radius:999px;
    color:#22D3EE;
    background:rgba(34,211,238,.065);
    font-size:11px;
    font-weight:800;
    letter-spacing:1.4px;
}

.hero h1 {
    position:relative;
    z-index:1;
    font-size:clamp(44px,6vw,78px);
    line-height:1.01;
    letter-spacing:-4px;
    margin:24px 0 18px;
    max-width:1000px;
}

.gradient {
    background:linear-gradient(90deg,#3B82F6 0%,#22D3EE 72%);
    -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;
    background-clip:text;
}

.subtitle {
    color:#8FA4C0;
    line-height:1.75;
    font-size:17px;
    max-width:820px;
}

.hero-mini {
    display:flex;
    gap:10px;
    flex-wrap:wrap;
    margin-top:28px;
}

.pill {
    padding:8px 12px;
    border:1px solid #1D304D;
    border-radius:999px;
    background:rgba(8,15,30,.55);
    color:#AFC1D8;
    font-size:12px;
}

/* ---------- SECTIONS ---------- */
.section-kicker {
    color:#22D3EE;
    font-size:11px;
    font-weight:800;
    letter-spacing:1.6px;
    text-transform:uppercase;
    margin-bottom:7px;
}

.section-title {
    color:#F1F5F9;
    font-size:30px;
    font-weight:850;
    letter-spacing:-1px;
    margin:0 0 22px;
}

.section-copy {
    color:#7F94B0;
    margin-top:-12px;
    margin-bottom:28px;
}

/* ---------- FEATURE CARDS ---------- */
.feature-card {
    min-height:205px;
    padding:27px;
    border-radius:20px;
    border:1px solid #1D304D;
    background:
        linear-gradient(145deg, rgba(17,28,49,.96), rgba(12,21,38,.92));
    box-shadow:0 16px 45px rgba(0,0,0,.20);
    transition:transform .2s ease, border-color .2s ease, box-shadow .2s ease;
}

.feature-icon {
    width:45px;
    height:45px;
    display:flex;
    align-items:center;
    justify-content:center;
    border-radius:13px;
    background:rgba(59,130,246,.10);
    border:1px solid rgba(59,130,246,.22);
    font-size:23px;
    margin-bottom:23px;
}

.feature-title {
    color:#F1F5F9;
    font-size:17px;
    font-weight:800;
    margin-bottom:9px;
}

.muted {
    color:#8FA4C0;
    line-height:1.65;
}

/* ---------- AUTH ---------- */
.auth-wrap {
    max-width:520px;
    margin:70px auto 0;
}

.auth-card {
    padding:40px;
    border:1px solid #1D304D;
    border-radius:26px;
    background:
        radial-gradient(circle at 80% 0%, rgba(34,211,238,.07), transparent 30%),
        #0C1628;
    box-shadow:0 35px 100px rgba(0,0,0,.42);
}

.auth-title {
    font-size:32px;
    font-weight:850;
    letter-spacing:-1px;
    margin-bottom:7px;
}

.auth-copy {
    color:#8297B2;
    margin-bottom:25px;
}

/* ---------- DASHBOARD ---------- */
.dash-hero {
    padding:34px 38px;
    border:1px solid #1D304D;
    border-radius:24px;
    background:linear-gradient(135deg,#101D33,#0A1324);
    box-shadow:0 22px 65px rgba(0,0,0,.30);
    margin-bottom:30px;
}

.metric {
    min-height:128px;
    padding:23px;
    border:1px solid #1D304D;
    border-radius:18px;
    background:#101B2F;
    box-shadow:0 12px 35px rgba(0,0,0,.16);
}

.metric-num {
    font-size:34px;
    font-weight:900;
    color:#38BDF8;
    letter-spacing:-1px;
}

.metric-label {
    color:#7890AD;
    font-size:10px;
    font-weight:800;
    letter-spacing:1.3px;
    margin-top:7px;
}

.panel {
    padding:26px;
    border:1px solid #1D304D;
    border-radius:20px;
    background:#0E192C;
    margin-top:24px;
}

/* ---------- STREAMLIT CONTROLS ---------- */
.stButton > button {
    min-height:47px;
    border-radius:12px !important;
    border:1px solid rgba(59,130,246,.65) !important;
    background:linear-gradient(135deg,#2563EB,#0891B2) !important;
    color:white !important;
    font-weight:800 !important;
    box-shadow:0 8px 24px rgba(37,99,235,.16);
    transition:all .18s ease;
}

.stButton > button:hover {
    border-color:#22D3EE !important;
    box-shadow:0 12px 34px rgba(34,211,238,.18);
    transform:translateY(-1px);
}

div[data-testid="stTextInput"] input {
    background:#0D182B !important;
    color:#E5EEF9 !important;
    border:1px solid #203653 !important;
    border-radius:12px !important;
}

div[data-testid="stTextInput"] input:focus {
    border-color:#3B82F6 !important;
    box-shadow:0 0 0 1px #3B82F6 !important;
}

[data-testid="stSidebar"] {
    background:#070D19;
    border-right:1px solid #1D304D;
}

[data-testid="stSidebar"] .stButton > button {
    text-align:left !important;
    background:#0D1728 !important;
    border-color:#172A44 !important;
    box-shadow:none !important;
}

[data-testid="stSidebar"] .stButton > button:hover {
    background:#12233C !important;
}

/* ---------- RESULT AREA ---------- */
.result-card {
    padding:22px;
    border-radius:17px;
    border:1px solid #1D304D;
    background:#101B2F;
}

.footer {
    margin-top:70px;
    padding-top:24px;
    border-top:1px solid rgba(148,163,184,.12);
    color:#64748B;
    font-size:12px;
}

/* reduce default vertical gaps */
div[data-testid="stVerticalBlock"] > div { gap: .45rem; }

@media (max-width: 900px) {
    .hero { padding:42px 28px; }
    .hero h1 { letter-spacing:-2px; }
    .auth-card { padding:28px; }
}
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# NAVIGATION
# ============================================================

def top_nav():
    left, h1, h2, h3 = st.columns([5.6, 1, 1, 1.25])

    with left:
        st.markdown(
            """
            <div class="topbar">
                <div class="brand">
                    <div class="brand-mark">🔭</div>
                    <div>
                        <div>RepoLens AI</div>
                        <div class="brand-sub">SOFTWARE ARCHITECTURE INTELLIGENCE</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with h1:
        if st.button("Home", use_container_width=True):
            st.session_state.page = "landing"
            st.rerun()

    with h2:
        if st.button("Features", use_container_width=True):
            st.session_state.page = "landing"
            st.rerun()

    with h3:
        if st.session_state.authenticated:
            if st.button("Dashboard", use_container_width=True):
                st.session_state.page = "dashboard"
                st.rerun()
        else:
            if st.button("Login", use_container_width=True):
                st.session_state.page = "login"
                st.rerun()


# ============================================================
# LANDING PAGE
# ============================================================

def landing():
    top_nav()

    logo_col, _ = st.columns([1, 7])
    with logo_col:
        if LOGO.exists():
            st.image(str(LOGO), width=110)

    st.markdown(
        """
        <div class="hero">
            <span class="badge">AI-POWERED SOFTWARE ARCHITECTURE INTELLIGENCE</span>

            <h1>
                See Your Codebase.<br>
                <span class="gradient">Understand Its Architecture.</span>
            </h1>

            <div class="subtitle">
                RepoLens AI analyzes a GitHub repository and transforms complex
                source code into an understandable architecture map — including
                components, connections, data flow, technologies and security intelligence.
            </div>

            <div class="hero-mini">
                <span class="pill">✦ AI Architecture Analysis</span>
                <span class="pill">◈ Visual Architecture</span>
                <span class="pill">🛡 Security Intelligence</span>
                <span class="pill">↗ Data Flow</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    b1, b2, spacer = st.columns([1.2, 1.2, 3.8])

    with b1:
        if st.button("🚀 Get Started", use_container_width=True):
            st.session_state.page = "signup"
            st.rerun()

    with b2:
        if st.button("🔐 Sign In", use_container_width=True):
            st.session_state.page = "login"
            st.rerun()

    st.write("")
    st.markdown('<div class="section-kicker">WHY REPOLENS AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Powerful Developer Intelligence</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">From raw source code to a visual understanding of how a software system is built.</div>',
        unsafe_allow_html=True,
    )

    features = [
        ("🧠", "AI Architecture Analysis", "Understand unfamiliar repositories with AI-powered architecture extraction."),
        ("◈", "Visual Architecture", "Generate a clear component relationship map from detected code structure."),
        ("🛡", "Security Intelligence", "Surface potential security concerns that can reasonably be inferred from the code."),
        ("↗", "Data Flow", "Understand important application data movement across detected components."),
        ("⚡", "Fast Scanning", "Scan public GitHub repositories quickly using shallow cloning and focused source extraction."),
        ("📊", "Developer Dashboard", "Keep your analyses organized with repository history and architecture metrics."),
    ]

    for row in range(2):
        cols = st.columns(3, gap="large")
        for col_idx in range(3):
            icon, title, desc = features[row * 3 + col_idx]
            with cols[col_idx]:
                st.markdown(
                    f"""
                    <div class="feature-card">
                        <div class="feature-icon">{icon}</div>
                        <div class="feature-title">{title}</div>
                        <div class="muted">{desc}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        st.write("")

    st.markdown(
        """
        <div class="footer">
            <b>RepoLens AI</b> · See Your Codebase. Understand Its Architecture.
            <br>AI-powered repository intelligence for developers.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# LOGIN / SIGNUP
# ============================================================

def auth_page(kind):
    top_nav()

    st.markdown('<div class="auth-wrap">', unsafe_allow_html=True)

    if kind == "login":
        st.markdown(
            """
            <div class="auth-card">
                <div class="badge">SECURE DEVELOPER ACCESS</div>
                <div class="auth-title">Welcome back 👋</div>
                <div class="auth-copy">
                    Sign in to access your RepoLens architecture workspace.
                </div>
            """,
            unsafe_allow_html=True,
        )

        email = st.text_input("Email", placeholder="you@example.com", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("🔐 Sign In", use_container_width=True):
            user = st.session_state.users.get(email.strip().lower())

            if user and user["password"] == password:
                st.session_state.authenticated = True
                st.session_state.user = email.strip().lower()
                st.session_state.page = "dashboard"
                st.rerun()
            else:
                st.error("Invalid email or password.")

        st.caption("Demo account: demo@repolens.ai / demo123")

        if st.button("Create a new account", use_container_width=True):
            st.session_state.page = "signup"
            st.rerun()

    else:
        st.markdown(
            """
            <div class="auth-card">
                <div class="badge">START YOUR WORKSPACE</div>
                <div class="auth-title">Create your account 🚀</div>
                <div class="auth-copy">
                    Build your personal repository intelligence workspace.
                </div>
            """,
            unsafe_allow_html=True,
        )

        name = st.text_input("Full name", key="signup_name")
        email = st.text_input("Email", placeholder="you@example.com", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        confirm = st.text_input("Confirm password", type="password", key="signup_confirm")

        if st.button("🚀 Create Account", use_container_width=True):
            email_clean = email.strip().lower()

            if not name.strip() or not email_clean or not password:
                st.error("Please fill all fields.")
            elif password != confirm:
                st.error("Passwords do not match.")
            elif email_clean in st.session_state.users:
                st.error("Account already exists.")
            else:
                st.session_state.users[email_clean] = {
                    "name": name.strip(),
                    "password": password,
                }
                st.session_state.authenticated = True
                st.session_state.user = email_clean
                st.session_state.page = "dashboard"
                st.rerun()

        if st.button("Already have an account? Sign in", use_container_width=True):
            st.session_state.page = "login"
            st.rerun()

    if st.button("← Back to Home", use_container_width=True):
        st.session_state.page = "landing"
        st.rerun()

    st.markdown("</div></div>", unsafe_allow_html=True)


# ============================================================
# DASHBOARD SIDEBAR
# ============================================================

def dashboard_sidebar():
    with st.sidebar:
        st.markdown("## 🔭 RepoLens AI")
        st.caption("Software Architecture Intelligence")
        st.divider()

        name = st.session_state.users.get(
            st.session_state.user, {}
        ).get("name", "Developer")

        st.markdown(f"**{name}**")
        st.caption(st.session_state.user)

        st.write("")

        if st.button("📊  Overview", use_container_width=True):
            st.session_state.tab = "overview"
            st.rerun()

        if st.button("🔍  Analyze Repository", use_container_width=True):
            st.session_state.tab = "analyze"
            st.rerun()

        if st.button("🕘  Analysis History", use_container_width=True):
            st.session_state.tab = "history"
            st.rerun()

        st.divider()

        if st.button("🚪  Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = ""
            st.session_state.page = "landing"
            st.rerun()


# ============================================================
# RESULTS
# ============================================================

def show_results(arch, files):
    comps = arch.get("components", [])
    conns = arch.get("connections", [])
    tech = arch.get("technologies", [])
    sec = arch.get("security_findings", [])
    flow = arch.get("data_flow", [])

    st.markdown('<div class="section-kicker">ANALYSIS COMPLETE</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Architecture Overview</div>', unsafe_allow_html=True)

    metrics = [
        ("FILES", len(files)),
        ("COMPONENTS", len(comps)),
        ("CONNECTIONS", len(conns)),
        ("SECURITY FINDINGS", len(sec)),
    ]

    cols = st.columns(4, gap="large")
    for col, (label, value) in zip(cols, metrics):
        with col:
            st.markdown(
                f"""
                <div class="metric">
                    <div class="metric-num">{value}</div>
                    <div class="metric-label">{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('<div class="section-title" style="margin-top:34px">Project Intelligence</div>', unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="result-card">
            <b>Project Type</b><br>
            <span class="muted">{arch.get("project_type", "Unknown")}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if tech:
        st.markdown('<div class="section-title" style="margin-top:30px">⚙️ Technologies</div>', unsafe_allow_html=True)
        st.markdown("  ".join(f"`{str(x)}`" for x in tech))

    st.markdown('<div class="section-title" style="margin-top:30px">◈ Visual Architecture</div>', unsafe_allow_html=True)

    try:
        diagram = create_visual_architecture(arch)
        st.image(diagram, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not render diagram: {e}")

    if comps:
        st.markdown('<div class="section-title" style="margin-top:30px">🧩 Components</div>', unsafe_allow_html=True)
        for component in comps:
            with st.expander(
                f'🔹 {component.get("name", "Unknown")} · {component.get("type", "Component")}'
            ):
                st.write(component.get("description", ""))

    if flow:
        st.markdown('<div class="section-title" style="margin-top:30px">↗ Data Flow</div>', unsafe_allow_html=True)
        for i, item in enumerate(flow, 1):
            st.markdown(f"**{i}.** {item}")

    st.markdown('<div class="section-title" style="margin-top:30px">🛡 Security Intelligence</div>', unsafe_allow_html=True)

    if sec:
        for item in sec:
            st.warning(str(item))
    else:
        st.success("No significant security findings were detected.")


# ============================================================
# DASHBOARD
# ============================================================

def dashboard():
    dashboard_sidebar()

    name = st.session_state.users.get(
        st.session_state.user, {}
    ).get("name", "Developer")

    st.markdown(
        f"""
        <div class="dash-hero">
            <div class="badge">REPOSITORY INTELLIGENCE WORKSPACE</div>
            <h1 style="font-size:43px;letter-spacing:-2px;margin:17px 0 8px">
                Welcome back, <span class="gradient">{name}</span>
            </h1>
            <div class="subtitle" style="font-size:15px">
                Understand your codebase. Visualize its architecture. Find what matters.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab = st.session_state.get("tab", "overview")

    if tab == "overview":
        history = st.session_state.history

        st.markdown('<div class="section-kicker">WORKSPACE</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Dashboard Overview</div>', unsafe_allow_html=True)

        repositories = len({item["repo"] for item in history})
        components = sum(item["components"] for item in history)
        security = sum(item["security"] for item in history)

        cols = st.columns(4, gap="large")
        values = [
            ("ANALYSES", len(history)),
            ("REPOSITORIES", repositories),
            ("COMPONENTS", components),
            ("SECURITY FINDINGS", security),
        ]

        for col, (label, value) in zip(cols, values):
            with col:
                st.markdown(
                    f"""
                    <div class="metric">
                        <div class="metric-num">{value}</div>
                        <div class="metric-label">{label}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("### 🚀 Quick Start")
        st.markdown(
            '<div class="muted">Paste a public GitHub repository and let RepoLens AI map its architecture.</div>',
            unsafe_allow_html=True,
        )
        st.write("")

        if st.button("🚀 Analyze a Repository", use_container_width=True):
            st.session_state.tab = "analyze"
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        if history:
            st.markdown("### Recent Analyses")
            for item in reversed(history[-5:]):
                st.markdown(
                    f"""
                    <div class="result-card" style="margin-bottom:10px">
                        <b>🔗 {item["repo"]}</b><br>
                        <span class="muted">
                            {item["project_type"]} ·
                            {item["components"]} components ·
                            {item["security"]} security findings
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    elif tab == "history":
        st.markdown('<div class="section-kicker">WORKSPACE</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Analysis History</div>', unsafe_allow_html=True)

        if not st.session_state.history:
            st.info("No analyses yet. Analyze your first repository to build your history.")
        else:
            for item in reversed(st.session_state.history):
                st.markdown(
                    f"""
                    <div class="result-card" style="margin-bottom:12px">
                        <b>🔗 {item["repo"]}</b><br>
                        <span class="muted">
                            {item["project_type"]} ·
                            {item["components"]} components ·
                            {item["security"]} security findings
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    else:
        st.markdown('<div class="section-kicker">AI ANALYZER</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Analyze Repository</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-copy">Enter a public GitHub URL. RepoLens AI will scan the source and build its architecture intelligence.</div>',
            unsafe_allow_html=True,
        )

        url = st.text_input(
            "GitHub Repository URL",
            value=st.session_state.repo_url,
            placeholder="https://github.com/username/repository",
            label_visibility="collapsed",
        )

        if st.button("🚀 ANALYZE REPOSITORY", use_container_width=True):
            if not url.strip():
                st.warning("Please enter a GitHub repository URL.")
            elif not client:
                st.error("GROQ_API_KEY is missing from Streamlit Secrets.")
            else:
                try:
                    with st.status("🔍 Analyzing repository...", expanded=True) as status:
                        status.write("📥 Cloning repository...")
                        path, err = clone_repository(url)

                        if err:
                            raise RuntimeError(err)

                        try:
                            status.write("📂 Scanning files...")
                            files = scan_repository(path)

                            status.write("📄 Extracting source code...")
                            code = extract_code(path, files)

                            status.write("🤖 Groq AI analyzing architecture...")
                            raw = analyze_architecture(code)
                            arch = parse_architecture_result(raw)

                            if not arch:
                                raise RuntimeError("AI returned an invalid architecture response.")

                        finally:
                            shutil.rmtree(path, ignore_errors=True)

                        status.update(
                            label="✅ Analysis completed!",
                            state="complete",
                        )

                    st.session_state.repo_url = url.strip()
                    st.session_state.files = files
                    st.session_state.architecture = arch

                    st.session_state.history.append(
                        {
                            "repo": url.strip(),
                            "project_type": arch.get("project_type", "Unknown"),
                            "components": len(arch.get("components", [])),
                            "security": len(arch.get("security_findings", [])),
                        }
                    )

                except Exception as e:
                    st.error(f"Analysis failed: {e}")
                    st.code(traceback.format_exc())

        if st.session_state.architecture:
            show_results(
                st.session_state.architecture,
                st.session_state.files,
            )


# ============================================================
# ROUTER
# ============================================================

if st.session_state.page == "landing":
    landing()

elif st.session_state.page == "login":
    auth_page("login")

elif st.session_state.page == "signup":
    auth_page("signup")

elif st.session_state.page == "dashboard":
    if not st.session_state.authenticated:
        st.session_state.page = "login"
        st.rerun()
    dashboard()
