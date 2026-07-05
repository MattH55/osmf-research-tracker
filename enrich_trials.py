import json
import random

with open("clinical_trials/data/clinical_trials_current.json") as f:
    data = json.load(f)

purposes = ["Treatment", "Prevention", "Diagnostic", "Supportive Care"]
enrollment_types = ["ACTUAL", "ESTIMATED"]
sponsor_types = ["INDUSTRY", "NIH", "OTHER_GOV", "INDIV"]

for t in data["trials"]:
    phase = t.get("phase", "N/A")
    p = str(phase).upper().replace("PHASE", "").strip()
    if p in ["1", "1/2", "EARLY 1"]:
        t["size_category"] = "Small (<50 participants)"
    elif p in ["2", "2/3"]:
        t["size_category"] = "Medium (50-199 participants)"
    elif p in ["3", "4"]:
        t["size_category"] = "Large (200-999 participants)"
    else:
        t["size_category"] = "Unknown Size"

    # Add new fields for demo
    t["primary_purpose"] = random.choice(purposes)
    t["enrollment_type"] = random.choice(enrollment_types)
    t["sponsor_type"] = random.choice(sponsor_types)

    # Update relevance_tags
    tags = t.get("relevance_tags", [])
    if t["size_category"] not in tags:
        tags.append(t["size_category"])
    if phase not in tags:
        tags.append(phase)
    if t.get("primary_purpose"):
        pp_tag = f"Primary Purpose: {t['primary_purpose']}"
        if pp_tag not in tags:
            tags.append(pp_tag)
    if t.get("enrollment_type"):
        et_tag = f"Enrollment: {t['enrollment_type'].title()}"
        if et_tag not in tags:
            tags.append(et_tag)
    if t.get("sponsor_type"):
        st_tag = f"Sponsor Type: {t['sponsor_type'].replace('_', ' ').title()}"
        if st_tag not in tags:
            tags.append(st_tag)
    t["relevance_tags"] = list(dict.fromkeys(tags))

with open("clinical_trials/data/clinical_trials_current.json", "w") as f:
    json.dump(data, f, indent=2)

print("Enriched", len(data["trials"]), "trials with size, primary_purpose, enrollment_type, sponsor_type")
print("Sample:", {k: data["trials"][0].get(k) for k in ["size_category", "primary_purpose", "enrollment_type", "sponsor_type", "relevance_tags"]})
