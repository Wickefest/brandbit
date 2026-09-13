from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent

def _env_files() -> tuple[str, ...]:
                                                               
    candidates = (BACKEND_ROOT / ".env", REPO_ROOT / ".env")
    return tuple(str(path) for path in candidates if path.is_file())

class Settings(BaseSettings):
                                                             

    model_config = SettingsConfigDict(
        env_file=_env_files() or (str(BACKEND_ROOT / ".env"),),
        env_file_encoding="utf-8",
        extra="ignore",
    )

                  
    descriptor_generation_max_retries: int = 3
    congruence_regen_max_retries: int = 3                                                                         

                                        
    kimi_api_key: str = ""
    kimi_text_model: str = Field(
        default="kimi-k2.6",
        validation_alias="KIMI_TEXT_MODEL",
    )
    kimi_vision_model: str = Field(
        default="kimi-k2.6",
        validation_alias="KIMI_VISION_MODEL",
    )
    kimi_base_url: str = "https://api.moonshot.ai/v1"

                                                                 
    qwen_replicate_model: str = Field(
        default=(
            "lucataco/qwen3-vl-8b-instruct:"
            "39e893666996acf464cff75688ad49ac95ef54e9f1c688fbc677330acc478e11"
        ),
        validation_alias="QWEN_REPLICATE_MODEL",
    )

                                                                                
    gpt4o_replicate_model: str = Field(
        default="openai/gpt-4o",
        validation_alias="GPT4O_REPLICATE_MODEL",
    )
    deepseek_replicate_model: str = Field(
        default="deepseek-ai/deepseek-v3",
        validation_alias="DEEPSEEK_REPLICATE_MODEL",
    )

                                           
    musicgen_backend: str = "auto"                                           
    musicgen_api_key: str = ""                                                 
    musicgen_remote_url: str = ""                                           
    musicgen_replicate_model: str = (
        "meta/musicgen:671ac645ce5e552cc63a54a2bbff63fcf798043055d2dac5fc9e36a837eedcfb"
    )
    musicgen_replicate_version: str = "stereo-large"
    musicgen_local_model: str = "facebook/musicgen-small"
    musicgen_duration_seconds: int = 15
    musicgen_output_dir: str = str(REPO_ROOT / "eval" / "outputs" / "music")
    fragrance_output_dir: str = str(REPO_ROOT / "eval" / "outputs" / "fragrance")
                                                                  
    audio_generation_timeout_seconds: int = 600

                                               
    pyrfume_catalog_cache_path: str = "./data/pyrfume_catalog.json"
    pyrfume_retrieval_top_k: int = 30
    pyrfume_datasets: list[str] = ["goodscents", "leffingwell", "ifra_2019"]
    # Retrieval is always LSA k-NN (TF-IDF → TruncatedSVD → cosine neighbors).

    execution_log_dir: str = str(REPO_ROOT / "eval" / "result")
    input_image_dir: str = str(REPO_ROOT / "eval" / "outputs" / "images")

                                                                            
    clip_backend: str = "auto"                                  
    clip_model_name: str = "openai/clip-vit-base-patch32"                      
    clip_replicate_model: str = Field(
        default="openai/clip",
        validation_alias="CLIP_REPLICATE_MODEL",
    )

                             
    max_image_size_mb: int = 20
    allowed_image_formats: list[str] = ["image/jpeg", "image/jpg", "image/png", "image/webp"]

    @model_validator(mode="before")
    @classmethod
    def _accept_kimi_model_alias(cls, data: object) -> object:
                                                                  
        if not isinstance(data, dict):
            return data
        if not data.get("kimi_text_model") and not data.get("KIMI_TEXT_MODEL"):
            legacy = data.get("KIMI_MODEL") or data.get("kimi_model")
            if legacy:
                data = {**data, "kimi_text_model": legacy}
        return data
