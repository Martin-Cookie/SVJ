from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "SVJ Správa"
    debug: bool = True
    base_dir: Path = Path(__file__).resolve().parent.parent
    database_path: Path = Path(__file__).resolve().parent.parent / "data" / "svj.db"
    upload_dir: Path = Path(__file__).resolve().parent.parent / "data" / "uploads"
    generated_dir: Path = Path(__file__).resolve().parent.parent / "data" / "generated"
    temp_dir: Path = Path(__file__).resolve().parent.parent / "data" / "temp"

    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_name: str = "SVJ"
    smtp_from_email: str = "svj@example.com"
    smtp_use_tls: bool = True

    libreoffice_path: str = "/Applications/LibreOffice.app/Contents/MacOS/soffice"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
