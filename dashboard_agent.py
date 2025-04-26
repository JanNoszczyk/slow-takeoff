import subprocess
import os
from typing import Dict, Any

def generate_dashboard() -> Dict[str, Any]:
    """
    Builds the dashboard as defined in the 'dashboard' project folder.

    Returns:
        dict: {
            "success": bool,
            "message": str,
            "output_path": str (if successful, else None)
        }
    """
    dashboard_dir = os.path.join(os.path.dirname(__file__), "dashboard")
    build_cmd = ["npm", "run", "build"]

    try:
        result = subprocess.run(
            build_cmd,
            cwd=dashboard_dir,
            capture_output=True,
            text=True,
            check=True
        )
        output_path = os.path.join(dashboard_dir, ".next")
        return {
            "success": True,
            "message": "Dashboard build succeeded.",
            "output_path": output_path
        }
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "message": f"Dashboard build failed: {e.stderr}",
            "output_path": None
        }
