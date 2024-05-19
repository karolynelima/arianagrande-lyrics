import argparse
import json
import socket
import lyricsgenius
import math
import pandas as pd
import re
import requests
from lyricsgenius.types import Song
from local import *

ALBUMS = {
    '/albums/12682': 'Taylor Swift',
    '/albums/152556': 'Beautiful Eyes',
    '/albums/734107': "Fearless (Taylor's Version)",
    '/albums/758025': "Speak Now (Taylor's Version)",
    '/albums/758022': "Red (Taylor's Version)",
    '/albums/1082316': "1989 (Taylor's Version)",
    '/albums/350247': 'reputation',
    '/albums/4508914': 'Lover',
    '/albums/5793971': 'folklore',
    '/albums/710147': 'evermore',
    '/albums/949856': 'Midnights',
    '/albums/1040217': 'Midnights',
    '/albums/1171508': 'The Tortured Poets Department',
    '/albums/39094': 'The Taylor Swift Holiday Collection',
    '/albums/8924411': 'The Hunger Games',
}

# Songs that don't have an album or for which Taylor Swift is not the primary artist
EXTRA_SONG_API_PATHS = {
    '/songs/6959851': 'How Long Do You Think It’s Gonna Last?',
    '/songs/4968964': 'Cats',
    '/songs/5114093': 'Cats',
    '/songs/7823793': 'Where The Crawdads Sing',
    '/songs/5077615': 'Christmas Tree Farm',
    '/songs/2927948': "Fifty Shades Darker",
    '/songs/5191847': "Miss Americana",
    '/songs/6959851': "How Long Do You Think It's Gonna Last",
    '/songs/642957': "Love Drunk",
    '/songs/6453633': "Women in Music Part III",
    '/songs/154241': "Two Lanes of Freedom",
}

# Songs that are somehow duplicates / etc.
IGNORE_SONGS = [
    'Should’ve Said No (Alternate Version)',
    'State Of Grace (Acoustic Version) (Taylor’s Version)',
    'Love Story (Taylor’s Version) [Elvira Remix]',
    'Forever & Always (Piano Version) [Taylor’s Version]',
    'Ronan',
    'Mine (Pop Mix)',
    'Haunted (Acoustic Version)',
    'Back To December (Acoustic)',
    'Sweet Nothing (Piano Remix)',
    'You’re On Your Own, Kid (Strings Remix)',
    'Need You Now',
    'Sweet Tea and God’s Graces',
    'What Do You Say',
    'Welcome Distraction',
    'Dark Blue Tennessee',
    'Never Mind',
    'Who I’ve Always Been',
    'Umbrella (Live from SoHo)',
    'willow (dancing witch version) [Elvira Remix]',
    'willow (lonely witch version)',
    'Teardrops On My Guitar (Cahill Radio Edit)',
    'Teardrops on My Guitar (Pop Version)',
]

ARTIST_ID = 1177
API_PATH = "https://api.genius.com"
ARTIST_URL = API_PATH + "/artists/" + str(ARTIST_ID)
CSV_PATH = 'songs.csv'
LYRIC_PATH = 'lyrics.csv'
LYRIC_JSON_PATH = 'lyrics.json'
SONG_LIST_PATH = 'song_titles.txt'


def main():
    parser = argparse.ArgumentParser()
    # Only look for songs that aren't already existing
    parser.add_argument('--append', action='store_true')
    # Append songs specifically in EXTRA_SONG_API_PATHS
    parser.add_argument('--appendpaths', action='store_true')
    args = parser.parse_args()
    existing_df, existing_songs = None, []
    if args.append or args.appendpaths:
        existing_df = pd.read_csv(CSV_PATH)
        existing_songs = list(existing_df['Title'])
    genius = lyricsgenius.Genius(access_token)
    # songs = get_songs(existing_songs) if not args.appendpaths else []
    num_retries = 0
    songs_by_album, has_failed, last_album, songs_so_far = {}, True, None, existing_songs
    while has_failed and num_retries < 4:
        songs_by_album, has_failed, last_album = get_songs_by_album(
            genius, songs_by_album, last_album, songs_so_far)
        num_retries += 1
    albums_to_songs_csv(songs_by_album, existing_df)
    songs_to_lyrics()
    lyrics_to_json()


def get_songs_by_album(genius, songs_by_album, last_album, songs_so_far):
    print('Getting songs from albums...')
    def get_song_data(api_path):
        request_url = API_PATH + api_path
        r = requests.get(request_url,
                         headers={'Authorization': "Bearer " + access_token})
        return json.loads(r.text)['response']['song']

    def clean_lyrics_and_append(song_data, album_name, lyrics, songs_by_album):
        cleaned_lyrics = clean_lyrics(lyrics)
        s = Song(genius, song_data, cleaned_lyrics)
        if album_name not in songs_by_album:
            songs_by_album[album_name] = []
        songs_by_album[album_name].append(s)

    album_index = 0
    
    for album_api_path in ALBUMS:
        if last_album is None or album_index >= list(ALBUMS.keys()).index(last_album):
            album_name = ALBUMS[album_api_path]
            print('Getting songs for album', album_name)
            next_page = 1
            tracks = []
            while next_page != None:
                try:
                    request_url = API_PATH + album_api_path + "/tracks?page=" + str(next_page)
                    r = requests.get(request_url,
                                    headers={'Authorization': "Bearer " + access_token})
                    track_data = json.loads(r.text)
                    tracks.extend(track_data['response']['tracks'])
                    next_page = track_data['response']['next_page']
                except Exception:
                    print(track_data.keys())
                    return songs_by_album, True, album_api_path
            for track in tracks:
                song = track['song']
                cleaned_song_title = clean_title(song['title'])
                try:
                    if cleaned_song_title not in songs_so_far and song['release_date_components'] != None and song['lyrics_state'] == 'complete':
                        lyrics = genius.lyrics(song_id=song['id'])
                        # Ensure that there are lyrics
                        if lyrics and has_song_identifier(lyrics):
                            songs_so_far.append(cleaned_song_title)
                            clean_lyrics_and_append(song, album_name, lyrics,
                                                    songs_by_album)
                except requests.exceptions.Timeout or socket.timeout:
                    print('Failed receiving song', cleaned_song_title,
                        '-- saving songs so far')
                    return songs_by_album, True, album_api_path
        album_index += 1
        
    for api_path in EXTRA_SONG_API_PATHS:
        song_data = get_song_data(api_path)
        if song_data['title'] not in existing_songs and song_data[
                'title'] not in songs_so_far:
            lyrics = genius.lyrics(song_id=song_data['id'])
            album_name = EXTRA_SONG_API_PATHS[api_path]
            clean_lyrics_and_append(song_data, album_name, lyrics,
                                    songs_by_album)

    return songs_by_album, False, None



def sort_songs_by_album(genius,
                        songs,
                        songs_by_album,
                        last_song,
                        existing_songs=[]):
    def get_song_data(api_path):
        request_url = API_PATH + api_path
        r = requests.get(request_url,
                         headers={'Authorization': "Bearer " + access_token})
        return json.loads(r.text)['response']['song']

    def clean_lyrics_and_append(song_data, album_name, lyrics, songs_by_album):
        cleaned_lyrics = clean_lyrics(lyrics)
        s = Song(genius, song_data, cleaned_lyrics)
        if album_name not in songs_by_album:
            songs_by_album[album_name] = []
        songs_by_album[album_name].append(s)

    print('Sorting songs by album...')
    songs_so_far = []
    for song in songs:
        lyrics = None
        if song['title'] > last_song and song[
                'title'] not in existing_songs and song[
                    'title'] not in IGNORE_SONGS:
            try:
                song_data = get_song_data(song['api_path'])
                if song_data != None and 'album' in song_data and song_data[
                        'lyrics_state'] == 'complete':
                    album_name = song_data['album']['name'].strip(
                    ) if song_data['album'] else None
                    # Handle special cases -- uncategorized songs are under "Taylor Swift " on Genius
                    if album_name == "Taylor Swift" and album_name != song_data[
                            'album']['name']:
                        album_name = "Uncategorized"
                    # Some of the 2004-2005 Demo CD songs are on Fearless TV, some are on Debut
                    if album_name == "2004–2005 Demo CD" and "(Taylor’s Version)" in song[
                            'title']:
                        album_name = "Fearless (Taylor’s Version)"
                    if album_name is None:
                        album_name = ""
                    lyrics = genius.lyrics(song_id=song_data['id'])
                    # Ensure that there are lyrics
                    if lyrics and has_song_identifier(lyrics) and (
                            album_name or (song['title'] in OTHER_SONGS)):
                        songs_so_far.append(song['title'])
                        clean_lyrics_and_append(song_data, album_name, lyrics,
                                                songs_by_album)
            except requests.exceptions.Timeout or socket.timeout:
                print('Failed receiving song', song['title'],
                      '-- saving songs so far')
                return songs_by_album, True, song['title']

    for api_path in EXTRA_SONG_API_PATHS:
        song_data = get_song_data(api_path)
        if song_data['title'] not in existing_songs and song_data[
                'title'] not in songs_so_far:
            lyrics = genius.lyrics(song_id=song_data['id'])
            album_name = EXTRA_SONG_API_PATHS[api_path]
            clean_lyrics_and_append(song_data, album_name, lyrics,
                                    songs_by_album)

    return songs_by_album, False, ''


def albums_to_songs_csv(songs_by_album, existing_df=None):
    print('Saving songs to CSV...')
    songs_records = []
    songs_titles = []
    for album in songs_by_album:
        for song in songs_by_album[album]:
            if song.title not in IGNORE_SONGS and song.title not in songs_titles:
                record = {
                    'Title': clean_title(song.title),
                    'Album': album,
                    'Lyrics': song.lyrics,
                }
                songs_records.append(record)
                songs_titles.append(song.title)

    song_df = pd.DataFrame.from_records(songs_records)
    if existing_df is not None:
        existing_df = existing_df[existing_df['Album'].isin(ALBUMS)]
        song_df = pd.concat([existing_df, song_df])
        song_df = song_df[~song_df['Title'].isin(IGNORE_SONGS)]
        song_df = song_df.drop_duplicates('Title', keep="last")
    song_df.to_csv(CSV_PATH, index=False)


def has_song_identifier(lyrics):
    if '[Intro' in lyrics or '[Verse' in lyrics or '[Chorus' in lyrics:
        return True
    return False


class Lyric:
    def __init__(self, lyric, prev_lyric=None, next_lyric=None):
        self.lyric = lyric
        self.prev = prev_lyric
        self.next = next_lyric

    def __eq__(self, other):
        return self.lyric == other.lyric and self.prev == other.prev and self.next == other.next

    def __repr__(self):
        return self.lyric

    def __hash__(self):
        return hash((self.prev or "") + self.lyric + (self.next or ""))


def songs_to_lyrics():
    print('Generating lyrics CSV...')
    song_data = pd.read_csv(CSV_PATH)
    lyric_records = []
    song_titles = []
    for song in song_data.to_records(index=False):
        title, album, lyrics = song
        if title not in song_titles and len(lyrics) > 1:
            song_titles.append(title)
            lyric_dict = get_lyric_list(lyrics)
            for lyric in lyric_dict:
                lyric_record = {
                    'Song': title,
                    'Album': album,
                    'Lyric': lyric.lyric,
                    'Previous Lyric': lyric.prev,
                    'Next Lyric': lyric.next,
                    'Multiplicity': lyric_dict[lyric]
                }
                lyric_records.append(lyric_record)
    lyric_df = pd.DataFrame.from_records(lyric_records)
    lyric_df.to_csv(LYRIC_PATH, index=False)
    # Writing song list to make it easy to compare changes
    with open(SONG_LIST_PATH, 'w') as f:
        f.write('\n'.join(sorted(set(song_titles))))
        f.close()


def get_lyric_list(lyrics):
    line = None
    lines = lyrics.split('\n')
    lyric_dict = {}
    for i in range(len(lines)):
        curr_line = lines[i].strip()
        if len(curr_line) > 0 and curr_line[0] != '[':
            prev_line = line
            line = curr_line
            next_line = lines[i + 1] if i + 1 < len(lines) and len(
                lines[i + 1]) > 0 and lines[i + 1][0] != '[' else None
            lyric = Lyric(line, prev_line, next_line)
            if lyric not in lyric_dict:
                lyric_dict[lyric] = 1
            else:
                lyric_dict[lyric] = lyric_dict[lyric] + 1
        # If there is a chorus / etc. indicator then set current line to "None"
        # if the previous line was not already set
        elif line is not None:
            line = None
    return lyric_dict


def lyrics_to_json():
    print('Generating lyrics JSON...')
    lyric_dict = {}
    lyric_data = pd.read_csv(LYRIC_PATH)
    for lyric in lyric_data.to_records(index=False):
        title, album, lyric, prev_lyric, next_lyric, multiplicity = lyric
        if album != album:  # handling for NaN
            album = title
        if album not in lyric_dict:
            lyric_dict[album] = {}
        if title not in lyric_dict[album]:
            lyric_dict[album][title] = []
        lyric_dict[album][title].append({
            'lyric':
            lyric,
            'prev':
            "" if prev_lyric != prev_lyric else prev_lyric,  # replace NaN
            'next':
            "" if next_lyric != next_lyric else next_lyric,
            'multiplicity':
            int(multiplicity),
        })
    lyric_json = json.dumps(lyric_dict, indent=4)
    with open(LYRIC_JSON_PATH, 'w') as f:
        f.write(lyric_json)
        f.close()

def clean_title(title: str) -> str:
    title = re.sub(r'\u2018|\u2019', "'", title)
    title = re.sub(r'\u201C|\u201D', '"', title)
    # Replace special unicode spaces with standard space
    title = re.sub(
        r'[\u00A0\u1680​\u180e\u2000-\u2009\u200a​\u200b​\u202f\u205f​\u3000]',
        " ", title)
    title = title.strip(' ')
    return title

def clean_lyrics(lyrics: str) -> str:
    # Remove first line (title + verse line)
    split_lyrics = lyrics.split(sep='\n', maxsplit=1)
    lyrics = split_lyrics[1] if len(split_lyrics) > 1 else ''
    # Replace special quotes with normal quotes
    lyrics = re.sub(r'\u2018|\u2019', "'", lyrics)
    lyrics = re.sub(r'\u201C|\u201D', '"', lyrics)
    # Replace special unicode spaces with standard space
    lyrics = re.sub(
        r'[\u00A0\u1680​\u180e\u2000-\u2009\u200a​\u200b​\u202f\u205f​\u3000]',
        " ", lyrics)
    # Replace dashes with space and single hyphen
    lyrics = re.sub(r'\u2013|\u2014', " - ", lyrics)
    # Replace hyperlink text
    lyrics = re.sub(r"[0-9]*URLCopyEmbedCopy", '', lyrics)
    lyrics = re.sub(r"[0-9]*Embed", '', lyrics)
    lyrics = re.sub(r"[0-9]*EmbedShare", '', lyrics)
    lyrics = re.sub(
        r"See [\w\s]* LiveGet tickets as low as \$\d*You might also like",
        '\n', lyrics)

    return lyrics


if __name__ == '__main__':
    main()
