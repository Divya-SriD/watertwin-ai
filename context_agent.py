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
# CONTEXT ANALYSIS
# ============================================================

def get_context_evidence(
    project_id,
    scenario_id
):
    """
    Analyze contextual signals for one WaterTwin scenario.

    Responsibility of this agent:

    OCCUPANCY
    - actual occupancy
    - expected occupancy
    - occupancy deviation
    - significant occupancy increases

    WEATHER
    - actual temperature
    - expected temperature
    - temperature deviation
    - significant temperature increases
    - rainfall
    - weather condition

    This agent does NOT determine root cause.

    It does NOT:
    - diagnose leaks
    - analyze pressure
    - analyze flow
    - diagnose sensor faults
    - recommend interventions
    - make final decisions
    """

    client = bigquery.Client(
        project=project_id
    )

    query = f"""
    SELECT
      scenario_id,

      COUNT(*) AS observation_count,

      -- ======================================================
      -- OCCUPANCY
      -- ======================================================

      ROUND(
        AVG(occupancy_count),
        2
      ) AS avg_actual_occupancy,

      ROUND(
        AVG(expected_occupancy),
        2
      ) AS avg_expected_occupancy,

      ROUND(
        AVG(occupancy_deviation_pct),
        2
      ) AS avg_occupancy_deviation_pct,

      ROUND(
        MAX(occupancy_deviation_pct),
        2
      ) AS max_occupancy_deviation_pct,

      ROUND(
        MIN(occupancy_deviation_pct),
        2
      ) AS min_occupancy_deviation_pct,

      COUNTIF(significant_occupancy_increase)
        AS significant_occupancy_observations,

      ROUND(
        SAFE_DIVIDE(
          COUNTIF(significant_occupancy_increase),
          COUNT(*)
        ) * 100,
        2
      ) AS occupancy_anomaly_rate_pct,

      -- ======================================================
      -- WEATHER / TEMPERATURE
      -- ======================================================

      ROUND(
        AVG(temperature_c),
        2
      ) AS avg_temperature_c,

      ROUND(
        AVG(expected_temperature),
        2
      ) AS avg_expected_temperature_c,

      ROUND(
        AVG(temperature_delta_c),
        2
      ) AS avg_temperature_delta_c,

      ROUND(
        MAX(temperature_delta_c),
        2
      ) AS max_temperature_delta_c,

      ROUND(
        MIN(temperature_delta_c),
        2
      ) AS min_temperature_delta_c,

      COUNTIF(significant_temperature_increase)
        AS significant_temperature_observations,

      ROUND(
        SAFE_DIVIDE(
          COUNTIF(significant_temperature_increase),
          COUNT(*)
        ) * 100,
        2
      ) AS temperature_anomaly_rate_pct,

      -- ======================================================
      -- RAINFALL / WEATHER CONDITION
      -- ======================================================

      ROUND(
        AVG(rainfall_mm),
        2
      ) AS avg_rainfall_mm,

      ROUND(
        MAX(rainfall_mm),
        2
      ) AS max_rainfall_mm,

      COUNTIF(
        rainfall_mm > 0
      ) AS rainfall_observations,

      COUNTIF(
        weather_condition IS NOT NULL
      ) AS weather_observations,

      ARRAY_AGG(
        DISTINCT weather_condition
        IGNORE NULLS
        LIMIT 10
      ) AS weather_conditions

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
            f"No context evidence found for "
            f"scenario {scenario_id}."
        )

    row = dict(rows[0])

    return row


# ============================================================
# OUTPUT VALIDATION
# ============================================================

def validate_context_evidence(
    evidence,
    scenario_id
):
    """
    Validate the structured Context Agent output.
    """

    required_fields = [
        "scenario_id",
        "observation_count",

        # Occupancy
        "avg_actual_occupancy",
        "avg_expected_occupancy",
        "avg_occupancy_deviation_pct",
        "max_occupancy_deviation_pct",
        "min_occupancy_deviation_pct",
        "significant_occupancy_observations",
        "occupancy_anomaly_rate_pct",

        # Temperature
        "avg_temperature_c",
        "avg_expected_temperature_c",
        "avg_temperature_delta_c",
        "max_temperature_delta_c",
        "min_temperature_delta_c",
        "significant_temperature_observations",
        "temperature_anomaly_rate_pct",

        # Weather
        "avg_rainfall_mm",
        "max_rainfall_mm",
        "rainfall_observations",
        "weather_observations",
        "weather_conditions",
    ]

    for field in required_fields:
        if field not in evidence:
            raise RuntimeError(
                f"Context Agent output is missing "
                f"required field: {field}"
            )

    if evidence["scenario_id"] != scenario_id:
        raise RuntimeError(
            "Context Agent returned evidence "
            "for the wrong scenario."
        )

    if int(
        evidence["observation_count"] or 0
    ) <= 0:
        raise RuntimeError(
            "Context Agent returned zero observations."
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
        f"Running WaterTwin Context Agent "
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
        "Retrieving context evidence "
        "from BigQuery..."
    )

    evidence = get_context_evidence(
        project_id,
        scenario_id
    )

    validate_context_evidence(
        evidence,
        scenario_id
    )

    print(
        "Context evidence retrieved "
        "successfully."
    )

    print(
        "\nContext Agent Result:"
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