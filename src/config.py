from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = ROOT_DIR / "schemas"
PROJECT_SCHEMA_PATH = SCHEMAS_DIR / "project.youtube.schema.json"
RENDERED_SCHEMA_PATH = SCHEMAS_DIR / "rendered.youtube.schema.json"
DB_PATH = ROOT_DIR / "data" / "trivia_shorts.db"
DB_SCHEMA_PATH = ROOT_DIR / "db" / "schema.sql"
RENDERS_DIR = ROOT_DIR / "renders"
