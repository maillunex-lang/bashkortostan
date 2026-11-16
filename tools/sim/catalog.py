"""A1: integer-only, draft catalogue simulator. No network or DB."""
import json
from pathlib import Path
from copy import deepcopy

MAX=2**63-1
def integer(n,positive=False):
    if type(n)!=int or n < (1 if positive else 0) or n>MAX: raise ValueError("invalid integer")
    return n
def validate(d):
    ids={}
    for kind in ("units","items","enterprises","recipes"):
        rows=d[kind]; keys=[x["id"] for x in rows]
        if len(set(keys))!=len(keys) or not all(isinstance(k,str) and k for k in keys): raise ValueError("duplicate ID")
        ids[kind]=set(keys)
    for u in d["units"]:
        integer(u["scale_integer"],True)
        if u["base_unit"] not in ids["units"]: raise ValueError("unit")
    for x in d["items"]:
        if x["unit_id"] not in ids["units"]: raise ValueError("unit reference")
        if not 0<=integer(x["quality_min"])<=integer(x["quality_max"])<=100: raise ValueError("quality")
    produced=set()
    for r in d["recipes"]:
        if r["enterprise_type_id"] not in ids["enterprises"]: raise ValueError("enterprise reference")
        for k in ("duration_ticks","version"): integer(r[k],True)
        for k in ("energy_units","workers_required"): integer(r[k])
        if not r["inputs"] or not r["outputs"]: raise ValueError("empty recipe")
        for side in ("inputs","outputs"):
            seen=set()
            for x in r[side]:
                if x["item_id"] not in ids["items"] or x["item_id"] in seen: raise ValueError("item reference")
                seen.add(x["item_id"]);integer(x["quantity"],True)
                if side=="inputs": integer(x["quality_weight"],True)
                else: produced.add(x["item_id"])
        if {x["item_id"] for x in r["inputs"]}&{x["item_id"] for x in r["outputs"]}: raise ValueError("same input/output")
    for e in d["enterprises"]:
        integer(e["equipment_slots"])
        for rid in e["allowed_recipe_ids"]:
            if rid not in ids["recipes"] or next(r for r in d["recipes"] if r["id"]==rid)["enterprise_type_id"]!=e["id"]: raise ValueError("recipe reference")
    if any(not x["is_raw"] and x["id"] not in produced for x in d["items"]): raise ValueError("no producer")
    reachable={x["id"] for x in d["items"] if x["is_raw"]}
    while True:
        old=len(reachable)
        for r in d["recipes"]:
            if all(x["item_id"] in reachable for x in r["inputs"]): reachable.update(x["item_id"] for x in r["outputs"])
        if old==len(reachable): break
    if reachable!=ids["items"]: raise ValueError("unreachable")
    return True
def round_half_up(n,d):
    integer(n);integer(d,True)
    return (2*n+d)//(2*d)
def quality(recipe,qualities,equipment,workers,research):
    for x in (equipment,workers,research):
        if integer(x)>100: raise ValueError("quality")
    weighted=0; total=0
    for x in recipe["inputs"]:
        q=integer(qualities[x["item_id"]]); w=integer(x["quality_weight"],True)
        if q>100: raise ValueError("quality")
        weighted+=q*w;total+=w
    s=round_half_up(weighted,total)
    return round_half_up(40*s+25*equipment+20*workers+15*research,100)
def simulate(d,recipe_id,stock,*,capacity_runs,energy,workers,tick_id,enterprise_id,company_id,ledger=None,feature_enabled=False):
    if not feature_enabled: raise RuntimeError("ECON_CATALOG_V1=false")
    validate(d)
    recipe=next((r for r in d["recipes"] if r["id"]==recipe_id),None)
    enterprise=next((e for e in d["enterprises"] if e["id"]==enterprise_id),None)
    if recipe is None or enterprise is None or recipe_id not in enterprise["allowed_recipe_ids"]: raise ValueError("unauthorized recipe")
    if not company_id or not tick_id: raise ValueError("identity")
    ledger={} if ledger is None else ledger
    key=(company_id,enterprise_id,recipe_id,tick_id)
    if key in ledger: return deepcopy(ledger[key])
    for n in (capacity_runs,energy,workers): integer(n)
    quantities={x["id"]:integer(stock.get(x["id"],0)) for x in d["items"]}
    limits=[capacity_runs]+[quantities[x["item_id"]]//x["quantity"] for x in recipe["inputs"]]
    if recipe["energy_units"]: limits.append(energy//recipe["energy_units"])
    if recipe["workers_required"]: limits.append(workers//recipe["workers_required"])
    runs=min(limits);result=quantities.copy()
    for x in recipe["inputs"]: result[x["item_id"]]-=runs*x["quantity"]
    for x in recipe["outputs"]:
        n=result[x["item_id"]]+runs*x["quantity"]
        if n>MAX: raise OverflowError("stock overflow")
        result[x["item_id"]]=n
    out={"runs":runs,"stock":result,"key":list(key)}
    ledger[key]=deepcopy(out)
    return out
def load_catalog(path): return json.loads(Path(path).read_text(encoding="utf-8"))
