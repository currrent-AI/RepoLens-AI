import os
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from git import Repo
from groq import Groq


# ============================================================
# ENVIRONMENT
# ============================================================

# Load .env from project root
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE)


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="RepoLens AI Backend",
    version="1.0.0",
    description="AI-powered repository architecture analyzer"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5501",
        "http://localhost:5501",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODEL
# ============================================================

class RepositoryRequest(BaseModel):
    github_url: str


# ============================================================
# GROQ CLIENT
# ============================================================

def get_groq_client() -> Groq:
    """
    Create Groq client using GROQ_API_KEY from .env.
    """

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail=(
                "GROQ_API_KEY is not configured. "
                "Please add GROQ_API_KEY=your_key to the .env file "
                "in the project root and restart the backend."
            )
        )

    api_key = api_key.strip()

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY is empty."
        )

    return Groq(api_key=api_key)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "RepoLens AI Backend",
        "groq_configured": bool(os.getenv("GROQ_API_KEY")),
        "message": "RepoLens AI Backend is running."
    }


# ============================================================
# HELPER FUNCTIONS
# ============================================================

IGNORED_DIRECTORIES = {
    ".git",
    ".github",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
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
    ".html",
    ".css",
    ".scss",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
}


IMPORTANT_FILES = {
    "README.md",
    "README",
    "pyproject.toml",
    "package.json",
    "requirements.txt",
    "requirements-dev.txt",
    "Pipfile",
    "poetry.lock",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "dockerfile",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "vite.config.js",
    "vite.config.ts",
    "next.config.js",
    "next.config.mjs",
    "tsconfig.json",
}


def is_ignored(path: Path) -> bool:
    """
    Check whether a file belongs to an ignored directory.
    """

    return any(
        part in IGNORED_DIRECTORIES
        for part in path.parts
    )


def collect_repository_files(repo_dir: str) -> list[Path]:
    """
    Find relevant source/configuration files.
    """

    root = Path(repo_dir)
    files = []

    for path in root.rglob("*"):

        if not path.is_file():
            continue

        if is_ignored(path):
            continue

        # Avoid very large files
        try:
            size = path.stat().st_size
            if size > 500_000:
                continue
        except OSError:
            continue

        if path.name in IMPORTANT_FILES:
            files.append(path)
            continue

        if path.suffix.lower() in ALLOWED_EXTENSIONS:
            files.append(path)

    return files


def file_priority(path: Path) -> int:
    """
    Prioritize important architectural files.
    """

    name = path.name.lower()
    parts = [p.lower() for p in path.parts]

    score = 0

    # Project configuration
    if name in {
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "cargo.toml",
        "go.mod",
        "pom.xml",
        "dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
    }:
        score += 100

    # Documentation
    if name in {"readme.md", "readme"}:
        score += 95

    # Common entry points
    if name in {
        "main.py",
        "app.py",
        "server.py",
        "index.js",
        "index.ts",
        "index.jsx",
        "index.tsx",
        "server.js",
        "server.ts",
    }:
        score += 90

    # Backend/frontend folders
    if "backend" in parts:
        score += 30

    if "frontend" in parts:
        score += 30

    if "src" in parts:
        score += 25

    if "api" in parts:
        score += 25

    if "routes" in parts:
        score += 20

    if "controllers" in parts:
        score += 20

    if "services" in parts:
        score += 20

    if "models" in parts:
        score += 20

    if "components" in parts:
        score += 20

    return score


def read_repository_files(
    files: list[Path],
    repo_dir: str,
    max_chars: int = 11000
) -> tuple[str, list[str]]:
    """
    Read only a controlled amount of source code.

    IMPORTANT:
    Groq organization has an 8000 TPM limit.
    Keeping context around 11k characters prevents huge requests.
    """

    root = Path(repo_dir)

    sorted_files = sorted(
        files,
        key=lambda p: (-file_priority(p), str(p))
    )

    chunks = []
    analyzed_files = []

    total_chars = 0

    for path in sorted_files:

        if total_chars >= max_chars:
            break

        try:
            text = path.read_text(
                encoding="utf-8",
                errors="ignore"
            )
        except Exception:
            continue

        if not text.strip():
            continue

        relative_path = path.relative_to(root)

        # Limit each individual file
        remaining = max_chars - total_chars

        # Never take huge content from one file
        file_limit = min(2500, remaining)

        content = text[:file_limit]

        if len(text) > file_limit:
            content += "\n...[truncated]..."

        chunk = (
            f"\n===== FILE: {relative_path} =====\n"
            f"{content}\n"
        )

        chunks.append(chunk)
        analyzed_files.append(str(relative_path))

        total_chars += len(chunk)

    return "".join(chunks), analyzed_files


def safe_list(value: Any) -> list:
    """
    Ensure a value is a list.
    """

    if isinstance(value, list):
        return value

    return []


def normalize_component(item: Any) -> dict:
    """
    Normalize component object.
    """

    if not isinstance(item, dict):
        return {
            "name": str(item),
            "type": "Component",
            "description": ""
        }

    return {
        "name": str(item.get("name", "Unknown Component")),
        "type": str(item.get("type", "Component")),
        "description": str(
            item.get("description", "")
        )
    }


def normalize_relationship(item: Any) -> dict:
    """
    Normalize relationship object.
    """

    if not isinstance(item, dict):
        return {
            "source": "",
            "target": "",
            "relationship": str(item)
        }

    return {
        "source": str(item.get("source", "")),
        "target": str(item.get("target", "")),
        "relationship": str(
            item.get("relationship", "")
        )
    }


def normalize_security(item: Any) -> dict:
    """
    Normalize security finding.
    """

    if not isinstance(item, dict):
        return {
            "severity": "Low",
            "finding": str(item),
            "recommendation": ""
        }

    severity = str(
        item.get("severity", "Low")
    ).capitalize()

    allowed = {
        "Low",
        "Medium",
        "High",
        "Critical"
    }

    if severity not in allowed:
        severity = "Low"

    return {
        "severity": severity,
        "finding": str(
            item.get("finding", "")
        ),
        "recommendation": str(
            item.get("recommendation", "")
        )
    }


def normalize_architecture(data: Any) -> dict:
    """
    Make sure frontend always receives the expected schema.
    """

    if not isinstance(data, dict):
        data = {}

    components = [
        normalize_component(item)
        for item in safe_list(
            data.get("components")
        )
    ]

    relationships = [
        normalize_relationship(item)
        for item in safe_list(
            data.get("relationships")
        )
    ]

    security_findings = [
        normalize_security(item)
        for item in safe_list(
            data.get("security_findings")
        )
    ]

    technologies = [
        str(item)
        for item in safe_list(
            data.get("technologies")
        )
    ]

    data_flow = [
        str(item)
        for item in safe_list(
            data.get("data_flow")
        )
    ]

    strengths = [
        str(item)
        for item in safe_list(
            data.get("strengths")
        )
    ]

    weaknesses = [
        str(item)
        for item in safe_list(
            data.get("weaknesses")
        )
    ]

    recommendations = [
        str(item)
        for item in safe_list(
            data.get("recommendations")
        )
    ]

    project_type = str(
        data.get(
            "project_type",
            "Architecture analysis"
        )
    )

    return {
        "project_type": project_type,
        "technologies": technologies,
        "components": components,
        "relationships": relationships,
        "data_flow": data_flow,
        "security_findings": security_findings,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
    }


def extract_json_from_response(text: str) -> dict:
    """
    Extract JSON even if the model accidentally adds markdown.
    """

    text = text.strip()

    # Remove markdown fences
    if text.startswith("```"):
        lines = text.splitlines()

        cleaned = []

        for line in lines:
            if line.strip().startswith("```"):
                continue

            cleaned.append(line)

        text = "\n".join(cleaned).strip()

    # Direct JSON
    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError:
        pass

    # Find first JSON object
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:

        candidate = text[start:end + 1]

        try:
            parsed = json.loads(candidate)

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            pass

    raise ValueError(
        "AI returned an invalid JSON response."
    )


# ============================================================
# AI ANALYSIS
# ============================================================

def analyze_with_groq(
    code_context: str,
    file_count: int
) -> dict:

    client = get_groq_client()

    system_prompt = """
You are RepoLens AI, an expert software architecture analyzer.

Analyze the provided repository source code and identify its
software architecture.

Return ONLY valid JSON.

Do not use markdown.
Do not add explanations outside JSON.

Required JSON schema:

{
  "project_type": "string",
  "technologies": ["string"],
  "components": [
    {
      "name": "string",
      "type": "string",
      "description": "string"
    }
  ],
  "relationships": [
    {
      "source": "string",
      "target": "string",
      "relationship": "string"
    }
  ],
  "data_flow": ["string"],
  "security_findings": [
    {
      "severity": "Low",
      "finding": "string",
      "recommendation": "string"
    }
  ],
  "strengths": ["string"],
  "weaknesses": ["string"],
  "recommendations": ["string"]
}

Rules:

- Identify real technologies from the repository.
- Identify meaningful architectural components.
- Create relationships between components.
- Describe the data flow.
- Identify practical security concerns.
- Do not invent technologies that are not supported by the code.
- Keep descriptions concise.
- Prefer 4-10 components.
- Prefer 3-10 relationships.
- Prefer 3-8 technologies.
- Prefer concise recommendations.
"""

    user_prompt = f"""
Repository contains approximately {file_count} relevant files.

Analyze this repository:

{code_context}
"""

    try:
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
            max_tokens=1800
        )

    except Exception as e:

        error_text = str(e)

        if "413" in error_text or "rate_limit" in error_text.lower():
            raise HTTPException(
                status_code=429,
                detail=(
                    "Groq request exceeded the organization token limit. "
                    "The repository context has been reduced, but please "
                    "try the analysis again."
                )
            )

        raise HTTPException(
            status_code=502,
            detail=f"Groq AI request failed: {error_text}"
        )

    try:
        content = response.choices[0].message.content

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Groq returned an empty response."
        )

    if not content:
        raise HTTPException(
            status_code=502,
            detail="Groq returned an empty AI response."
        )

    try:
        parsed = extract_json_from_response(
            content
        )

    except ValueError:
        # Return a safe architecture object
        return normalize_architecture({
            "project_type": "AI analysis generated",
            "technologies": [],
            "components": [],
            "relationships": [],
            "data_flow": [],
            "security_findings": [],
            "strengths": [],
            "weaknesses": [],
            "recommendations": []
        })

    return normalize_architecture(parsed)


# ============================================================
# ANALYZE ENDPOINT
# ============================================================

@app.post("/analyze")
def analyze_repository(
    request: RepositoryRequest
):

    repo_url = request.github_url.strip()

    # --------------------------------------------------------
    # Validate GitHub URL
    # --------------------------------------------------------

    if not repo_url:
        raise HTTPException(
            status_code=400,
            detail="GitHub repository URL is required."
        )

    if "github.com/" not in repo_url.lower():
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid GitHub repository URL."
        )

    # --------------------------------------------------------
    # Create temporary directory
    # --------------------------------------------------------

    temp_dir = tempfile.mkdtemp(
        prefix="repolens_"
    )

    try:

        # ----------------------------------------------------
        # Clone repository
        # ----------------------------------------------------

        try:

            Repo.clone_from(
                repo_url,
                temp_dir,
                depth=1
            )

        except Exception as e:

            raise HTTPException(
                status_code=400,
                detail=f"Could not clone repository: {str(e)}"
            )

        # ----------------------------------------------------
        # Scan files
        # ----------------------------------------------------

        files = collect_repository_files(
            temp_dir
        )

        files_found = len(files)

        if files_found == 0:

            raise HTTPException(
                status_code=400,
                detail=(
                    "No supported source files were found "
                    "in this repository."
                )
            )

        # ----------------------------------------------------
        # Extract controlled source context
        # ----------------------------------------------------

        code_context, analyzed_files = (
            read_repository_files(
                files,
                temp_dir,
                max_chars=11000
            )
        )

        if not code_context.strip():

            raise HTTPException(
                status_code=400,
                detail="Could not extract readable source code."
            )

        # ----------------------------------------------------
        # AI architecture analysis
        # ----------------------------------------------------

        architecture = analyze_with_groq(
            code_context,
            files_found
        )

        # ----------------------------------------------------
        # Final response
        # ----------------------------------------------------

        return {
            "success": True,
            "repository": repo_url,
            "files_found": files_found,
            "files_analyzed": len(analyzed_files),
            "analyzed_files": analyzed_files,
            "architecture": architecture
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Repository analysis failed: {str(e)}"
        )

    finally:

        # Always remove cloned repository
        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )


# ============================================================
# DEBUG ENV ENDPOINT
# ============================================================

@app.get("/config-status")
def config_status():

    api_key = os.getenv("GROQ_API_KEY")

    return {
        "groq_api_key_loaded": bool(api_key),
        "env_file": str(ENV_FILE),
        "env_file_exists": ENV_FILE.exists()
    }