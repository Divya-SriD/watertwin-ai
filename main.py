import json
import os
import subprocess
import sys

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(
    title="WaterTwin AI",
    description="Evidence-Based Intelligence for Water Infrastructure",
    version="1.0.0",
)


PROJECT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

ORCHESTRATOR = os.path.join(
    PROJECT_DIR,
    "adk_orchestrator.py"
)


class AnalysisRequest(BaseModel):
    scenario_id: str = Field(
        ...,
        min_length=2,
        max_length=10
    )

    budget: float = Field(
        default=2000.0,
        ge=0
    )


def extract_final_package(output: str):
    """
    Extract the final WaterTwin JSON package from
    orchestrator stdout.

    The orchestrator currently prints human-readable
    progress information before the final JSON object.
    """

    decoder = json.JSONDecoder()

    candidates = []

    for index, character in enumerate(output):

        if character != "{":
            continue

        try:

            obj, _ = decoder.raw_decode(
                output[index:]
            )

            if isinstance(obj, dict):

                if (
                    "scenario_id" in obj
                    and "orchestration_status" in obj
                ):
                    candidates.append(obj)

        except json.JSONDecodeError:
            continue

    if not candidates:

        raise ValueError(
            "Could not extract final WaterTwin "
            "decision package from orchestrator output."
        )

    return candidates[-1]


@app.get("/")
def root():
    return {
        "service": "WaterTwin AI",
        "status": "RUNNING",
        "message": "Evidence-Based Intelligence for Water Infrastructure",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "watertwin-ai",
    }


@app.post("/analyze")
@app.post("/api/analyze")
def analyze(request: AnalysisRequest):

    scenario_id = (
        request.scenario_id
        .strip()
        .upper()
    )

    if not scenario_id:

        raise HTTPException(
            status_code=400,
            detail="scenario_id cannot be empty."
        )

    if not os.path.exists(ORCHESTRATOR):

        raise HTTPException(
            status_code=500,
            detail="adk_orchestrator.py was not found."
        )

    command = [
        sys.executable,
        ORCHESTRATOR,
        scenario_id,
        str(request.budget),
    ]

    try:

        completed = subprocess.run(
            command,
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=300,
        )

    except subprocess.TimeoutExpired:

        raise HTTPException(
            status_code=504,
            detail="WaterTwin analysis timed out."
        )

    if completed.returncode != 0:

        raise HTTPException(
            status_code=500,
            detail={
                "message": "WaterTwin orchestration failed.",
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            },
        )

    try:

        package = extract_final_package(
            completed.stdout
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=500,
            detail={
                "message": str(exc),
                "stdout": completed.stdout[-4000:],
            },
        )

    return package