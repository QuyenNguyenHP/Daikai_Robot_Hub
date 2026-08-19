"""Process-wide coordination for Unitree DDS entity initialization."""

import threading


# CycloneDDS supports concurrent readers after initialization, but creating
# several Unitree clients against the shared participant at exactly the same
# time can fail with DDS_RETCODE_BAD_PARAMETER on some SDK/CycloneDDS builds.
UNITREE_DDS_INIT_LOCK = threading.Lock()
