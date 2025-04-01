#!/usr/bin/env python3
"""
munge.py

This script takes data/collected-chicago-street-centerlines.csv and created a munged version
and a simplified JSON that can be thrown into a webapp for a quick demo (e.g. docs/index.html)

The raw collected data is a bit messy, with multiple records/coordinates for the same intersection.

munge.py naively dedupes the records to produce a small file of ~24,000 unique intersections
"""


import csv
from pathlib import Path
import re
from collections import defaultdict
from dateutil import parser as dateparser
import json
from sys import stderr

READ_PATH = Path("data/collected-chicago-street-centerlines.csv")
WRIT_PATH = Path("data/munged-chicago-intersections.csv")
WRIT_JSON_PATH = Path("docs/static/chicago-intersections.json")

STREETSORTKEY = ("N", "S", "W", "E")
OUTPUT_HEADERS = (
    "intersection",
    "street_1",
    "street_2",
    "zipcode",
    "longitude",
    "latitude",
)


def normalize_string(txt):
    return re.sub(r"\s+", " ", txt).strip()


def sortkey_street_record(sname: str) -> tuple:
    """
    when sorting which street should come first in a pair, we sort by cardinal direction and then the street name
    """
    return (STREETSORTKEY.index(sname[0]), sname)


def extract_coord_pairs(txt: str, sigdigits=5) -> list[tuple[float]]:
    """
    convert a MULTILINESTRING text string into lng, lat float pairs
    e.g.
    MULTILINESTRING ((-87.66068257500989 41.88418745060361, -87.66107301637707 41.88418175252413))
    """
    datastring = txt.replace("MULTILINESTRING ((", "").replace("))", "")
    coords = []
    for p in datastring.split(","):
        # Split by whitespace and convert to float
        x_str, y_str = p.strip().split(" ")
        coords.append([round(float(x_str), sigdigits), round(float(y_str), sigdigits)])
    return coords


def clean_records(records: list[dict]) -> list[dict]:
    cdata = []

    def make_mainstreet(row: dict) -> str:
        """
        concatenates the street direction, name, and type field to create a single name, e.g.
        "N CLARK ST"
        """
        streetname = " ".join(row[c] for c in ["PRE_DIR", "STREET_NAM", "STREET_TYP"])
        return normalize_string(streetname)

    for row in records:
        d = {}
        d["mainstreet_id"] = int(row["STREETNAME"])
        d["xstreet_id"] = int(row["F_CROSS_ST"])

        # remove all records where the subject street nor its first cross street has
        # an id less than 2
        if d["xstreet_id"] >= 2 and d["mainstreet_id"] >= 2:
            d["mainstreet"] = make_mainstreet(row)

            points = extract_coord_pairs(row["the_geom"])
            d["longitude"], d["latitude"] = points[0]
            d["zipcode"] = row["R_ZIP"]
            d["object_id"] = row["OBJECTID"]  # for debugging
            d["shape_length"] = float(row["SHAPE_LEN"])
            d["updated_at"] = dateparser.parse(row["UPDATE_TIM"]).isoformat()
            cdata.append(d)
    return cdata


def build_street_id_to_name_lookup(data: list[dict]) -> dict[int, str]:
    """
    create a simple lookup matchiing numerical street ids to street names.
    we use this to fill out "xstreet" (i.e. cross street name) using xstreet_id
    """
    lookuptable = {}
    for row in data:
        lookuptable[row["mainstreet_id"]] = row["mainstreet"]
    return lookuptable


def main():
    outdata = defaultdict(list)

    with open(READ_PATH) as rf:
        rawdata = list(csv.DictReader(rf))

    stderr.write(f"Raw records: {len(rawdata)}\n")

    cdata = clean_records(rawdata)
    stderr.write(f"Cleaned records with valid x-street ids: {len(cdata)}\n")

    # create a look up of mainstreet names and their ids
    streetlookup = build_street_id_to_name_lookup(cdata)
    for d in cdata:
        xid = d["xstreet_id"]
        mname = streetlookup.get(xid)
        if not mname:
            # if xstreet_id isn't among the mainstreet_ids, then we just ignore it
            pass
        else:
            d["xstreet"] = mname
            # the database contains records for when a street and its pair are mainstreet/xstreet and vice versa
            # e.g. "N CLARK ST" & "W DIVERSEY AVE",  "W DIVERSEY AVE" & "N CLARK ST"
            # we normalize the pair to: "N CLARK ST & W DIVERSEY AVE"
            d["street_1"], d["street_2"] = sorted(
                [d["xstreet"], d["mainstreet"]], key=lambda q: sortkey_street_record(q)
            )

            d["intersection"] = normalize_string(
                " & ".join([d["street_1"], d["street_2"]])
            )
            outdata[d["intersection"]].append(d)

    # for various reasons, there are more than one set of coordinates for each street intersection
    # so we arbitrarily choose the first value, sorted on the most recently updated, and then the longest
    outdata = sorted(
        [
            sorted(v, key=lambda q: (q["updated_at"], q["shape_length"]), reverse=True)[
                0
            ]
            for v in outdata.values()
        ],
        key=lambda r: sortkey_street_record(r["intersection"]),
    )

    print(len(outdata), "de-duped intersections")

    WRIT_PATH.parent.mkdir(exist_ok=True, parents=True)
    with open(WRIT_PATH, "w") as wf:
        wcsv = csv.DictWriter(wf, fieldnames=OUTPUT_HEADERS, extrasaction="ignore")
        wcsv.writeheader()
        wcsv.writerows(outdata)
        stderr.write(f"Wrote munged CSV to:\n{WRIT_PATH}\n")

    WRIT_JSON_PATH.parent.mkdir(exist_ok=True, parents=True)
    # trim it for json
    jdata = [
        {k: v for k, v in row.items() if k in ("intersection", "longitude", "latitude")}
        for row in outdata
    ]
    with open(WRIT_JSON_PATH, "w") as wf:
        json.dump(jdata, wf, sort_keys=True, indent=0)
        stderr.write(f"Wrote simplified JSON to:\n{WRIT_JSON_PATH}\n")


if __name__ == "__main__":
    main()
