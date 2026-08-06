#!/usr/bin/env python3
"""Turn a live agent-data capture into a fixture that can be committed.

The repo does not commit live posting text — .gitignore says so for eval output, and the same
holds here. What a fixture is FOR is the row shape, so the scrub keeps every key, every type,
every null, the row count, and the per-source date pattern, and replaces only what identifies a
real posting: company, title, the two ids, the URL, the description body, and the department and
team the opening sits in.

`department_name` and `team_name` are replaced because a live capture puts a company's internal
org chart in the fixture — "Nirvana", "Merchant Services", "CEO Office" name one employer even
after the company field is fictional. Which rows have them is a parser input, so a null stays null
and a filled field stays filled.

`salary_display` and `location_display` are deliberately left alone. Both are genuine parser
inputs: `skills/agent-data-reference/SKILL.md` records that `salary_display` is free text that
arrives as raw HTML on some rows, and a synthesised band would stop testing that.

A fractional-seconds part is dropped from `posted_at` and `published_at`. Microsecond precision is
a live value with nothing to test in it, and dropping it leaves the shape that tells the two
sources apart — Ashby sends no timezone, LinkedIn sends `+00:00` — exactly as it was.

Usage: python3 tests/fixtures/scrub.py raw.search.linkedin.json search.linkedin.json

The posting id is seeded with the source as well as the row number, so the same row number in two
fixtures does not get the same id. A test that reads two fixtures into one dict keyed by id —
test_posted_at_takes_whichever_date_field_the_source_filled does — would otherwise compare a
LinkedIn event against an Ashby row.

`data.pagination.next_cursor` is replaced rather than kept. The live cursor base64-encodes the
real keywords, the real location and the last real posting id of the page, so keeping it would
carry into the fixture the values the rest of this scrub takes out. Nothing in this repo decodes a
cursor; it is replayed as an opaque string, which is what the replacement is.
"""
import base64, hashlib, json, re, sys

COMPANIES = ["Globex", "Initech", "Umbrella Systems", "Northwind Labs", "Acme Robotics",
             "Vandelay Industries", "Soylent Foods", "Cyberdyne", "Wonka Industries", "Tyrell Corp"]
TITLES = ["Strategic Finance Manager", "Senior Financial Analyst", "Director, FP&A",
          "Finance Business Partner", "Corporate Development Associate"]
DEPARTMENTS = ["Finance", "Operations", "Corporate Development", "Business Operations",
               "Accounting", "Strategy"]
TEAMS = ["FP&A", "Treasury", "Strategic Finance", "Financial Planning", "Corporate Finance",
         "Revenue Finance"]

# Every character a JSON string can carry that the scanner and the event builder must survive.
HOSTILE = ('A role at the company. He said "it\'s a \\"strong\\" fit" — path C:\\temp, '
           'a {braced} phrase, a tab\there and a newline\nafter it.\n\n')

# Every scrubbed description is a prefix of this, cut to the length of the text it replaces, so a
# test can tell a scrubbed description from a live one without knowing how long the live one was.
BODY = HOSTILE + ("Responsibilities and requirements. " * 120)

# What a paging cursor becomes. A cursor is opaque everywhere in this repo — it is replayed, never
# read — so replacing it with one fixed value loses nothing a fixture was testing.
SCRUBBED_CURSOR = base64.urlsafe_b64encode(
    json.dumps({"scrubbed": True}).encode()).decode().rstrip("=")


def pick(seq, seed):
    return seq[int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(seq)]


def scrub_row(row, i):
    # Seeded with the source and the row number, both of which this function leaves alone, so the
    # scrub is stable from its first pass. Seeding off `source_id` — which line 3 below replaces —
    # made a re-run reseed every company and title off the already-scrubbed id, and re-scrubbing
    # moved 19 of 25 LinkedIn company names and 20 of 25 Ashby ones with nothing having asked for
    # it. The source is not scrubbed: it names a job board, not a posting.
    seed = "%s-%d" % (row.get("source", "src"), i)
    if "company_name" in row and row["company_name"] is not None:
        row["company_name"] = pick(COMPANIES, seed)
    if "title" in row and row["title"] is not None:
        row["title"] = pick(TITLES, seed + "t")
    for key, vocab in (("department_name", DEPARTMENTS), ("team_name", TEAMS)):
        if row.get(key):
            row[key] = pick(vocab, seed + key)
    for key in ("posted_at", "published_at"):
        if row.get(key):
            row[key] = re.sub(r"\.\d+", "", row[key])
    if row.get("source_id"):
        row["source_id"] = "%s-%04d" % (row.get("source", "src"), i)
    if row.get("id"):
        row["id"] = "jp_%s" % hashlib.sha256(seed.encode()).hexdigest()[:12]
    if row.get("source_url"):
        # Keep LinkedIn's tracking-parameter shape; it is a real parser input.
        tail = "?position=%d&pageNum=0&refId=AAAA%%3D%%3D" % (i + 1) if "?" in row["source_url"] else ""
        row["source_url"] = "https://example.invalid/jobs/%s%s" % (row["id"], tail)
    if row.get("description_markdown"):
        row["description_markdown"] = BODY[:len(row["description_markdown"])] or BODY
    if row.get("apply_url"):
        row["apply_url"] = "https://example.invalid/apply/%s" % row["id"]
    return row


def main(src, dst):
    doc = json.load(open(src, encoding="utf-8"))
    data = doc.get("data")
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        for i, row in enumerate(data["results"]):
            scrub_row(row, i)
        q = data.get("query") or {}
        for k in ("keywords", "location"):
            if q.get(k):
                q[k] = "scrubbed"
        page = data.get("pagination") or {}
        if page.get("next_cursor"):
            page["next_cursor"] = SCRUBBED_CURSOR
    elif isinstance(data, dict):
        scrub_row(data, 0)
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    # Case-insensitive: 13 of the 25 live Ashby URLs in one capture carry a capitalised company
    # segment (`jobs.ashbyhq.com/OpenAI/…`), which a case-sensitive `[a-z]` does not catch.
    assert not re.search(r"linkedin\.com/jobs/view|ashbyhq\.com/[a-z]", text, re.I), "an id survived"
    open(dst, "w", encoding="utf-8").write(text)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
