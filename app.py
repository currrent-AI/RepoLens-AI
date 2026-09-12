
import streamlit as st
import os
import re
import json
import tempfile
import shutil
from pathlib import Path

from git import Repo
from groq import Groq
import graphviz


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="RepoLens AI",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_NAME = "openai/gpt-oss-120b"

# Keep this deliberately low because the Groq organization
# currently has an 8,000 TPM limit.
MAX_TOTAL_CHARS = 20000
MAX_FILE_CHARS = 5000

IGNORE_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    ".next",
    ".cache",
    ".idea",
    ".vscode"
}

CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".cpp", ".c", ".h", ".hpp",
    ".cs", ".go", ".rs", ".php",
    ".rb", ".swift", ".kt", ".kts",
    ".sql", ".html", ".css", ".scss",
    ".json", ".yaml", ".yml"
}


# ============================================================
# GROQ CLIENT
# ============================================================

def get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        try:
            api_key = st.secrets["GROQ_API_KEY"]
        except Exception:
            api_key = None

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured. "
            "Add it to Streamlit Secrets."
        )

    return Groq(api_key=api_key)


# ============================================================
# REPOSITORY CLONING
# ============================================================

def clone_repository(github_url):
    github_url = github_url.strip()

    if not github_url.startswith("https://github.com/"):
        raise ValueError(
            "Please enter a valid public GitHub repository URL."
        )

    temp_dir = tempfile.mkdtemp(prefix="repolens_")

    try:
        Repo.clone_from(
            github_url,
            temp_dir,
            depth=1
        )
        return temp_dir

    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


# ============================================================
# REPOSITORY SCANNING
# ============================================================

def scan_repository(repo_path):
    files = []

    for root, dirs, filenames in os.walk(repo_path):

        dirs[:] = [
            d for d in dirs
            if d not in IGNORE_DIRS
        ]

        for filename in filenames:
            path = Path(root) / filename

            if path.suffix.lower() in CODE_EXTENSIONS:
                relative_path = path.relative_to(repo_path)

                files.append({
                    "path": str(relative_path),
                    "full_path": str(path)
                })

    return files


# ============================================================
# SOURCE EXTRACTION
# ============================================================

def extract_code(repo_path, files, max_chars=MAX_TOTAL_CHARS):

    codebase = []
    total_chars = 0

    for item in files:

        try:
            file_path = item["path"]
            full_path = os.path.join(repo_path, file_path)

            with open(
                full_path,
                "r",
                encoding="utf-8",
                errors="ignore"
            ) as f:
                content = f.read()

            if not content.strip():
                continue

            remaining = max_chars - total_chars

            if remaining <= 0:
                break

            per_file_limit = min(
                MAX_FILE_CHARS,
                remaining
            )

            content = content[:per_file_limit]

            codebase.append({
                "path": file_path,
                "content": content
            })

            total_chars += len(content)

        except Exception:
            continue

    return codebase


# ============================================================
# AI ARCHITECTURE ANALYSIS
# ============================================================

def analyze_architecture(codebase):

    client = get_groq_client()

    code_text = ""

    for item in codebase:
        code_text += (
            f"\n\n===== FILE: {item['path']} =====\n"
        )
        code_text += item["content"]

    system_prompt = """
You are an expert software architecture analyzer.

Analyze the provided source code and identify the
software architecture.

Return ONLY valid JSON using exactly this structure:

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
- Do not invent components that are not supported by the code.
- Identify frontend, backend, APIs, databases, services
  and important modules when present.
- "connections" should describe how detected components
  communicate.
- "data_flow" should describe the important flow of data.
- "security_findings" should contain only potential issues
  reasonably inferred from the provided code.
- If something cannot be determined, use an empty array
  or "Unknown".
"""

    user_prompt = f"""
Analyze this repository:

{code_text}
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
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


# ============================================================
# JSON PARSER
# ============================================================

def parse_architecture_result(raw_result):

    if not raw_result:
        return {
            "project_type": "Unknown",
            "technologies": [],
            "components": [],
            "connections": [],
            "data_flow": [],
            "security_findings": []
        }

    text = raw_result.strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:

        try:
            return json.loads(
                text[start:end + 1]
            )

        except json.JSONDecodeError:
            pass

    return {
        "project_type": "Unknown",
        "technologies": [],
        "components": [],
        "connections": [],
        "data_flow": [],
        "security_findings": []
    }


# ============================================================
# ARCHITECTURE DIAGRAM
# ============================================================

def create_visual_architecture(architecture):

    dot = graphviz.Digraph(
        "RepoLens_Architecture",
        format="png"
    )

    dot.attr(
        rankdir="LR",
        bgcolor="#080F1E",
        pad="0.5",
        nodesep="0.5",
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
        margin="0.2"
    )

    dot.attr(
        "edge",
        color="#22D3EE",
        fontcolor="#8FA4C2",
        fontname="Arial"
    )

    components = architecture.get(
        "components",
        []
    )

    connections = architecture.get(
        "connections",
        []
    )

    component_names = set()

    for component in components:

        name = component.get(
            "name",
            "Unknown"
        )

        component_type = component.get(
            "type",
            ""
        )

        description = component.get(
            "description",
            ""
        )

        node_id = re.sub(
            r"[^a-zA-Z0-9_]",
            "_",
            name
        )

        component_names.add(name)

        label = (
            f"{name}\\n"
            f"{component_type}\\n"
            f"{description[:80]}"
        )

        dot.node(
            node_id,
            label=label
        )

    for connection in connections:

        source = connection.get("from", "")
        target = connection.get("to", "")
        relationship = connection.get(
            "relationship",
            ""
        )

        if source not in component_names:
            continue

        if target not in component_names:
            continue

        source_id = re.sub(
            r"[^a-zA-Z0-9_]",
            "_",
            source
        )

        target_id = re.sub(
            r"[^a-zA-Z0-9_]",
            "_",
            target
        )

        dot.edge(
            source_id,
            target_id,
            label=relationship
        )

    output_dir = tempfile.mkdtemp(
        prefix="repolens_diagram_"
    )

    output_base = os.path.join(
        output_dir,
        "architecture"
    )

    output_path = dot.render(
        output_base,
        cleanup=True
    )

    return output_path


# ============================================================
# FORMATTING HELPERS
# ============================================================

def format_technologies(technologies):

    if not technologies:
        return "No technologies detected."

    lines = []

    for tech in technologies:

        if isinstance(tech, dict):
            name = tech.get("name", "Unknown")
            category = tech.get(
                "category",
                ""
            )

            if category:
                lines.append(
                    f"• **{name}** — {category}"
                )
            else:
                lines.append(
                    f"• **{name}**"
                )

        else:
            lines.append(
                f"• **{tech}**"
            )

    return "\n\n".join(lines)


def format_components(components):

    if not components:
        return "No components detected."

    lines = []

    for component in components:

        name = component.get(
            "name",
            "Unknown"
        )

        component_type = component.get(
            "type",
            "Unknown"
        )

        description = component.get(
            "description",
            ""
        )

        lines.append(
            f"### {name}\n"
            f"**Type:** {component_type}\n\n"
            f"{description}"
        )

    return "\n\n---\n\n".join(lines)


def format_security(findings):

    if not findings:
        return "### ✅ No potential security findings detected."

    lines = []

    for finding in findings:

        if isinstance(finding, dict):

            title = finding.get(
                "title",
                finding.get(
                    "issue",
                    "Security finding"
                )
            )

            description = finding.get(
                "description",
                finding.get(
                    "details",
                    ""
                )
            )

            severity = finding.get(
                "severity",
                ""
            )

            line = f"### ⚠️ {title}"

            if severity:
                line += f" — **{severity}**"

            if description:
                line += f"\n\n{description}"

            lines.append(line)

        else:
            lines.append(
                f"### ⚠️ {finding}"
            )

    return "\n\n".join(lines)


def format_data_flow(data_flow):

    if not data_flow:
        return "No significant data flow detected."

    lines = []

    for item in data_flow:

        if isinstance(item, dict):

            source = item.get(
                "from",
                item.get(
                    "source",
                    ""
                )
            )

            target = item.get(
                "to",
                item.get(
                    "target",
                    ""
                )
            )

            description = item.get(
                "description",
                item.get(
                    "flow",
                    ""
                )
            )

            if source or target:
                lines.append(
                    f"**{source} → {target}**\n\n"
                    f"{description}"
                )
            else:
                lines.append(
                    str(description)
                )

        else:
            lines.append(
                f"• {item}"
            )

    return "\n\n".join(lines)


# ============================================================
# COMPLETE ANALYSIS
# ============================================================

def analyze_repository(github_url):

    repo_path = None

    try:

        repo_path = clone_repository(
            github_url
        )

        files = scan_repository(
            repo_path
        )

        codebase = extract_code(
            repo_path,
            files
        )

        raw_result = analyze_architecture(
            codebase
        )

        architecture = parse_architecture_result(
            raw_result
        )

        diagram_path = create_visual_architecture(
            architecture
        )

        return {
            "architecture": architecture,
            "diagram": diagram_path,
            "file_count": len(files),
            "analyzed_files": len(codebase),
            "characters": sum(
                len(item["content"])
                for item in codebase
            )
        }

    finally:

        if repo_path and os.path.exists(repo_path):
            shutil.rmtree(
                repo_path,
                ignore_errors=True
            )


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .stApp {
        background:
            radial-gradient(
                circle at top right,
                rgba(59,130,246,0.10),
                transparent 35%
            ),
            #080F1E;
        color: #F1F5F9;
    }

    .main-title {
        font-size: 3.5rem;
        font-weight: 800;
        letter-spacing: -2px;
        margin-bottom: 0.2rem;
    }

    .gradient-text {
        background: linear-gradient(
            90deg,
            #3B82F6,
            #22D3EE
        );
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .subtitle {
        color: #8FA4C2;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }

    .hero {
        padding: 2rem 0 1rem 0;
    }

    .card {
        background: rgba(17,28,49,0.72);
        border: 1px solid #1D304D;
        border-radius: 18px;
        padding: 1.4rem;
        margin-bottom: 1rem;
        backdrop-filter: blur(12px);
    }

    .stat-number {
        font-size: 2rem;
        font-weight: 800;
    }

    .stat-label {
        color: #8FA4C2;
        font-size: 0.85rem;
    }

    .section-title {
        font-size: 1.4rem;
        font-weight: 700;
        margin-top: 1.5rem;
        margin-bottom: 0.8rem;
    }

    div[data-testid="stTextInput"] input {
        background: #111C31;
        border: 1px solid #1D304D;
        color: #F1F5F9;
        border-radius: 10px;
    }

    div[data-testid="stButton"] button {
        background: linear-gradient(
            90deg,
            #2563EB,
            #0891B2
        );
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: 700;
        padding: 0.7rem 1.2rem;
    }

    div[data-testid="stButton"] button:hover {
        border: 1px solid #22D3EE;
        box-shadow:
            0 0 20px rgba(34,211,238,0.18);
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# HEADER
# ============================================================

col_logo, col_title = st.columns(
    [1, 7],
    vertical_alignment="center"
)

with col_logo:
    logo_path = Path(
        "assets/repolens_logo.png"
    )

    if logo_path.exists():
        st.image(
            str(logo_path),
            width=75
        )
    else:
        st.markdown(
            "🔍",
            unsafe_allow_html=True
        )

with col_title:
    st.markdown(
        '<div style="font-size:1.8rem;font-weight:800;">'
        '<span class="gradient-text">RepoLens AI</span>'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div style="color:#8FA4C2;">'
        'AI-Powered Repository Intelligence'
        '</div>',
        unsafe_allow_html=True
    )



# ============================================================
# PREMIUM REPOLENS AI UI
# ============================================================

# Premium spacing + component styling
st.markdown("""
<style>

.block-container {
    padding-top: 1.5rem !important;
    padding-left: 5% !important;
    padding-right: 5% !important;
    padding-bottom: 4rem !important;
}

/* HERO */
.rl-hero {
    position: relative;
    overflow: hidden;
    margin-top: 2rem;
    padding: 72px 64px;
    border-radius: 30px;
    border: 1px solid rgba(67, 198, 255, 0.18);
    background:
        radial-gradient(circle at 88% 20%, rgba(0, 196, 255, 0.14), transparent 30%),
        radial-gradient(circle at 8% 90%, rgba(50, 90, 255, 0.12), transparent 32%),
        linear-gradient(135deg, #0d1729 0%, #0a1324 55%, #08111f 100%);
    box-shadow:
        0 30px 80px rgba(0,0,0,0.35),
        inset 0 1px 0 rgba(255,255,255,0.035);
}

.rl-hero::after {
    content: "";
    position: absolute;
    width: 420px;
    height: 420px;
    right: -160px;
    top: -180px;
    border-radius: 50%;
    border: 1px solid rgba(45, 211, 255, 0.12);
    box-shadow:
        0 0 0 45px rgba(45,211,255,0.025),
        0 0 0 90px rgba(45,211,255,0.018);
}

.rl-eyebrow {
    display: inline-block;
    padding: 10px 16px;
    margin-bottom: 25px;
    border-radius: 999px;
    border: 1px solid rgba(55, 203, 255, 0.25);
    background: rgba(24, 166, 220, 0.08);
    color: #35d5ff;
    font-size: 0.75rem;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
}

.rl-title {
    position: relative;
    z-index: 2;
    max-width: 850px;
    margin: 0;
    color: #f4f8ff;
    font-size: clamp(2.7rem, 5vw, 5.2rem);
    line-height: 1.03;
    font-weight: 850;
    letter-spacing: -3px;
}

.rl-gradient {
    background: linear-gradient(90deg, #35d5ff, #6c8cff, #8c7bff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.rl-subtitle {
    position: relative;
    z-index: 2;
    max-width: 700px;
    margin-top: 25px;
    color: #93a8c5;
    font-size: 1.08rem;
    line-height: 1.8;
}

.rl-status {
    position: relative;
    z-index: 2;
    display: flex;
    gap: 10px;
    align-items: center;
    margin-top: 32px;
    color: #8fa4c2;
    font-size: 0.85rem;
}

.rl-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #22c55e;
    box-shadow: 0 0 15px rgba(34,197,94,0.8);
}

/* SECTION */
.rl-section {
    margin-top: 62px;
    margin-bottom: 24px;
}

.rl-kicker {
    color: #35d5ff;
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 8px;
}

.rl-section-title {
    color: #f1f5f9;
    font-size: 1.9rem;
    font-weight: 800;
    letter-spacing: -0.7px;
}

/* FEATURE CARDS */
.rl-card {
    min-height: 205px;
    padding: 28px;
    border-radius: 22px;
    border: 1px solid rgba(91, 128, 171, 0.18);
    background: linear-gradient(
        145deg,
        rgba(20, 34, 57, 0.96),
        rgba(12, 23, 40, 0.96)
    );
    box-shadow: 0 18px 45px rgba(0,0,0,0.20);
}

.rl-card-icon {
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 14px;
    background: linear-gradient(135deg, rgba(45,211,255,0.18), rgba(85,110,255,0.14));
    border: 1px solid rgba(55,211,255,0.18);
    font-size: 1.35rem;
    margin-bottom: 20px;
}

.rl-card-title {
    color: #f1f5f9;
    font-size: 1.05rem;
    font-weight: 750;
    margin-bottom: 10px;
}

.rl-card-text {
    color: #8297b4;
    font-size: 0.88rem;
    line-height: 1.65;
}

/* ANALYZER */
.rl-analyzer {
    margin-top: 50px;
    padding: 34px;
    border-radius: 25px;
    border: 1px solid rgba(64, 123, 180, 0.22);
    background: linear-gradient(
        145deg,
        rgba(17,29,49,0.98),
        rgba(9,18,32,0.98)
    );
    box-shadow: 0 25px 65px rgba(0,0,0,0.25);
}

.rl-analyzer-title {
    color: #f5f8ff;
    font-size: 1.45rem;
    font-weight: 800;
}

.rl-analyzer-subtitle {
    color: #8297b4;
    margin-top: 7px;
    margin-bottom: 24px;
    font-size: 0.9rem;
}

/* INPUT */
div[data-testid="stTextInput"] input {
    height: 54px !important;
    border-radius: 14px !important;
    border: 1px solid #243b5b !important;
    background: #0b1525 !important;
    color: #f1f5f9 !important;
    padding-left: 18px !important;
}

div[data-testid="stTextInput"] input:focus {
    border-color: #35d5ff !important;
    box-shadow: 0 0 0 1px rgba(53,213,255,0.18) !important;
}

/* BUTTON */
div.stButton > button {
    height: 52px !important;
    border-radius: 14px !important;
    border: 1px solid rgba(53,213,255,0.25) !important;
    background: linear-gradient(90deg, #147bd1, #159cc9) !important;
    color: white !important;
    font-weight: 800 !important;
    letter-spacing: 0.4px !important;
    box-shadow: 0 10px 30px rgba(21,156,201,0.18) !important;
}

div.stButton > button:hover {
    border-color: #35d5ff !important;
    transform: translateY(-1px);
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# HERO
# ============================================================

st.markdown("""
<div class="rl-hero">

    <div class="rl-eyebrow">
        ✦ AI-POWERED SOFTWARE ARCHITECTURE INTELLIGENCE
    </div>

    <div class="rl-title">
        See Your Codebase.
        <br>
        <span class="rl-gradient">
            Understand Its Architecture.
        </span>
    </div>

    <div class="rl-subtitle">
        Analyze any GitHub repository with AI and transform
        complex source code into a clear, visual understanding
        of your software architecture.
    </div>

    <div class="rl-status">
        <span class="rl-dot"></span>
        AI Architecture Analysis Engine Online
    </div>

</div>
""", unsafe_allow_html=True)


# ============================================================
# FEATURES
# ============================================================

st.markdown("""
<div class="rl-section">
    <div class="rl-kicker">WHAT REPOLENS DOES</div>
    <div class="rl-section-title">From source code to architecture intelligence.</div>
</div>
""", unsafe_allow_html=True)

feature_col1, feature_col2, feature_col3 = st.columns(3, gap="large")

with feature_col1:
    st.markdown("""
    <div class="rl-card">
        <div class="rl-card-icon">🔍</div>
        <div class="rl-card-title">Repository Intelligence</div>
        <div class="rl-card-text">
            Scan GitHub repositories and understand the structure,
            files, technologies and important source-code patterns.
        </div>
    </div>
    """, unsafe_allow_html=True)

with feature_col2:
    st.markdown("""
    <div class="rl-card">
        <div class="rl-card-icon">🧠</div>
        <div class="rl-card-title">AI Architecture Analysis</div>
        <div class="rl-card-text">
            Use AI to identify components, relationships,
            architecture patterns, data flow and potential risks.
        </div>
    </div>
    """, unsafe_allow_html=True)

with feature_col3:
    st.markdown("""
    <div class="rl-card">
        <div class="rl-card-icon">🗺️</div>
        <div class="rl-card-title">Visual Architecture</div>
        <div class="rl-card-text">
            Convert the analyzed codebase into an architecture
            diagram that is easier for developers to understand.
        </div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# ANALYZER
# ============================================================

st.markdown("""
<div class="rl-analyzer">

    <div class="rl-analyzer-title">
        🚀 Analyze a Repository
    </div>

    <div class="rl-analyzer-subtitle">
        Enter a public GitHub repository URL to generate its AI architecture report.
    </div>

</div>
""", unsafe_allow_html=True)

github_url = st.text_input(
    "GitHub Repository URL",
    placeholder="https://github.com/username/repository",
    label_visibility="collapsed"
)

analyze = st.button(
    "🚀  ANALYZE REPOSITORY",
    use_container_width=True
)


# ============================================================
# ANALYSIS
# ============================================================
# ANALYSIS
# ============================================================

if analyze:

    if not github_url.strip():

        st.error(
            "Please enter a GitHub repository URL."
        )

    else:

        with st.spinner(
            "🔍 Cloning repository and scanning source code..."
        ):

            try:

                result = analyze_repository(
                    github_url
                )

                architecture = result[
                    "architecture"
                ]

                st.success(
                    "✅ Repository analysis completed!"
                )

                # ------------------------------------------------
                # STATS
                # ------------------------------------------------

                components = architecture.get(
                    "components",
                    []
                )

                technologies = architecture.get(
                    "technologies",
                    []
                )

                security = architecture.get(
                    "security_findings",
                    []
                )

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric(
                        "Files Found",
                        result["file_count"]
                    )

                with col2:
                    st.metric(
                        "Files Analyzed",
                        result["analyzed_files"]
                    )

                with col3:
                    st.metric(
                        "Components",
                        len(components)
                    )

                with col4:
                    st.metric(
                        "Security Findings",
                        len(security)
                    )

                # ------------------------------------------------
                # PROJECT TYPE
                # ------------------------------------------------

                st.markdown(
                    '<div class="section-title">'
                    '📊 Project Overview'
                    '</div>',
                    unsafe_allow_html=True
                )

                st.markdown(
                    '<div class="card">'
                    f'<b>Project Type:</b> '
                    f'{architecture.get("project_type", "Unknown")}'
                    '</div>',
                    unsafe_allow_html=True
                )

                # ------------------------------------------------
                # TECHNOLOGIES
                # ------------------------------------------------

                st.markdown(
                    '<div class="section-title">'
                    '⚙️ Technologies'
                    '</div>',
                    unsafe_allow_html=True
                )

                st.markdown(
                    format_technologies(
                        technologies
                    )
                )

                # ------------------------------------------------
                # COMPONENTS
                # ------------------------------------------------

                st.markdown(
                    '<div class="section-title">'
                    '🧩 Architecture Components'
                    '</div>',
                    unsafe_allow_html=True
                )

                st.markdown(
                    format_components(
                        components
                    )
                )

                # ------------------------------------------------
                # SECURITY
                # ------------------------------------------------

                st.markdown(
                    '<div class="section-title">'
                    '🛡️ Security Intelligence'
                    '</div>',
                    unsafe_allow_html=True
                )

                st.markdown(
                    format_security(
                        security
                    )
                )

                # ------------------------------------------------
                # DATA FLOW
                # ------------------------------------------------

                st.markdown(
                    '<div class="section-title">'
                    '🔄 Data Flow'
                    '</div>',
                    unsafe_allow_html=True
                )

                st.markdown(
                    format_data_flow(
                        architecture.get(
                            "data_flow",
                            []
                        )
                    )
                )

                # ------------------------------------------------
                # DIAGRAM
                # ------------------------------------------------

                st.markdown(
                    '<div class="section-title">'
                    '🗺️ Architecture Diagram'
                    '</div>',
                    unsafe_allow_html=True
                )

                diagram_path = result[
                    "diagram"
                ]

                if diagram_path and os.path.exists(
                    diagram_path
                ):
                    st.image(
                        diagram_path,
                        use_container_width=True
                    )

                st.caption(
                    f"🧠 AI analyzed "
                    f"{result['characters']:,} characters "
                    f"from {result['analyzed_files']} source files."
                )

            except Exception as e:

                st.error(
                    f"❌ Analysis failed: {e}"
                )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div style="
        text-align:center;
        color:#64748B;
        padding:3rem 0 1rem 0;
    ">
        RepoLens AI · AI-Powered Software Architecture Intelligence
    </div>
    """,
    unsafe_allow_html=True
)
