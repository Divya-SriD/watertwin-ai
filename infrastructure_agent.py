import json
import os
import sys

from google.cloud import bigquery


# ============================================================
# CONFIGURATION
# ============================================================

DATASET = "water_twin"
EVIDENCE_TABLE = "water_evidence_features"


# ============================================================
# GOOGLE CLOUD PROJECT
# ============================================================

def get_project_id():
    """
    Determine the active Google Cloud project.

    No credentials or API keys are stored in source code.
    """

    project_id = os.environ.get(
        "GOOGLE_CLOUD_PROJECT"
    )

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
# INFRASTRUCTURE ANALYSIS
# ============================================================

def get_infrastructure_evidence(
    project_id,
    scenario_id
):
    """
    Analyze infrastructure-related evidence for one
    WaterTwin scenario.

    Responsibility of this agent:

    FLOW
    - actual flow rate
    - expected flow rate
    - flow deviation
    - significant flow observations
    - night-time flow behavior

    PRESSURE
    - actual pressure
    - expected pressure
    - pressure delta
    - significant pressure drops

    METER / DATA QUALITY
    - meter status
    - reading quality
    - data-quality issues
    - poor-quality readings
    - non-OK meter readings

    This agent does NOT determine root cause.

    It does NOT:
    - diagnose a leak
    - diagnose a pressure fault
    - diagnose a sensor anomaly
    - recommend an intervention
    - make a final decision
    """

    client = bigquery.Client(
        project=project_id
    )

    query = f"""
    SELECT
      scenario_id,

      COUNT(*) AS observation_count,

      -- ======================================================
      -- FLOW
      -- ======================================================

      ROUND(
        AVG(flow_rate_lpm),
        2
      ) AS avg_actual_flow_lpm,

      ROUND(
        AVG(expected_flow_lpm),
        2
      ) AS avg_expected_flow_lpm,

      ROUND(
        AVG(flow_deviation_pct),
        2
      ) AS avg_flow_deviation_pct,

      ROUND(
        MAX(flow_deviation_pct),
        2
      ) AS max_flow_deviation_pct,

      ROUND(
        MIN(flow_deviation_pct),
        2
      ) AS min_flow_deviation_pct,

      COUNTIF(significant_flow_increase)
        AS significant_flow_observations,

      ROUND(
        SAFE_DIVIDE(
          COUNTIF(significant_flow_increase),
          COUNT(*)
        ) * 100,
        2
      ) AS flow_anomaly_rate_pct,

      COUNTIF(
        is_night AND significant_flow_increase
      ) AS night_flow_anomaly_hours,

      ROUND(
        AVG(
          IF(
            is_night,
            flow_deviation_pct,
            NULL
          )
        ),
        2
      ) AS avg_night_flow_deviation_pct,

      ROUND(
        MAX(
          IF(
            is_night,
            flow_deviation_pct,
            NULL
          )
        ),
        2
      ) AS max_night_flow_deviation_pct,

      -- ======================================================
      -- PRESSURE
      -- ======================================================

      ROUND(
        AVG(pressure_psi),
        2
      ) AS avg_actual_pressure_psi,

      ROUND(
        AVG(expected_pressure_psi),
        2
      ) AS avg_expected_pressure_psi,

      ROUND(
        AVG(pressure_delta_psi),
        2
      ) AS avg_pressure_delta_psi,

      ROUND(
        MAX(pressure_delta_psi),
        2
      ) AS max_pressure_delta_psi,

      ROUND(
        MIN(pressure_delta_psi),
        2
      ) AS min_pressure_delta_psi,

      COUNTIF(significant_pressure_drop)
        AS significant_pressure_observations,

      ROUND(
        SAFE_DIVIDE(
          COUNTIF(significant_pressure_drop),
          COUNT(*)
        ) * 100,
        2
      ) AS pressure_anomaly_rate_pct,

      -- ======================================================
      -- METER / DATA QUALITY
      -- ======================================================

      COUNTIF(data_quality_issue = TRUE)
        AS data_quality_issue_count,

      COUNTIF(reading_quality = 'POOR')
        AS poor_quality_readings,

      COUNTIF(meter_status != 'OK')
        AS non_ok_meter_readings,

      -- IMPORTANT:
      -- Source data uses GOOD for healthy readings.
      COUNTIF(reading_quality = 'GOOD')
        AS good_quality_readings,

      COUNTIF(meter_status = 'OK')
        AS ok_meter_readings,

      ARRAY_AGG(
        DISTINCT meter_status
        IGNORE NULLS
        LIMIT 10
      ) AS meter_status_values,

      ARRAY_AGG(
        DISTINCT reading_quality
        IGNORE NULLS
        LIMIT 10
      ) AS reading_quality_values

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
            f"No infrastructure evidence found "
            f"for scenario {scenario_id}."
        )

    row = dict(rows[0])

    return row


# ============================================================
# OUTPUT VALIDATION
# ============================================================

def validate_infrastructure_evidence(
    evidence,
    scenario_id
):
    """
    Validate the structured Infrastructure Agent output.
    """

    required_fields = [
        "scenario_id",
        "observation_count",

        # Flow
        "avg_actual_flow_lpm",
        "avg_expected_flow_lpm",
        "avg_flow_deviation_pct",
        "max_flow_deviation_pct",
        "min_flow_deviation_pct",
        "significant_flow_observations",
        "flow_anomaly_rate_pct",
        "night_flow_anomaly_hours",
        "avg_night_flow_deviation_pct",
        "max_night_flow_deviation_pct",

        # Pressure
        "avg_actual_pressure_psi",
        "avg_expected_pressure_psi",
        "avg_pressure_delta_psi",
        "max_pressure_delta_psi",
        "min_pressure_delta_psi",
        "significant_pressure_observations",
        "pressure_anomaly_rate_pct",

        # Data quality
        "data_quality_issue_count",
        "poor_quality_readings",
        "non_ok_meter_readings",
        "good_quality_readings",
        "ok_meter_readings",
        "meter_status_values",
        "reading_quality_values",
    ]

    for field in required_fields:
        if field not in evidence:
            raise RuntimeError(
                f"Infrastructure Agent output is missing "
                f"required field: {field}"
            )

    if evidence["scenario_id"] != scenario_id:
        raise RuntimeError(
            "Infrastructure Agent returned evidence "
            "for the wrong scenario."
        )

    if int(
        evidence["observation_count"] or 0
    ) <= 0:
        raise RuntimeError(
            "Infrastructure Agent returned zero observations."
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
        f"Running WaterTwin Infrastructure Agent "
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
        "Retrieving infrastructure evidence "
        "from BigQuery..."
    )

    evidence = get_infrastructure_evidence(
        project_id,
        scenario_id
    )

    validate_infrastructure_evidence(
        evidence,
        scenario_id
    )

    print(
        "Infrastructure evidence retrieved "
        "successfully."
    )

    print(
        "\nInfrastructure Agent Result:"
    )

    print(
        json.dumps(
            evidence,
            indent=2,
            default=str
        )
    )


if __name__ == "__main__":
    main()