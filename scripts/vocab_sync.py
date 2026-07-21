#!/usr/bin/env python3
"""Pin an HPO JSON release and regenerate the small, shipped PAIS subset."""
from __future__ import annotations
import argparse, glob, hashlib, json, os, shutil, urllib.request
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR=os.path.join(ROOT,"data","vocab","hpo"); RELEASE=os.path.join(DIR,"RELEASE"); SUBSET=os.path.join(DIR,"hp-subset.json")

def hpid(uri): return uri.rsplit("/",1)[-1].replace("_", ":")
def read(p):
    with open(p,encoding="utf-8") as f:return json.load(f)
def terms_in_use():
    used=set()
    for p in glob.glob(os.path.join(ROOT,"data","cohorts","*.json")):
        for e in read(p).get("estimates",[]):
            if e.get("construct","").startswith("HP:"): used.add(e["construct"])
    return used
def sync(release):
    os.makedirs(DIR,exist_ok=True); url=f"https://github.com/obophenotype/human-phenotype-ontology/releases/download/v{release}/hp.json"; out=os.path.join(DIR,f"hp-{release}.json")
    with urllib.request.urlopen(url) as r, open(out,"wb") as f: shutil.copyfileobj(r,f)
    digest=hashlib.sha256(open(out,"rb").read()).hexdigest()
    with open(RELEASE,"w",encoding="utf-8",newline="\n") as f:f.write(f"release: {release}\nretrieved: {__import__('datetime').date.today()}\nsource: {url}\nsha256: {digest}\n")
    return out
def subset(full):
    g=read(full)["graphs"][0]; nodes={hpid(x["id"]):x for x in g["nodes"]}; parents={hpid(e["sub"]):hpid(e["obj"]) for e in g["edges"] if e.get("pred"," ").endswith("subClassOf")}
    wanted=terms_in_use()|{"HP:0000118"}; keep=set()
    for term in wanted:
        cur=term
        while cur and cur not in keep:
            keep.add(cur); cur=parents.get(cur)
    records=[]
    for term in sorted(keep):
        n=nodes.get(term)
        if not n: raise SystemExit(f"Referenced HPO term is not in pinned release: {term}")
        meta=n.get("meta",{}); records.append({"id":term,"label":n.get("lbl"),"obsolete":bool(meta.get("deprecated")),"parents":[parents[term]] if term in parents and parents[term] in keep else []})
    with open(SUBSET,"w",encoding="utf-8",newline="\n") as f:json.dump({"release":os.path.basename(full)[3:-5],"terms":records},f,ensure_ascii=False,indent=2);f.write("\n")
def main():
    p=argparse.ArgumentParser();p.add_argument("--release");p.add_argument("--full");a=p.parse_args()
    full=sync(a.release) if a.release else (a.full or sorted(glob.glob(os.path.join(DIR,"hp-*.json")))[-1])
    subset(full);print("Regenerated",SUBSET)
if __name__=="__main__":main()
