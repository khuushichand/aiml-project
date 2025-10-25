# tldw_Server_API/app/api/v1/API_Deps/validation_deps.py
from tldw_Server_API.app.core.config import settings, MAGIC_FILE_PATH, YARA_RULES_PATH
from tldw_Server_API.app.core.Ingestion_Media_Processing.Upload_Sink import FileValidator
from tldw_Server_API.app.core.Utils.Utils import logging # Your logger
#
########################################################################################################################
#
#
# Rely on FileValidator to configure python-magic when available; avoid global side effects


file_validator_instance = FileValidator(
    yara_rules_path=YARA_RULES_PATH,
    # custom_media_configs can be loaded from settings too if needed
)

def get_file_validator() -> FileValidator:
    return file_validator_instance

#
# End of validations_deps.py
#######################################################################################################################
