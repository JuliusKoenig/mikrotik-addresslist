from pydantic import Field
from pydantic_settings import BaseSettings
from wiederverwendbar.logger import LoggerSettings, LogLevels
from wiederverwendbar.typer import TyperSettings

from mikrotik_addresslist import __title__, __description__, __author__, __author_email__, __version__, __license__, __license_url__, __terms_of_service__, __env_prefix__


class Settings(BaseSettings, LoggerSettings, TyperSettings):
    model_config = {
        "env_prefix": __env_prefix__,
        "case_sensitive": False
    }


settings = Settings(branding_title=__title__,
                    branding_description=__description__,
                    branding_version=__version__,
                    branding_author=__author__,
                    branding_author_email=__author_email__,
                    branding_license=__license__,
                    branding_license_url=__license_url__,
                    branding_terms_of_service=__terms_of_service__,
                    log_level=LogLevels.DEBUG)  # ToDo: Change to LogLevels.INFO in production
