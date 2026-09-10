import json
import os
import sys

from google.cloud import bigquery


# ============================================================
# CONFIGURATION
# ============================================================

DATASET = "water_twin"
EVIDENCE_TABLE = "water_evidence_features"

# Keep the visualization payload intentionally small.
# The Consumption Agent still analyzes the complete scenario;
# this is only the evidence subset exposed for the UI.
EVIDENCE_TIMESERIES_LIMIT = 24


# ============================================================
# GOOGLE CLOUD PROJECT
# ============================================================

def get_project_id():
    """
    Determine the active Google Cloud project.

    The project ID is obtained from the runtime environment or
    Application Default Credentials.

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
# CONSUMPTION ANALYSIS
# ============================================================

def get_consumption_evidence(
    project_id,
    scenario_id
):
    """
    Analyze consumption behavior for one WaterTwin scenario.

    Responsibility of this agent:

    - actual consumption
    - expected consumption baseline
    - consumption deviation
    - consumption anomaly count
    - consumption anomaly rate
    - maximum deviation
    - average deviation
    - small deterministic evidence time-series for UI

    This agent does NOT investigate:

    - weather
    - occupancy
    - pressure
    - infrastructure faults
    - sensor faults
    - root causes
    - interventions
    - recommendations

    Those responsibilities belong to other WaterTwin agents.
    """

    client = bigquery.Client(
        project=project_id
    )

    # --------------------------------------------------------
    # Summary analytics
    # --------------------------------------------------------

    query = f"""
    SELECT
      scenario_id,

      COUNT(*) AS observation_count,

      ROUND(
        AVG(actual_consumption_litres),
        2
      ) AS avg_actual_consumption_litres,

      ROUND(
        AVG(expected_consumption_litres),
        2
      ) AS avg_expected_consumption_litres,

      ROUND(
        AVG(consumption_deviation_pct),
        2
      ) AS avg_consumption_deviation_pct,

      ROUND(
        MAX(consumption_deviation_pct),
        2
      ) AS max_consumption_deviation_pct,

      ROUND(
        MIN(consumption_deviation_pct),
        2
      ) AS min_consumption_deviation_pct,

      COUNTIF(consumption_anomaly)
        AS significant_consumption_observations,

      ROUND(
        SAFE_DIVIDE(
          COUNTIF(consumption_anomaly),
          COUNT(*)
        ) * 100,
        2
      ) AS consumption_anomaly_rate_pct,

      COUNTIF(above_upper_bound)
        AS above_upper_bound_observations,

      COUNTIF(below_lower_bound)
        AS below_lower_bound_observations,

      COUNTIF(is_night AND consumption_anomaly)
        AS night_consumption_anomaly_hours

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
            f"No consumption evidence found for "
            f"scenario {scenario_id}."
        )

    row = dict(rows[0])

    # --------------------------------------------------------
    # Deterministic evidence time-series
    # --------------------------------------------------------
    #
    # The full scenario remains available to the analytics
    # query above. Only a small 24-observation subset is exposed
    # to keep the API response compact and UI-friendly.
    #
    # The data comes directly from BigQuery.
    # No values are calculated or invented by Gemini/frontend.
    #

    timeseries_query = f"""
    SELECT
      CAST(timestamp AS STRING) AS timestamp,
      ROUND(actual_consumption_litres, 2)
        AS actual_consumption_litres,
      ROUND(expected_consumption_litres, 2)
        AS expected_consumption_litres,
      ROUND(consumption_deviation_pct, 2)
        AS deviation_pct
    FROM
      `{project_id}.{DATASET}.{EVIDENCE_TABLE}`
    WHERE
      scenario_id = @scenario_id
    ORDER BY
      timestamp
    LIMIT {EVIDENCE_TIMESERIES_LIMIT}
    """

    timeseries_rows = list(
        client.query(
            timeseries_query,
            job_config=job_config
        ).result()
    )

    row["evidence_timeseries"] = [
        dict(timeseries_row)
        for timeseries_row in timeseries_rows
    ]

    return row


# ============================================================
# OUTPUT VALIDATION
# ============================================================

def validate_consumption_evidence(
    evidence,
    scenario_id
):
    """
    Validate the structured output contract.
    """

    required_fields = [
        "scenario_id",
        "observation_count",
        "avg_actual_consumption_litres",
        "avg_expected_consumption_litres",
        "avg_consumption_deviation_pct",
        "max_consumption_deviation_pct",
        "min_consumption_deviation_pct",
        "significant_consumption_observations",
        "consumption_anomaly_rate_pct",
        "above_upper_bound_observations",
        "below_lower_bound_observations",
        "night_consumption_anomaly_hours",
        "evidence_timeseries",
    ]

    for field in required_fields:
        if field not in evidence:
            raise RuntimeError(
                f"Consumption Agent output is missing "
                f"required field: {field}"
            )

    if evidence["scenario_id"] != scenario_id:
        raise RuntimeError(
            "Consumption Agent returned evidence "
            "for the wrong scenario."
        )

    if int(
        evidence["observation_count"] or 0
    ) <= 0:
        raise RuntimeError(
            "Consumption Agent returned zero observations."
        )

    if not isinstance(
        evidence["evidence_timeseries"],
        list
    ):
        raise RuntimeError(
            "Consumption Agent evidence_timeseries "
            "must be a list."
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
        f"Running WaterTwin Consumption Agent "
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
        "Retrieving consumption evidence "
        "from BigQuery..."
    )

    evidence = get_consumption_evidence(
        project_id,
        scenario_id
    )

    validate_consumption_evidence(
        evidence,
        scenario_id
    )

    print(
        "Consumption evidence retrieved "
        "successfully."
    )

    print(
        "\nConsumption Agent Result:"
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