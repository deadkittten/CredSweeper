from typing import Dict, Any, List

from tests import SAMPLES_POST_CRED_COUNT, SAMPLES_IN_DEEP_3, SAMPLES_CRED_COUNT, SAMPLES_IN_DOC

DATA_TEST_CFG: List[Dict[str, Any]] = [{
    "__cred_count": SAMPLES_POST_CRED_COUNT,
    "sort_output": True,
    "json_filename": "output.json"
}, {
    "__cred_count": SAMPLES_IN_DOC,
    "sort_output": True,
    "json_filename": "doc.json",
    "doc": True
}, {
    "__cred_count": SAMPLES_IN_DEEP_3,
    "sort_output": True,
    "json_filename": "depth_3.json",
    "depth": 3
}, {
    "__cred_count": SAMPLES_CRED_COUNT,
    "sort_output": True,
    "json_filename": "ml_threshold_0.json",
    "ml_threshold": 0
}]
