import os
import requests
import json
from datetime import datetime
from urllib.parse import urlencode

DISCOGS_BASE_URL = "https://api.discogs.com"
DISCOGS_USER_AGENT = "DiscogsDataPipeline/1.0"
DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN")

DEFAULT_PARAMS = {
    "type": "release",
    "per_page": 100,
    "page": 1
}

HEADERS = {
    "User-Agent": DISCOGS_USER_AGENT,
    "Authorization": f"Discogs token={DISCOGS_TOKEN}"
}


def search_discogs(params):
    """
    Executa uma busca na API do Discogs usando o endpoint /database/search
    """
    query = urlencode(params)
    url = f"{DISCOGS_BASE_URL}/database/search?{query}"
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        raise Exception(f"Erro na requisição: {response.status_code} - {response.text}")

    return response.json()


def extract_ids(results):
    """
    Extrai IDs de artistas, releases e labels da resposta da API
    """
    ids = {
        "release_ids": [],
        "artist_ids": [],
        "label_ids": []
    }

    for item in results.get("results", []):
        if "id" in item and item.get("type") == "release":
            ids["release_ids"].append(item["id"])

        if "artist" in item:
            ids["artist_ids"].extend([artist["id"] for artist in item.get("artist", []) if "id" in artist])

        if "label" in item:
            ids["label_ids"].extend([label["id"] for label in item.get("label", []) if "id" in label])

    return ids


def save_ids_to_file(ids_dict, base_path="data/bronze/discovery/", reference="default"):
    """
    Salva os IDs extraídos como arquivos JSON em diretórios separados
    """
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    output_path = os.path.join(base_path, reference, timestamp)
    os.makedirs(output_path, exist_ok=True)

    for key, values in ids_dict.items():
        unique_values = list(set(values))
        with open(f"{output_path}/{key}.json", "w") as f:
            json.dump(unique_values, f, indent=2)
        print(f"✔️ Salvou {len(unique_values)} {key} em {output_path}/{key}.json")


def run_discovery(year: int, genre: str = None, style: str = None, pages: int = 3):
    """
    Roda o processo de descoberta por ano e (opcionalmente) gênero e estilo
    """
    print(f"🔍 Iniciando busca por releases do ano {year}...")

    all_ids = {
        "release_ids": [],
        "artist_ids": [],
        "label_ids": []
    }

    for page in range(1, pages + 1):
        params = DEFAULT_PARAMS.copy()
        params["year"] = year
        params["page"] = page
        if genre:
            params["genre"] = genre
        if style:
            params["style"] = style

        data = search_discogs(params)
        ids = extract_ids(data)

        for k in all_ids:
            all_ids[k].extend(ids.get(k, []))

    save_ids_to_file(all_ids, reference=f"{year}")

    return all_ids