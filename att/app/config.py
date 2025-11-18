# att/app/config.py

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

class ConfigLoader:
    """
    Carrega e fornece acesso seguro às configurações do 'config.json'.
    Recebe os caminhos pré-definidos do main.py.
    """

    def __init__(self, 
                 config_path: Path, 
                 db_usuarios_path: Path, 
                 icons_path: Optional[Path], 
                 base_path: Path, 
                 db_empresas_path: Path):
        self.config_path = config_path
        
        # --- MODIFICAÇÃO: Corrigido de 'self.db_path' para 'self.db_usuarios_path' ---
        self.db_usuarios_path = db_usuarios_path 
        # --- FIM DA MODIFICAÇÃO ---

        self.icons_path = icons_path
        self.base_path = base_path
        self.db_empresas_path = db_empresas_path # <-- Armazena o caminho do SQLite

        if not self.config_path.exists():
            raise FileNotFoundError(f"Arquivo de configuração não encontrado em: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config_data: Dict[str, Any] = json.load(f)

    @property
    def salt(self) -> str:
        return self._config_data.get("SECURITY", {}).get("SALT", "m3u_s4l_s3cr3t0_p4r4_0_4pp")

    @property
    def admin_user(self) -> str:
        return self._config_data.get("SECURITY", {}).get("ADMIN_USER", "admin")

    @property
    def tolerancia_valor(self) -> float:
        return self._config_data.get("FISCAL_RULES", {}).get("TOLERANCIA_VALOR", 0.03)

    @property
    def cfop_sem_credito_icms(self) -> List[str]:
        return self._config_data.get("FISCAL_RULES", {}).get("CFOP_SEM_CREDITO_ICMS", [])

    @property
    def cfop_sem_credito_ipi(self) -> List[str]:
        return self._config_data.get("FISCAL_RULES", {}).get("CFOP_SEM_CREDITO_IPI", [])

    @property
    def theme_name(self) -> str:
        return self._config_data.get("UI_THEME", {}).get("THEME_NAME", "SuperModerno")

    @property
    def font_family(self) -> str:
        return self._config_data.get("UI_THEME", {}).get("FONT_FAMILY", "Segoe UI")

    @property
    def theme_definition(self) -> Dict[str, Any]:
        return self._config_data.get("UI_THEME", {}).get("THEME_DEFINITION", {})

    @property
    def btn_colors(self) -> Dict[str, Any]:
        return self._config_data.get("UI_THEME", {}).get("BTN_COLORS", {})

    @property
    def app_icon_path(self) -> Optional[str]:
        """Retorna o caminho completo para o ícone da aplicação."""
        icon_name = self._config_data.get("UI_THEME", {}).get("APP_ICON_NAME")
        if not icon_name or not self.icons_path: # <-- Verifica se icons_path não é None
            return None

        icon_path = self.icons_path / icon_name 

        if not icon_path.exists():
            print(f"Aviso: Ícone da aplicação não encontrado em: {icon_path}")
            return None
        
        return str(icon_path) # <-- Retorna string



    @property
    def log_directory_path(self) -> Optional[str]:
        """Retorna o caminho cacompleto para a PASTA de logs, se definido."""
        # Lê a seção "LOGGING", pega a chave "LOG_DIRECTORY_PATH"
        path = self._config_data.get("LOGGING", {}).get("LOG_DIRECTORY_PATH")
        return path if path else None

    @property
    def log_level(self) -> str:
        """Retorna o nível de log (ex: "INFO", "DEBUG"). Padrão é "INFO"."""
        return self._config_data.get("LOGGING", {}).get("LOG_LEVEL", "INFO")