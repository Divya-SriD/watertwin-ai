import json
import sys
from typing import Any, Dict

# ============================================================
# WaterTwin AI - Intervention Simulator
# WT-06 + WT-07
#
# Responsibility:
#   Apply deterministic budget and impact calculations to the
#   Recommendation Engine output.
#
# Important architectural rule:
#   This component does NOT call recommendation_engine.py.
#   It consumes the Recommendation Result as its input.
# ============================================================


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def annual_savings(litres_per_day: float) -> float:
    return round(litres_per_day * 365.0, 2)


def cost_per_1000_litres(cost: float, litres_per_day: float):
    if litres_per_day <= 0:
        return None
    return round(cost / (litres_per_day / 1000.0), 2)


def simulate(recommendation: Dict[str, Any], budget: float) -> Dict[str, Any]:
    decision = str(recommendation.get("decision", "")).upper()
    status = str(recommendation.get("status", decision)).upper()
    hypothesis = str(recommendation.get("primary_hypothesis", "")).upper()
    confidence = str(recommendation.get("confidence_level", "")).upper()
    scenario_id = str(recommendation.get("scenario_id", "UNKNOWN"))

    if decision == "ABSTAIN":
        return {
            "scenario_id": scenario_id,
            "simulation": {
                "budget": round(budget, 2),
                "simulation_status": "ABSTAIN",
                "message": (
                    "WaterTwin abstains because the investigation evidence is "
                    "insufficient or conflicting. The simulator does not override the abstention."
                ),
                "decision": "ABSTAIN",
                "primary_hypothesis": hypothesis,
                "confidence_level": confidence,
                "recommended_intervention": None,
                "impact": {
                    "selected": False,
                    "estimated_cost": 0.0,
                    "estimated_water_savings_litres_per_day": 0.0,
                    "estimated_water_savings_litres_per_year": 0.0,
                    "cost_per_1000_litres_saved": None,
                    "budget_remaining": round(budget, 2),
                },
            },
        }

    if decision == "NO_ACTION":
        simulation_status = "BUDGET_CONSTRAINED" if status == "BUDGET_CONSTRAINED" else "NO_ACTION"
        message = (
            "No evidence-aligned intervention is currently feasible within the supplied budget."
            if simulation_status == "BUDGET_CONSTRAINED"
            else "The evidence does not require an intervention."
        )
        return {
            "scenario_id": scenario_id,
            "simulation": {
                "budget": round(budget, 2),
                "simulation_status": simulation_status,
                "message": message,
                "decision": "NO_ACTION",
                "primary_hypothesis": hypothesis,
                "confidence_level": confidence,
                "recommended_intervention": None,
                "impact": {
                    "selected": False,
                    "estimated_cost": 0.0,
                    "estimated_water_savings_litres_per_day": 0.0,
                    "estimated_water_savings_litres_per_year": 0.0,
                    "cost_per_1000_litres_saved": None,
                    "budget_remaining": round(budget, 2),
                },
            },
        }

    if decision == "EXPLAIN":
        return {
            "scenario_id": scenario_id,
            "simulation": {
                "budget": round(budget, 2),
                "simulation_status": "EXPLAIN",
                "message": (
                    "The Investigation Engine returned EXPLAIN. "
                    "The simulator does not upgrade an explanation into an intervention."
                ),
                "decision": "EXPLAIN",
                "primary_hypothesis": hypothesis,
                "confidence_level": confidence,
                "recommended_intervention": None,
                "impact": {
                    "selected": False,
                    "estimated_cost": 0.0,
                    "estimated_water_savings_litres_per_day": 0.0,
                    "estimated_water_savings_litres_per_year": 0.0,
                    "cost_per_1000_litres_saved": None,
                    "budget_remaining": round(budget, 2),
                },
            },
        }

    intervention = recommendation.get("recommended_intervention")
    if not isinstance(intervention, dict):
        return {
            "scenario_id": scenario_id,
            "simulation": {
                "budget": round(budget, 2),
                "simulation_status": "NO_ACTION",
                "message": "No recommended intervention was supplied by the Recommendation Engine.",
                "decision": "NO_ACTION",
                "primary_hypothesis": hypothesis,
                "confidence_level": confidence,
                "recommended_intervention": None,
                "impact": {
                    "selected": False,
                    "estimated_cost": 0.0,
                    "estimated_water_savings_litres_per_day": 0.0,
                    "estimated_water_savings_litres_per_year": 0.0,
                    "cost_per_1000_litres_saved": None,
                    "budget_remaining": round(budget, 2),
                },
            },
        }

    cost = safe_float(intervention.get("estimated_cost"))
    daily = safe_float(intervention.get("estimated_water_savings_litres_per_day"))
    remaining = round(budget - cost, 2)

    if cost > budget:
        raise ValueError("Recommendation Engine returned an intervention above the supplied budget.")

    normalized = dict(intervention)
    normalized["estimated_cost"] = round(cost, 2)
    normalized["estimated_water_savings_litres_per_day"] = round(daily, 2)
    normalized["estimated_water_savings_litres_per_year"] = annual_savings(daily)
    normalized["budget_remaining"] = remaining

    return {
        "scenario_id": scenario_id,
        "simulation": {
            "budget": round(budget, 2),
            "simulation_status": "ACTION_FEASIBLE",
            "message": "The evidence-aligned intervention is within the supplied budget and can be simulated.",
            "decision": "RECOMMEND",
            "primary_hypothesis": hypothesis,
            "confidence_level": confidence,
            "recommended_intervention": normalized,
            "impact": {
                "selected": True,
                "estimated_cost": round(cost, 2),
                "estimated_water_savings_litres_per_day": round(daily, 2),
                "estimated_water_savings_litres_per_year": annual_savings(daily),
                "cost_per_1000_litres_saved": cost_per_1000_litres(cost, daily),
                "budget_remaining": remaining,
            },
        },
    }


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] != "--json":
        raise ValueError(
            "This version requires machine-readable input. "
            "Use: python3 intervention_simulator.py --json < recommendation.json"
        )

    raw = sys.stdin.read().strip()
    if not raw:
        raise ValueError("No JSON input supplied on stdin.")

    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Simulator input must be a JSON object.")

    recommendation = payload.get("recommendation")
    if not isinstance(recommendation, dict):
        raise ValueError("Input field 'recommendation' must be an object.")

    budget = safe_float(
        payload.get("budget", recommendation.get("budget", 2000.0)),
        2000.0,
    )
    if budget < 0:
        raise ValueError("Budget cannot be negative.")

    result = simulate(recommendation, budget)
    print("\nWaterTwin Intervention Simulator Result:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
