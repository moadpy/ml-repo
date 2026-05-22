"""
Test the trained model against the specific high-CPU incident.
"""
import os
import sys
import json

# Add src to python path so we can import score
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import score

# Tell score.py to look for the model.pkl in the outputs directory
os.environ["AZUREML_MODEL_DIR"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "../outputs"))

def main():
    # Load model
    print("Initializing model...")
    try:
        score.init()
    except Exception as e:
        print(f"Error loading model: {e}")
        print("Make sure you have trained the model first using:")
        print("  python src/train.py --data_path data/rca_poc/telemetry_labeled.csv")
        return

    # The incident payload given by the user
    payload = {
        "cpu_percent_avg5": 99.99,
        "memory_percent_avg5": 19.13,
        "http_5xx_rate_avg5": 1.96,
        "db_conn_pool_wait_avg5": 17.33,
        "request_latency_p99_avg5": 205.0,
        "breaching_metric": "cpu_percent"
    }

    print("\nRunning inference for payload:")
    print(json.dumps(payload, indent=2))

    # Run classification
    raw_response = score.run(json.dumps(payload))
    response = json.loads(raw_response)

    print("\nClassification Result:")
    print(json.dumps(response, indent=2))

if __name__ == "__main__":
    main()
