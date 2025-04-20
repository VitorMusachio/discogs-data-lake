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

def fetch_collection_data(collection_id):
    url = f"{BASE_URL}/users/{collection_id}/collection/folders/0/releases"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Erro ao coletar coleção {collection_id}: {response.status_code}")
        return None

def run_collection_collector(input_path: str, output_dir: str, execution_date: str):
    with open(input_path, "r") as f:
        discovered_ids = json.load(f)

    collection_ids = discovered_ids.get("collection_ids", [])

    output_data = []
    for collection_id in collection_ids:
        data = fetch_collection_data(collection_id)
        if data:
            output_data.append(data)

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = f"{output_dir}/collections_{execution_date}.json"
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    upload_file_to_minio(
        local_path=output_path,
        bucket="bronze",
        object_name=f"collections/year={execution_date[:4]}/collections_{execution_date}.json"
    )