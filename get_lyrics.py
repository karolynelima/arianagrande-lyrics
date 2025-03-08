import requests
import json
import pandas as pd
import time

# Substitua pelo seu token de API do Genius
GENIUS_ACCESS_TOKEN = "rHSd5O17tg670PZgATFNW-8tacXqvEmydD_5g_KheO5WRfDMG3fLmWyP4nbZxBMi"

# Lista de músicas da Ariana Grande para buscar
SONGS = [
    "no tears left to cry",
    "positions",
    "7 rings",
    "thank u, next",
    "Into You",
    "Dangerous Woman",
    "God is a Woman",
    "Side to Side",
]

# URL base da API do Genius
BASE_URL = "https://api.genius.com"

# Função para buscar o ID da música no Genius
def get_song_id(song_title):
    headers = {"Authorization": f"Bearer {GENIUS_ACCESS_TOKEN}"}
    search_url = f"{BASE_URL}/search"
    params = {"q": song_title}
    
    response = requests.get(search_url, headers=headers, params=params)
    if response.status_code == 200:
        hits = response.json().get("response", {}).get("hits", [])
        if hits:
            return hits[0]["result"]["id"]
    return None

# Função para buscar a letra da música pelo ID
def get_lyrics(song_id):
    headers = {"Authorization": f"Bearer {GENIUS_ACCESS_TOKEN}"}
    song_url = f"{BASE_URL}/songs/{song_id}"
    
    response = requests.get(song_url, headers=headers)
    if response.status_code == 200:
        song_info = response.json().get("response", {}).get("song", {})
        return song_info.get("url")  # Genius não fornece letras diretamente, então pegamos a URL
    return None

# Lista para armazenar as músicas
data = []

# Buscar letras das músicas
for song in SONGS:
    print(f"Buscando: {song}")
    song_id = get_song_id(song)
    if song_id:
        lyrics_url = get_lyrics(song_id)
        if lyrics_url:
            data.append({"title": song, "lyrics_url": lyrics_url})
    time.sleep(1)  # Evita excesso de requisições

# Criar DataFrame
df = pd.DataFrame(data)

# Salvar CSV
df.to_csv("lyrics.csv", index=False, encoding="utf-8")

# Salvar JSON
with open("lyrics.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print("Letras salvas em lyrics.csv e lyrics.json!")
