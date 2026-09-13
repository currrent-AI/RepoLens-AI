import os
import re
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from groq import Groq


# ============================================================
# ENVIRONMENT
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

# Local development only
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except Exception:
    pass

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

MODEL_NAME = os.environ.get(
    "GROQ_MODEL",
    "openai/gpt-oss-120b"
)


# ============================================================
# FRONTEND DIRECTORY
# ============================================================

FRONTEND_DIR = BASE_DIR / "frontend"


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="RepoLens AI",
    description="AI-powered software architecture analyzer",
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


# ============================================================
# REQUEST MODEL
# ============================================================

class AnalyzeRequest(BaseModel):
    github_url: str


# ============================================================
# BASIC ROUTES
# ============================================================

@app.get("/")
def root():
    """
    Serve RepoLens AI frontend on the main Vercel URL.
    """

    index_file = FRONTEND_DIR / "index.html"

    if index_file.exists():
        return FileResponse(
            index_file,
            media_type="text/html"
        )

    return {
        "status": "online",
        "service": "RepoLens AI",
        "message": "See Your Codebase. Understand Its Architecture.",
        "version": "1.0.0"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "groq_configured": bool(GROQ_API_KEY)
    }


# ============================================================
# FRONTEND FILE ROUTES
# ============================================================

@app.get("/{page_name}.html")
def frontend_page(page_name: str):
    """
    Serve frontend HTML pages such as:

    /login.html
    /signup.html
    /dashboard.html
    /architecture.html
    /history.html
    /settings.html
    """

    # Only allow safe filenames
    if not re.fullmatch(r"[A-Za-z0-9_-]+", page_name):
        raise HTTPException(
            status_code=404,
            detail="Page not found."
        )

    page_file = FRONTEND_DIR / f"{page_name}.html"

    if not page_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Page not found."
        )

    return FileResponse(
        page_file,
        media_type="text/html"
    )


# ============================================================
# FRONTEND STATIC FILES
# ============================================================

# CSS
@app.get("/style.css")
def frontend_css():
    css_file = FRONTEND_DIR / "style.css"

    if not css_file.exists():
        raise HTTPException(
            status_code=404,
            detail="style.css not found."
        )

    return FileResponse(
        css_file,
        media_type="text/css"
    )


# JavaScript
@app.get("/script.js")
def frontend_js():
    js_file = FRONTEND_DIR / "script.js"

    if not js_file.exists():
        raise HTTPException(
            status_code=404,
            detail="script.js not found."
        )

    return FileResponse(
        js_file,
        media_type="application/javascript"
    )


# ============================================================
# FRONTEND ASSETS
# ============================================================

@app.get("/assets/{file_name:path}")
def frontend_asset(file_name: str):
    """
    Serve files from /assets folder.
    """

    asset_file = BASE_DIR / "assets" / file_name

    # Security check
    try:
        asset_file.resolve().relative_to(
            (BASE_DIR / "assets").resolve()
        )
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Asset not found."
        )

    if not asset_file.exists() or not asset_file.is_file():
        raise HTTPException(
            status_code=404,
            detail="Asset not found."
        )

    return FileResponse(asset_file)


# ============================================================
# GITHUB HELPERS
# ============================================================

def parse_github_url(url: str):
    """
    Convert common GitHub URLs into owner/repository.
    """

    url = url.strip()

    # Remove trailing slash
    url = url.rstrip("/")

    # Remove .git
    if url.endswith(".git"):
        url = url[:-4]

    match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)",
        url,
        re.IGNORECASE
    )

    if not match:
        raise ValueError(
            "Please provide a valid public GitHub repository URL."
        )

    owner = match.group(1)
    repo = match.group(2)

    return owner, repo


# ============================================================
# DOWNLOAD GITHUB REPOSITORY
# ============================================================

def download_github_repository(
    github_url: str,
    destination: Path
) -> Path:
    """
    Download a public GitHub repository as a ZIP.

    This replaces GitPython because Vercel does not provide
    a git executable inside the Python runtime.
    """

    owner, repo = parse_github_url(github_url)

    zip_url = (
        f"https://github.com/{owner}/{repo}"
        f"/archive/refs/heads/main.zip"
    )

    zip_path = destination / "repository.zip"

    request = Request(
        zip_url,
        headers={
            "User-Agent": "RepoLens-AI/1.0"
        }
    )

    try:
        with urlopen(request, timeout=30) as response:
            data = response.read()

        with open(zip_path, "wb") as f:
            f.write(data)

    except HTTPError as e:

        # Some repositories use master instead of main
        if e.code == 404:

            zip_url = (
                f"https://github.com/{owner}/{repo}"
                f"/archive/refs/heads/master.zip"
            )

            request = Request(
                zip_url,
                headers={
                    "User-Agent": "RepoLens-AI/1.0"
                }
            )

            try:
                with urlopen(request, timeout=30) as response:
                    data = response.read()

                with open(zip_path, "wb") as f:
                    f.write(data)

            except Exception as second_error:
                raise ValueError(
                    f"Unable to download GitHub repository: "
                    f"{second_error}"
                )

        else:
            raise ValueError(
                f"GitHub returned HTTP {e.code}."
            )

    except URLError as e:
        raise ValueError(
            f"Could not connect to GitHub: {e.reason}"
        )

    except Exception as e:
        raise ValueError(
            f"Repository download failed: {str(e)}"
        )

    # Extract ZIP
    extract_dir = destination / "repo"

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

    except zipfile.BadZipFile:
        raise ValueError(
            "GitHub did not return a valid repository ZIP."
        )

    # GitHub ZIP contains one top-level directory
    folders = [
        p
        for p in extract_dir.iterdir()
        if p.is_dir()
    ]

    if folders:
        return folders[0]

    return extract_dir


# ============================================================
# FILE FILTERS
# ============================================================

IGNORED_DIRS = {
    ".git",
    ".github",
    ".idea",
    ".vscode",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".next",
    "dist",
    "build",
    "coverage",
    "venv",
    ".venv",
    "env",
    ".env",
    "vendor",
    "target",
    "bin",
    "obj"
}


ALLOWED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".php",
    ".rb",
    ".swift",
    ".kt",
    ".kts",
    ".sql",
    ".html",
    ".css",
    ".scss",
    ".vue",
    ".dart",
    ".json",
    ".yaml",
    ".yml",
    ".md",
    ".toml",
    ".xml"
}


IGNORED_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "composer.lock",
    "Cargo.lock"
}


# ============================================================
# SCAN REPOSITORY
# ============================================================

def scan_repository(repo_path: Path) -> List[Path]:

    files = []

    for root, dirs, filenames in os.walk(repo_path):

        # Modify dirs in-place so ignored directories are skipped
        dirs[:] = [
            d
            for d in dirs
            if d not in IGNORED_DIRS
        ]

        for filename in filenames:

            if filename in IGNORED_FILES:
                continue

            file_path = Path(root) / filename

            if file_path.suffix.lower() in ALLOWED_EXTENSIONS:

                try:
                    size = file_path.stat().st_size

                    # Avoid huge generated files
                    if size <= 200_000:
                        files.append(file_path)

                except Exception:
                    continue

    return files


# ============================================================
# EXTRACT SOURCE CODE
# ============================================================

def extract_code(
    repo_path: Path,
    files: List[Path],
    max_chars: int = 12000
) -> str:

    chunks = []

    # Prioritize important files
    priority_names = {
        "main.py",
        "app.py",
        "server.py",
        "index.js",
        "index.ts",
        "index.jsx",
        "index.tsx",
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "README.md",
        "docker-compose.yml",
        "Dockerfile"
    }

    def priority(path: Path):

        if path.name in priority_names:
            return 0

        return 1

    files_sorted = sorted(
        files,
        key=priority
    )

    total_chars = 0

    for file_path in files_sorted:

        try:
            relative = file_path.relative_to(repo_path)

            content = file_path.read_text(
                encoding="utf-8",
                errors="ignore"
            )

        except Exception:
            continue

        remaining = max_chars - total_chars

        if remaining <= 0:
            break

        # Keep individual files manageable
        content = content[
            :min(4000, remaining)
        ]

        block = (
            f"\n\n"
            f"===== FILE: {relative} =====\n"
            f"{content}\n"
            f"===== END FILE =====\n"
        )

        chunks.append(block)

        total_chars += len(block)

    return "".join(chunks)


# ============================================================
# PROJECT METADATA
# ============================================================

def detect_project_type(
    files: List[Path]
) -> str:

    names = {
        f.name.lower()
        for f in files
    }

    extensions = {
        f.suffix.lower()
        for f in files
    }

    if "package.json" in names:

        if (
            ".tsx" in extensions
            or ".jsx" in extensions
        ):
            return (
                "JavaScript/TypeScript "
                "web application"
            )

        return (
            "JavaScript/Node.js application"
        )

    if (
        "requirements.txt" in names
        or "pyproject.toml" in names
        or ".py" in extensions
    ):
        return "Python application/library"

    if ".java" in extensions:
        return "Java application"

    if ".cs" in extensions:
        return "C# application"

    if ".go" in extensions:
        return "Go application"

    if ".rs" in extensions:
        return "Rust application"

    if (
        ".cpp" in extensions
        or ".c" in extensions
    ):
        return "C/C++ application"

    return "Software project"


def detect_technologies(
    files: List[Path]
) -> List[str]:

    technologies = []

    names = {
        f.name.lower()
        for f in files
    }

    extensions = {
        f.suffix.lower()
        for f in files
    }

    if ".py" in extensions:
        technologies.append("Python")

    if ".js" in extensions:
        technologies.append("JavaScript")

    if ".jsx" in extensions:
        technologies.append("React")

    if ".ts" in extensions:
        technologies.append("TypeScript")

    if ".tsx" in extensions:
        technologies.append(
            "React + TypeScript"
        )

    if ".java" in extensions:
        technologies.append("Java")

    if ".go" in extensions:
        technologies.append("Go")

    if ".rs" in extensions:
        technologies.append("Rust")

    if "package.json" in names:
        technologies.append("Node.js")

    if "requirements.txt" in names:
        technologies.append(
            "Python dependencies"
        )

    if "dockerfile" in names:
        technologies.append("Docker")

    if "docker-compose.yml" in names:
        technologies.append(
            "Docker Compose"
        )

    if ".sql" in extensions:
        technologies.append("SQL")

    if ".vue" in extensions:
        technologies.append("Vue.js")

    if ".dart" in extensions:
        technologies.append(
            "Dart / Flutter"
        )

    # Remove duplicates
    return list(
        dict.fromkeys(technologies)
    )


# ============================================================
# GROQ ANALYZER
# ============================================================

def analyze_architecture(
    code_context: str,
    project_type: str,
    technologies: List[str]
) -> Dict[str, Any]:

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    client = Groq(
        api_key=GROQ_API_KEY
    )

    prompt = f"""
You are RepoLens AI, an expert software architecture analyzer.

Analyze the supplied source-code snapshot.

PROJECT TYPE:
{project_type}

DETECTED TECHNOLOGIES:
{", ".join(technologies) if technologies else "Unknown"}

SOURCE CODE:
{code_context}

Return ONLY valid JSON.
Do not use markdown.
Do not put JSON inside ``` blocks.

Use exactly this structure:

{{
  "project_summary": "short summary",
  "architecture_style": "architecture style",
  "components": [
    {{
      "name": "component name",
      "type": "component type",
      "description": "short description"
    }}
  ],
  "relationships": [
    {{
      "from": "component name",
      "to": "component name",
      "label": "relationship"
    }}
  ],
  "data_flow": [
    "step 1",
    "step 2",
    "step 3"
  ],
  "security_findings": [
    {{
      "severity": "High",
      "title": "finding",
      "description": "description"
    }}
  ],
  "strengths": [
    "strength"
  ],
  "weaknesses": [
    "weakness"
  ],
  "recommendations": [
    "recommendation"
  ]
}}

Rules:

1. Only mention components supported by the source.
2. Do not invent frameworks.
3. Keep components between 3 and 12.
4. Keep relationships between 2 and 15.
5. Keep security findings concise.
6. If no security issue is visible, return an empty array.
7. Make recommendations practical.
8. Focus on architecture, dependencies, data flow and security.
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior software "
                    "architect. Return strictly "
                    "valid JSON."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.1,
        max_tokens=2000
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "Groq returned an empty response."
        )

    return parse_architecture_result(
        content
    )


# ============================================================
# ROBUST JSON PARSER
# ============================================================

def parse_architecture_result(
    text: str
) -> Dict[str, Any]:

    text = text.strip()

    # Remove markdown fences
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

    text = text.strip()

    # First attempt
    try:

        result = json.loads(text)

        if isinstance(result, dict):
            return result

    except Exception:
        pass

    # Find first JSON object
    start = text.find("{")

    if start == -1:
        raise RuntimeError(
            "AI response did not contain valid JSON."
        )

    decoder = json.JSONDecoder()

    try:

        result, _ = decoder.raw_decode(
            text[start:]
        )

        if isinstance(result, dict):
            return result

    except Exception as e:

        raise RuntimeError(
            f"Could not parse AI architecture JSON: {e}"
        )

    raise RuntimeError(
        "Invalid architecture result."
    )


# ============================================================
# SAFE DATA NORMALIZATION
# ============================================================

def normalize_list(value):

    if isinstance(value, list):
        return value

    if value is None:
        return []

    return [str(value)]


def normalize_components(value):

    if not isinstance(value, list):
        return []

    result = []

    for item in value:

        if isinstance(item, dict):

            result.append({
                "name": str(
                    item.get(
                        "name",
                        "Unknown"
                    )
                ),
                "type": str(
                    item.get(
                        "type",
                        "Component"
                    )
                ),
                "description": str(
                    item.get(
                        "description",
                        ""
                    )
                )
            })

        else:

            result.append({
                "name": str(item),
                "type": "Component",
                "description": ""
            })

    return result


def normalize_relationships(value):

    if not isinstance(value, list):
        return []

    result = []

    for item in value:

        if not isinstance(item, dict):
            continue

        result.append({
            "from": str(
                item.get(
                    "from",
                    ""
                )
            ),
            "to": str(
                item.get(
                    "to",
                    ""
                )
            ),
            "label": str(
                item.get(
                    "label",
                    "uses"
                )
            )
        })

    return result


def normalize_security(value):

    if not isinstance(value, list):
        return []

    result = []

    for item in value:

        if isinstance(item, dict):

            result.append({
                "severity": str(
                    item.get(
                        "severity",
                        "Info"
                    )
                ),
                "title": str(
                    item.get(
                        "title",
                        "Finding"
                    )
                ),
                "description": str(
                    item.get(
                        "description",
                        ""
                    )
                )
            })

        else:

            result.append({
                "severity": "Info",
                "title": str(item),
                "description": ""
            })

    return result


# ============================================================
# SVG ARCHITECTURE GRAPH
# ============================================================

def escape_svg(value: str) -> str:

    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def create_visual_architecture(
    components: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]]
) -> str:

    width = 1100

    if not components:

        return f"""
        <svg xmlns="http://www.w3.org/2000/svg"
             width="{width}"
             height="500"
             viewBox="0 0 {width} 500">

            <rect width="100%"
                  height="100%"
                  fill="#080F1E"/>

            <text x="550"
                  y="250"
                  text-anchor="middle"
                  fill="#8FA4BD"
                  font-size="22">

                No architecture components detected

            </text>

        </svg>
        """

    count = len(components)

    cols = 3

    rows = (
        (count + cols - 1)
        // cols
    )

    box_width = 280
    box_height = 110

    gap_x = 70
    gap_y = 80

    height = max(
        500,
        100 + rows * (
            box_height + gap_y
        )
    )

    positions = {}

    for index, component in enumerate(
        components
    ):

        row = index // cols
        col = index % cols

        x = (
            60
            + col * (
                box_width + gap_x
            )
        )

        y = (
            60
            + row * (
                box_height + gap_y
            )
        )

        name = component["name"]

        positions[name.lower()] = (
            x,
            y
        )

    svg = []

    svg.append(
        f"""
        <svg xmlns="http://www.w3.org/2000/svg"
             width="{width}"
             height="{height}"
             viewBox="0 0 {width} {height}">

        <defs>

            <marker
                id="arrow"
                markerWidth="10"
                markerHeight="10"
                refX="8"
                refY="3"
                orient="auto"
                markerUnits="strokeWidth">

                <path
                    d="M0,0 L0,6 L9,3 z"
                    fill="#3B82F6"/>

            </marker>

        </defs>

        <rect
            width="100%"
            height="100%"
            rx="18"
            fill="#080F1E"/>

        <text
            x="40"
            y="35"
            fill="#F1F5F9"
            font-size="18"
            font-family="Arial"
            font-weight="bold">

            Repository Architecture

        </text>
        """
    )

    # Relationships first
    for relation in relationships:

        source = str(
            relation.get(
                "from",
                ""
            )
        ).lower()

        target = str(
            relation.get(
                "to",
                ""
            )
        ).lower()

        if (
            source not in positions
            or target not in positions
        ):
            continue

        sx, sy = positions[source]
        tx, ty = positions[target]

        x1 = (
            sx
            + box_width / 2
        )

        y1 = (
            sy
            + box_height / 2
        )

        x2 = (
            tx
            + box_width / 2
        )

        y2 = (
            ty
            + box_height / 2
        )

        label = escape_svg(
            relation.get(
                "label",
                "uses"
            )
        )

        svg.append(
            f"""
            <line
                x1="{x1}"
                y1="{y1}"
                x2="{x2}"
                y2="{y2}"
                stroke="#3B82F6"
                stroke-width="2"
                opacity="0.75"
                marker-end="url(#arrow)"/>

            <text
                x="{(x1+x2)/2}"
                y="{(y1+y2)/2 - 8}"
                text-anchor="middle"
                fill="#8FA4BD"
                font-size="12"
                font-family="Arial">

                {label}

            </text>
            """
        )

    # Components
    for component in components:

        name = escape_svg(
            component.get(
                "name",
                "Component"
            )
        )

        component_type = escape_svg(
            component.get(
                "type",
                "Component"
            )
        )

        x, y = positions[
            component["name"].lower()
        ]

        svg.append(
            f"""
            <rect
                x="{x}"
                y="{y}"
                width="{box_width}"
                height="{box_height}"
                rx="14"
                fill="#111C31"
                stroke="#1D304D"
                stroke-width="2"/>

            <rect
                x="{x}"
                y="{y}"
                width="5"
                height="{box_height}"
                rx="3"
                fill="#3B82F6"/>

            <text
                x="{x + 22}"
                y="{y + 40}"
                fill="#F1F5F9"
                font-size="17"
                font-family="Arial"
                font-weight="bold">

                {name[:28]}

            </text>

            <text
                x="{x + 22}"
                y="{y + 68}"
                fill="#8FA4BD"
                font-size="13"
                font-family="Arial">

                {component_type[:35]}

            </text>
            """
        )

    svg.append("</svg>")

    return "".join(svg)


# ============================================================
# ANALYZE ENDPOINT
# ============================================================

@app.post("/analyze")
def analyze_repository(
    request: AnalyzeRequest
):

    github_url = request.github_url.strip()

    if not github_url:

        raise HTTPException(
            status_code=400,
            detail=(
                "GitHub repository URL "
                "is required."
            )
        )

    if "github.com/" not in github_url.lower():

        raise HTTPException(
            status_code=400,
            detail=(
                "Please provide a valid "
                "GitHub repository URL."
            )
        )

    if not GROQ_API_KEY:

        raise HTTPException(
            status_code=500,
            detail=(
                "GROQ_API_KEY is not "
                "configured on the server."
            )
        )

    temp_dir = Path(
        tempfile.mkdtemp(
            prefix="repolens_"
        )
    )

    try:

        # ----------------------------------------------------
        # 1. DOWNLOAD REPOSITORY
        # ----------------------------------------------------

        repo_path = download_github_repository(
            github_url,
            temp_dir
        )

        # ----------------------------------------------------
        # 2. SCAN FILES
        # ----------------------------------------------------

        files = scan_repository(
            repo_path
        )

        if not files:

            raise HTTPException(
                status_code=400,
                detail=(
                    "No supported source "
                    "files were found in "
                    "this repository."
                )
            )

        # ----------------------------------------------------
        # 3. EXTRACT SOURCE
        # ----------------------------------------------------

        code_context = extract_code(
            repo_path,
            files,
            max_chars=12000
        )

        # ----------------------------------------------------
        # 4. DETECT PROJECT INFO
        # ----------------------------------------------------

        project_type = detect_project_type(
            files
        )

        technologies = detect_technologies(
            files
        )

        # ----------------------------------------------------
        # 5. GROQ AI ANALYSIS
        # ----------------------------------------------------

        architecture = analyze_architecture(
            code_context,
            project_type,
            technologies
        )

        # ----------------------------------------------------
        # 6. NORMALIZE AI RESULT
        # ----------------------------------------------------

        components = normalize_components(
            architecture.get(
                "components",
                []
            )
        )

        relationships = normalize_relationships(
            architecture.get(
                "relationships",
                []
            )
        )

        data_flow = normalize_list(
            architecture.get(
                "data_flow",
                []
            )
        )

        security_findings = normalize_security(
            architecture.get(
                "security_findings",
                []
            )
        )

        strengths = normalize_list(
            architecture.get(
                "strengths",
                []
            )
        )

        weaknesses = normalize_list(
            architecture.get(
                "weaknesses",
                []
            )
        )

        recommendations = normalize_list(
            architecture.get(
                "recommendations",
                []
            )
        )

        # ----------------------------------------------------
        # 7. CREATE SVG GRAPH
        # ----------------------------------------------------

        graph_svg = create_visual_architecture(
            components,
            relationships
        )

        # ----------------------------------------------------
        # 8. FINAL RESPONSE
        # ----------------------------------------------------

        result = {

            "success": True,

            "repository": {
                "url": github_url,
                "name": (
                    github_url
                    .rstrip("/")
                    .split("/")[-1]
                )
            },

            "files_found": len(files),

            # Number of source files
            # included in AI context
            "files_analyzed": len(
                code_context.split(
                    "===== FILE:"
                )
            ) - 1,

            "project_type": architecture.get(
                "project_summary",
                project_type
            ),

            "architecture_style": architecture.get(
                "architecture_style",
                "Not specified"
            ),

            "technologies": (
                technologies
                if technologies
                else []
            ),

            "components": components,

            "relationships": relationships,

            "data_flow": data_flow,

            "security_findings": (
                security_findings
            ),

            "strengths": strengths,

            "weaknesses": weaknesses,

            "recommendations": (
                recommendations
            ),

            "graph_svg": graph_svg
        }

        return result

    except HTTPException:
        raise

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:

        print(
            "RepoLens analysis error: "
            f"{type(e).__name__}: {e}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Repository analysis failed. "
                f"{str(e)}"
            )
        )

    finally:

        # Cleanup temporary files
        try:

            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )

        except Exception:
            pass


# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )