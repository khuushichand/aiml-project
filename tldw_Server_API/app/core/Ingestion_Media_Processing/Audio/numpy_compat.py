# numpy_compat.py
#########################################
# NumPy 2.0 Compatibility Module
# This module provides compatibility patches for libraries that haven't been updated
# for NumPy 2.0 breaking changes.
#
####################

import numpy as np
from loguru import logger

logger = logger

def patch_numpy_sctypes():
    """
    Monkey patch for NumPy 2.0 compatibility.

    np.sctypes was removed in NumPy 2.0. This patch adds it back for libraries
    that haven't been updated yet (like Nemo ASR).
    """
    if not hasattr(np, 'sctypes'):
        logger.info("Applying NumPy 2.0 compatibility patch for np.sctypes")

        # Recreate the sctypes dictionary that was removed in NumPy 2.0
        np.sctypes = {
            'int': [np.int8, np.int16, np.int32, np.int64],
            'uint': [np.uint8, np.uint16, np.uint32, np.uint64],
            'float': [np.float16, np.float32, np.float64],
            'complex': [np.complex64, np.complex128],
            'others': [bool, object, bytes, str, np.void]
        }

        logger.info("NumPy 2.0 compatibility patch applied successfully")

def ensure_numpy_compatibility():
    """
    Ensure NumPy compatibility for all required features.

    This function should be called before importing libraries that may have
    NumPy 2.0 compatibility issues.
    """
    patch_numpy_sctypes()

    # Add any other compatibility patches here as needed

    logger.debug("NumPy compatibility ensured")

# Apply patches on module import
ensure_numpy_compatibility()
