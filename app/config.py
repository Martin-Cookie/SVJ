from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "SVJ Správa"
    debug: bool = False
    base_dir: Path = Path(__file__).resolve().parent.parent
    database_path: Path = Path(__file__).resolve().parent.parent / "data" / "svj.db"
    upload_dir: Path = Path(__file__).resolve().parent.parent / "data" / "uploads"
    generated_dir: Path = Path(__file__).resolve().parent.parent / "data" / "generated"
    backup_dir: Path = Path(__file__).resolve().parent.parent / "data" / "backups"
    temp_dir: Path = Path(__file__).resolve().parent.parent / "data" / "temp"

    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_name: str = "SVJ"
    smtp_from_email: str = "svj@example.com"
    smtp_use_tls: bool = True

    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_use_ssl: bool = True

    libreoffice_path: str = "/Applications/LibreOffice.app/Contents/MacOS/soffice"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
