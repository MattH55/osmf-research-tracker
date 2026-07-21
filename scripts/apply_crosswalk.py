#!/usr/bin/env python3
"""Opt-in consumer utility; never changes core PAIS exports."""
import csv, json, os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT,'data','pais-estimates.csv'),encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f))
for r in rows: r['crosswalk_applied']='false'
with open(os.path.join(ROOT,'data','pais-estimates-crosswalked.csv'),'w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=(list(rows[0]) if rows else ['crosswalk_applied'])); w.writeheader(); w.writerows(rows)
