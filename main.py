import pyttsx3
import os
from dotenv import load_dotenv
import requests
import base64
import json
from datetime import (
    datetime as dt,
    timedelta as td,
)
from random import choices, choice
import vlc
import speech_recognition as sr
from time import sleep
from typing import Optional
from difflib import SequenceMatcher

load_dotenv()

class Game:
    def __init__(self) -> None:
        # Spotify
        self.spotifyExpiry: dt = (dt.utcnow() - td(seconds=10))
        self.spotifyAccessToken: str = ""
        self.baseSpotifyUrl: str = "https://api.spotify.com/v1"
        self.spotifyHeaders: dict = {}
        
        self.playlists: dict = {
            "hindi": ["37i9dQZF1DWXtlo6ENS92N", "37i9dQZF1DX14CbVHtvHRB", "37i9dQZF1DXdpQPPZq3F7n", "37i9dQZF1DX0XUfTFmNBRM", "37i9dQZF1DXd8cOUiye1o2"],
            "english": ["37i9dQZF1DX0ieekvzt1Ic", "37i9dQZF1DXbYM3nMM0oPk", "6IdR78TOog83PV4XhLDvWN", "50JkxtsGUsZ8QRKR57Czt9", "2mzlU8dfi5qqdWahPvbQyE"],
            "telugu": ["37i9dQZF1DX5EbPl0mQHmo", "37i9dQZF1DX5VOFoIqmrOV", "37i9dQZF1DX6XE7HRLM75P", "37i9dQZF1DX3VuB7FVwxmc", "37i9dQZF1DX1MYRp9oolwH", "37i9dQZF1DWWwrjLPC16W7"],
            "kannada": ["4nRDM69vmrfaqCKqi1aQmc", "5gsiTUtJY2XZh67Y94rZDV", "37i9dQZF1DX1ahAlaaz0ZE", "0td8Ug256plxMIOzOXKHNo", "4GbsZ1dxsKOPi9R7XOkkEk"],
        }
        self.category: str = ""

        self.total_tracks: int = 0
        self.current_track: Optional[int] = 1
        self.tracks: list = []

        # Points
        self.points: int = 0
        self.points_per_q: int = 20
        self.points_per_b: int = 10

        # Accuracy
        self.title_accuracy: float = 0.5
        self.artist_accuracy: float = 0.4

        # Speach
        self.speachEngine = pyttsx3.init()

        voices = self.speachEngine.getProperty('voices')
        self.speachEngine.setProperty('voice', voices[1].id) # 0 - Male voice, 1 - Female voice
        self.speachEngine.setProperty('rate', 150) # Default: 200

        self.recognizer = sr.Recognizer()

    def close(self) -> None:
        self.speachEngine.stop()
    
    def start(self, total_tracks: int = 5) -> None:
        self.total_tracks: int = total_tracks
        self.get_category()
        if self.category == "":
            return

        playlist: str = str(choice(list(self.playlists[str(self.category)])))
        self.get_spotify_tracks(playlist, self.total_tracks)

        for _ in range(self.total_tracks):
            if self.current_track is None:
                break
            if self.current_track == 1:
                self.speak("Name the song title or artist after the music stops. You can name both for bonus points. If you need more time, just say repeat.")
            self.speak(f"Question {self.current_track} of {self.total_tracks} for {self.points_per_q} points.")
            self.play_current_track()

        self.play("Tunes\TB7L64W-winning.mp3")

        self.speak(f"You earned {self.points} points this game!")
        self.speak("Thank you for playing.")
        self.close()

    def speak(self, content: str) -> None:
        print(f"Speach: {content}")
        self.speachEngine.say(content)
        self.speachEngine.runAndWait()

    def get_category(self) -> str:
        p = list(self.playlists.keys())
        self.speak("Pick your category. You can say " + ", ".join(p[:-1]) + " or " + p[-1:][0])
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
            print("listening..")
            try:
                audio = self.recognizer.listen(source, timeout=15, phrase_time_limit=3)
            except:
                self.speak("Sorry! I didn't get that.")
                self.get_category()
            else:
                print("thinking..")
                try:
                    text: str = str(list((self.recognizer.recognize_google(audio, language="en-IN", show_all=True, with_confidence=True))["alternative"])[0]["transcript"])
                except:
                    self.speak("Sorry! I didn't get that.")
                    self.get_category()
                else:
                    text: str = text.lower()
                    if text == "stop":
                        return
                    if text in list(self.playlists.keys()):
                        self.category: str = text
                        self.speak("You picked " + text)
                        return self.category
                    else:
                        self.speak("Thats not a valid category.")
                        self.get_category()

    def get_spotify_access_token(self) -> str:
        spotifyClientId: str = os.getenv('SPOTCLIENT_ID')
        spotifyClientSecret: str = os.getenv('SPOTCLIENT_SECRET')
        spotifyCredentials: str = str(base64.b64encode(f"{spotifyClientId}:{spotifyClientSecret}".encode("ascii")).decode("ascii")) # f"{spotifyClientId}:{spotifyClientSecret}"

        authUrl: str = "https://accounts.spotify.com/api/token"
        authHeaders: dict = {
            "Authorization": f"Basic {spotifyCredentials}",
        }
        data = {
            "grant_type": "client_credentials",
        }
        r = requests.post(
            url = authUrl,
            headers = authHeaders,
            data = data,
        )
        if r.status_code != 200:
            print(r.text)
            raise RuntimeError()
        
        self.spotifyAccessToken: str = str(r.json()["access_token"])
        expires_in: int = int(r.json()["expires_in"])
        self.spotifyExpiry = (dt.utcnow() + td(seconds=int(expires_in)))

        self.spotifyHeaders = {
            "Authorization": "Bearer " + self.spotifyAccessToken,
            "Content-Type": "application/json",
        }

        return self.spotifyAccessToken

    @property
    def get_spotify_headers(self) -> dict:
        if self.spotifyExpiry <= dt.utcnow():
            self.get_spotify_access_token()
        return self.spotifyHeaders

    def get_spotify_tracks(self, spotifyPlaylistId: str, limit: int) -> list:
        headers = self.get_spotify_headers
        r = requests.get(
            url = self.baseSpotifyUrl + f"/playlists/{spotifyPlaylistId}/tracks" + "?fields=(items.track(uri, preview_url, artists(name), name))",
            headers = headers,
        )
        if r.status_code != 200:
            print(r.text)
            raise RuntimeError()
        
        content = r.json()
        d = json.loads(json.dumps(content, indent=4))["items"]
        tracks: list = list(choices(list(d), k=limit))

        for track in tracks:
            if track["track"]["preview_url"] is not None:
                self.tracks.append(track)

        remaining = self.total_tracks - len(self.tracks)
        if remaining != 0:
            self.get_spotify_tracks(spotifyPlaylistId, remaining)

        return self.tracks

    def play(self, url: str, duration: Optional[float] = None) -> bool:
        p = vlc.MediaPlayer(url)
        p.play()

        if duration is None:
            while not p.is_playing():
                sleep(0.0025)
            while p.is_playing():
                sleep(0.0025)
        else:
            sleep(duration)
            try:
                p.stop()
            except:
                pass

        return True

    def accuracy(self, a: str, b: str) -> float:
        return SequenceMatcher(None, str(a), str(b)).ratio()

    def filter(self, content: str) -> str:
        if "(" in content:
            content, _ = content.split("(", maxsplit=1)
        if "-" in content:
            content, _ = content.split("-", maxsplit=1)

        f = [",", "'", ":", "-", "+", ".", "?", "/", "_", "=", "(", ")", "*", "&", "^", "%", "$", "#", "@", "!", "{", "}", "[", "]", "\"", "|", ";", "<", ">", "`", "~", "\\", "’"]
        for c in f:
            content = content.replace(c, "")
        return content.strip()

    def play_current_track(self) -> None:
        url = str(self.tracks[(self.current_track-1)]["track"]["preview_url"])
        self.play(url, 10)

        name: str = self.filter(str(self.tracks[(self.current_track-1)]["track"]["name"]).lower())
        artist: str = self.filter(str(self.tracks[(self.current_track-1)]["track"]["artists"][0]["name"]).lower())

        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            print("listening..")
            try:
                audio = self.recognizer.listen(source, timeout=15, phrase_time_limit=5)
            except:
                self.speak("Playing the clip again.")
                self.play_current_track()
            else:
                print("thinking..")
                try:
                    answers: list = list((self.recognizer.recognize_google(audio, language="en-IN", show_all=True, with_confidence=True))["alternative"])
                    
                    if len(answers) > 2:
                        confidence: float = round(float(answers[0]["confidence"]), 1)
                        if confidence <= 0.6:
                            text = str(answers[1]["transcript"])
                        else:
                            text = str(answers[0]["transcript"])
                    else:
                        text = str(answers[0]["transcript"])
                    
                    text = text.lower()
                except:
                    self.speak("Sorry! I didn't get that.")
                    self.play_current_track()
                else:
                    if "repeat" in text:
                        self.speak("Playing the clip again.")
                        self.play_current_track()
                    elif "stop" in text:
                        self.current_track = None
                        return
                    else:
                        if not "skip" in text:
                            if "by" in text:
                                gname, gartist = text.split("by", maxsplit=1)
                            else:
                                gname = text
                                gartist = ""

                            gname = self.filter(gname)
                            gartist = self.filter(gartist)

                            cl = []
                            if gname != "" and gname in name:
                                if self.accuracy(name, gname) > self.title_accuracy:
                                    cl.append("title")
                            if gartist != "" and gartist in artist:
                                if self.accuracy(artist, gartist) > self.artist_accuracy:
                                    cl.append("artist")
                            
                            if len(cl) == 2:
                                self.points += (self.points_per_q + self.points_per_b)
                                self.play("Tunes\mixkit-video-game-win-2016.wav")
                                self.speak("You got the title and artist correct.")
                                self.speak(f"You earned {self.points_per_q} points plus an extra {self.points_per_b} bonus points.")
                            elif len(cl) == 1:
                                self.points += self.points_per_q
                                self.play("Tunes\mixkit-melodic-bonus-collect-1938.wav")
                                self.speak(f"You got the {cl[0]} correct.")
                                self.speak(f"You earned {self.points_per_q} points.")
                            else:
                                self.play("Tunes\VRT9U6F-incorrect-answer-fail.mp3")
                                self.speak("Incorrect.")

                        self.speak(f"The song was '{name}' by '{artist}'.")
                        self.speak(f"Your currently have {self.points} points.")
                        self.current_track += 1

Game().start(7)