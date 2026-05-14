#!/usr/bin/env python3
"""
WxFlight Planner – Cross-Platform Setup Script
Run: python setup_wxflight.py

Creates the project folder, installs dependencies,
and generates convenience scripts.
"""

import subprocess
import sys
import os
from pathlib import Path

APP_NAME = "WxFlight Planner"
ENV_NAME = "wxflight"

def run(cmd, check=True):
    """Run a shell command."""
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  ⚠️  Error: {result.stderr[:200]}")
        return False
    return True

def main():
    print(f"\n✈️  {APP_NAME} – Setup")
    print("=" * 50)

    # 1. Determine project directory
    home = Path.home()
    project_dir = home / "wxflight-planner"
    project_dir.mkdir(exist_ok=True)
    os.chdir(project_dir)
    print(f"\n📁 Project directory: {project_dir}")

    # 2. Check if conda is available
    print("\n🔍 Checking for conda...")
    has_conda = run("conda --version", check=False)

    if has_conda:
        print("\n🐍 Creating conda environment...")
        run(f"conda create -n {ENV_NAME} python=3.10 eccodes cfgrib "
            f"-c conda-forge -y")
        
        # Install pip packages inside conda env
        print("\n📦 Installing pip packages...")
        if sys.platform == "win32":
            pip_path = home / "miniconda3" / "envs" / ENV_NAME / "Scripts" / "pip"
            if not pip_path.exists():
                pip_path = home / "anaconda3" / "envs" / ENV_NAME / "Scripts" / "pip"
        else:
            pip_path = home / "miniconda3" / "envs" / ENV_NAME / "bin" / "pip"
            if not pip_path.exists():
                pip_path = home / "anaconda3" / "envs" / ENV_NAME / "bin" / "pip"
        
        pip_cmd = str(pip_path) if pip_path.exists() else "pip"
        run(f"{pip_cmd} install herbie-data xarray pandas numpy "
            f"matplotlib pytz streamlit requests")
    else:
        print("\n⚠️  conda not found. Installing with pip only...")
        print("   (Note: eccodes/cfgrib may need manual install)")
        run(f"{sys.executable} -m pip install herbie-data xarray cfgrib "
            f"pandas numpy matplotlib pytz streamlit requests")

    # 3. Create directory structure
    (project_dir / "output").mkdir(exist_ok=True)
    (project_dir / ".streamlit").mkdir(exist_ok=True)

    # 4. Write config files
    (project_dir / "requirements.txt").write_text(
        "herbie-data\nxarray\ncfgrib\npandas\nnumpy\n"
        "matplotlib\npytz\nstreamlit\nrequests\n")

    (project_dir / "environment.yml").write_text(f"""name: {ENV_NAME}
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.10
  - eccodes
  - cfgrib
  - xarray
  - pandas
  - numpy
  - matplotlib
  - pytz
  - pip:
    - herbie-data
    - streamlit
    - requests
""")

    (project_dir / ".streamlit" / "config.toml").write_text("""[theme]
primaryColor = "#7c4dff"
backgroundColor = "#0e1117"
secondaryBackgroundColor = "#1a1f2e"
textColor = "#fafafa"
font = "monospace"

[server]
headless = true
port = 8501
""")

    # 5. Create run scripts
    if sys.platform == "win32":
        (project_dir / "run_bankhead.bat").write_text(
            "@echo off\ncall conda activate wxflight\n"
            "python wxflight_core.py --site bankhead --hour 12\npause\n")
        (project_dir / "run_dustieaim.bat").write_text(
            "@echo off\ncall conda activate wxflight\n"
            "python wxflight_core.py --site dustieaim --hour 12\npause\n")
        (project_dir / "run_app.bat").write_text(
            "@echo off\ncall conda activate wxflight\n"
            "streamlit run wxflight_app.py\n")
    else:
        for name, cmd in [
            ("run_bankhead.sh",
             "#!/bin/bash\nconda activate wxflight\n"
             "python wxflight_core.py --site bankhead --hour 12\n"),
            ("run_dustieaim.sh",
             "#!/bin/bash\nconda activate wxflight\n"
             "python wxflight_core.py --site dustieaim --hour 12\n"),
            ("run_app.sh",
             "#!/bin/bash\nconda activate wxflight\n"
             "streamlit run wxflight_app.py\n"),
        ]:
            p = project_dir / name
            p.write_text(cmd)
            p.chmod(0o755)

    # 6. Print summary
    print(f"""
{'='*50}
✅ Setup complete!

📂 Project: {project_dir}

📄 Files to add manually:
   - wxflight_core.py  (copy from the code provided)
   - wxflight_app.py   (copy from the code provided)
   - index.html        (the WxFlight Planner HTML app)

🚀 Usage:
   conda activate {ENV_NAME}
   cd {project_dir}

   # Bankhead NF forecast (today, 12Z):
   python wxflight_core.py --site bankhead --hour 12

   # DustieAim Phoenix:
   python wxflight_core.py --site dustieaim --hour 12

   # Custom location:
   python wxflight_core.py --lat 40.0 --lon -105.0 --name Boulder

   # Streamlit web app:
   streamlit run wxflight_app.py

{'='*50}
""")


if __name__ == "__main__":
    main()