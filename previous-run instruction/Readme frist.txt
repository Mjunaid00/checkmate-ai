Here's how to set up CheckMate AI on a new laptop:

Step 1: Get the Code
Copy the project folder to the new laptop (USB, zip, or git):


# If using git:
git clone <your-repo-url>

# Or just copy the checkmate-ai folder



Step 2: Backend Setup

# Install Anaconda/Miniconda first, then:
conda create -n checkmate-ai python=3.10 -y
conda activate checkmate-ai

cd checkmate-ai/backend
pip install -r requirements.txt

# Create your .env file
cp .env.example .env



How to Recreate the EnvironmentOnce you have your file, here is how you (or your friend) would bring it back to life:


File Type           Command to Restore

1. The Standard YAML Method (Best for Sharing)
This is the most common approach. It creates a .yml file that includes the environment name, channels, and all dependencies 
(including those installed via pip).


YAML (.yml)         conda env create -f environment.yml



2. The Spec List (Best for Same OS)
If you just need a quick backup to use on the same machine or the same OS, you can create an explicit "spec list." 
This is faster but strictly limited to Conda packages (it ignores pip).

Spec List (.txt)     conda create --name new_env --file spec-file.txt



3. Pro Tip: If you want to make the file more "cross-platform" (e.g., moving from Windows to Mac), use the --no-builds flag.
 It removes the specific build numbers that might not exist on a different operating system:

conda env export --no-builds > environment.yml




Step 3: Frontend Setup
# Install Node.js 18+ first, then:
cd checkmate-ai/frontend
npm install


Step 4: Install MongoDB
Download MongoDB Community Server
Install with "Run as Windows Service" checked
Optionally install MongoDB Compass for GUI


Step 5: Install LM Studio
Download LM Studio
Search and download qwen2.5-vl-7b
Load the model and Start Server (port 1234)


Step 6: Run
Open 2 terminals:


# Terminal 1 — Backend
conda activate checkmate-ai
cd checkmate-ai/backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Frontend
cd checkmate-ai/frontend
npm run dev
Open http://localhost:5173 in browser.

Important: What NOT to copy
Delete these before copying to avoid issues:


# Remove from backend
backend/__pycache__/         # (and all nested __pycache__ folders)
backend/.env                 # contains secrets — use .env.example

# Remove from frontend
frontend/node_modules/       # reinstall with npm install
Quick Checklist
Requirement	Check
Python 3.10+ (Anaconda)	python --version
Node.js 18+	node --version
MongoDB running	Open Compass, connect to localhost:27017
LM Studio server running	Visit http://localhost:1234
Backend running	Visit http://localhost:8000/health
Frontend running	Visit http://localhost:5173