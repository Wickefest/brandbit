# Saves and loads pipeline execution records as JSON.
# Also writes specialist fragrance and music side files.

from __future__ import annotations
from pathlib import Path
from src.config import Settings
from src.models.execution import PipelineExecutionRecord
from src.services.path_safety import contained_path
from src.services.specialist_outputs import save_specialist_outputs


def _get_log_dir(settings: Settings | None = None) -> Path:
    if settings is None:
        settings = Settings()
    return Path(settings.execution_log_dir)


# Writes the execution JSON and specialist side files then returns the log path.
def log_execution(record: PipelineExecutionRecord, settings: Settings | None = None) -> str:
    settings = settings or Settings()
    log_dir = _get_log_dir(settings)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Keep the log path inside the configured execution log directory.
    file_path = contained_path(log_dir, record.execution_id, suffix=".json")
    file_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    save_specialist_outputs(
        record.execution_id,
        record.fragrance_concept,
        record.music_direction,
        settings,
    )

    return str(file_path)


# Loads a previously logged execution by id or returns nothing if missing.
def get_execution(execution_id: str, settings: Settings | None = None) -> PipelineExecutionRecord | None:
    settings = settings or Settings()
    log_dir = _get_log_dir(settings)
    try:
        file_path = contained_path(log_dir, execution_id, suffix=".json")
    except ValueError:
        return None

    if not file_path.exists():
        return None

    try:
        return PipelineExecutionRecord.model_validate_json(
            file_path.read_text(encoding="utf-8")
        )
    except Exception:
        return None
