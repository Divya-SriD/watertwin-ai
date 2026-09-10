import json
import sys
from datetime import datetime, timezone

from google.cloud import pubsub_v1


PROJECT_ID = "project-4e41dc93-8aec-4f29-8fd"
TOPIC_ID = "water-twin-events"


SCENARIO_METADATA = {
    "S1": {
        "event_type": "NORMAL_OPERATION",
        "priority": "LOW",
    },
    "S2": {
        "event_type": "WATER_USAGE_ANOMALY",
        "priority": "HIGH",
    },
    "S3": {
        "event_type": "PRESSURE_ANOMALY",
        "priority": "HIGH",
    },
    "S4": {
        "event_type": "WATER_USAGE_ANOMALY",
        "priority": "MEDIUM",
    },
    "S5": {
        "event_type": "WATER_USAGE_ANOMALY",
        "priority": "MEDIUM",
    },
    "S6": {
        "event_type": "SENSOR_ANOMALY",
        "priority": "HIGH",
    },
    "S7": {
        "event_type": "AMBIGUOUS_WATER_USAGE_ANOMALY",
        "priority": "HIGH",
    },
}


def publish_event(scenario_id: str) -> str:
    scenario_id = scenario_id.strip().upper()

    if scenario_id not in SCENARIO_METADATA:
        raise ValueError(
            f"Unknown WaterTwin scenario: {scenario_id}. "
            f"Expected one of: {', '.join(SCENARIO_METADATA)}"
        )

    metadata = SCENARIO_METADATA[scenario_id]

    event = {
        "scenario_id": scenario_id,
        "event_type": metadata["event_type"],
        "priority": metadata["priority"],
        "source": "synthetic_simulator",
        "published_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    publisher = pubsub_v1.PublisherClient()

    topic_path = publisher.topic_path(
        PROJECT_ID,
        TOPIC_ID,
    )

    payload = json.dumps(
        event
    ).encode("utf-8")

    future = publisher.publish(
        topic_path,
        payload,
        scenario_id=scenario_id,
        event_type=metadata["event_type"],
        source="synthetic_simulator",
    )

    message_id = future.result()

    print()
    print("=" * 70)
    print("WaterTwin Pub/Sub Publisher")
    print("=" * 70)

    print(
        f"Project: {PROJECT_ID}"
    )

    print(
        f"Topic: {TOPIC_ID}"
    )

    print(
        f"Scenario: {scenario_id}"
    )

    print(
        f"Event type: {metadata['event_type']}"
    )

    print(
        f"Priority: {metadata['priority']}"
    )

    print()
    print("Published event:")
    print(
        json.dumps(
            event,
            indent=2,
        )
    )

    print()
    print(
        f"Pub/Sub message ID: {message_id}"
    )

    print()
    print(
        "WaterTwin event published successfully."
    )

    return message_id


def main() -> None:
    if len(sys.argv) != 2:
        print(
            "Usage:"
        )
        print(
            "  python3 water_twin_publisher.py S2"
        )
        sys.exit(1)

    scenario_id = sys.argv[1]

    publish_event(
        scenario_id
    )


if __name__ == "__main__":
    main()
