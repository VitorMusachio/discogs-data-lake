import os
import json
import requests
import boto3
from datetime import datetime

# Configurações
DISCOGS_BASE_URL = "https://api.discogs.com"
HEADERS = {"User-Agent": "DiscogsDataCollector/1.0"}

# Informações do MinIO
MINIO_ENDPOINT = "http://minio:9000"
MINIO_ACCESS_KEY = "minio"
MINIO_SECRET_KEY = "minio123"
BUCKET_NAME = "bronze"

# Pasta temporária local
OUTPUT_FOLDER = "/tmp/discogs_data"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def fetch_artist_data(artist_id: int):
    url = f"{DISCOGS_BASE_URL}/artists/{artist_id}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"[!] Falha ao buscar artista {artist_id}: {response.status_code}")
        return None


def save_to_file(data, artist_id):
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"artist_{artist_id}_{ts}.json"
    filepath = os.path.join(OUTPUT_FOLDER, filename)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    return filepath


def upload_to_minio(filepath, filename):
    s3 = boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    )

    # Garante que o bucket existe
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
    except:
        s3.create_bucket(Bucket=BUCKET_NAME)

    s3.upload_file(filepath, BUCKET_NAME, f"bronze/artists/{filename}")
    print(f"[✓] Upload concluído: {filename}")


def main():
    artist_ids = [1, 45, 108713]  # Exemplo: artistas conhecidos
    for artist_id in artist_ids:
        data = fetch_artist_data(artist_id)
        if data:
            filepath = save_to_file(data, artist_id)
            filename = os.path.basename(filepath)
            upload_to_minio(filepath, filename)


if __name__ == "__main__":
    main()