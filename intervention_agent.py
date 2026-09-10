import json
import os
import sys

from google.cloud import bigquery


# ============================================================
# WATER TWIN - INTERVENTION AGENT
# ============================================================
#
# Responsibility:
#   Convert evidence-backed findings into candidate
#   interventions with deterministic impact estimates.
#
# The Intervention Agent does NOT:
#   - detect anomalies
#   - determine root cause
#   - invent measurements
#   - make Gemini-based decisions
#
# It consumes deterministic evidence from BigQuery and
# produces candidate actions.
# ============================================================


DATASET = "water_twin"
EVIDENCE_TABLE = "water_evidence_features"


# ============================================================
# GOOGLE CLOUD PROJECT
# ============================================================

def get_project_id():
    """
    Determine the active Google Cloud project.
    """

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")

    if project_id:
        return project_id

    try:
        import google.auth

        _, project_id = google.auth.default()

        if project_id:
            return project_id

    except Exception as exc:
        raise RuntimeError(
            "Unable to determine Google Cloud project."
        ) from exc

    raise RuntimeError(
        "Google Cloud project could not be determined."
    )


# ============================================================
# RETRIEVE EVIDENCE
# ============================================================

def get_evidence(project_id, scenario_id):
    """
    Retrieve deterministic evidence required for
    intervention generation.
    """

    client = bigquery.Client(project=project_id)

    query = f"""
    SELECT

      scenario_id,

      COUNT(*) AS observation_count,

      -- ====================================================
      -- CONSUMPTION
      -- ====================================================

      AVG(actual_consumption_litres)
        AS avg_actual_consumption_litres,

      AVG(expected_consumption_litres)
        AS avg_expected_consumption_litres,

      AVG(consumption_deviation_pct)
        AS avg_consumption_deviation_pct,

      MAX(consumption_deviation_pct)
        AS max_consumption_deviation_pct,

      COUNTIF(consumption_anomaly)
        AS significant_consumption_observations,

      -- ====================================================
      -- OCCUPANCY
      -- ====================================================

      MAX(occupancy_deviation_pct)
        AS max_occupancy_deviation_pct,

      COUNTIF(significant_occupancy_increase)
        AS significant_occupancy_observations,

      -- ====================================================
      -- WEATHER
      -- ====================================================

      MAX(temperature_delta_c)
        AS max_temperature_delta_c,

      COUNTIF(significant_temperature_increase)
        AS significant_temperature_observations,

      -- ====================================================
      -- FLOW
      -- ====================================================

      MAX(flow_deviation_pct)
        AS max_flow_deviation_pct,

      COUNTIF(significant_flow_increase)
        AS significant_flow_observations,

      COUNTIF(
        is_night
        AND significant_flow_increase
      ) AS night_flow_anomaly_hours,

      -- ====================================================
      -- PRESSURE
      -- ====================================================

      MIN(pressure_delta_psi)
        AS min_pressure_delta_psi,

      COUNTIF(significant_pressure_drop)
        AS significant_pressure_observations,

      -- ====================================================
      -- DATA QUALITY
      -- ====================================================

      COUNTIF(data_quality_issue = TRUE)
        AS data_quality_issue_count,

      COUNTIF(reading_quality = 'POOR')
        AS poor_quality_readings,

      COUNTIF(meter_status != 'OK')
        AS non_ok_meter_readings

    FROM
      `{project_id}.{DATASET}.{EVIDENCE_TABLE}`

    WHERE
      scenario_id = @scenario_id

    GROUP BY
      scenario_id
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "scenario_id",
                "STRING",
                scenario_id
            )
        ]
    )

    rows = list(
        client.query(
            query,
            job_config=job_config
        ).result()
    )

    if not rows:
        raise ValueError(
            f"No evidence found for scenario {scenario_id}."
        )

    return dict(rows[0])


# ============================================================
# HELPER
# ============================================================

def safe_float(value):
    if value is None:
        return 0.0

    return float(value)


def safe_int(value):
    if value is None:
        return 0

    return int(value)


# ============================================================
# INTERVENTION GENERATION
# ============================================================

def generate_interventions(evidence):
    """
    Generate deterministic intervention candidates.

    Important:
      These are candidate interventions.

      Final prioritization will be handled later by the
      Recommendation Logic and Intervention Simulator.
    """

    scenario_id = evidence["scenario_id"]

    interventions = []

    consumption_anomalies = safe_int(
        evidence[
            "significant_consumption_observations"
        ]
    )

    flow_anomalies = safe_int(
        evidence[
            "significant_flow_observations"
        ]
    )

    night_flow_hours = safe_int(
        evidence[
            "night_flow_anomaly_hours"
        ]
    )

    pressure_anomalies = safe_int(
        evidence[
            "significant_pressure_observations"
        ]
    )

    occupancy_anomalies = safe_int(
        evidence[
            "significant_occupancy_observations"
        ]
    )

    temperature_anomalies = safe_int(
        evidence[
            "significant_temperature_observations"
        ]
    )

    data_quality = (
        safe_int(
            evidence[
                "data_quality_issue_count"
            ]
        )
        + safe_int(
            evidence[
                "poor_quality_readings"
            ]
        )
        + safe_int(
            evidence[
                "non_ok_meter_readings"
            ]
        )
    )

    # ========================================================
    # DATA QUALITY INTERVENTION
    # ========================================================

    if data_quality > 0:

        interventions.append({
            "action_id": "I_DATA_QUALITY_CHECK",
            "action": (
                "Validate meter telemetry and "
                "calibration"
            ),
            "category": "DATA_QUALITY",
            "reason": (
                "Measurement quality is degraded, "
                "so physical intervention should not "
                "be prioritized until telemetry is "
                "validated."
            ),
            "estimated_cost": 4500,
            "estimated_water_savings_litres_per_day": 0,
            "operational_impact": "LOW",
            "feasibility": "HIGH",
            "priority_basis": (
                "Required before trusting physical "
                "water-loss estimates."
            )
        })

        return interventions

    # ========================================================
    # LEAK / CONTINUOUS FLOW
    # ========================================================

    if (
        night_flow_hours > 0
        and flow_anomalies > 0
    ):

        max_flow_deviation = safe_float(
            evidence[
                "max_flow_deviation_pct"
            ]
        )

        avg_expected = safe_float(
            evidence[
                "avg_expected_consumption_litres"
            ]
        )

        # Conservative deterministic estimate:
        #
        # expected daily avoidable water loss is estimated
        # from the observed night-flow anomaly magnitude.
        #
        # This is deliberately an estimate rather than a
        # claim of physically measured leakage.

        estimated_daily_loss = (
            avg_expected
            * min(max_flow_deviation / 100.0, 1.0)
            * 0.10
        )

        interventions.append({
            "action_id": "I_LEAK_INSPECTION",
            "action": (
                "Inspect and isolate the affected "
                "water zone for continuous flow"
            ),
            "category": "LEAK",
            "reason": (
                "Persistent night-time flow anomalies "
                "indicate potential continuous "
                "unintended water loss."
            ),
            "estimated_cost": 4000,
            "estimated_water_savings_litres_per_day": round(
                estimated_daily_loss,
                2
            ),
            "operational_impact": "MEDIUM",
            "feasibility": "HIGH",
            "priority_basis": (
                "Targets persistent off-peak flow "
                "that is inconsistent with normal "
                "demand."
            )
        })

    # ========================================================
    # PRESSURE ANOMALY
    # ========================================================

    if pressure_anomalies > 0:

        min_pressure = safe_float(
            evidence[
                "min_pressure_delta_psi"
            ]
        )

        interventions.append({
            "action_id": "I_PRESSURE_DIAGNOSTIC",
            "action": (
                "Inspect upstream supply pressure, "
                "pump operation and PRV settings"
            ),
            "category": "PRESSURE",
            "reason": (
                "Persistent pressure deviation "
                "requires infrastructure diagnostics "
                "before physical remediation."
            ),
            "estimated_cost": 2500,
            "estimated_water_savings_litres_per_day": 0,
            "operational_impact": "LOW",
            "feasibility": "HIGH",
            "priority_basis": (
                f"Minimum pressure deviation is "
                f"{min_pressure:.2f} psi."
            )
        })

    # ========================================================
    # OCCUPANCY-DRIVEN DEMAND
    # ========================================================

    if occupancy_anomalies > 0:

        interventions.append({
            "action_id": "I_DEMAND_MANAGEMENT",
            "action": (
                "Review high-occupancy water demand "
                "and implement demand-management measures"
            ),
            "category": "DEMAND_MANAGEMENT",
            "reason": (
                "Higher occupancy can legitimately "
                "increase water consumption."
            ),
            "estimated_cost": 2000,
            "estimated_water_savings_litres_per_day": round(
                safe_float(
                    evidence[
                        "avg_expected_consumption_litres"
                    ]
                )
                * 0.03,
                2
            ),
            "operational_impact": "LOW",
            "feasibility": "HIGH",
            "priority_basis": (
                "Targets consumption efficiency during "
                "elevated occupancy periods."
            )
        })

    # ========================================================
    # WEATHER-DRIVEN DEMAND
    # ========================================================

    if temperature_anomalies > 0:

        interventions.append({
            "action_id": "I_WEATHER_DEMAND_CONTROL",
            "action": (
                "Review irrigation and cooling-system "
                "water schedules"
            ),
            "category": "WEATHER_MANAGEMENT",
            "reason": (
                "Elevated temperature can increase "
                "water demand through irrigation or "
                "cooling operations."
            ),
            "estimated_cost": 3500,
            "estimated_water_savings_litres_per_day": round(
                safe_float(
                    evidence[
                        "avg_expected_consumption_litres"
                    ]
                )
                * 0.02,
                2
            ),
            "operational_impact": "LOW",
            "feasibility": "HIGH",
            "priority_basis": (
                "Targets controllable weather-driven "
                "water demand."
            )
        })

    # ========================================================
    # NO INTERVENTION
    # ========================================================

    if not interventions:

        interventions.append({
            "action_id": "I_NO_ACTION",
            "action": (
                "Continue normal monitoring"
            ),
            "category": "MONITORING",
            "reason": (
                "No material intervention trigger "
                "was identified in the available evidence."
            ),
            "estimated_cost": 0,
            "estimated_water_savings_litres_per_day": 0,
            "operational_impact": "NONE",
            "feasibility": "HIGH",
            "priority_basis": (
                "Evidence does not justify physical "
                "intervention."
            )
        })

    return interventions


# ============================================================
# VALIDATION
# ============================================================

def validate_result(result, scenario_id):

    if result.get("scenario_id") != scenario_id:
        raise RuntimeError(
            "Intervention result contains the wrong scenario."
        )

    if "interventions" not in result:
        raise RuntimeError(
            "Intervention result is missing interventions."
        )

    if not isinstance(
        result["interventions"],
        list
    ):
        raise RuntimeError(
            "Interventions must be a list."
        )

    required_fields = [
        "action_id",
        "action",
        "category",
        "reason",
        "estimated_cost",
        "estimated_water_savings_litres_per_day",
        "operational_impact",
        "feasibility",
        "priority_basis"
    ]

    for intervention in result["interventions"]:

        for field in required_fields:

            if field not in intervention:
                raise RuntimeError(
                    "Intervention is missing field: "
                    f"{field}"
                )

        if intervention[
            "estimated_cost"
        ] < 0:

            raise RuntimeError(
                "Intervention cost cannot be negative."
            )

        if intervention[
            "estimated_water_savings_litres_per_day"
        ] < 0:

            raise RuntimeError(
                "Estimated water savings cannot "
                "be negative."
            )


# ============================================================
# MAIN
# ============================================================

def main():

    scenario_id = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "S2"
    )

    print(
        f"Running WaterTwin Intervention Agent "
        f"for scenario: {scenario_id}"
    )

    print(
        "Determining Google Cloud project..."
    )

    project_id = get_project_id()

    print(
        f"Using Google Cloud project: "
        f"{project_id}"
    )

    print(
        "Retrieving intervention evidence "
        "from BigQuery..."
    )

    evidence = get_evidence(
        project_id,
        scenario_id
    )

    print(
        "BigQuery evidence retrieved successfully."
    )

    print(
        "Generating deterministic intervention "
        "candidates..."
    )

    interventions = generate_interventions(
        evidence
    )

    result = {
        "scenario_id": scenario_id,

        "evidence_summary": {
            "consumption_anomalies": safe_int(
                evidence[
                    "significant_consumption_observations"
                ]
            ),
            "flow_anomalies": safe_int(
                evidence[
                    "significant_flow_observations"
                ]
            ),
            "night_flow_anomaly_hours": safe_int(
                evidence[
                    "night_flow_anomaly_hours"
                ]
            ),
            "pressure_anomalies": safe_int(
                evidence[
                    "significant_pressure_observations"
                ]
            ),
            "occupancy_anomalies": safe_int(
                evidence[
                    "significant_occupancy_observations"
                ]
            ),
            "temperature_anomalies": safe_int(
                evidence[
                    "significant_temperature_observations"
                ]
            ),
            "data_quality_issues": safe_int(
                evidence[
                    "data_quality_issue_count"
                ]
            )
        },

        "interventions": interventions
    }

    validate_result(
        result,
        scenario_id
    )

    print(
        "\nWaterTwin Intervention Agent Result:"
    )

    print(
        json.dumps(
            result,
            indent=2,
            default=str
        )
    )


if __name__ == "__main__":
    main()