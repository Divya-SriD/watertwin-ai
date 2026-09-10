#!/usr/bin/env python3

"""
WaterTwin AI - Pub/Sub Processor

Milestone 14C

Reads a WaterTwin Pub/Sub event, validates the event payload,
and triggers the existing ADK orchestrator for the specified
scenario.

The processor contains no Gemini reasoning. Gemini reasoning
remains inside the existing WaterTwin investigation workflow.

NOTE:
The current ADK orchestrator prints the final JSON package followed
by a completion message. Until the orchestrator exposes a cleaner
machine-readable interface, this processor extracts the final JSON
object from stdout using JSONDecoder.raw_decode().
"""

import json
import subprocess
import sys
from typing import Any, Dict


PROJECT_ID = "project-4e41dc93-8aec-4f29-8fd"
ORCHESTRATOR = "adk_orchestrator.py"

SUPPORTED_SCENARIOS = {
    "S1",
    "S2",
    "S3",
    "S4",
    "S5",
    "S6",
    "S7",
}


def print_header(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def validate_event(event: Dict[str, Any]) -> str:
    """Validate the minimum WaterTwin event contract."""

    if not isinstance(event, dict):
        raise ValueError("Event payload must be a JSON object.")

    scenario_id = event.get("scenario_id")

    if not scenario_id:
        raise ValueError("Missing required field: scenario_id")

    scenario_id = str(scenario_id).upper().strip()

    if scenario_id not in SUPPORTED_SCENARIOS:
        raise ValueError(
            f"Unsupported scenario_id: {scenario_id}. "
            f"Expected one of: {sorted(SUPPORTED_SCENARIOS)}"
        )

    event_type = event.get("event_type")

    if not event_type:
        raise ValueError("Missing required field: event_type")

    source = event.get("source")

    if not source:
        raise ValueError("Missing required field: source")

    return scenario_id


def extract_final_package(output: str) -> Dict[str, Any]:
    """
    Extract the final WaterTwin JSON package from orchestrator stdout.

    The current orchestrator writes logs and then prints the final JSON
    object followed by a completion message. JSONDecoder.raw_decode()
    allows us to parse exactly one JSON object without requiring the
    JSON to occupy the entire remaining stdout.
    """

    decoder = json.JSONDecoder()

    candidates = []

    for index, character in enumerate(output):
        if character == "{":
            candidates.append(index)

    for start_index in reversed(candidates):
        candidate = output[start_index:]

        try:
            parsed, _ = decoder.raw_decode(candidate)

            if isinstance(parsed, dict):
                if (
                    parsed.get("scenario_id") is not None
                    and parsed.get("workflow") is not None
                    and parsed.get("final_decision") is not None
                ):
                    return parsed

        except json.JSONDecodeError:
            continue

    raise ValueError(
        "Could not extract the final WaterTwin JSON package "
        "from the ADK orchestrator output."
    )


def run_orchestrator(
    scenario_id: str,
    budget: float = 2000.0,
) -> Dict[str, Any]:
    """
    Execute the existing ADK orchestrator.

    The orchestrator remains responsible for coordinating the
    WaterTwin agents. This processor only triggers it and captures
    its structured final result.
    """

    command = [
        "python3",
        ORCHESTRATOR,
        scenario_id,
        str(budget),
    ]

    print_header("Triggering WaterTwin ADK Orchestrator")

    print(f"Scenario: {scenario_id}")
    print(f"Budget: {budget:.2f}")
    print(f"Command: {' '.join(command)}")
    print()

    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    print(process.stdout)

    if process.returncode != 0:
        if process.stderr:
            print(process.stderr, file=sys.stderr)

        raise RuntimeError(
            "ADK orchestrator failed "
            f"with exit code {process.returncode}"
        )

    return extract_final_package(process.stdout)


def process_event(
    event: Dict[str, Any],
    budget: float = 2000.0,
) -> Dict[str, Any]:
    """Process one WaterTwin Pub/Sub event."""

    print_header("WaterTwin Pub/Sub Processor")

    print(f"Project: {PROJECT_ID}")

    scenario_id = validate_event(event)

    print(f"Scenario: {scenario_id}")
    print(f"Event type: {event['event_type']}")
    print(f"Source: {event['source']}")

    result = run_orchestrator(
        scenario_id=scenario_id,
        budget=budget,
    )

    processor_result = {
        "processor_status": "SUCCESS",
        "scenario_id": scenario_id,
        "event_type": event["event_type"],
        "source": event["source"],
        "orchestration_status": "SUCCESS",
        "water_twin_result": result,
    }

    print_header("Pub/Sub Processing Result")

    print(
        json.dumps(
            processor_result,
            indent=2,
            default=str,
        )
    )

    return processor_result


def load_event_from_argument(argument: str) -> Dict[str, Any]:
    """
    Load an event from either a JSON string or JSON file.
    """

    try:
        parsed = json.loads(argument)

        if not isinstance(parsed, dict):
            raise ValueError("JSON event must be an object.")

        return parsed

    except json.JSONDecodeError:
        pass

    try:
        with open(argument, "r", encoding="utf-8") as file:
            parsed = json.load(file)

        if not isinstance(parsed, dict):
            raise ValueError("JSON event must be an object.")

        return parsed

    except FileNotFoundError:
        raise ValueError(
            "Argument is neither valid JSON nor an existing JSON file."
        )


def main() -> None:
    """
    Command-line entry point.

    Usage:

        python3 pubsub_processor.py S2

    or:

        python3 pubsub_processor.py S2 2000

    or:

        python3 pubsub_processor.py \
          '{"scenario_id":"S2","event_type":"WATER_USAGE_ANOMALY","source":"synthetic_simulator"}'
    """

    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print(
            "Usage:\n"
            "  python3 pubsub_processor.py S2\n"
            "  python3 pubsub_processor.py S2 2000\n"
            "  python3 pubsub_processor.py "
            "'{\"scenario_id\":\"S2\","
            "\"event_type\":\"WATER_USAGE_ANOMALY\","
            "\"source\":\"synthetic_simulator\"}'"
        )
        sys.exit(1)

    first_argument = sys.argv[1]

    if first_argument.startswith("{"):
        event = load_event_from_argument(first_argument)
        budget = float(sys.argv[2]) if len(sys.argv) == 3 else 2000.0
    else:
        scenario_id = first_argument.upper().strip()

        event = {
            "scenario_id": scenario_id,
            "event_type": "WATER_USAGE_ANOMALY",
            "priority": "HIGH",
            "source": "synthetic_simulator",
        }

        budget = float(sys.argv[2]) if len(sys.argv) == 3 else 2000.0

    try:
        process_event(
            event=event,
            budget=budget,
        )

    except Exception as exc:
        print_header("Pub/Sub Processing Failed")
        print(f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
