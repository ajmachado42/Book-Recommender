#!/usr/bin/env python3

from __future__ import annotations

import argparse
import difflib
import html
import math
import sys
from dataclasses import dataclass, field, replace
from urllib.parse import quote_plus

# --------------------------------------------------------------------------
# Rules for the catalog
# --------------------------------------------------------------------------
BOOK_CUTOFF_YEAR = 2010   # books must be published BEFORE this year
SHOW_WINDOW_START = 2016  # shows must have aired in 2016 or later


EMOTION_DIMS = ("joy", "sadness", "fear", "anger", "tension", "warmth", "humor", "hope")
DEFAULT_EMOTION_WEIGHT = 0.35  # share of the final score that comes from mood


@dataclass(frozen=True)
class Emotion:
    """Emotional fingerprint of a show or book.

    Eight feelings, each 0-1 (how strongly the work evokes it), plus:
      valence    -1 (bleak) .. +1 (uplifting): the overall sentiment
      intensity   0 (gentle) .. 1 (relentless): how hard it hits
    """
    joy: float
    sadness: float
    fear: float
    anger: float
    tension: float
    warmth: float
    humor: float
    hope: float
    valence: float
    intensity: float

    def vector(self) -> tuple[float, ...]:
        return tuple(getattr(self, d) for d in EMOTION_DIMS)

    @property
    def tone(self) -> str:
        """One word for the overall sentiment."""
        v = self.valence
        if v <= -0.6:
            return "bleak"
        if v <= -0.2:
            return "dark"
        if v < 0.2:
            return "mixed"
        if v < 0.6:
            return "light"
        return "uplifting"


@dataclass(frozen=True)
class Show:
    title: str
    first_aired: int
    last_aired: int | None          # None = still airing
    tags: dict[str, float]
    aliases: tuple[str, ...] = ()
    emotion: Emotion | None = None  # filled from SHOW_EMOTIONS if left out

    def in_window(self) -> bool:
        """True if the show aired at any point from 2016 to now."""
        return self.last_aired is None or self.last_aired >= SHOW_WINDOW_START


@dataclass(frozen=True)
class Book:
    title: str
    author: str
    year: int
    tags: dict[str, float]
    # Optional: pin a book to its exact Goodreads page, e.g. "50833" or
    # "50833.Valley_of_the_Dolls" (the part after /book/show/ in the URL).
    goodreads_id: str | None = None
    emotion: Emotion | None = None  # filled from BOOK_EMOTIONS if left out

    @property
    def goodreads_url(self) -> str:
        """Direct profile link if goodreads_id is set, else a title+author search."""
        if self.goodreads_id:
            return f"https://www.goodreads.com/book/show/{self.goodreads_id}"
        query = quote_plus(f"{self.title} {self.author}")
        return f"https://www.goodreads.com/search?q={query}"


# --------------------------------------------------------------------------
# Catalog: TV shows (2016-present)
# Tag weights run 0-1: how central that theme is to the show.
# Note: a few franchises began earlier but are still airing new seasons
# today, so they qualify (last_aired=None).
# --------------------------------------------------------------------------
SHOWS: list[Show] = [
    Show("Real Housewives", 2006, None,
         {"glamour": 1.0, "rivalry": 1.0, "gossip": 0.9, "friendship_betrayal": 0.9,
          "women": 0.8, "wealth": 0.8, "fame": 0.7, "scandal": 0.8, "excess": 0.8,
          "status": 0.6},
         ("The Real Housewives", "RHOBH", "RHONY", "RHOA", "RHOC", "RHOP", "RHOSLC")),
    Show("Succession", 2018, 2023,
         {"wealth": 1.0, "family": 1.0, "power": 1.0, "betrayal": 0.9, "ambition": 0.8,
          "satire": 0.8, "status": 0.7, "dark_comedy": 0.6, "corporate": 0.8}),
    Show("The White Lotus", 2021, None,
         {"wealth": 1.0, "satire": 0.9, "class": 0.9, "murder": 0.6, "travel": 0.8,
          "deception": 0.8, "status": 0.8, "dark_comedy": 0.7, "excess": 0.7}),
    Show("Bridgerton", 2020, None,
         {"romance": 1.0, "regency": 1.0, "society": 0.9, "marriage_market": 1.0,
          "gossip": 0.8, "women": 0.7, "family": 0.7, "status": 0.7}),
    Show("Stranger Things", 2016, None,
         {"supernatural": 1.0, "horror": 0.8, "small_town": 0.9, "kids": 1.0,
          "friendship": 0.9, "monsters": 0.9, "nostalgia": 0.8}),
    Show("Black Mirror", 2011, 2025,
         {"dystopia": 1.0, "technology": 1.0, "satire": 0.8, "surveillance": 0.8,
          "society": 0.7, "dark_comedy": 0.4, "anthology": 0.9}),
    Show("Westworld", 2016, 2022,
         {"artificial_intelligence": 1.0, "technology": 0.9, "consciousness": 1.0,
          "dystopia": 0.7, "theme_park": 0.8, "rebellion": 0.8, "science_fiction": 1.0}),
    Show("Game of Thrones", 2011, 2019,
         {"fantasy": 1.0, "power": 1.0, "war": 0.9, "family": 0.9, "betrayal": 0.9,
          "politics": 0.9, "dragons": 0.6, "epic": 1.0}),
    Show("The Crown", 2016, 2023,
         {"royalty": 1.0, "history": 1.0, "power": 0.8, "family": 0.8, "politics": 0.8,
          "duty": 0.9, "society": 0.6}),
    Show("Euphoria", 2019, None,
         {"teens": 1.0, "drugs": 1.0, "addiction": 0.9, "alienation": 0.8,
          "identity": 0.8, "excess": 0.8, "coming_of_age": 0.8}),
    Show("Mindhunter", 2017, 2019,
         {"serial_killers": 1.0, "crime": 0.9, "psychology": 1.0, "fbi": 0.8,
          "true_crime": 0.9, "procedural": 0.7}),
    Show("True Detective", 2014, None,
         {"crime": 1.0, "murder": 0.9, "noir": 0.9, "detectives": 1.0,
          "bleak": 0.8, "small_town": 0.6, "psychology": 0.6}),
    Show("Big Little Lies", 2017, 2019,
         {"suburbia": 1.0, "women": 1.0, "marriage": 0.9, "secrets": 0.9, "murder": 0.6,
          "domestic_abuse": 0.7, "friendship": 0.7, "wealth": 0.6, "gossip": 0.6}),
    Show("Yellowjackets", 2021, None,
         {"survival": 1.0, "teens": 0.8, "women": 0.8, "isolation": 0.9, "horror": 0.7,
          "savagery": 0.9, "trauma": 0.7}),
    Show("Squid Game", 2021, None,
         {"survival": 1.0, "death_games": 1.0, "class": 0.9, "dystopia": 0.7,
          "desperation": 0.9, "society": 0.6, "satire": 0.5}),
    Show("The Last of Us", 2023, None,
         {"post_apocalypse": 1.0, "survival": 1.0, "journey": 0.9, "parenthood": 0.8,
          "bleak": 0.8, "horror": 0.6, "plague": 0.9}),
    Show("Severance", 2022, None,
         {"corporate": 1.0, "dystopia": 0.9, "alienation": 1.0, "identity": 0.8,
          "surveillance": 0.7, "bureaucracy": 1.0, "absurdism": 0.8, "mystery": 0.7}),
    Show("Dark", 2017, 2020,
         {"time_travel": 1.0, "small_town": 0.8, "family": 0.8, "mystery": 0.9,
          "fate": 1.0, "science_fiction": 0.9, "bleak": 0.7}),
    Show("Only Murders in the Building", 2021, None,
         {"murder": 0.9, "mystery": 1.0, "whodunit": 1.0, "dark_comedy": 0.9,
          "ensemble": 0.8, "true_crime": 0.6}),
    Show("Killing Eve", 2018, 2022,
         {"assassin": 1.0, "obsession": 1.0, "cat_and_mouse": 1.0, "psychopath": 0.9,
          "women": 0.7, "dark_comedy": 0.6, "murder": 0.6}),
    Show("Slow Horses", 2022, None,
         {"espionage": 1.0, "intelligence": 1.0, "bureaucracy": 1.0, "betrayal": 0.9,
          "cover_up": 0.8, "politics": 0.8, "surveillance": 0.8, "pressure": 0.8,
          "dark_comedy": 0.7, "deception": 0.7, "duty": 0.7, "murder": 0.2},
         aliases=("Slow Horse",)),
    Show("You", 2018, 2025,
         {"obsession": 1.0, "stalking": 1.0, "psychopath": 0.9, "murder": 0.7,
          "dark_comedy": 0.5, "deception": 0.8, "unreliable_narrator": 0.9}),
    Show("Ozark", 2017, 2022,
         {"crime": 1.0, "family": 0.8, "money_laundering": 1.0, "cartel": 0.9,
          "moral_decay": 1.0, "bleak": 0.7}),
    Show("Peaky Blinders", 2013, 2022,
         {"crime": 1.0, "family": 0.9, "gangsters": 1.0, "power": 0.8, "history": 0.7,
          "loyalty": 0.8, "post_war": 0.8}),
    Show("The Marvelous Mrs. Maisel", 2017, 2023,
         {"comedy": 1.0, "women": 1.0, "ambition": 0.9, "showbiz": 1.0, "period": 0.8,
          "rivalry": 0.4, "fame": 0.7}),
    Show("Hacks", 2021, None,
         {"comedy": 0.9, "showbiz": 1.0, "women": 0.9, "mentorship": 1.0, "fame": 0.8,
          "rivalry": 0.6, "ambition": 0.8, "generation_gap": 0.8}),
    Show("Feud", 2017, None,
         {"showbiz": 1.0, "hollywood": 1.0, "rivalry": 1.0, "women": 0.9, "fame": 0.9,
          "history": 0.6, "glamour": 0.7, "scandal": 0.6}),
    Show("Selling Sunset", 2019, None,
         {"glamour": 1.0, "wealth": 0.9, "rivalry": 0.9, "gossip": 0.8, "women": 0.7,
          "ambition": 0.7, "status": 0.8}),
    Show("Emily in Paris", 2020, None,
         {"fashion": 1.0, "romance": 0.8, "ambition": 0.8, "workplace": 0.8,
          "glamour": 0.8, "women": 0.7, "travel": 0.6, "comedy": 0.6}),
    Show("Gossip Girl", 2007, 2023,
         {"teens": 0.8, "wealth": 1.0, "gossip": 1.0, "status": 0.9, "society": 0.9,
          "scandal": 0.8, "new_york": 0.9, "class": 0.7}),
    Show("Fleabag", 2016, 2019,
         {"comedy": 0.9, "women": 1.0, "grief": 0.9, "dark_comedy": 0.9,
          "unreliable_narrator": 0.7, "family": 0.6, "romance": 0.5, "self_destruction": 0.8}),
    Show("Schitt's Creek", 2015, 2020,
         {"comedy": 1.0, "family": 0.9, "wealth": 0.6, "fish_out_of_water": 1.0,
          "small_town": 0.9, "heartwarming": 1.0, "class": 0.6}),
    Show("Ted Lasso", 2020, 2023,
         {"heartwarming": 1.0, "comedy": 0.8, "sports": 0.9, "optimism": 1.0,
          "fish_out_of_water": 0.8, "workplace": 0.6, "friendship": 0.7}),
    Show("The Bear", 2022, None,
         {"food": 1.0, "workplace": 0.9, "family": 0.8, "chaos": 1.0, "grief": 0.7,
          "pressure": 1.0, "ambition": 0.7, "addiction": 0.3}),
    Show("Chernobyl", 2019, 2019,
         {"disaster": 1.0, "history": 0.9, "bureaucracy": 0.9, "cover_up": 1.0,
          "science": 0.8, "bleak": 0.8, "truth": 0.9}),
]

# --------------------------------------------------------------------------
# Catalog: Books (all published before 2010)
# --------------------------------------------------------------------------
BOOKS: list[Book] = [
    Book("Valley of the Dolls", "Jacqueline Susann", 1966,
         {"glamour": 1.0, "rivalry": 1.0, "friendship_betrayal": 1.0, "women": 1.0,
          "fame": 0.9, "scandal": 0.9, "excess": 0.9, "gossip": 0.8, "showbiz": 0.9,
          "drugs": 0.8, "ambition": 0.7, "hollywood": 0.6, "wealth": 0.6, "status": 0.6},
         goodreads_id="581811.Valley_of_the_Dolls"),
    Book("The Devil Wears Prada", "Lauren Weisberger", 2003,
         {"fashion": 1.0, "workplace": 1.0, "ambition": 0.9, "women": 0.8,
          "glamour": 0.8, "rivalry": 0.6, "new_york": 0.7, "comedy": 0.5}),
    Book("Bonfire of the Vanities", "Tom Wolfe", 1987,
         {"wealth": 1.0, "status": 1.0, "satire": 1.0, "new_york": 1.0, "class": 0.9,
          "scandal": 0.8, "power": 0.7, "excess": 0.8, "society": 0.8}),
    Book("The Great Gatsby", "F. Scott Fitzgerald", 1925,
         {"wealth": 1.0, "excess": 0.9, "class": 0.9, "society": 0.8, "romance": 0.7,
          "status": 0.8, "deception": 0.7, "new_york": 0.6, "moral_decay": 0.6}),
    Book("The Talented Mr. Ripley", "Patricia Highsmith", 1955,
         {"psychopath": 1.0, "deception": 1.0, "murder": 0.9, "wealth": 0.8, "obsession": 0.8,
          "travel": 0.7, "class": 0.7, "unreliable_narrator": 0.6, "identity": 0.7,
          "cat_and_mouse": 0.6}),
    Book("Death on the Nile", "Agatha Christie", 1937,
         {"murder": 1.0, "mystery": 1.0, "whodunit": 1.0, "wealth": 0.8, "travel": 0.9,
          "deception": 0.8, "status": 0.5}),
    Book("And Then There Were None", "Agatha Christie", 1939,
         {"murder": 1.0, "mystery": 1.0, "whodunit": 1.0, "isolation": 0.9,
          "ensemble": 0.9, "death_games": 0.6, "survival": 0.4}),
    Book("Pride and Prejudice", "Jane Austen", 1813,
         {"romance": 1.0, "marriage_market": 1.0, "regency": 1.0, "society": 1.0,
          "family": 0.8, "status": 0.8, "women": 0.8, "gossip": 0.6, "class": 0.7}),
    Book("Sense and Sensibility", "Jane Austen", 1811,
         {"romance": 1.0, "marriage_market": 0.9, "regency": 1.0, "women": 0.9,
          "family": 0.8, "status": 0.7, "society": 0.8}),
    Book("Emma", "Jane Austen", 1815,
         {"romance": 0.9, "marriage_market": 1.0, "regency": 1.0, "society": 0.9,
          "gossip": 0.8, "women": 0.8, "comedy": 0.6}),
    Book("Vanity Fair", "William Makepeace Thackeray", 1848,
         {"satire": 1.0, "ambition": 1.0, "society": 1.0, "status": 0.9, "regency": 0.8,
          "women": 0.7, "marriage_market": 0.7, "wealth": 0.7}),
    Book("The Age of Innocence", "Edith Wharton", 1920,
         {"society": 1.0, "new_york": 1.0, "status": 0.9, "romance": 0.8, "gossip": 0.8,
          "class": 0.8, "wealth": 0.7, "duty": 0.8, "marriage_market": 0.6}),
    Book("Nineteen Eighty-Four", "George Orwell", 1949,
         {"dystopia": 1.0, "surveillance": 1.0, "bureaucracy": 0.8, "truth": 0.9,
          "power": 0.8, "bleak": 0.9, "technology": 0.5}),
    Book("Brave New World", "Aldous Huxley", 1932,
         {"dystopia": 1.0, "technology": 0.9, "society": 0.8, "satire": 0.8,
          "science_fiction": 0.8, "identity": 0.6}),
    Book("Fahrenheit 451", "Ray Bradbury", 1953,
         {"dystopia": 1.0, "technology": 0.7, "surveillance": 0.6, "truth": 0.8,
          "society": 0.7, "science_fiction": 0.8}),
    Book("Do Androids Dream of Electric Sheep?", "Philip K. Dick", 1968,
         {"artificial_intelligence": 1.0, "consciousness": 1.0, "science_fiction": 1.0,
          "dystopia": 0.7, "post_apocalypse": 0.5, "technology": 0.8, "noir": 0.4}),
    Book("Frankenstein", "Mary Shelley", 1818,
         {"artificial_intelligence": 0.7, "consciousness": 0.9, "science_fiction": 0.8,
          "science": 0.9, "monsters": 0.9, "horror": 0.7, "isolation": 0.7}),
    Book("Jurassic Park", "Michael Crichton", 1990,
         {"theme_park": 1.0, "science": 0.9, "technology": 0.8, "survival": 0.8,
          "monsters": 0.8, "science_fiction": 0.8, "chaos": 0.6}),
    Book("A Game of Thrones", "George R. R. Martin", 1996,
         {"fantasy": 1.0, "power": 1.0, "war": 0.9, "family": 0.9, "politics": 1.0,
          "betrayal": 0.9, "epic": 1.0, "dragons": 0.5}),
    Book("The Count of Monte Cristo", "Alexandre Dumas", 1844,
         {"betrayal": 1.0, "revenge": 1.0, "wealth": 0.7, "power": 0.6, "deception": 0.8,
          "epic": 0.8, "justice": 0.7, "loyalty": 0.5, "crime": 0.4}),
    Book("The Godfather", "Mario Puzo", 1969,
         {"crime": 1.0, "family": 1.0, "gangsters": 1.0, "power": 0.9, "loyalty": 0.9,
          "betrayal": 0.8, "moral_decay": 0.6}),
    Book("No Country for Old Men", "Cormac McCarthy", 2005,
         {"crime": 1.0, "cartel": 0.9, "money_laundering": 0.5, "bleak": 1.0,
          "moral_decay": 0.8, "cat_and_mouse": 0.9, "small_town": 0.5, "murder": 0.7}),
    Book("In Cold Blood", "Truman Capote", 1966,
         {"true_crime": 1.0, "murder": 1.0, "crime": 0.9, "psychology": 0.9,
          "small_town": 0.8, "serial_killers": 0.4, "bleak": 0.6}),
    Book("The Silence of the Lambs", "Thomas Harris", 1988,
         {"serial_killers": 1.0, "fbi": 1.0, "psychology": 1.0, "psychopath": 0.9,
          "cat_and_mouse": 0.9, "crime": 0.9, "women": 0.6, "procedural": 0.6}),
    Book("Tinker Tailor Soldier Spy", "John le Carré", 1974,
         {"espionage": 1.0, "intelligence": 1.0, "betrayal": 1.0, "politics": 0.9,
          "surveillance": 0.8, "bureaucracy": 0.8, "mystery": 0.9, "deception": 0.9,
          "pressure": 0.7, "cover_up": 0.7, "duty": 0.6, "loyalty": 0.7}),
    Book("The Big Sleep", "Raymond Chandler", 1939,
         {"noir": 1.0, "detectives": 1.0, "crime": 0.9, "murder": 0.7, "bleak": 0.6,
          "wealth": 0.5, "deception": 0.7}),
    Book("The Revolutionary Road", "Richard Yates", 1961,
         {"suburbia": 1.0, "marriage": 1.0, "secrets": 0.6, "bleak": 0.8,
          "moral_decay": 0.6, "women": 0.5, "alienation": 0.8}),
    Book("The Stepford Wives", "Ira Levin", 1972,
         {"suburbia": 1.0, "women": 1.0, "marriage": 0.8, "secrets": 0.9,
          "science_fiction": 0.5, "satire": 0.7, "horror": 0.5, "murder": 0.4}),
    Book("Lord of the Flies", "William Golding", 1954,
         {"survival": 1.0, "savagery": 1.0, "isolation": 1.0, "teens": 0.8, "kids": 0.9,
          "society": 0.7, "bleak": 0.7}),
    Book("Battle Royale", "Koushun Takami", 1999,
         {"death_games": 1.0, "survival": 1.0, "teens": 0.9, "dystopia": 0.8,
          "desperation": 0.8, "savagery": 0.7}),
    Book("The Road", "Cormac McCarthy", 2006,
         {"post_apocalypse": 1.0, "survival": 1.0, "journey": 1.0, "parenthood": 1.0,
          "bleak": 1.0}),
    Book("I Am Legend", "Richard Matheson", 1954,
         {"post_apocalypse": 1.0, "plague": 1.0, "survival": 0.9, "isolation": 0.9,
          "horror": 0.7, "monsters": 0.8}),
    Book("It", "Stephen King", 1986,
         {"horror": 1.0, "kids": 1.0, "small_town": 1.0, "friendship": 1.0,
          "monsters": 1.0, "supernatural": 0.9, "nostalgia": 0.7}),
    Book("The Shining", "Stephen King", 1977,
         {"horror": 1.0, "supernatural": 0.9, "isolation": 1.0, "addiction": 0.6,
          "family": 0.6, "kids": 0.4}),
    Book("The Trial", "Franz Kafka", 1925,
         {"bureaucracy": 1.0, "absurdism": 1.0, "alienation": 1.0, "corporate": 0.5,
          "dystopia": 0.6, "identity": 0.5, "mystery": 0.4}),
    Book("Bartleby, the Scrivener", "Herman Melville", 1853,
         {"workplace": 0.8, "bureaucracy": 0.8, "alienation": 1.0, "absurdism": 0.7,
          "corporate": 0.6, "new_york": 0.5}),
    Book("Slaughterhouse-Five", "Kurt Vonnegut", 1969,
         {"time_travel": 1.0, "war": 0.9, "fate": 1.0, "science_fiction": 0.8,
          "trauma": 0.8, "dark_comedy": 0.8, "absurdism": 0.8, "satire": 0.7}),
    Book("The Time Machine", "H. G. Wells", 1895,
         {"time_travel": 1.0, "science_fiction": 1.0, "class": 0.7, "dystopia": 0.6,
          "science": 0.6, "fate": 0.4}),
    Book("American Psycho", "Bret Easton Ellis", 1991,
         {"psychopath": 1.0, "satire": 0.9, "wealth": 0.8, "murder": 0.8, "new_york": 0.8,
          "excess": 0.9, "unreliable_narrator": 0.9, "obsession": 0.6, "dark_comedy": 0.7}),
    Book("Less Than Zero", "Bret Easton Ellis", 1985,
         {"teens": 1.0, "drugs": 1.0, "wealth": 0.8, "excess": 1.0, "alienation": 1.0,
          "addiction": 0.8, "hollywood": 0.6}),
    Book("The Catcher in the Rye", "J. D. Salinger", 1951,
         {"teens": 1.0, "alienation": 1.0, "coming_of_age": 1.0, "identity": 0.8,
          "new_york": 0.7, "unreliable_narrator": 0.6}),
    Book("The Bell Jar", "Sylvia Plath", 1963,
         {"women": 1.0, "self_destruction": 1.0, "identity": 0.8, "alienation": 0.8,
          "new_york": 0.5, "unreliable_narrator": 0.6, "coming_of_age": 0.6}),
    Book("Lolita", "Vladimir Nabokov", 1955,
         {"obsession": 1.0, "unreliable_narrator": 1.0, "psychopath": 0.6,
          "deception": 0.8, "travel": 0.7, "stalking": 0.5, "dark_comedy": 0.4}),
    Book("Bridget Jones's Diary", "Helen Fielding", 1996,
         {"comedy": 1.0, "women": 1.0, "romance": 0.9, "self_destruction": 0.4,
          "workplace": 0.5, "unreliable_narrator": 0.4}),
    Book("Postcards from the Edge", "Carrie Fisher", 1987,
         {"showbiz": 1.0, "hollywood": 1.0, "addiction": 0.9, "women": 0.8,
          "comedy": 0.8, "fame": 0.9, "family": 0.6, "dark_comedy": 0.7}),
    Book("Kitchen Confidential", "Anthony Bourdain", 2000,
         {"food": 1.0, "chaos": 1.0, "workplace": 1.0, "pressure": 1.0, "addiction": 0.7,
          "new_york": 0.6, "comedy": 0.4}),
    Book("Anne of Green Gables", "L. M. Montgomery", 1908,
         {"heartwarming": 1.0, "optimism": 1.0, "fish_out_of_water": 0.9,
          "small_town": 0.9, "kids": 0.7, "family": 0.8, "coming_of_age": 0.7}),
    Book("Cold Comfort Farm", "Stella Gibbons", 1932,
         {"comedy": 1.0, "fish_out_of_water": 1.0, "family": 0.9, "satire": 0.9,
          "small_town": 0.8, "heartwarming": 0.5}),
    Book("Wolf Hall", "Hilary Mantel", 2009,
         {"royalty": 1.0, "history": 1.0, "power": 1.0, "politics": 1.0,
          "ambition": 0.8, "duty": 0.5}),
    Book("Voices from Chernobyl", "Svetlana Alexievich", 2005,
         {"disaster": 1.0, "history": 0.8, "truth": 1.0, "cover_up": 0.7,
          "bleak": 0.8, "bureaucracy": 0.5, "science": 0.4}),
    Book("The Moonstone", "Wilkie Collins", 1868,
         {"mystery": 1.0, "detectives": 0.9, "whodunit": 0.9, "society": 0.5,
          "ensemble": 0.6}),
    Book("Rebecca", "Daphne du Maurier", 1938,
         {"secrets": 1.0, "marriage": 1.0, "wealth": 0.7, "murder": 0.6, "women": 0.8,
          "obsession": 0.7, "mystery": 0.8, "class": 0.6}),
]

# --------------------------------------------------------------------------
# Emotional weights
# Column order:
#   joy, sadness, fear, anger, tension, warmth, humor, hope, valence, intensity
# The eight feelings run 0-1, valence runs -1 (bleak) to +1 (uplifting), and
# intensity runs 0 (gentle) to 1 (relentless). Edit these to retune the mood.
# --------------------------------------------------------------------------
SHOW_EMOTIONS: dict[str, Emotion] = {k: Emotion(*v) for k, v in {
    "Real Housewives":              (.4, .3, .1, .7, .6, .2, .6, .2, -0.1, .70),
    "Succession":                   (.1, .5, .2, .8, .8, .1, .6, .1, -0.6, .80),
    "The White Lotus":              (.3, .4, .3, .5, .7, .1, .7, .1, -0.3, .60),
    "Bridgerton":                   (.7, .3, .1, .3, .5, .8, .5, .7,  0.6, .60),
    "Stranger Things":              (.5, .5, .8, .4, .8, .7, .4, .7,  0.2, .80),
    "Black Mirror":                 (.1, .6, .7, .5, .8, .1, .3, .1, -0.7, .80),
    "Westworld":                    (.1, .6, .6, .6, .8, .1, .1, .3, -0.4, .80),
    "Game of Thrones":              (.2, .7, .7, .8, .9, .2, .2, .2, -0.6, .95),
    "The Crown":                    (.2, .6, .2, .4, .5, .4, .1, .3, -0.1, .50),
    "Euphoria":                     (.3, .8, .6, .6, .8, .2, .2, .2, -0.5, .90),
    "Mindhunter":                   (.0, .5, .6, .4, .8, .1, .1, .1, -0.6, .70),
    "True Detective":               (.0, .8, .6, .5, .8, .1, .0, .1, -0.7, .80),
    "Big Little Lies":              (.2, .7, .5, .7, .8, .5, .4, .3, -0.3, .80),
    "Yellowjackets":                (.1, .7, .9, .7, .9, .2, .2, .1, -0.7, .90),
    "Squid Game":                   (.1, .8, .8, .7, .95, .2, .1, .3, -0.7, .95),
    "The Last of Us":               (.2, .9, .8, .5, .8, .8, .1, .6, -0.3, .90),
    "Severance":                    (.1, .6, .5, .4, .8, .2, .4, .4, -0.3, .60),
    "Dark":                         (.0, .8, .6, .3, .8, .3, .0, .2, -0.6, .80),
    "Only Murders in the Building": (.5, .3, .2, .1, .5, .7, .9, .6,  0.5, .40),
    "Killing Eve":                  (.3, .3, .5, .5, .8, .1, .8, .2, -0.2, .70),
    "Slow Horses":                 (.1, .5, .4, .5, .8, .1, .7, .2, -0.4, .70),
    "You":                          (.1, .3, .7, .5, .9, .1, .5, .0, -0.6, .70),
    "Ozark":                        (.0, .6, .7, .6, .9, .2, .2, .1, -0.7, .80),
    "Peaky Blinders":               (.1, .6, .5, .8, .8, .3, .1, .2, -0.5, .85),
    "The Marvelous Mrs. Maisel":    (.8, .3, .0, .2, .3, .7, .9, .8,  0.7, .50),
    "Hacks":                        (.5, .4, .1, .4, .4, .6, .9, .6,  0.4, .50),
    "Feud":                         (.2, .6, .1, .8, .6, .1, .4, .1, -0.4, .60),
    "Selling Sunset":               (.5, .2, .0, .5, .4, .2, .6, .3,  0.1, .50),
    "Emily in Paris":               (.8, .1, .0, .1, .2, .5, .7, .8,  0.7, .40),
    "Gossip Girl":                  (.4, .4, .1, .6, .5, .3, .5, .3, -0.1, .60),
    "Fleabag":                      (.3, .8, .2, .5, .5, .5, .9, .4,  0.0, .80),
    "Schitt's Creek":               (.8, .3, .0, .1, .2, .95, .95, .9, 0.9, .50),
    "Ted Lasso":                    (.8, .4, .0, .1, .3, .95, .8, .95, 0.9, .50),
    "The Bear":                     (.2, .7, .5, .7, .95, .5, .4, .4, -0.1, .95),
    "Chernobyl":                    (.0, .9, .8, .7, .9, .2, .0, .1, -0.8, .90),
}.items()}

BOOK_EMOTIONS: dict[str, Emotion] = {k: Emotion(*v) for k, v in {
    "Valley of the Dolls":                 (.3, .6, .2, .7, .6, .2, .4, .2, -0.3, .70),
    "The Devil Wears Prada":               (.5, .2, .1, .5, .5, .3, .8, .5,  0.3, .50),
    "Bonfire of the Vanities":             (.1, .4, .3, .7, .7, .0, .7, .0, -0.5, .70),
    "The Great Gatsby":                    (.3, .9, .2, .4, .5, .3, .1, .2, -0.5, .60),
    "The Talented Mr. Ripley":             (.1, .4, .7, .3, .9, .0, .1, .0, -0.6, .70),
    "Death on the Nile":                   (.2, .3, .4, .4, .7, .2, .3, .4,  0.0, .50),
    "And Then There Were None":            (.0, .4, .8, .4, .95, .0, .1, .1, -0.6, .70),
    "Pride and Prejudice":                 (.8, .2, .0, .3, .5, .8, .8, .9,  0.8, .50),
    "Sense and Sensibility":               (.6, .6, .0, .3, .5, .8, .6, .8,  0.6, .50),
    "Emma":                                (.7, .2, .0, .2, .4, .8, .9, .8,  0.7, .40),
    "Vanity Fair":                         (.3, .5, .1, .5, .5, .2, .9, .2, -0.2, .50),
    "The Age of Innocence":                (.2, .9, .0, .4, .6, .5, .2, .2, -0.4, .60),
    "Nineteen Eighty-Four":                (.0, .8, .8, .7, .8, .1, .1, .1, -0.9, .90),
    "Brave New World":                     (.2, .6, .4, .4, .6, .1, .5, .1, -0.4, .60),
    "Fahrenheit 451":                      (.1, .6, .6, .7, .7, .2, .1, .5, -0.4, .70),
    "Do Androids Dream of Electric Sheep?": (.0, .7, .6, .4, .7, .2, .2, .3, -0.4, .60),
    "Frankenstein":                        (.1, .9, .8, .6, .7, .2, .0, .1, -0.7, .80),
    "Jurassic Park":                       (.3, .2, .8, .3, .9, .1, .4, .5,  0.1, .80),
    "A Game of Thrones":                   (.2, .7, .7, .8, .9, .2, .3, .2, -0.5, .90),
    "The Count of Monte Cristo":           (.4, .7, .3, .8, .8, .4, .2, .6,  0.0, .80),
    "The Godfather":                       (.1, .6, .5, .7, .8, .5, .1, .1, -0.5, .80),
    "No Country for Old Men":              (.0, .7, .8, .4, .95, .0, .2, .0, -0.9, .80),
    "In Cold Blood":                       (.0, .8, .7, .5, .8, .1, .0, .0, -0.8, .70),
    "The Silence of the Lambs":            (.0, .4, .9, .4, .95, .1, .1, .4, -0.6, .80),
    "Tinker Tailor Soldier Spy":            (.0, .5, .6, .4, .9, .1, .2, .2, -0.5, .70),
    "The Big Sleep":                       (.0, .5, .4, .4, .7, .0, .5, .1, -0.4, .50),
    "The Revolutionary Road":              (.0, .9, .2, .8, .7, .0, .1, .0, -0.9, .80),
    "The Stepford Wives":                  (.1, .5, .8, .5, .8, .0, .3, .1, -0.6, .70),
    "Lord of the Flies":                   (.1, .8, .9, .7, .8, .0, .0, .1, -0.8, .80),
    "Battle Royale":                       (.0, .8, .9, .8, .95, .2, .1, .3, -0.8, .95),
    "The Road":                            (.0, .95, .8, .3, .8, .8, .0, .4, -0.7, .80),
    "I Am Legend":                         (.0, .9, .8, .4, .8, .3, .0, .2, -0.7, .70),
    "It":                                  (.3, .5, .95, .5, .9, .7, .2, .5, -0.3, .90),
    "The Shining":                         (.0, .6, .95, .7, .95, .1, .0, .1, -0.8, .90),
    "The Trial":                           (.0, .6, .6, .5, .7, .0, .4, .0, -0.6, .50),
    "Bartleby, the Scrivener":             (.0, .8, .1, .1, .4, .1, .3, .0, -0.5, .30),
    "Slaughterhouse-Five":                 (.1, .8, .3, .5, .4, .3, .8, .2, -0.3, .60),
    "The Time Machine":                    (.1, .6, .6, .2, .6, .2, .0, .4, -0.2, .50),
    "American Psycho":                     (.0, .2, .7, .7, .8, .0, .7, .0, -0.8, .90),
    "Less Than Zero":                      (.1, .9, .4, .4, .5, .0, .2, .0, -0.8, .60),
    "The Catcher in the Rye":              (.1, .8, .1, .7, .3, .3, .5, .2, -0.4, .50),
    "The Bell Jar":                        (.0, .95, .4, .5, .5, .1, .3, .1, -0.8, .80),
    "Lolita":                              (.1, .7, .4, .3, .6, .1, .6, .0, -0.6, .70),
    "Bridget Jones's Diary":               (.7, .3, .0, .2, .2, .8, .95, .8, 0.7, .40),
    "Postcards from the Edge":             (.4, .5, .1, .5, .4, .5, .9, .5,  0.2, .60),
    "Kitchen Confidential":                (.4, .3, .2, .6, .8, .4, .8, .4,  0.2, .90),
    "Anne of Green Gables":                (.9, .4, .0, .1, .2, .95, .7, .95, 0.95, .50),
    "Cold Comfort Farm":                   (.5, .2, .0, .3, .3, .5, .95, .7, 0.5, .30),
    "Wolf Hall":                           (.1, .6, .4, .5, .8, .2, .3, .2, -0.2, .60),
    "Voices from Chernobyl":               (.0, .95, .7, .7, .7, .4, .0, .2, -0.8, .90),
    "The Moonstone":                       (.2, .2, .3, .2, .6, .3, .4, .5,  0.2, .40),
    "Rebecca":                             (.1, .7, .8, .4, .9, .2, .0, .3, -0.5, .70),
}.items()}

# --------------------------------------------------------------------------
# Editor's picks: guaranteed pairings that always rank first.
# --------------------------------------------------------------------------
EDITORS_PICKS: dict[str, list[str]] = {
    "Real Housewives": ["Valley of the Dolls"],
    "Succession": ["Bonfire of the Vanities"],
    "Bridgerton": ["Pride and Prejudice"],
    "Black Mirror": ["Nineteen Eighty-Four"],
    "Squid Game": ["Battle Royale"],
    "Stranger Things": ["It"],
    "The Bear": ["Kitchen Confidential"],
    "Severance": ["The Trial"],
    "Slow Horses": ["Tinker Tailor Soldier Spy"],
}


# --------------------------------------------------------------------------
# Recommender
# --------------------------------------------------------------------------
def make_link(text: str, url: str, fmt: str) -> str:
    """Render a hyperlink for the chosen output format.

    terminal -> clickable OSC 8 link (iTerm2, VS Code, Windows Terminal, GNOME, etc.)
    markdown -> [text](url)
    html     -> <a> tag that opens in a new browser tab
    text     -> text (url)
    """
    if fmt == "terminal":
        return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"
    if fmt == "markdown":
        return f"[{text}]({url})"
    if fmt == "html":
        return (f'<a href="{html.escape(url)}" target="_blank" '
                f'rel="noopener noreferrer">{html.escape(text)}</a>')
    return f"{text} ({url})"


@dataclass
class Recommendation:
    show: Show
    book: Book
    score: float
    editors_pick: bool = False
    shared_themes: list[str] = field(default_factory=list)
    theme_score: float = 0.0
    emotion_score: float | None = None   # None if either side has no profile
    shared_emotions: list[str] = field(default_factory=list)

    @property
    def mood_pct(self) -> int | None:
        return None if self.emotion_score is None else round(self.emotion_score * 100)

    @property
    def sentiment_line(self) -> str | None:
        if not (self.show.emotion and self.book.emotion):
            return None
        return f"{self.show.emotion.tone} show, {self.book.emotion.tone} book"

    def sentence(self) -> str:
        return (f"If you like {self.show.title}, "
                f"then you'll love {self.book.title} by {self.book.author}.")

    def linked_sentence(self, fmt: str = "markdown") -> str:
        """Same sentence, with the book (title + author) linked to Goodreads."""
        book = make_link(f"{self.book.title} by {self.book.author}",
                         self.book.goodreads_url, fmt)
        return f"If you like {self.show.title}, then you'll love {book}."


class BookRecommender:
    def __init__(self, shows: list[Show] = SHOWS, books: list[Book] = BOOKS,
                 emotion_weight: float = DEFAULT_EMOTION_WEIGHT):
        if not 0.0 <= emotion_weight <= 1.0:
            raise ValueError("emotion_weight must be between 0 and 1")
        self.emotion_weight = emotion_weight

        # Attach emotional profiles (an Emotion set directly on the entry wins).
        shows = [s if s.emotion else replace(s, emotion=SHOW_EMOTIONS.get(s.title))
                 for s in shows]
        books = [b if b.emotion else replace(b, emotion=BOOK_EMOTIONS.get(b.title))
                 for b in books]

        # Enforce the catalog rules up front so bad data fails loudly.
        bad_books = [b.title for b in books if b.year >= BOOK_CUTOFF_YEAR]
        if bad_books:
            raise ValueError(f"Books must be published before {BOOK_CUTOFF_YEAR}: {bad_books}")
        bad_shows = [s.title for s in shows if not s.in_window()]
        if bad_shows:
            raise ValueError(f"Shows must have aired in {SHOW_WINDOW_START} or later: {bad_shows}")

        self.shows = {s.title: s for s in shows}
        self.books = {b.title: b for b in books}
        self._lookup = self._build_lookup(shows)
        self._idf = self._compute_idf(books)
        self._emotion_mean = self._mean_emotion(books)

    # ---- show lookup (case-insensitive, aliases, typo tolerant) ----------
    @staticmethod
    def _build_lookup(shows: list[Show]) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for s in shows:
            lookup[s.title.lower()] = s.title
            for alias in s.aliases:
                lookup[alias.lower()] = s.title
        return lookup

    def find_show(self, query: str) -> Show | None:
        q = query.strip().lower()
        if q.startswith("the ") and q not in self._lookup:
            q_no_the = q[4:]
        else:
            q_no_the = q
        for candidate in (q, q_no_the, "the " + q):
            if candidate in self._lookup:
                return self.shows[self._lookup[candidate]]
        close = difflib.get_close_matches(q, self._lookup.keys(), n=1, cutoff=0.75)
        return self.shows[self._lookup[close[0]]] if close else None

    def suggest_shows(self, query: str, n: int = 5) -> list[str]:
        close = difflib.get_close_matches(query.lower(), self._lookup.keys(), n=n, cutoff=0.4)
        seen: list[str] = []
        for c in close:
            title = self._lookup[c]
            if title not in seen:
                seen.append(title)
        return seen

    # ---- scoring ---------------------------------------------------------
    @staticmethod
    def _compute_idf(books: list[Book]) -> dict[str, float]:
        """Rare tags get a higher weight than tags that appear on many books."""
        n = len(books)
        df: dict[str, int] = {}
        for b in books:
            for tag in b.tags:
                df[tag] = df.get(tag, 0) + 1
        return {tag: math.log((1 + n) / (1 + count)) + 1 for tag, count in df.items()}

    def _vector(self, tags: dict[str, float]) -> dict[str, float]:
        return {t: w * self._idf.get(t, 1.0) for t, w in tags.items()}

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        dot = sum(a[t] * b[t] for t in a.keys() & b.keys())
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    @staticmethod
    def _mean_emotion(books: list[Book]) -> tuple[float, ...]:
        """Average feeling profile of the library, used as the 'neutral' baseline."""
        vecs = [b.emotion.vector() for b in books if b.emotion]
        if not vecs:
            return (0.0,) * len(EMOTION_DIMS)
        return tuple(sum(col) / len(vecs) for col in zip(*vecs))

    def _emotion_match(self, a: Emotion, b: Emotion) -> tuple[float, list[str]]:
        """Emotional similarity, 0-1, plus the feelings both works share strongly.

        Blend of three parts:
          60%  feeling profile (cosine, measured against the library's average
               mood so that what is distinctive about each work is what counts)
          25%  sentiment (how close the bleak-to-uplifting scores are)
          15%  intensity (how close the gentle-to-relentless scores are)
        """
        va = [x - m for x, m in zip(a.vector(), self._emotion_mean)]
        vb = [x - m for x, m in zip(b.vector(), self._emotion_mean)]
        na = math.sqrt(sum(x * x for x in va))
        nb = math.sqrt(sum(x * x for x in vb))
        feelings = max(0.0, sum(x * y for x, y in zip(va, vb)) / (na * nb)) if na and nb else 0.0
        sentiment = 1 - abs(a.valence - b.valence) / 2
        intensity = 1 - abs(a.intensity - b.intensity)
        score = 0.60 * feelings + 0.25 * sentiment + 0.15 * intensity

        both = {d: min(getattr(a, d), getattr(b, d)) for d in EMOTION_DIMS}
        shared = [d for d in sorted(both, key=both.get, reverse=True) if both[d] >= 0.5]
        return score, shared[:2]

    def recommend(self, show_query: str, n: int = 3) -> list[Recommendation]:
        show = self.find_show(show_query)
        if show is None:
            return []

        w = self.emotion_weight
        show_vec = self._vector(show.tags)
        scored: dict[str, Recommendation] = {}
        for book in self.books.values():
            theme = self._cosine(show_vec, self._vector(book.tags))
            shared = sorted(
                show.tags.keys() & book.tags.keys(),
                key=lambda t: show.tags[t] * book.tags[t],
                reverse=True,
            )
            emo, shared_emo, score = None, [], theme
            if show.emotion and book.emotion:
                emo, shared_emo = self._emotion_match(show.emotion, book.emotion)
                score = (1 - w) * theme + w * emo
            scored[book.title] = Recommendation(
                show, book, score, False, shared[:3], theme, emo, shared_emo)

        # Editor's picks are always first, regardless of computed score.
        picks: list[Recommendation] = []
        for title in EDITORS_PICKS.get(show.title, []):
            if title in scored:
                rec = scored.pop(title)
                rec.editors_pick = True
                picks.append(rec)

        rest = sorted(scored.values(), key=lambda r: r.score, reverse=True)
        return (picks + [r for r in rest if r.score > 0])[:n]


# --------------------------------------------------------------------------
# Command line interface
# --------------------------------------------------------------------------
def render_html(results: list[Recommendation]) -> str:
    """A standalone web page. Every Goodreads link opens in a new tab."""
    esc = html.escape

    def sentence(r: Recommendation) -> str:
        book = make_link(f"{r.book.title} by {r.book.author}", r.book.goodreads_url, "html")
        return f"If you like {esc(r.show.title)}, then you'll love {book}."

    top = results[0]
    themes = ", ".join(t.replace("_", " ") for t in top.shared_themes)
    def mood(r: Recommendation) -> str:
        return f" · {r.mood_pct}% emotional match" if r.mood_pct is not None else ""

    more = "\n".join(
        f'      <li>{sentence(r)} <span class="muted">({r.book.year}{mood(r)})</span></li>'
        for r in results[1:]
    )
    if top.mood_pct is not None:
        feels = f" (shared: {esc(', '.join(top.shared_emotions))})" if top.shared_emotions else ""
        mood_line = (f'\n    <p class="muted">Emotional match: {top.mood_pct}%{feels} · '
                     f'Sentiment: {esc(top.sentiment_line or "")}</p>')
    else:
        mood_line = ""
    more_block = f"\n    <h2>More picks</h2>\n    <ul>\n{more}\n    </ul>" if more else ""
    themes_line = f'\n    <p class="muted">Shared themes: {esc(themes)}</p>' if themes else ""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Book recommendations for {esc(top.show.title)}</title>
  <style>
    body {{ font: 18px/1.5 Georgia, serif; max-width: 42rem; margin: 3rem auto; padding: 0 1rem; }}
    h2 {{ font-size: 1rem; text-transform: uppercase; letter-spacing: .05em; margin-top: 2rem; }}
    .top {{ font-size: 1.4rem; }}
    .muted {{ color: #666; font-size: .9rem; }}
    li {{ margin-bottom: .5rem; }}
  </style>
</head>
<body>
  <main>
    <p class="top">{sentence(top)}</p>
    <p class="muted">Published {top.book.year}</p>{themes_line}{mood_line}{more_block}
  </main>
</body>
</html>"""


def print_recommendations(rec: BookRecommender, query: str, n: int,
                          fmt: str = "markdown") -> bool:
    results = rec.recommend(query, n)
    if not results:
        print(f"Sorry, I don't have '{query}' yet.")
        hints = rec.suggest_shows(query)
        if hints:
            print("Did you mean: " + ", ".join(hints) + "?")
        return False

    if fmt == "html":
        print(render_html(results))
        return True

    top = results[0]
    print(top.linked_sentence(fmt))
    print(f"   Published {top.book.year}")
    if fmt == "terminal":
        # Fallback for terminals that don't render clickable links.
        print(f"   Goodreads: {top.book.goodreads_url}")
    if top.shared_themes:
        print("   Shared themes: " + ", ".join(t.replace("_", " ") for t in top.shared_themes))
    if top.mood_pct is not None:
        feels = f"  (shared: {', '.join(top.shared_emotions)})" if top.shared_emotions else ""
        print(f"   Emotional match: {top.mood_pct}%{feels}")
        print(f"   Sentiment: {top.sentiment_line}")

    if len(results) > 1:
        print("\nMore picks:")
        for r in results[1:]:
            mood = f" · {r.mood_pct}% emotional match" if r.mood_pct is not None else ""
            print(f"  - {r.linked_sentence(fmt)}  ({r.book.year}{mood})")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recommend pre-2010 books from modern TV shows.")
    parser.add_argument("show", nargs="*", help="TV show title (aired 2016-present)")
    parser.add_argument("-n", "--num", type=int, default=3, help="number of books to recommend")
    parser.add_argument("--list", action="store_true", help="list supported TV shows")
    parser.add_argument(
        "--format", choices=["auto", "terminal", "markdown", "text", "html"], default="auto",
        help="how to show Goodreads links: clickable terminal links, markdown, plain "
             "text, or a web page whose links open in a new tab (html; needs a show "
             "title). Default: terminal if run in a terminal, else markdown")
    parser.add_argument(
        "--emotion-weight", type=float, default=DEFAULT_EMOTION_WEIGHT, metavar="W",
        help="how much mood (feelings, sentiment, intensity) counts versus themes, "
             f"from 0 to 1 (default {DEFAULT_EMOTION_WEIGHT}; 0 = themes only)")
    args = parser.parse_args(argv)
    if not 0.0 <= args.emotion_weight <= 1.0:
        parser.error("--emotion-weight must be between 0 and 1")
    fmt = args.format
    if fmt == "auto":
        fmt = "terminal" if sys.stdout.isatty() else "markdown"
    if fmt == "html" and not args.show:
        parser.error("--format html needs a show title, e.g. "
                     "python book_recommender.py \"Hacks\" --format html > recs.html")

    rec = BookRecommender(emotion_weight=args.emotion_weight)

    if args.list:
        for title in sorted(rec.shows):
            print(title)
        return 0

    if args.show:
        return 0 if print_recommendations(rec, " ".join(args.show), args.num, fmt) else 1

    print("TV-to-Book Recommendation Machine  (type 'list' to see shows, 'quit' to exit)")
    while True:
        try:
            query = input("\nWhat TV show do you like? ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not query:
            continue
        if query.lower() in {"quit", "exit", "q"}:
            return 0
        if query.lower() == "list":
            print(", ".join(sorted(rec.shows)))
            continue
        print()
        print_recommendations(rec, query, args.num, fmt)


if __name__ == "__main__":
    sys.exit(main())
