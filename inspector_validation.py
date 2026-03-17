from pathlib import Path
from typing import Optional, Tuple
from inspector_types import ScanConfig, ErrorResponse, validate_scan_config, FileSystemProvider, LocalFileSystemProvider
from inspector_utils import InspectorUtils

class InspectorValidation:
    """
    Boundary validation for the headless inspector.
    """

    @staticmethod
    def validate_inputs(config: ScanConfig, fs: Optional[FileSystemProvider] = None) -> Tuple[bool, Optional[ErrorResponse]]:
        """
        Validates the configuration and the target path.
        Returns (is_valid, error_response).
        """
        fs = fs or LocalFileSystemProvider()
        # 1. Schema/Config validation
        config_error = validate_scan_config(config)
        if config_error:
            return False, {
                "status": "error",
                "code": "INVALID_INPUT",
                "message": config_error,
                "target_path": config.get("root_path", "")
            }

        # 2. Path existence and type
        root_path = Path(config["root_path"])
        if not fs.exists(root_path):
            return False, {
                "status": "error",
                "code": "PATH_NOT_FOUND",
                "message": f"Path not found: {config['root_path']}",
                "target_path": str(root_path.absolute())
            }
        
        if not fs.is_dir(root_path):
            return False, {
                "status": "error",
                "code": "INVALID_TARGET",
                "message": f"Target is not a directory: {config['root_path']}",
                "target_path": str(root_path.absolute())
            }

        # 3. Access check
        try:
            list(fs.iterdir(root_path))
        except (PermissionError, OSError) as e:
            error_data = InspectorUtils.derive_error(e)
            return False, {
                "status": "error",
                "code": "ACCESS_DENIED",
                "message": error_data["message"],
                "target_path": str(root_path.absolute())
            }

        return True, None

    @staticmethod
    def validate_file_node_json(node: dict) -> bool:
        """
        Deep schema validation for a single FileNodeJSON.
        Returns True if the node matches the contract exactly.
        """
        required_fields = {
            "path_absolute": str,
            "name": str,
            "is_dir": bool,
            "size_bytes": int,
            "modified_epoch_s": float,
            "extension": str,
            "depth": int,
            "error": (dict, type(None))
        }
        
        # 1. Check presence and types
        for field, expected_type in required_fields.items():
            if field not in node:
                return False
            if not isinstance(node[field], expected_type):
                return False
        
        # 2. Field-specific invariants
        # path_absolute must be absolute and normalized
        path_obj = Path(node["path_absolute"])
        if not path_obj.is_absolute():
            return False
        
        # Extension invariant: Directories should not have extensions in our model
        if node["is_dir"] and node["extension"] != "":
            return False
            
        # Error format invariant: If present, must be a structured object with 'code' and 'message'
        error_obj = node["error"]
        if error_obj is not None:
            if not isinstance(error_obj, dict):
                return False
            if "code" not in error_obj or "message" not in error_obj:
                return False
            if not isinstance(error_obj["code"], str) or not isinstance(error_obj["message"], str):
                return False
            # Code must be uppercase (NodeErrorCode convention)
            if not error_obj["code"].isupper():
                return False

        # Ranges
        if node["size_bytes"] < 0:
            return False
        if node["depth"] < 0:
            return False
        # reasonable epoch check (e.g. > year 1970 and < year 2100)
        if node["modified_epoch_s"] < 0.0 or node["modified_epoch_s"] > 4102444800.0:
            return False
            
        return True
