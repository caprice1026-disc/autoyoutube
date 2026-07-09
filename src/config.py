from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"
BGM_ASSETS_DIR = ASSETS_DIR / "bgm"
BGM_MANIFEST_PATH = BGM_ASSETS_DIR / "bgm_manifest.json"
DEFAULT_BGM_TRACK_ID = "No One Here Gets In Alive"
DEFAULT_BGM_FILE_PATH = BGM_ASSETS_DIR / "No One Here Gets In Alive - National Sweetheart.mp3"
SCHEMAS_DIR = ROOT_DIR / "schemas"
PROJECT_SCHEMA_PATH = SCHEMAS_DIR / "project.youtube.schema.json"
RENDERED_SCHEMA_PATH = SCHEMAS_DIR / "rendered.youtube.schema.json"
DB_PATH = ROOT_DIR / "data" / "trivia_shorts.db"
DB_SCHEMA_PATH = ROOT_DIR / "db" / "schema.sql"
RENDERS_DIR = ROOT_DIR / "renders"
