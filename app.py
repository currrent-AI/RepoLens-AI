
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
        max_tokens=1500
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
# RepoLens AI — Product UI
# Landing → Login/Signup → Dashboard → Analyzer
# ============================================================
import streamlit as st
import traceback

st.set_page_config(page_title='RepoLens AI', page_icon='🔭', layout='wide')

if 'page' not in st.session_state: st.session_state.page='landing'
if 'authenticated' not in st.session_state: st.session_state.authenticated=False
if 'user' not in st.session_state: st.session_state.user=''
if 'users' not in st.session_state: st.session_state.users={'demo@repolens.ai':{'name':'Demo User','password':'demo123'}}
if 'history' not in st.session_state: st.session_state.history=[]
if 'architecture' not in st.session_state: st.session_state.architecture=None
if 'files' not in st.session_state: st.session_state.files=[]
if 'repo_url' not in st.session_state: st.session_state.repo_url=''

st.markdown('''<style>
.stApp{background:radial-gradient(circle at 15% 5%,rgba(59,130,246,.12),transparent 28%),radial-gradient(circle at 85% 15%,rgba(34,211,238,.08),transparent 25%),#080F1E;color:#F1F5F9}
.block-container{max-width:1380px;padding-top:1.3rem;padding-bottom:4rem}
.hero{padding:50px;border:1px solid #1D304D;border-radius:26px;background:linear-gradient(135deg,rgba(17,28,49,.97),rgba(8,15,30,.94));box-shadow:0 25px 80px rgba(0,0,0,.35);margin:22px 0 28px}
.hero h1{font-size:clamp(42px,6vw,72px);line-height:1.02;margin:12px 0;letter-spacing:-2.5px}.gradient{background:linear-gradient(90deg,#3B82F6,#22D3EE);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.subtitle,.muted{color:#8FA4C0;line-height:1.7}.subtitle{font-size:18px;max-width:820px}.badge{display:inline-block;padding:7px 13px;border:1px solid #274568;border-radius:999px;color:#22D3EE;background:rgba(34,211,238,.07);font-size:12px;font-weight:700;letter-spacing:1px}
.card{background:rgba(17,28,49,.86);border:1px solid #1D304D;border-radius:18px;padding:24px;height:100%}.section-title{font-size:26px;font-weight:800;margin:30px 0 16px}.feature-title{font-size:18px;font-weight:750;margin:10px 0 7px}.metric{background:#111C31;border:1px solid #1D304D;border-radius:16px;padding:18px;text-align:center}.metric-num{font-size:30px;font-weight:850;color:#3B82F6}.metric-label{color:#8FA4C0;font-size:12px}
.auth{max-width:560px;margin:60px auto;background:#0D1729;border:1px solid #1D304D;border-radius:24px;padding:36px;box-shadow:0 25px 80px rgba(0,0,0,.4)}
.stButton>button{min-height:46px;border-radius:11px;border:1px solid #3B82F6;background:linear-gradient(135deg,#2563EB,#0891B2);color:white;font-weight:750}[data-testid=stSidebar]{background:#080D1A;border-right:1px solid #1D304D}
</style>''',unsafe_allow_html=True)

def nav():
    a,b,c,d=st.columns([5,1,1,1])
    with a: st.markdown('### 🔭 **RepoLens AI**')
    with b:
        if st.button('Home'): st.session_state.page='landing';st.rerun()
    with c:
        if st.button('Features'): st.session_state.page='landing';st.rerun()
    with d:
        if st.session_state.authenticated:
            if st.button('Dashboard'): st.session_state.page='dashboard';st.rerun()
        else:
            if st.button('Login'): st.session_state.page='login';st.rerun()

def landing():
    nav(); logo=Path('assets/repolens_logo.png')
    if logo.exists():
        x,y=st.columns([1,6]); x.image(str(logo),width=88)
    st.markdown('''<div class="hero"><span class="badge">AI-POWERED SOFTWARE ARCHITECTURE INTELLIGENCE</span><h1>See Your Codebase.<br><span class="gradient">Understand Its Architecture.</span></h1><div class="subtitle">RepoLens AI analyzes a GitHub repository and transforms complex source code into an understandable architecture map — with components, connections, data flow, technologies and security intelligence.</div></div>''',unsafe_allow_html=True)
    a,b,_=st.columns([1.3,1.1,3])
    with a:
        if st.button('🚀 Get Started',use_container_width=True): st.session_state.page='signup';st.rerun()
    with b:
        if st.button('🔐 Sign In',use_container_width=True): st.session_state.page='login';st.rerun()
    st.markdown('<div class="section-title">Powerful Developer Intelligence</div>',unsafe_allow_html=True)
    features=[('🧠','AI Architecture Analysis','Understand unfamiliar repositories with AI.'),('🗺️','Visual Architecture','Generate a clear component relationship map.'),('🛡️','Security Intelligence','Surface potential security concerns.'),('🔄','Data Flow','Understand important application data movement.'),('⚡','Fast Scanning','Scan public GitHub repositories quickly.'),('📊','Developer Dashboard','Keep your analysis workspace organized.')]
    cs=st.columns(3)
    for i,(ic,t,desc) in enumerate(features):
        with cs[i%3]: st.markdown(f'<div class="card"><div style="font-size:28px">{ic}</div><div class="feature-title">{t}</div><div class="muted">{desc}</div></div>',unsafe_allow_html=True)
        if i%3==2: st.write('')

def auth(kind):
    st.markdown('<div class="auth">',unsafe_allow_html=True)
    st.markdown('## '+('Welcome back 👋' if kind=='login' else 'Create your account 🚀'))
    if kind=='login':
        email=st.text_input('Email',placeholder='you@example.com');pw=st.text_input('Password',type='password')
        if st.button('🔐 Sign In',use_container_width=True):
            u=st.session_state.users.get(email.strip().lower())
            if u and u['password']==pw: st.session_state.authenticated=True;st.session_state.user=email.strip().lower();st.session_state.page='dashboard';st.rerun()
            else: st.error('Invalid email or password.')
        st.caption('Demo: demo@repolens.ai / demo123')
        if st.button('Create a new account'): st.session_state.page='signup';st.rerun()
    else:
        name=st.text_input('Full name');email=st.text_input('Email',placeholder='you@example.com');pw=st.text_input('Password',type='password');cpw=st.text_input('Confirm password',type='password')
        if st.button('🚀 Create Account',use_container_width=True):
            e=email.strip().lower()
            if not name.strip() or not e or not pw: st.error('Please fill all fields.')
            elif pw!=cpw: st.error('Passwords do not match.')
            elif e in st.session_state.users: st.error('Account already exists.')
            else: st.session_state.users[e]={'name':name.strip(),'password':pw};st.session_state.authenticated=True;st.session_state.user=e;st.session_state.page='dashboard';st.rerun()
        if st.button('Already have an account? Sign in'): st.session_state.page='login';st.rerun()
    if st.button('← Back to Home'): st.session_state.page='landing';st.rerun()
    st.markdown('</div>',unsafe_allow_html=True)

def sidebar():
    with st.sidebar:
        st.markdown('## 🔭 RepoLens AI');st.caption('Software Architecture Intelligence');st.divider()
        st.markdown('**Signed in as**');st.caption(st.session_state.user)
        if st.button('📊 Overview',use_container_width=True): st.session_state.tab='overview';st.rerun()
        if st.button('🔍 Analyze Repository',use_container_width=True): st.session_state.tab='analyze';st.rerun()
        if st.button('🕘 Analysis History',use_container_width=True): st.session_state.tab='history';st.rerun()
        st.divider()
        if st.button('🚪 Logout',use_container_width=True): st.session_state.authenticated=False;st.session_state.user='';st.session_state.page='landing';st.rerun()

def results(arch,files):
    comps=arch.get('components',[]);conns=arch.get('connections',[]);tech=arch.get('technologies',[]);sec=arch.get('security_findings',[]);flow=arch.get('data_flow',[])
    st.markdown('<div class="section-title">📊 Architecture Overview</div>',unsafe_allow_html=True)
    for col,(lab,val) in zip(st.columns(4),[('FILES',len(files)),('COMPONENTS',len(comps)),('CONNECTIONS',len(conns)),('SECURITY FINDINGS',len(sec))]):
        with col: st.markdown(f'<div class="metric"><div class="metric-num">{val}</div><div class="metric-label">{lab}</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="section-title">🧩 Project Intelligence</div>',unsafe_allow_html=True);st.markdown(f'<div class="card"><b>Project Type</b><br><span class="muted">{arch.get("project_type","Unknown")}</span></div>',unsafe_allow_html=True)
    if tech: st.markdown('<div class="section-title">⚙️ Technologies</div>',unsafe_allow_html=True);st.markdown('  '.join('`'+str(x)+'`' for x in tech))
    st.markdown('<div class="section-title">🗺️ Visual Architecture</div>',unsafe_allow_html=True)
    try: st.image(create_visual_architecture(arch),use_container_width=True)
    except Exception as e: st.warning(f'Could not render diagram: {e}')
    if comps:
        st.markdown('<div class="section-title">🧱 Components</div>',unsafe_allow_html=True)
        for c in comps:
            with st.expander(f'🔹 {c.get("name","Unknown")} · {c.get("type","Component")}'): st.write(c.get('description',''))
    if flow:
        st.markdown('<div class="section-title">🔄 Data Flow</div>',unsafe_allow_html=True)
        for i,x in enumerate(flow,1): st.markdown(f'**{i}.** {x}')
    st.markdown('<div class="section-title">🛡️ Security Intelligence</div>',unsafe_allow_html=True)
    for x in sec: st.warning(str(x))
    if not sec: st.success('No significant security findings were detected.')

def dashboard():
    sidebar()
    if 'tab' not in st.session_state: st.session_state.tab='overview'
    name=st.session_state.users.get(st.session_state.user,{}).get('name','Developer')
    st.markdown(f'<div class="hero" style="padding:30px 36px"><span class="badge">REPOSITORY INTELLIGENCE</span><h1 style="font-size:42px">Welcome back, <span class="gradient">{name}</span></h1><div class="subtitle" style="font-size:15px">Understand your codebase. Visualize its architecture. Find what matters.</div></div>',unsafe_allow_html=True)
    if st.session_state.tab=='overview':
        st.markdown('## 📊 Dashboard');h=st.session_state.history
        for col,(lab,val) in zip(st.columns(4),[('ANALYSES',len(h)),('REPOSITORIES',len({x['repo'] for x in h})),('COMPONENTS',sum(x['components'] for x in h)),('SECURITY FINDINGS',sum(x['security'] for x in h))]):
            with col: st.markdown(f'<div class="metric"><div class="metric-num">{val}</div><div class="metric-label">{lab}</div></div>',unsafe_allow_html=True)
        st.markdown('<div class="section-title">Quick Actions</div>',unsafe_allow_html=True)
        if st.button('🚀 Analyze a Repository',use_container_width=True): st.session_state.tab='analyze';st.rerun()
    elif st.session_state.tab=='history':
        st.markdown('## 🕘 Analysis History')
        if not st.session_state.history: st.info('No analyses yet.')
        for x in reversed(st.session_state.history): st.markdown(f'<div class="card"><b>🔗 {x["repo"]}</b><br><span class="muted">{x["project_type"]} · {x["components"]} components · {x["security"]} security findings</span></div>',unsafe_allow_html=True)
    else:
        st.markdown('## 🔍 Analyze Repository');url=st.text_input('GitHub Repository URL',value=st.session_state.repo_url,placeholder='https://github.com/username/repository')
        if st.button('🚀 ANALYZE REPOSITORY',use_container_width=True):
            if not url.strip(): st.warning('Please enter a GitHub repository URL.')
            elif not client: st.error('GROQ_API_KEY is missing from Streamlit Secrets.')
            else:
                try:
                    with st.status('🔍 Analyzing repository...',expanded=True) as s:
                        s.write('📥 Cloning repository...');path,err=clone_repository(url)
                        if err: raise RuntimeError(err)
                        try:
                            s.write('📂 Scanning files...');files=scan_repository(path)
                            s.write('📄 Extracting source code...');code=extract_code(path,files)
                            s.write('🤖 Groq AI analyzing architecture...');raw=analyze_architecture(code);arch=parse_architecture_result(raw)
                        finally: shutil.rmtree(path,ignore_errors=True)
                        s.update(label='✅ Analysis completed!',state='complete')
                    st.session_state.repo_url=url.strip();st.session_state.files=files;st.session_state.architecture=arch;st.session_state.history.append({'repo':url.strip(),'project_type':arch.get('project_type','Unknown'),'components':len(arch.get('components',[])),'security':len(arch.get('security_findings',[]))})
                except Exception as e: st.error(f'Analysis failed: {e}');st.code(traceback.format_exc())
        if st.session_state.architecture: results(st.session_state.architecture,st.session_state.files)

if st.session_state.page=='landing': landing()
elif st.session_state.page=='login': auth('login')
elif st.session_state.page=='signup': auth('signup')
elif st.session_state.page=='dashboard':
    if not st.session_state.authenticated: st.session_state.page='login';st.rerun()
    dashboard()

st.markdown('---');st.caption('RepoLens AI · See Your Codebase. Understand Its Architecture.')
