#!/usr/bin/env python3
"""Rebuild the Feather-compatible source files from their original sources.

Outputs (written next to this script):
  buildstore-feather-slim.json   Build Store, latest version only, short descriptions
  ipalibrary-feather.json        IPALibrary, cleaned
  iosgods-feather.json           iOSGods-tagged apps taken from Build Store

A source that fails to download is skipped and its old file is left untouched.
"""
import collections
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BUILDSTORE_URL = "https://raw.githubusercontent.com/drphe/KhoIPA/main/upload/repo.buildstore.json"
IPALIBRARY_URL = "https://raw.githubusercontent.com/2nkn0w/ipalibrary.me-source/main/ipalibrary_source.json"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "feather-source-updater"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def hexc(c):
    c = (c or "").strip()
    return c if (not c or c.startswith("#")) else "#" + c


def clean_buildstore(d):
    """Fix the things Feather's strict parser rejects, keep only latest version."""
    fallback_icon = d.get("iconURL", "")
    apps = []
    for a in d["apps"]:
        url = a["downloadURL"].strip().replace(" ", "%20")
        apps.append({
            "name": a["name"],
            "bundleIdentifier": a["bundleIdentifier"],
            "developerName": a.get("developerName") or "Unknown",
            "subtitle": a.get("subtitle", ""),
            "localizedDescription": (a.get("localizedDescription") or "")[:150],
            "iconURL": a.get("iconURL") or fallback_icon,
            "tintColor": hexc(a.get("tintColor")),
            "screenshotURLs": [],
            "beta": a.get("beta") is True,  # some entries had the string "xxx"
            "version": a["version"],
            "versionDate": a["versionDate"],
            "versionDescription": "",
            "size": a["size"],
            "downloadURL": url,
            "versions": [{
                "version": a["version"],
                "date": a["versionDate"],
                "size": a["size"],
                "downloadURL": url,
                "localizedDescription": "",
            }],
        })
    ids = {a["bundleIdentifier"] for a in apps}
    news = [{k: v for k, v in n.items() if v is not None} for n in d.get("news", [])]
    return {
        "name": d["name"],
        "identifier": d["identifier"],
        "subtitle": d.get("subtitle", ""),
        "description": d.get("description", ""),
        "iconURL": d.get("iconURL", ""),
        "website": d.get("website", ""),
        "sourceURL": d.get("sourceURL", ""),
        "tintColor": hexc(d.get("tintColor")),
        "featuredApps": [x for x in d.get("featuredApps", []) if x in ids],
        "apps": apps,
        "news": news,
    }


def clean_ipalibrary(d):
    """Fix bad URLs and duplicate bundle IDs, add the fields Feather expects."""
    seen = collections.Counter()
    apps = []
    for a in d["apps"]:
        url = a["downloadURL"].strip().replace(" ", "%20")
        bid = a["bundleIdentifier"]
        seen[bid] += 1
        if seen[bid] > 1:  # two different apps sharing one bundle ID
            bid = f"{bid}.{'plus' if '+' in a['name'] else 'v' + str(seen[bid])}"
        size = a.get("size", 0)
        apps.append({
            "name": a["name"],
            "bundleIdentifier": bid,
            "developerName": a.get("developerName") or "Unknown",
            "subtitle": "",
            "localizedDescription": a.get("localizedDescription", ""),
            "iconURL": (a.get("iconURL") or d.get("iconURL", "")).strip().replace(" ", "%20"),
            "tintColor": "#3c2474",
            "screenshotURLs": [],
            "beta": False,
            "version": a["version"],
            "versionDate": a["versionDate"],
            "versionDescription": "",
            "size": size,
            "downloadURL": url,
            "versions": [{
                "version": a["version"],
                "date": a["versionDate"],
                "size": size,
                "downloadURL": url,
                "localizedDescription": "",
            }],
        })
    return {
        "name": d["name"],
        "identifier": d["identifier"],
        # the original puts a timestamp here, which would change the file every run
        "subtitle": "Custom AltStore source for IPALibrary apps",
        "description": "Custom AltStore source for IPALibrary apps.",
        "iconURL": d.get("iconURL", ""),
        "website": d.get("website", ""),
        "tintColor": "#3c2474",
        "featuredApps": [],
        "apps": apps,
        "news": [],
    }


def iosgods_subset(slim):
    sub = dict(slim)
    sub["apps"] = [a for a in slim["apps"] if "iosgods" in a["developerName"].lower()]
    sub.update({
        "name": "iOSGods (via Build Store)",
        "identifier": "io.build.store.iosgods",
        "subtitle": "iOSGods-tagged apps from the Build Store catalog",
        "description": "Subset of the Build Store source: apps listed under the iOSGods.com developer.",
        "featuredApps": [],
        "news": [],
    })
    sub.pop("sourceURL", None)
    return sub


def write(name, data):
    path = os.path.join(HERE, name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)
    print(f"wrote {name}: {len(data['apps'])} apps, {os.path.getsize(path) / 1e6:.1f} MB")


def main():
    failed = False

    try:
        slim = clean_buildstore(fetch(BUILDSTORE_URL))
        if not slim["apps"]:
            raise ValueError("Build Store source had no apps")
        write("buildstore-feather-slim.json", slim)
        sub = iosgods_subset(slim)
        if sub["apps"]:
            write("iosgods-feather.json", sub)
    except Exception as e:
        failed = True
        print(f"ERROR Build Store: {e}", file=sys.stderr)

    try:
        lib = clean_ipalibrary(fetch(IPALIBRARY_URL))
        if not lib["apps"]:
            raise ValueError("IPALibrary source had no apps")
        ids = [a["bundleIdentifier"] for a in lib["apps"]]
        assert len(ids) == len(set(ids)), "duplicate bundle IDs"
        write("ipalibrary-feather.json", lib)
    except Exception as e:
        failed = True
        print(f"ERROR IPALibrary: {e}", file=sys.stderr)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
