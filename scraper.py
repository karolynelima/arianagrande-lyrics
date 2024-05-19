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

ALBUMS = [
    "1989 (Taylor’s Version)", "1989 (Taylor’s Version) [Deluxe]",
    '1989 (Taylor’s Version) [Tangerine Edition]', 'Beautiful Eyes - EP', 
    'Christmas Tree Farm', 'Cats: Highlights From the Motion Picture Soundtrack',
    'Carolina (From The Motion Picture “Where The Crawdads Sing”) - Single',
    'Fearless (Taylor’s Version)',
    'Fifty Shades Darker (Original Motion Picture Soundtrack)',
    'Hannah Montana: The Movie', 'Lover',
    'How Long Do You Think It’s Gonna Last?', 'Miss Americana',
    'Red (Taylor’s Version)', 'Speak Now (Taylor’s Version)', 'Taylor Swift',
    'Taylor Swift (Deluxe)', "Taylor Swift (Best Buy Exclusive)",
    'Taylor Swift (Big Machine Radio Release Special)',
    'The Taylor Swift Holiday Collection - EP', 'Unreleased Songs', 'evermore',
    'evermore (deluxe version)', "evermore (Japanese Edition)", 'folklore',
    'folklore (deluxe version)', 'reputation',
    'Two Lanes of Freedom (Accelerated Deluxe)', 'Love Drunk',
    'Women in Music Pt. III (Expanded Edition)', 'Midnights',
    'Midnights (3am Edition)', 'Midnights (Target Exclusive)',
    'Midnights (The Late Night Edition)', '2004–2005 Demo CD',
    'The Hunger Games', 'The More Lover Chapter', 'iTunes Essentials',
    'The More Red (Taylor’s Version) Chapter',
    'The More Fearless (Taylor’s Version) Chapter', 'The Tortured Poets Department', ''
]

# Songs that don't have an album or for which Taylor Swift is not the primary artist
OTHER_SONGS = [
    'Only The Young', 'Christmas Tree Farm', 'Renegade', 'Carolina',
    "I Don’t Wanna Live Forever", 'Beautiful Eyes', "Highway Don’t Care",
    'Two Is Better Than One', 'Gasoline (Remix)'
]

# Songs for which there is trouble retrieving them by name - some of these are probably no longer an issue anyways
EXTRA_SONG_API_PATHS = {
    '/songs/187017': 'Beautiful Eyes - EP',
    '/songs/186861': 'The Taylor Swift Holiday Collection - EP',
    '/songs/6959851': 'How Long Do You Think It’s Gonna Last?',
    '/songs/4968964': 'Cats: Highlights From the Motion Picture Soundtrack',
    '/songs/5114093': 'Cats: Highlights From the Motion Picture Soundtrack',
    '/songs/7823793': 'Carolina (From The Motion Picture “Where The Crawdads Sing”) - Single',
    '/songs/5077615': 'Christmas Tree Farm',
    '/songs/8924411': 'The More Red (Taylor’s Version) Chapter',
    # Manually adding in TTPD songs so that it generates faster on release night
    '/songs/10024009': 'The Tortured Poets Department',
    '/songs/10024578': 'The Tortured Poets Department',
    '/songs/10024528': 'The Tortured Poets Department',
    '/songs/10024535': 'The Tortured Poets Department',
    '/songs/10024536': 'The Tortured Poets Department',
    '/songs/10024520': 'The Tortured Poets Department',
    '/songs/10024544': 'The Tortured Poets Department',
    '/songs/10291434': 'The Tortured Poets Department',
    '/songs/10024517': 'The Tortured Poets Department',
    '/songs/10024563': 'The Tortured Poets Department',
    '/songs/10024518': 'The Tortured Poets Department',
    '/songs/10024526': 'The Tortured Poets Department',
    '/songs/10024512': 'The Tortured Poets Department',
    '/songs/10024519': 'The Tortured Poets Department',
    '/songs/10024521': 'The Tortured Poets Department',
    '/songs/10024516': 'The Tortured Poets Department',
    # TTPD Bonus Tracks
    '/songs/10064067': 'The Tortured Poets Department',
    '/songs/10021428': 'The Tortured Poets Department',
    '/songs/10124160': 'The Tortured Poets Department',
    '/songs/10090426': 'The Tortured Poets Department',
    '/songs/10296670': 'The Tortured Poets Department',
    '/songs/10296695': 'The Tortured Poets Department',
    '/songs/10296686': 'The Tortured Poets Department',
    '/songs/10296673': 'The Tortured Poets Department',
    '/songs/10296676': 'The Tortured Poets Department',
    '/songs/10296677': 'The Tortured Poets Department',
    '/songs/10296681': 'The Tortured Poets Department',
    '/songs/10296661': 'The Tortured Poets Department',
    '/songs/10296680': 'The Tortured Poets Department',
    '/songs/10296682': 'The Tortured Poets Department',
    '/songs/10296690': 'The Tortured Poets Department',
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
    songs = get_songs(existing_songs) if not args.appendpaths else []
    songs_by_album, has_failed, last_song = {}, True, ''
    while has_failed:
        songs_by_album, has_failed, last_song = sort_songs_by_album(
            genius, songs, songs_by_album, last_song, existing_songs)
    albums_to_songs_csv(songs_by_album, existing_df)
    songs_to_lyrics()
    lyrics_to_json()


def get_songs(existing_songs):
    print('Getting songs...')
    songs = []
    next_page = 1
    while next_page != None:
        request_url = ARTIST_URL + "/songs?page=" + str(next_page)
        r = requests.get(request_url,
                         headers={'Authorization': "Bearer " + access_token})
        song_data = json.loads(r.text)
        songs.extend(song_data['response']['songs'])
        next_page = song_data['response']['next_page']
    returned_songs = []
    for song in songs:
        if song['title'] not in existing_songs and song[
                'title'] + " (Taylor’s Version)" not in existing_songs and song[
                    'release_date_components'] != None and song[
                        'lyrics_state'] == 'complete' and (
                            song['primary_artist']['id'] == ARTIST_ID
                            or song['title'] in OTHER_SONGS):
            returned_songs.append(song)
    return returned_songs


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
        if album in ALBUMS:
            for song in songs_by_album[album]:
                if song.title not in IGNORE_SONGS and song.title not in songs_titles:
                    record = {
                        'Title': song.title.replace('\u200b', ''),
                        'Album':
                        album if 'Lover (Target' not in album else 'Lover',
                        'Lyrics': song.lyrics,
                    }
                    songs_records.append(record)
                    songs_titles.append(song.title)
        else:
            for song in songs_by_album[album]:
                if song in OTHER_SONGS and song.title not in songs_titles:
                    record = {
                        'Title': song.title.replace('\u200b', ''),
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


def clean_lyrics(lyrics: str) -> str:
    # Remove first line (title + verse line)
    split_lyrics = lyrics.split(sep='\n', maxsplit=1)
    lyrics = split_lyrics[1] if len(split_lyrics) > 1 else ''
    # Replace special quotes with normal quotes
    lyrics = re.sub(r'\u2018|\u2019', "'", lyrics)
    lyrics = re.sub(r'\u201C|\u201D', '"', lyrics)
    # Replace special unicode spaces with standard space
    lyrics = re.sub(
        r'[\u00A0\u1680​\u180e\u2000-\u2009\u200a​\u202f\u205f​\u3000]',
        " ", lyrics)
    # Replace zero-width space with empty string
    lyrics = lyrics.replace('\u200b', '')
    # Replace Cyrillic 'e' letters with English 'e'.
    lyrics = re.sub(r'\u0435', "e", lyrics)
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
