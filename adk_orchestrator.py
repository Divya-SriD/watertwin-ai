import json
import os
import subprocess
import sys
from typing import Any, Dict

# ============================================================
# WaterTwin AI - ADK Orchestrator
# WT-06 + WT-07 + first part of WT-13
#
# Workflow:
#   DETECT -> INVESTIGATE -> EXPLAIN -> SIMULATE -> PRIORITIZE -> ACT
#
# Architecture:
#   Detection/context/infrastructure/evidence
#          -> Gemini Investigation
#          -> Intervention Agent
#          -> Recommendation Engine
#          -> Intervention Simulator
#          -> Final Decision
#
# The orchestrator coordinates components. It does not calculate
# anomalies, perform Gemini reasoning, invent evidence, calculate
# intervention costs/savings, or override abstention.
# ============================================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

AGENTS = {
    "consumption": "consumption_agent.py",
    "context": "context_agent.py",
    "infrastructure": "infrastructure_agent.py",
    "evidence": "evidence_agent.py",
    "investigation": "investigation_engine.py",
    "intervention": "intervention_agent.py",
    "recommendation": "recommendation_engine.py",
    "simulator": "intervention_simulator.py",
}

DEFAULT_BUDGET = 20000.0


def print_section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def run_python_agent(
    filename: str,
    scenario_id: str,
    extra_args=None,
    stdin_payload: Dict[str, Any] = None,
) -> Dict[str, Any]:
    if extra_args is None:
        extra_args = []

    path = os.path.join(PROJECT_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Required WaterTwin component not found: {path}")

    command = [sys.executable, path]
    if scenario_id is not None:
        command.append(scenario_id)
    command.extend(str(arg) for arg in extra_args)

    if stdin_payload is not None:
        command.append("--json")

    completed = subprocess.run(
        command,
        cwd=PROJECT_DIR,
        input=json.dumps(stdin_payload) if stdin_payload is not None else None,
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        print(completed.stdout)
        print(completed.stderr)
        raise RuntimeError(
            f"{filename} failed with exit code {completed.returncode}"
        )

    output = completed.stdout.strip()
    print(output)
    return {
        "agent": filename,
        "scenario_id": scenario_id,
        "raw_output": output,
    }


def extract_json_objects(text: str):
    decoder = json.JSONDecoder()
    objects = []
    index = 0

    while index < len(text):
        try:
            start = text.index("{", index)
        except ValueError:
            break

        try:
            obj, end = decoder.raw_decode(text[start:])
            objects.append(obj)
            index = start + end
        except json.JSONDecodeError:
            index = start + 1

    return objects


def extract_latest_json(output: str) -> Dict[str, Any]:
    objects = extract_json_objects(output)
    if not objects:
        raise RuntimeError("No JSON object found in component output.")
    return objects[-1]


def execute_component(
    filename: str,
    scenario_id: str,
    extra_args=None,
) -> Dict[str, Any]:
    result = run_python_agent(filename, scenario_id, extra_args)
    return extract_latest_json(result["raw_output"])


def execute_json_component(
    filename: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    scenario_id = str(payload.get("scenario_id", "UNKNOWN"))
    result = run_python_agent(
        filename,
        scenario_id=None,
        stdin_payload=payload,
    )
    return extract_latest_json(result["raw_output"])


def orchestrate(scenario_id: str, budget: float) -> Dict[str, Any]:
    print_section(f"WaterTwin ADK Orchestrator - Scenario {scenario_id}")
    print(f"Simulation budget: {budget:.2f}")

    print_section("1. DETECT - Consumption Agent")
    consumption = execute_component(AGENTS["consumption"], scenario_id)

    print_section("2. CONTEXT - Context Agent")
    context = execute_component(AGENTS["context"], scenario_id)

    print_section("3. INFRASTRUCTURE - Infrastructure Agent")
    infrastructure = execute_component(AGENTS["infrastructure"], scenario_id)

    print_section("4. EVIDENCE - Evidence Agent")
    evidence = execute_component(AGENTS["evidence"], scenario_id)

    print_section("5. INVESTIGATE / EXPLAIN - Gemini Investigation")
    investigation = execute_component(AGENTS["investigation"], scenario_id)

    print_section("6. INTERVENTION - Intervention Agent")
    intervention = execute_component(AGENTS["intervention"], scenario_id)

    # --------------------------------------------------------
    # 7. PRIORITIZE - Recommendation Engine
    # Machine-readable handoff: Investigation + Intervention + budget.
    # --------------------------------------------------------
    print_section("7. PRIORITIZE - Recommendation Engine")
    recommendation_input = {
        "scenario_id": scenario_id,
        "budget": budget,
        "investigation": investigation,
        "intervention": intervention,
    }
    recommendation = execute_json_component(
        AGENTS["recommendation"],
        recommendation_input,
    )

    # --------------------------------------------------------
    # 8. SIMULATE - Intervention Simulator
    # Machine-readable handoff: Recommendation + budget.
    # --------------------------------------------------------
    print_section("8. SIMULATE - Intervention Simulator")
    simulation_input = {
        "scenario_id": scenario_id,
        "budget": budget,
        "recommendation": recommendation,
    }
    simulation = execute_json_component(
        AGENTS["simulator"],
        simulation_input,
    )

    simulation_result = simulation.get("simulation", {})

    final_package = {
        "scenario_id": scenario_id,
        "workflow": [
            "DETECT",
            "INVESTIGATE",
            "EXPLAIN",
            "SIMULATE",
            "PRIORITIZE",
            "ACT",
        ],
        "simulation_budget": budget,
        "agents": {
            "consumption_agent": consumption,
            "context_agent": context,
            "infrastructure_agent": infrastructure,
            "evidence_agent": evidence,
            "investigation_engine": investigation,
            "intervention_agent": intervention,
            "recommendation_engine": recommendation,
            "intervention_simulator": simulation,
        },
        "final_decision": {
            "decision": simulation_result.get("decision"),
            "primary_hypothesis": simulation_result.get("primary_hypothesis"),
            "confidence_level": simulation_result.get("confidence_level"),
            "recommended_intervention": simulation_result.get("recommended_intervention"),
            "impact": simulation_result.get("impact"),
            "simulation_status": simulation_result.get("simulation_status"),
        },
        "orchestration_status": "SUCCESS",
    }

    return final_package


def validate_package(package: Dict[str, Any]) -> None:
    required_fields = [
        "scenario_id",
        "workflow",
        "simulation_budget",
        "agents",
        "final_decision",
        "orchestration_status",
    ]
    for field in required_fields:
        if field not in package:
            raise RuntimeError(f"Final orchestration package is missing: {field}")

    required_agents = [
        "consumption_agent",
        "context_agent",
        "infrastructure_agent",
        "evidence_agent",
        "investigation_engine",
        "intervention_agent",
        "recommendation_engine",
        "intervention_simulator",
    ]
    for agent in required_agents:
        if agent not in package["agents"]:
            raise RuntimeError(f"Final package is missing component output: {agent}")

    required_decision_fields = [
        "decision",
        "primary_hypothesis",
        "confidence_level",
        "simulation_status",
    ]
    for field in required_decision_fields:
        if field not in package["final_decision"]:
            raise RuntimeError(f"Final decision is missing: {field}")

    if package["orchestration_status"] != "SUCCESS":
        raise RuntimeError("WaterTwin orchestration did not complete successfully.")


def main() -> None:
    if len(sys.argv) not in {2, 3}:
        print("Usage:")
        print("  python3 adk_orchestrator.py S2")
        print("  python3 adk_orchestrator.py S2 20000")
        sys.exit(1)

    scenario_id = sys.argv[1].strip().upper()
    if not scenario_id:
        raise ValueError("Scenario ID cannot be empty.")

    if len(sys.argv) == 3:
        try:
            budget = float(sys.argv[2])
        except ValueError:
            raise ValueError("Budget must be a valid number.")
    else:
        budget = DEFAULT_BUDGET

    if budget < 0:
        raise ValueError("Budget cannot be negative.")

    print("WaterTwin AI orchestration starting...")
    print(f"Scenario: {scenario_id}")
    print(f"Budget: {budget:.2f}")

    package = orchestrate(scenario_id, budget)
    validate_package(package)

    print_section("FINAL WATERTWIN ORCHESTRATION PACKAGE")
    print(json.dumps(package, indent=2))
    print()
    print("WaterTwin ADK orchestration completed successfully.")


if __name__ == "__main__":
    main()
