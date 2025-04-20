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

def fetch_search_results(query):
    url = f"{BASE_URL}/database/search?q={query}&type=release"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Erro ao buscar por {query}: {response.status_code}")
        return None

def run_search_collector(query: str, output_dir: str, execution_date: str):
    data = fetch_search_results(query)
    if data:
        output_data = data.get("results", [])

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        output_path = f"{output_dir}/search_{execution_date}.json"
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)

        upload_file_to_minio(
            local_path=output_path,
            bucket="bronze",
            object_name=f"search/year={execution_date[:4]}/search_{execution_date}.json"
        )