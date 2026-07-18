#!/usr/bin/env python
"""Seed the catalog with a small demo dataset — no API keys required.

Inserts a set of well-known shows with hand-authored script features (the
kind the LLM extraction pipeline would produce), embeds them, and indexes
them in ChromaDB. Useful for trying the app, demos, and running the
evaluation harness before ingesting real transcripts.

Usage:
    python scripts/seed_demo.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.db import show_store, user_store, vector_store  # noqa: E402
from backend.models.schemas import ScriptFeatures, ShowInfo  # noqa: E402
from backend.pipeline.embed import embed_text, features_to_text  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Hand-authored demo features approximating what LLM extraction produces.
DEMO_SHOWS = [
    {
        "id": "succession",
        "title": "Succession",
        "year": 2018,
        "network": "HBO",
        "genres": ["Drama", "Comedy"],
        "overview": "The Roy family controls one of the biggest media conglomerates in the world — and is at war over who will run it next.",
        "features": {
            "themes": ["power", "family dysfunction", "wealth", "betrayal", "succession"],
            "tone": ["dark", "satirical", "acidic", "tense"],
            "humor_type": ["dry wit", "cruel insult comedy", "absurdist"],
            "dialogue_style": ["rapid-fire", "profanity-laced", "overlapping", "corporate jargon"],
            "emotional_register": ["restrained", "explosive", "wounded"],
            "pacing": "fast",
            "genre_blend": ["drama", "dark comedy", "corporate thriller"],
            "narrative_structure": "serialized",
            "vocabulary_complexity": "dense",
            "style_summary": "Acid-tongued corporate power struggle where love is expressed through insults and betrayal is a family tradition.",
        },
    },
    {
        "id": "billions",
        "title": "Billions",
        "year": 2016,
        "network": "Showtime",
        "genres": ["Drama"],
        "overview": "A hedge fund king and a U.S. attorney wage a cat-and-mouse war of wealth, influence and power in New York finance.",
        "features": {
            "themes": ["power", "wealth", "ambition", "rivalry", "loyalty"],
            "tone": ["slick", "tense", "swaggering"],
            "humor_type": ["dry wit", "pop-culture riffing"],
            "dialogue_style": ["rapid-fire", "reference-dense", "corporate jargon"],
            "emotional_register": ["controlled", "competitive"],
            "pacing": "fast",
            "genre_blend": ["drama", "financial thriller"],
            "narrative_structure": "serialized",
            "vocabulary_complexity": "dense",
            "style_summary": "Testosterone-fueled finance chess match told in dense, reference-packed power talk.",
        },
    },
    {
        "id": "veep",
        "title": "Veep",
        "year": 2012,
        "network": "HBO",
        "genres": ["Comedy"],
        "overview": "Former Senator Selina Meyer becomes Vice President and discovers the job is nothing like she expected.",
        "features": {
            "themes": ["political ambition", "incompetence", "ego", "power"],
            "tone": ["cynical", "farcical", "acidic"],
            "humor_type": ["cruel insult comedy", "profane wordplay", "cringe"],
            "dialogue_style": ["rapid-fire", "profanity-laced", "overlapping", "improvisational"],
            "emotional_register": ["manic", "exasperated"],
            "pacing": "fast",
            "genre_blend": ["political satire", "comedy"],
            "narrative_structure": "serialized",
            "vocabulary_complexity": "moderate",
            "style_summary": "Machine-gun political satire built on baroque profanity and gleeful institutional incompetence.",
        },
    },
    {
        "id": "the_thick_of_it",
        "title": "The Thick of It",
        "year": 2005,
        "network": "BBC",
        "genres": ["Comedy"],
        "overview": "Satire of the inner workings of British government, centered on the ferocious spin doctor Malcolm Tucker.",
        "features": {
            "themes": ["political spin", "incompetence", "media", "power"],
            "tone": ["cynical", "farcical", "abrasive"],
            "humor_type": ["cruel insult comedy", "profane wordplay", "cringe"],
            "dialogue_style": ["rapid-fire", "profanity-laced", "improvisational", "overlapping"],
            "emotional_register": ["manic", "furious"],
            "pacing": "fast",
            "genre_blend": ["political satire", "mockumentary-adjacent comedy"],
            "narrative_structure": "episodic",
            "vocabulary_complexity": "moderate",
            "style_summary": "Handheld Whitehall farce where creative swearing is elevated to poetry and everyone is one leak from ruin.",
        },
    },
    {
        "id": "the_office",
        "title": "The Office",
        "year": 2005,
        "network": "NBC",
        "genres": ["Comedy"],
        "overview": "A mockumentary about the everyday lives of office employees at the Dunder Mifflin paper company in Scranton, Pennsylvania.",
        "features": {
            "themes": ["workplace tedium", "friendship", "romance", "self-delusion"],
            "tone": ["warm", "awkward", "observational"],
            "humor_type": ["cringe", "observational", "deadpan talking heads"],
            "dialogue_style": ["naturalistic", "interview asides", "awkward pauses"],
            "emotional_register": ["earnest", "vulnerable"],
            "pacing": "variable",
            "genre_blend": ["mockumentary", "comedy", "romance"],
            "narrative_structure": "episodic",
            "vocabulary_complexity": "simple",
            "style_summary": "Mockumentary cringe comedy that hides real warmth under awkward silences and to-camera glances.",
        },
    },
    {
        "id": "parks_and_recreation",
        "title": "Parks and Recreation",
        "year": 2009,
        "network": "NBC",
        "genres": ["Comedy"],
        "overview": "Mockumentary following the tireless Leslie Knope and the Parks Department of Pawnee, Indiana.",
        "features": {
            "themes": ["optimism", "civic duty", "friendship", "small-town life"],
            "tone": ["warm", "earnest", "goofy"],
            "humor_type": ["observational", "character-driven absurdism", "deadpan talking heads"],
            "dialogue_style": ["naturalistic", "interview asides", "quotable one-liners"],
            "emotional_register": ["earnest", "buoyant"],
            "pacing": "fast",
            "genre_blend": ["mockumentary", "comedy"],
            "narrative_structure": "episodic",
            "vocabulary_complexity": "simple",
            "style_summary": "Sunny mockumentary where relentless optimism and small-town absurdity power dense, kind-hearted jokes.",
        },
    },
    {
        "id": "breaking_bad",
        "title": "Breaking Bad",
        "year": 2008,
        "network": "AMC",
        "genres": ["Drama", "Crime"],
        "overview": "A terminally ill chemistry teacher partners with a former student to build a methamphetamine empire.",
        "features": {
            "themes": ["moral descent", "pride", "family", "consequences", "transformation"],
            "tone": ["tense", "bleak", "simmering"],
            "humor_type": ["gallows humor", "situational irony"],
            "dialogue_style": ["sparse", "loaded silences", "monologue-heavy"],
            "emotional_register": ["restrained", "explosive"],
            "pacing": "slow-burn",
            "genre_blend": ["crime drama", "thriller", "tragedy"],
            "narrative_structure": "serialized",
            "vocabulary_complexity": "moderate",
            "style_summary": "Slow-burn tragedy of an ordinary man's corruption, told in taut silences that detonate into violence.",
        },
    },
    {
        "id": "better_call_saul",
        "title": "Better Call Saul",
        "year": 2015,
        "network": "AMC",
        "genres": ["Drama", "Crime"],
        "overview": "The trials of small-time lawyer Jimmy McGill as he becomes the morally flexible Saul Goodman.",
        "features": {
            "themes": ["moral descent", "brotherhood", "identity", "self-sabotage"],
            "tone": ["melancholic", "tense", "wry"],
            "humor_type": ["gallows humor", "con-man charm"],
            "dialogue_style": ["monologue-heavy", "courtroom rhetoric", "loaded silences"],
            "emotional_register": ["restrained", "wounded"],
            "pacing": "slow-burn",
            "genre_blend": ["crime drama", "legal drama", "tragedy"],
            "narrative_structure": "serialized",
            "vocabulary_complexity": "moderate",
            "style_summary": "Patient, mournful character study where charm curdles into corruption one small compromise at a time.",
        },
    },
    {
        "id": "ozark",
        "title": "Ozark",
        "year": 2017,
        "network": "Netflix",
        "genres": ["Drama", "Crime"],
        "overview": "A financial adviser drags his family to the Missouri Ozarks, where he must launder money for a drug cartel.",
        "features": {
            "themes": ["moral descent", "family under threat", "money", "survival"],
            "tone": ["bleak", "cold", "tense"],
            "humor_type": ["gallows humor"],
            "dialogue_style": ["clipped", "transactional", "loaded silences"],
            "emotional_register": ["restrained", "desperate"],
            "pacing": "slow-burn",
            "genre_blend": ["crime drama", "thriller"],
            "narrative_structure": "serialized",
            "vocabulary_complexity": "moderate",
            "style_summary": "Ice-cold family crime spiral told in muted blues and transactional, dread-soaked conversations.",
        },
    },
    {
        "id": "fleabag",
        "title": "Fleabag",
        "year": 2016,
        "network": "BBC",
        "genres": ["Comedy", "Drama"],
        "overview": "A dry-witted woman navigates grief, family, and love in London while confiding directly in the audience.",
        "features": {
            "themes": ["grief", "guilt", "family", "desire", "faith"],
            "tone": ["dark", "confessional", "melancholic", "wickedly funny"],
            "humor_type": ["dry wit", "fourth-wall asides", "self-deprecating"],
            "dialogue_style": ["direct-address", "rapid-fire", "naturalistic"],
            "emotional_register": ["vulnerable", "deflecting"],
            "pacing": "fast",
            "genre_blend": ["dark comedy", "drama"],
            "narrative_structure": "serialized",
            "vocabulary_complexity": "moderate",
            "style_summary": "Confessional dark comedy that weaponizes fourth-wall winks to dodge — and finally face — grief.",
        },
    },
    {
        "id": "russian_doll",
        "title": "Russian Doll",
        "year": 2019,
        "network": "Netflix",
        "genres": ["Comedy", "Drama", "Sci-Fi"],
        "overview": "Nadia keeps dying and reliving her 36th birthday party in an existential time loop.",
        "features": {
            "themes": ["mortality", "trauma", "self-destruction", "connection"],
            "tone": ["dark", "wry", "existential"],
            "humor_type": ["dry wit", "self-deprecating", "absurdist"],
            "dialogue_style": ["rapid-fire", "raspy monologue", "naturalistic"],
            "emotional_register": ["deflecting", "vulnerable"],
            "pacing": "fast",
            "genre_blend": ["dark comedy", "sci-fi", "drama"],
            "narrative_structure": "serialized",
            "vocabulary_complexity": "moderate",
            "style_summary": "Existential time-loop comedy narrated in a whiskey growl, where jokes are armor against trauma.",
        },
    },
    {
        "id": "black_mirror",
        "title": "Black Mirror",
        "year": 2011,
        "network": "Netflix",
        "genres": ["Sci-Fi", "Drama", "Thriller"],
        "overview": "An anthology exploring a twisted, high-tech near-future where humanity's greatest innovations collide with its darkest instincts.",
        "features": {
            "themes": ["technology", "surveillance", "alienation", "consequence"],
            "tone": ["bleak", "unsettling", "cerebral"],
            "humor_type": ["dark irony"],
            "dialogue_style": ["naturalistic", "concept-driven exposition"],
            "emotional_register": ["dread", "cold"],
            "pacing": "slow-burn",
            "genre_blend": ["sci-fi", "anthology", "thriller"],
            "narrative_structure": "anthology",
            "vocabulary_complexity": "moderate",
            "style_summary": "Idea-first anthology where every clever gadget arrives with a bleak twist about who we really are.",
        },
    },
    {
        "id": "severance",
        "title": "Severance",
        "year": 2022,
        "network": "Apple TV+",
        "genres": ["Sci-Fi", "Drama", "Thriller"],
        "overview": "Employees at Lumon Industries have their memories surgically divided between work and personal lives.",
        "features": {
            "themes": ["identity", "corporate control", "alienation", "grief"],
            "tone": ["eerie", "sterile", "deadpan", "unsettling"],
            "humor_type": ["deadpan", "dark irony"],
            "dialogue_style": ["stilted corporate speak", "measured", "loaded silences"],
            "emotional_register": ["suppressed", "dread"],
            "pacing": "slow-burn",
            "genre_blend": ["sci-fi", "corporate thriller", "mystery"],
            "narrative_structure": "serialized",
            "vocabulary_complexity": "moderate",
            "style_summary": "Sterile corporate uncanny — polite, procedural dialogue that makes existential horror feel like HR policy.",
        },
    },
    {
        "id": "community",
        "title": "Community",
        "year": 2009,
        "network": "NBC",
        "genres": ["Comedy"],
        "overview": "A disbarred lawyer enrolls at a community college and forms a misfit study group that becomes a found family.",
        "features": {
            "themes": ["found family", "identity", "pop culture", "belonging"],
            "tone": ["playful", "meta", "absurdist"],
            "humor_type": ["meta references", "parody", "absurdist", "joke-dense"],
            "dialogue_style": ["rapid-fire", "reference-dense", "quotable one-liners"],
            "emotional_register": ["earnest under irony"],
            "pacing": "fast",
            "genre_blend": ["sitcom", "parody"],
            "narrative_structure": "episodic",
            "vocabulary_complexity": "moderate",
            "style_summary": "Genre-hopping meta sitcom that deconstructs TV tropes while sneaking in real feeling.",
        },
    },
    {
        "id": "30_rock",
        "title": "30 Rock",
        "year": 2006,
        "network": "NBC",
        "genres": ["Comedy"],
        "overview": "Liz Lemon runs a live sketch show in New York while managing her eccentric star and mercurial network boss.",
        "features": {
            "themes": ["show business", "ambition", "workplace chaos"],
            "tone": ["zany", "satirical", "absurdist"],
            "humor_type": ["joke-dense", "absurdist", "cutaway gags", "wordplay"],
            "dialogue_style": ["rapid-fire", "reference-dense", "quotable one-liners"],
            "emotional_register": ["manic"],
            "pacing": "fast",
            "genre_blend": ["sitcom", "satire"],
            "narrative_structure": "episodic",
            "vocabulary_complexity": "moderate",
            "style_summary": "Joke-per-second showbiz satire with absurd cutaways and gleefully quotable nonsense.",
        },
    },
    {
        "id": "true_detective",
        "title": "True Detective",
        "year": 2014,
        "network": "HBO",
        "genres": ["Crime", "Drama", "Mystery"],
        "overview": "Anthology crime series following troubled detectives consumed by haunting cases.",
        "features": {
            "themes": ["obsession", "evil", "time", "redemption"],
            "tone": ["brooding", "philosophical", "gothic"],
            "humor_type": ["gallows humor"],
            "dialogue_style": ["monologue-heavy", "philosophical musings", "sparse"],
            "emotional_register": ["haunted", "restrained"],
            "pacing": "slow-burn",
            "genre_blend": ["crime drama", "mystery", "anthology"],
            "narrative_structure": "anthology",
            "vocabulary_complexity": "dense",
            "style_summary": "Swampy philosophical noir where detectives narrate the void between long silences.",
        },
    },
    {
        "id": "broadchurch",
        "title": "Broadchurch",
        "year": 2013,
        "network": "ITV",
        "genres": ["Crime", "Drama", "Mystery"],
        "overview": "The murder of a young boy tears apart a small English coastal town under the eyes of two mismatched detectives.",
        "features": {
            "themes": ["grief", "community", "secrets", "justice"],
            "tone": ["mournful", "atmospheric", "restrained"],
            "humor_type": ["dry wit"],
            "dialogue_style": ["naturalistic", "sparse", "loaded silences"],
            "emotional_register": ["grief-stricken", "restrained"],
            "pacing": "slow-burn",
            "genre_blend": ["crime drama", "mystery"],
            "narrative_structure": "serialized",
            "vocabulary_complexity": "simple",
            "style_summary": "Windswept small-town mystery where grief, not the whodunit, is the real subject.",
        },
    },
    {
        "id": "mad_men",
        "title": "Mad Men",
        "year": 2007,
        "network": "AMC",
        "genres": ["Drama"],
        "overview": "Ad executive Don Draper navigates the ruthless world of 1960s Madison Avenue advertising.",
        "features": {
            "themes": ["identity", "ambition", "gender", "the American dream"],
            "tone": ["elegant", "melancholic", "restrained"],
            "humor_type": ["dry wit", "period irony"],
            "dialogue_style": ["measured", "subtext-heavy", "pitch monologues"],
            "emotional_register": ["repressed", "yearning"],
            "pacing": "slow-burn",
            "genre_blend": ["period drama", "character study"],
            "narrative_structure": "serialized",
            "vocabulary_complexity": "dense",
            "style_summary": "Immaculately tailored period drama where everything important goes unsaid until a pitch meeting says it for them.",
        },
    },
]


def main() -> None:
    show_store.init_db()
    user_store.init_db()

    for entry in DEMO_SHOWS:
        features = ScriptFeatures(show_title=entry["title"], **entry["features"])
        show = ShowInfo(
            id=entry["id"],
            title=entry["title"],
            year=entry["year"],
            network=entry["network"],
            genres=entry["genres"],
            overview=entry["overview"],
            num_episodes_analyzed=1,
            features=features,
        )
        show_store.upsert_show(show)

        text = features_to_text(features.model_dump(exclude={"show_title", "season", "episode"}))
        embedding = embed_text(text)
        vector_store.upsert_show(
            entry["id"],
            embedding,
            {"title": entry["title"], "year": entry["year"], "style_summary": features.style_summary},
        )
        logger.info(f"Seeded {entry['title']}")

    logger.info(f"Done — {show_store.get_show_count()} shows in catalog.")


if __name__ == "__main__":
    main()
