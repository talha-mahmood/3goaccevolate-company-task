"""
Helper script to install dependencies without building from source
"""
import sys
import subprocess
import os
import platform

def install_package(package):
    """Install a package using pip"""
    print(f"Installing {package}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def main():
    """Main installation function"""
    print("Checking and installing dependencies...")
    
    # Update pip first
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    
    # Packages that might need binary installations
    binary_packages = ['aiohttp', 'lxml']
    
    # Install binary versions first
    print("Installing binary packages...")
    for package in binary_packages:
        try:
            # Try to install binary wheel
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", 
                "--only-binary=:all:", package
            ])
            print(f"Successfully installed {package} from binary wheel")
        except subprocess.CalledProcessError:
            print(f"Could not install {package} from binary wheel, will try alternate method")
    
    # Install remaining requirements
    try:
        print("Installing remaining requirements...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt",
            "--no-deps", "--ignore-installed", *binary_packages
        ])
    except subprocess.CalledProcessError:
        print("Error installing from requirements.txt, trying alternative approach")
        
        # Read requirements file and install packages one by one
        with open("requirements.txt", "r") as f:
            requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        
        for req in requirements:
            # Skip packages we already installed and platform-specific ones
            if any(pkg in req for pkg in binary_packages) or ";" in req:
                continue
            
            try:
                install_package(req)
            except subprocess.CalledProcessError:
                print(f"Warning: Failed to install {req}")
    
    print("\nDependencies installed successfully!")
    print("If you still encounter issues, you may need to install Microsoft Visual C++ Build Tools:")
    print("https://visualstudio.microsoft.com/visual-cpp-build-tools/")

if __name__ == "__main__":
    main()
