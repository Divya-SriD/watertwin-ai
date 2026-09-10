import json
import sys
from typing import Any, Dict, List, Optional, Tuple

# ============================================================
# WaterTwin AI - Recommendation Engine
# WT-06 + WT-07
#
# Responsibility:
#   Convert the machine-readable Investigation Result and
#   Intervention Agent Result into a deterministic recommendation.
#
# Important architectural rule:
#   This component does NOT know scenario ground truth and does
#   NOT contain scenario-specific answers.
#   It consumes upstream outputs only.
#
# Gemini is not called here. All ranking, budget filtering and
# impact arithmetic remain deterministic.
# ============================================================

HYPOTHESIS_TO_CATEGORY: Dict[str, str] = {
    "LEAK": "LEAK",
    "PRESSURE_ANOMALY": "PRESSURE",
    "OCCUPANCY_DRIVEN": "DEMAND_MANAGEMENT",
    "WEATHER_DRIVEN": "WEATHER_MANAGEMENT",
    "SENSOR_ANOMALY": "DATA_QUALITY",
}

VALID_DECISIONS = {"NO_ACTION", "EXPLAIN", "RECOMMEND", "ABSTAIN"}
VALID_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def annual_water_savings(litres_per_day: float) -> float:
    return round(litres_per_day * 365.0, 2)


def calculate_payback_days(cost: float, litres_per_day: float) -> Optional[float]:
    # No trusted water tariff exists in the MVP, so monetary payback
    # is deliberately not invented.
    return None


def normalize_candidate(item: Dict[str, Any]) -> Dict[str, Any]:
    required = [
        "action_id",
        "action",
        "category",
        "estimated_cost",
        "estimated_water_savings_litres_per_day",
        "operational_impact",
        "feasibility",
    ]
    missing = [field for field in required if field not in item]
    if missing:
        raise ValueError(
            "Intervention candidate is missing required fields: "
            + ", ".join(missing)
        )

    return {
        "action_id": str(item["action_id"]),
        "action": str(item["action"]),
        "category": str(item["category"]),
        "estimated_cost": round(safe_float(item["estimated_cost"]), 2),
        "estimated_water_savings_litres_per_day": round(
            safe_float(item["estimated_water_savings_litres_per_day"]), 2
        ),
        "operational_impact": str(item["operational_impact"]).upper(),
        "feasibility": str(item["feasibility"]).upper(),
        **({"reason": item["reason"]} if "reason" in item else {}),
        **({"priority_basis": item["priority_basis"]} if "priority_basis" in item else {}),
    }


def get_candidates(intervention_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = intervention_result.get("interventions", [])
    if not isinstance(raw, list):
        raise ValueError("Intervention Agent result must contain an interventions list.")
    return [normalize_candidate(item) for item in raw if isinstance(item, dict)]


def split_candidates_by_alignment(
    candidates: List[Dict[str, Any]],
    primary_hypothesis: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    preferred_category = HYPOTHESIS_TO_CATEGORY.get(primary_hypothesis)
    aligned: List[Dict[str, Any]] = []
    secondary: List[Dict[str, Any]] = []

    for candidate in candidates:
        if preferred_category and candidate.get("category") == preferred_category:
            aligned.append(candidate)
        else:
            secondary.append(candidate)

    return aligned, secondary


def rank_intervention(item: Dict[str, Any]) -> tuple:
    impact_rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
    savings = safe_float(item.get("estimated_water_savings_litres_per_day"))
    cost = safe_float(item.get("estimated_cost"))
    impact = impact_rank.get(str(item.get("operational_impact", "HIGH")).upper(), 3)
    return (
        -savings,
        cost,
        impact,
        str(item.get("action_id", "")),
    )


def investigation_fields(investigation: Dict[str, Any]) -> Tuple[str, str, str]:
    decision = str(investigation.get("decision", "")).upper()
    primary_hypothesis = str(investigation.get("primary_hypothesis", "")).upper()
    confidence = str(investigation.get("confidence_level", "")).upper()

    if decision not in VALID_DECISIONS:
        raise ValueError(f"Invalid investigation decision: {decision}")
    if confidence not in VALID_CONFIDENCE:
        raise ValueError(f"Invalid investigation confidence: {confidence}")
    if not primary_hypothesis:
        raise ValueError("Investigation result is missing primary_hypothesis.")

    return decision, primary_hypothesis, confidence


def generate_recommendation(
    investigation: Dict[str, Any],
    intervention_result: Dict[str, Any],
    budget: float,
) -> Dict[str, Any]:
    if budget < 0:
        raise ValueError("Budget cannot be negative.")

    scenario_id = str(
        investigation.get("scenario_id")
        or intervention_result.get("scenario_id")
        or "UNKNOWN"
    )

    if (
        intervention_result.get("scenario_id")
        and str(intervention_result["scenario_id"]) != scenario_id
    ):
        raise ValueError("Investigation and Intervention results refer to different scenarios.")

    decision, primary_hypothesis, confidence = investigation_fields(investigation)
    candidates = get_candidates(intervention_result)

    # Safety gate 1: investigation abstention is authoritative.
    if decision == "ABSTAIN":
        return {
            "scenario_id": scenario_id,
            "status": "ABSTAIN",
            "decision": "ABSTAIN",
            "primary_hypothesis": primary_hypothesis,
            "confidence_level": confidence,
            "reason": (
                "Investigation evidence is insufficient or conflicting. "
                "WaterTwin will not force a physical recommendation."
            ),
            "budget": round(budget, 2),
            "recommended_intervention": None,
            "alternatives": candidates,
            "decision_basis": "Abstention is preserved from the Investigation Engine; budget cannot override an evidence-safety gate.",
        }

    # Safety gate 2: normal operation requires no action.
    if decision == "NO_ACTION":
        return {
            "scenario_id": scenario_id,
            "status": "NO_ACTION",
            "decision": "NO_ACTION",
            "primary_hypothesis": primary_hypothesis,
            "confidence_level": confidence,
            "reason": "Evidence is consistent with normal operation. No intervention is required.",
            "budget": round(budget, 2),
            "recommended_intervention": None,
            "alternatives": [],
            "decision_basis": "Investigation Engine classified the evidence as normal operation; no intervention is selected.",
        }

    aligned_candidates, secondary_candidates = split_candidates_by_alignment(
        candidates,
        primary_hypothesis,
    )

    # If the investigation is uncertain/ambiguous and has no aligned category,
    # do not manufacture an alignment. For EXPLAIN, preserve the explanation
    # state instead of silently converting it into a recommendation.
    if decision == "EXPLAIN":
        return {
            "scenario_id": scenario_id,
            "status": "EXPLAIN",
            "decision": "EXPLAIN",
            "primary_hypothesis": primary_hypothesis,
            "confidence_level": confidence,
            "reason": "Investigation evidence supports an explanation but does not request a physical intervention.",
            "budget": round(budget, 2),
            "recommended_intervention": None,
            "alternatives": candidates,
            "decision_basis": "The Investigation Engine returned EXPLAIN; Recommendation Engine preserves that decision rather than upgrading it to RECOMMEND.",
        }

    # RECOMMEND: only evidence-aligned candidates can become the primary action.
    eligible_candidates = aligned_candidates if aligned_candidates else []

    feasible = [
        item for item in eligible_candidates
        if safe_float(item.get("estimated_cost")) <= budget
        and str(item.get("feasibility", "HIGH")).upper() != "BLOCKED"
    ]
    infeasible = [
        item for item in eligible_candidates
        if safe_float(item.get("estimated_cost")) > budget
    ]
    feasible.sort(key=rank_intervention)

    if not feasible:
        minimum_cost = None
        if eligible_candidates:
            minimum_cost = min(
                safe_float(item.get("estimated_cost"))
                for item in eligible_candidates
            )

        return {
            "scenario_id": scenario_id,
            "status": "BUDGET_CONSTRAINED",
            "decision": "NO_ACTION",
            "primary_hypothesis": primary_hypothesis,
            "confidence_level": confidence,
            "reason": (
                "Investigation evidence supports an evidence-aligned intervention, "
                "but no such intervention fits within the supplied budget."
            ),
            "budget": round(budget, 2),
            "minimum_intervention_cost": minimum_cost,
            "recommended_intervention": None,
            "alternatives": secondary_candidates,
            "infeasible_interventions": infeasible,
            "decision_basis": (
                "The primary intervention category was selected from the Investigation "
                "Result, then budget feasibility was applied deterministically."
            ),
        }

    selected = feasible[0]
    selected_cost = safe_float(selected.get("estimated_cost"))
    daily_savings = safe_float(selected.get("estimated_water_savings_litres_per_day"))

    selected_intervention = {
        "action_id": selected["action_id"],
        "action": selected["action"],
        "category": selected["category"],
        "estimated_cost": selected_cost,
        "estimated_water_savings_litres_per_day": daily_savings,
        "estimated_water_savings_litres_per_year": annual_water_savings(daily_savings),
        "operational_impact": selected["operational_impact"],
        "feasibility": selected["feasibility"],
        "budget_remaining": round(budget - selected_cost, 2),
        "payback_days": calculate_payback_days(selected_cost, daily_savings),
    }

    return {
        "scenario_id": scenario_id,
        "status": "RECOMMEND",
        "decision": "RECOMMEND",
        "primary_hypothesis": primary_hypothesis,
        "confidence_level": confidence,
        "budget": round(budget, 2),
        "recommended_intervention": selected_intervention,
        "alternatives_within_budget": feasible[1:],
        "secondary_context_interventions": secondary_candidates,
        "budget_excluded_interventions": infeasible,
        "decision_basis": (
            "Selected deterministically from an evidence-aligned intervention category "
            "matching the primary investigation hypothesis. Budget feasibility is applied "
            "after evidence alignment so unrelated interventions cannot override the primary "
            "finding merely because they have higher estimated savings."
        ),
    }


def load_input() -> Dict[str, Any]:
    if len(sys.argv) >= 2 and sys.argv[1] == "--json":
        raw = sys.stdin.read().strip()
        if not raw:
            raise ValueError("No JSON input supplied on stdin.")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Recommendation input must be a JSON object.")
        return payload

    raise ValueError(
        "This version requires machine-readable input. "
        "Use: python3 recommendation_engine.py --json < payload.json"
    )


def main() -> None:
    payload = load_input()
    investigation = payload.get("investigation")
    intervention_result = payload.get("intervention")
    budget = safe_float(payload.get("budget"), 20000.0)

    if not isinstance(investigation, dict):
        raise ValueError("Input field 'investigation' must be an object.")
    if not isinstance(intervention_result, dict):
        raise ValueError("Input field 'intervention' must be an object.")

    result = generate_recommendation(
        investigation,
        intervention_result,
        budget,
    )

    print("\nWaterTwin Recommendation Engine Result:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
