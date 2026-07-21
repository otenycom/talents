#!/usr/bin/env python3
"""maplink — the deterministic map-deeplink builder for OtenyTravelTalent.

Every "getting somewhere" reply MUST end with a real, tappable map link, because the
deeplink hands the traveller authoritative LIVE routing in their own map app — the source
of truth even when the bot's prose is wrong. But URL-encoding place names and assembling
query strings by hand is exactly the fiddly task the weak runtime model (Gemini-Flash) gets
subtly wrong (a missing %2C, a dropped param, a malformed slug). So — like preflight.py and
monitor_transport.py — the error-prone step lives in a deterministic SCRIPT, never the model:

    python3 ~/.hermes/skills/talents/oteny-travel-talent/scripts/maplink.py \
        --origin "OLVG Oost, Amsterdam" --destination "Haarlemmermeerstraat 6, Amsterdam" \
        --mode transit

It prints ready-to-paste links (one per line, ``LABEL: <url>``):

  * **Google Maps** (universal, no key, every platform) — path form so mobile
    Universal Links cannot drop origin/destination:
    https://www.google.com/maps/dir/<enc-origin>/<enc-destination>/?travelmode=<mode>
  * **9292** (the NL authoritative timetable + live delays) — only for an NL trip:
    https://9292.nl/reisadvies/<van-slug>/<naar-slug>
  * **9292 live departures board** ("when's the next one?") — printed for the destination
    stop when --mode transit:  https://9292.nl/locaties/<stop-slug>/departures
  * **Apple Maps** — OFF by default. Printed ONLY when --apple is passed (a stored
    iPhone-user preference in memory.md/overrides.md sets it via the ADJUST flow). Google
    (+ 9292 for NL) are the day-one default; never auto-detect the platform.

HARD CONSTRAINTS (encoded here + guarded by a test):
  * NEVER emit a Routes/OVapi/JSON/key-bearing/server-side URL to a user — those are
    server-side and would leak a credential. This script only ever builds CONSUMER deeplinks.
  * NEVER claim a *departure time* inside a link — no consumer deeplink scheme supports it.
    Say the time in TEXT and tell the user to adjust in-app; the link only carries the route.

Pure / stdlib-only / read-only / side-effect-free. Exit code is always 0 (a non-zero would
make the LLM's terminal call look failed); the links are in the output.
"""
from __future__ import annotations

import argparse
import re
import sys
from urllib.parse import quote

# Google's travelmode vocabulary (the only modes the dir/ deeplink accepts). We map our
# own {transit, walking, driving} 1:1 — an unknown mode falls back to transit (the OV core).
_GOOGLE_MODES = {"transit": "transit", "walking": "walking", "driving": "driving"}


def google_dir(origin: str, destination: str, mode: str) -> str:
    """The universal, key-free Google Maps directions deeplink (every platform).

    Path form — origin and destination ride in the URL path, not ``?api=1&origin=&destination=``
    query params. Telegram → Google Maps on iOS/Android hands the URL to the Maps app via
    Universal Links; that handoff has been observed to drop the query string, leaving an
    empty directions form (prod 2026-07-21: ``dir/<coords>//@…`` with blank dest). Path
    segments survive. Place names are percent-encoded with NO safe chars (``,`` → ``%2C``,
    space → ``%20``, ``/`` → ``%2F`` so a slash in an address cannot split the path). Travel
    mode stays a query param Google's web+app both honour when the query survives; when it
    doesn't, origin/dest still open and Maps picks a sensible default mode.
    """
    travelmode = _GOOGLE_MODES.get(mode, "transit")
    o = quote(origin.strip(), safe="")
    d = quote(destination.strip(), safe="")
    return (f"https://www.google.com/maps/dir/{o}/{d}/"
            f"?travelmode={travelmode}")


def apple_dir(origin: str, destination: str, mode: str) -> str:
    """The Apple Maps directions deeplink — emitted ONLY on an explicit --apple opt-in.

    Uses the modern ``directions?source=&destination=&mode=`` form (the legacy
    ``daddr=lat,lng`` is broken on iOS 18.4+). Mode maps transit->transit, walking->walking,
    driving->driving."""
    o = quote(origin.strip(), safe="")
    d = quote(destination.strip(), safe="")
    mode = mode if mode in ("transit", "walking", "driving") else "transit"
    return (f"https://maps.apple.com/directions?source={o}&destination={d}&mode={mode}")


def slugify_place(place: str) -> str:
    """A 9292 location slug for a free-text place.

    9292's web routes key locations by a human-readable slug. We build the two slug shapes
    9292 uses, deterministically from the words the tenant gave (never invented):

      * a numbered street address -> ``adres-<street>-<number>-<city>``
        ("Haarlemmermeerstraat 6, Amsterdam" -> ``adres-haarlemmermeerstraat-6-amsterdam``)
      * anything else (a station / stop / POI name) -> ``station-<name>``
        ("Amsterdam Centraal" -> ``station-amsterdam-centraal``;
         "OLVG Oost, Amsterdam" -> ``station-olvg-oost-amsterdam``)

    Lowercased; every run of non-alphanumerics collapses to a single ``-``; leading/trailing
    ``-`` trimmed. A street address is detected by a street-name followed by a house number,
    optionally then a city after a comma."""
    raw = place.strip()
    # Split off a trailing ", City" if present (kept as part of the slug tail either way).
    city = ""
    head = raw
    if "," in raw:
        head, _, city = raw.partition(",")
        head, city = head.strip(), city.strip()
    # Address shape: "<street words> <number>" (number may carry a letter suffix, e.g. 26a).
    m = re.match(r"^(.*?\S)\s+(\d+[a-zA-Z]?)$", head)
    if m:
        street, number = m.group(1), m.group(2)
        parts = ["adres", street, number]
        if city:
            parts.append(city)
        return _slug("-".join(parts))
    # Otherwise a named stop/station/POI.
    name = head if not city else f"{head} {city}"
    return _slug(f"station-{name}")


def _slug(text: str) -> str:
    """Lowercase, collapse non-alphanumerics to single ``-``, trim ``-`` ends."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return s.strip("-")


def nine292_route(origin: str, destination: str) -> str:
    """The 9292 door-to-door reisadvies (route advice) deeplink for an NL trip."""
    return (f"https://9292.nl/reisadvies/{slugify_place(origin)}/"
            f"{slugify_place(destination)}")


def nine292_departures(stop: str) -> str:
    """The 9292 live-departures board for a stop — the honest answer to 'when's the next
    one?' (a real board, never a fabricated 'next at 08:51')."""
    return f"https://9292.nl/locaties/{slugify_place(stop)}/departures"


def build_links(*, origin: str, destination: str, mode: str, nl: bool = True,
                apple: bool = False) -> list[tuple[str, str]]:
    """The ordered (label, url) deeplinks for one route question. Google always; 9292
    route + departures for an NL trip; Apple only on opt-in. Never a server-side URL."""
    links: list[tuple[str, str]] = [("Google Maps", google_dir(origin, destination, mode))]
    if nl:
        links.append(("9292 (NL)", nine292_route(origin, destination)))
        if mode == "transit":
            # The live board for the DESTINATION stop answers "when does it come?".
            links.append(("9292 live departures",
                          nine292_departures(destination)))
    if apple:
        links.append(("Apple Maps", apple_dir(origin, destination, mode)))
    return links


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Deterministic map-deeplink builder for OtenyTravelTalent")
    ap.add_argument("--origin", required=True, help="origin place name (free text)")
    ap.add_argument("--destination", required=True, help="destination place name")
    ap.add_argument("--mode", default="transit",
                    choices=["transit", "walking", "driving"], help="travel mode")
    nl = ap.add_mutually_exclusive_group()
    nl.add_argument("--nl", dest="nl", action="store_true", default=True,
                    help="include the NL 9292 links (default)")
    nl.add_argument("--no-nl", dest="nl", action="store_false",
                    help="non-NL trip — Google only")
    ap.add_argument("--apple", action="store_true",
                    help="also emit an Apple Maps link (set only when the iPhone-user "
                         "preference is recorded in memory.md/overrides.md)")
    args = ap.parse_args(argv)

    links = build_links(origin=args.origin, destination=args.destination,
                        mode=args.mode, nl=args.nl, apple=args.apple)
    for label, url in links:
        print(f"{label}: {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
