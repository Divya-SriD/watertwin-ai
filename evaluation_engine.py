#!/usr/bin/env python3
"""WaterTwin AI deterministic evaluation engine.

Compares saved WaterTwin orchestration results with scenario ground truth in
BigQuery. This is an evaluation tool, not a runtime agent, and it never calls
Gemini.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.cloud import bigquery


EXPECTED_SCENARIOS = {"S1", "S2", "S3", "S4", "S5", "S6", "S7"}


def pct(numerator: int, denominator: int) -> Optional[float]:
    if denominator == 0:
        return None
    return round((numerator / denominator) * 100.0, 2)


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return data


def load_ground_truth(client: bigquery.Client, project: Optional[str], dataset: str) -> Dict[str, Dict[str, Any]]:
    dataset_ref = f"{project}.{dataset}" if project else f"{client.project}.{dataset}"
    query = f"""
        SELECT
          scenario_id,
          scenario_name,
          ground_truth_anomaly,
          ground_truth_cause,
          expected_decision,
          primary_evidence,
          evidence_category
        FROM `{dataset_ref}.scenario_ground_truth`
        ORDER BY scenario_id
    """
    rows = client.query(query).result()
    result = {}
    for row in rows:
        result[row["scenario_id"]] = dict(row.items())
    return result


def get_final_decision(result: Dict[str, Any]) -> Dict[str, Any]:
    decision = result.get("final_decision")
    if not isinstance(decision, dict):
        raise ValueError(f"{result.get('scenario_id', '?')}: final_decision is missing or invalid")
    return decision


def get_consumption_agent(result: Dict[str, Any]) -> Dict[str, Any]:
    agents = result.get("agents")
    if not isinstance(agents, dict):
        raise ValueError(f"{result.get('scenario_id', '?')}: agents is missing or invalid")
    consumption = agents.get("consumption_agent")
    if not isinstance(consumption, dict):
        raise ValueError(f"{result.get('scenario_id', '?')}: consumption_agent is missing or invalid")
    return consumption


def normalize_intervention_category(category: Any) -> Optional[str]:
    if category is None:
        return None
    value = str(category).upper().strip()
    aliases = {
        "PRESSURE": "PRESSURE_ANOMALY",
        "PRESSURE_ISSUE": "PRESSURE_ANOMALY",
        "OCCUPANCY": "OCCUPANCY_DRIVEN",
        "WEATHER": "WEATHER_DRIVEN",
        "SENSOR": "SENSOR_ANOMALY",
    }
    return aliases.get(value, value)


def evaluate_scenario(result: Dict[str, Any], truth: Dict[str, Any]) -> Dict[str, Any]:
    scenario_id = result.get("scenario_id")
    final = get_final_decision(result)
    consumption = get_consumption_agent(result)

    predicted_decision = final.get("decision")
    predicted_cause = final.get("primary_hypothesis")
    confidence = final.get("confidence_level")
    expected_decision = truth.get("expected_decision")
    ground_truth_cause = truth.get("ground_truth_cause")
    ground_truth_anomaly = bool(truth.get("ground_truth_anomaly"))

    # Deterministic anomaly signal from the Consumption Agent. We intentionally
    # do not use ground truth to decide whether WaterTwin detected an anomaly.
    significant_obs = int(consumption.get("significant_consumption_observations") or 0)
    anomaly_rate = float(consumption.get("consumption_anomaly_rate_pct") or 0.0)
    predicted_anomaly = significant_obs > 0 or anomaly_rate > 0.0

    anomaly_correct = predicted_anomaly == ground_truth_anomaly
    root_cause_correct = predicted_cause == ground_truth_cause
    decision_correct = predicted_decision == expected_decision

    abstention_expected = expected_decision == "ABSTAIN"
    abstention_correct = predicted_decision == "ABSTAIN" if abstention_expected else None
    unsafe_abstention_case = abstention_expected and predicted_decision != "ABSTAIN"

    intervention = final.get("recommended_intervention")
    if not isinstance(intervention, dict):
        intervention = None

    action_id = intervention.get("action_id") if intervention else None
    action_category = normalize_intervention_category(intervention.get("category")) if intervention else None
    selected = bool((final.get("impact") or {}).get("selected", False))

    if expected_decision == "RECOMMEND":
        intervention_quality = bool(
            predicted_decision == "RECOMMEND"
            and intervention
            and action_id
            and action_category == ground_truth_cause
            and selected
        )
        intervention_quality_status = "CORRECT" if intervention_quality else "INCORRECT"
    else:
        intervention_quality = None
        intervention_quality_status = "NOT_APPLICABLE"

    impact = final.get("impact") or {}
    estimated_cost = float(impact.get("estimated_cost") or 0.0)
    savings_day = float(impact.get("estimated_water_savings_litres_per_day") or 0.0)
    savings_year = float(impact.get("estimated_water_savings_litres_per_year") or 0.0)

    return {
        "scenario_id": scenario_id,
        "scenario_name": truth.get("scenario_name"),
        "ground_truth": {
            "anomaly": ground_truth_anomaly,
            "cause": ground_truth_cause,
            "expected_decision": expected_decision,
        },
        "prediction": {
            "anomaly": predicted_anomaly,
            "cause": predicted_cause,
            "decision": predicted_decision,
            "confidence": confidence,
        },
        "metrics": {
            "anomaly_correct": anomaly_correct,
            "root_cause_correct": root_cause_correct,
            "decision_correct": decision_correct,
            "abstention_expected": abstention_expected,
            "abstention_correct": abstention_correct,
            "unsafe_abstention_case": unsafe_abstention_case,
            "intervention_quality": intervention_quality,
            "intervention_quality_status": intervention_quality_status,
        },
        "evidence": {
            "significant_consumption_observations": significant_obs,
            "consumption_anomaly_rate_pct": anomaly_rate,
        },
        "intervention": {
            "action_id": action_id,
            "category": action_category,
            "selected": selected,
            "estimated_cost": round(estimated_cost, 2),
            "estimated_water_savings_litres_per_day": round(savings_day, 2),
            "estimated_water_savings_litres_per_year": round(savings_year, 2),
        },
        "orchestration_status": result.get("orchestration_status"),
    }


def summarize(evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(evaluations)
    anomaly_correct = sum(x["metrics"]["anomaly_correct"] for x in evaluations)
    root_correct = sum(x["metrics"]["root_cause_correct"] for x in evaluations)
    decision_correct = sum(x["metrics"]["decision_correct"] for x in evaluations)

    normal_cases = [x for x in evaluations if not x["ground_truth"]["anomaly"]]
    anomaly_false_positives = sum(x["prediction"]["anomaly"] for x in normal_cases)
    decision_false_positives = sum(
        x["prediction"]["decision"] != "NO_ACTION" for x in normal_cases
    )

    abstention_cases = [x for x in evaluations if x["metrics"]["abstention_expected"]]
    correct_abstentions = sum(x["metrics"]["abstention_correct"] is True for x in abstention_cases)
    unsafe_abstentions = sum(x["metrics"]["unsafe_abstention_case"] for x in abstention_cases)

    recommendation_cases = [x for x in evaluations if x["ground_truth"]["expected_decision"] == "RECOMMEND"]
    correct_interventions = sum(x["metrics"]["intervention_quality"] is True for x in recommendation_cases)

    selected_interventions = [x for x in evaluations if x["intervention"]["selected"]]
    total_cost = sum(x["intervention"]["estimated_cost"] for x in selected_interventions)
    total_daily_savings = sum(x["intervention"]["estimated_water_savings_litres_per_day"] for x in selected_interventions)
    total_annual_savings = sum(x["intervention"]["estimated_water_savings_litres_per_year"] for x in selected_interventions)

    complete_status = all(x["orchestration_status"] == "SUCCESS" for x in evaluations)
    supplied_ids = {x["scenario_id"] for x in evaluations}

    return {
        "scenario_count": total,
        "scenario_ids": sorted(supplied_ids),
        "complete_7_scenario_coverage": supplied_ids == EXPECTED_SCENARIOS,
        "missing_scenarios": sorted(EXPECTED_SCENARIOS - supplied_ids),
        "all_orchestrations_successful": complete_status,
        "anomaly_detection": {
            "correct": anomaly_correct,
            "total": total,
            "accuracy_pct": pct(anomaly_correct, total),
            "false_positive_rate_pct": pct(anomaly_false_positives, len(normal_cases)),
            "normal_cases": len(normal_cases),
            "false_positives": anomaly_false_positives,
            "note": "False-positive rate is undefined when no ground-truth normal scenario is supplied.",
        },
        "decision_accuracy": {
            "correct": decision_correct,
            "total": total,
            "accuracy_pct": pct(decision_correct, total),
        },
        "root_cause_accuracy": {
            "correct": root_correct,
            "total": total,
            "accuracy_pct": pct(root_correct, total),
        },
        "abstention_behavior": {
            "expected_abstention_cases": len(abstention_cases),
            "correct_abstentions": correct_abstentions,
            "abstention_accuracy_pct": pct(correct_abstentions, len(abstention_cases)),
            "unsafe_non_abstentions": unsafe_abstentions,
        },
        "normal_case_safety": {
            "normal_cases": len(normal_cases),
            "decision_false_positive_rate_pct": pct(decision_false_positives, len(normal_cases)),
            "normal_cases_with_non_no_action_decision": decision_false_positives,
        },
        "intervention_quality": {
            "actionable_recommendation_cases": len(recommendation_cases),
            "correct_interventions": correct_interventions,
            "quality_pct": pct(correct_interventions, len(recommendation_cases)),
        },
        "selected_intervention_impact": {
            "selected_intervention_count": len(selected_interventions),
            "estimated_total_cost": round(total_cost, 2),
            "estimated_total_water_savings_litres_per_day": round(total_daily_savings, 2),
            "estimated_total_water_savings_litres_per_year": round(total_annual_savings, 2),
            "note": "Impact is the sum of deterministic simulator outputs from selected interventions; it is an estimate, not measured savings.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate WaterTwin saved orchestration results against BigQuery ground truth.")
    parser.add_argument("results", nargs="+", help="Saved WaterTwin result JSON files")
    parser.add_argument("--dataset", default="water_twin", help="BigQuery dataset (default: water_twin)")
    parser.add_argument("--project", default=None, help="Google Cloud project ID (default: BigQuery client project)")
    parser.add_argument("--output", default=None, help="Optional output JSON path")
    parser.add_argument("--require-all", action="store_true", help="Fail unless S1-S7 are all supplied")
    args = parser.parse_args()

    try:
        results = [load_json(path) for path in args.results]
        ids = [r.get("scenario_id") for r in results]
        if any(not sid for sid in ids):
            raise ValueError("Every result JSON must contain scenario_id")
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate scenario_id found in supplied result files")

        client = bigquery.Client(project=args.project) if args.project else bigquery.Client()
        truth = load_ground_truth(client, args.project, args.dataset)

        missing_truth = sorted(set(ids) - set(truth))
        if missing_truth:
            raise ValueError(f"No ground truth found in BigQuery for: {', '.join(missing_truth)}")

        evaluations = [evaluate_scenario(result, truth[result["scenario_id"]]) for result in results]
        summary = summarize(evaluations)

        output = {
            "evaluation_version": "WT-16-v1",
            "project_id": args.project or client.project,
            "dataset": args.dataset,
            "source_files": [str(Path(p)) for p in args.results],
            "scenarios": evaluations,
            "summary": summary,
        }

        text = json.dumps(output, indent=2, sort_keys=False)
        print(text)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(text + "\n")
            print(f"\nSaved evaluation report: {args.output}")

        if args.require_all and not summary["complete_7_scenario_coverage"]:
            print("ERROR: --require-all was specified but S1-S7 are not all present.", file=sys.stderr)
            return 2

        return 0

    except Exception as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
