import os
import json
import requests
from pathlib import Path
from datetime import datetime
from utils.minio_client import upload_file_to_minio

DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN")
BASE_URL = "https://api.discogs.com"

HEADERS = {
    "Authorization": f"Discogs token={DISCOGS_TOKEN}",
    "User-Agent": "DiscogsDataPipeline/1.0"
}

def fetch_user_data(user_id):
    url = f"{BASE_URL}/users/{user_id}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Erro ao coletar usuário {user_id}: {response.status_code}")
        return None

def run_user_collector(input_path: str, output_dir: str, execution_date: str):
    with open(input_path, "r") as f:
        discovered_ids = json.load(f)

    user_ids = discovered_ids.get("user_ids", [])

    output_data = []
    for user_id in user_ids:
        data = fetch_user_data(user_id)
        if data:
            output_data.append(data)

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = f"{output_dir}/users_{execution_date}.json"
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    upload_file_to_minio(
        local_path=output_path,
        bucket="bronze",
        object_name=f"users/year={execution_date[:4]}/users_{execution_date}.json"
    )