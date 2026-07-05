import json
with open("data/therapeutic_agents.json") as f:
    data = json.load(f)
agents = data["agents"]
print("Agents with trials:")
for a in agents:
    if a.get("trials"):
        print("- " + a["Therapeutic Agent"])
        print("  Conditions: " + str(a["Primary Conditions"]))
        print("  Evidence: " + a["Evidence Level"])
        print("  # Trials: " + str(len(a["trials"])))
        for tr in a["trials"][:1]:
            print("    " + tr.get("nct_id", "") + ": " + tr.get("title","")[:55] + " (" + tr.get("status","") + ")")
        print()
print("\nTotal with trials:", sum(1 for a in agents if a.get("trials")))
