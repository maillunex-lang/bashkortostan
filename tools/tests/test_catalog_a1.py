import unittest
from pathlib import Path
from copy import deepcopy
from tools.sim.catalog import load_catalog,validate,simulate,quality,round_half_up
D=load_catalog(Path(__file__).resolve().parents[2]/"data/catalog/demo.json")
def run(recipe,stock,enterprise,**kw):
    return simulate(D,recipe,stock,capacity_runs=kw.get("capacity",3),energy=3,workers=3,tick_id=kw.get("tick","1"),enterprise_id=enterprise,company_id="c",ledger=kw.get("ledger"),feature_enabled=True)
class CatalogTests(unittest.TestCase):
    def test_valid(self): self.assertTrue(validate(D))
    def test_duplicate(self):
        d=deepcopy(D);d["items"].append(d["items"][0])
        with self.assertRaises(ValueError):validate(d)
    def test_bad_reference(self):
        d=deepcopy(D);d["recipes"][0]["inputs"][0]["item_id"]="unknown"
        with self.assertRaises(ValueError):validate(d)
    def test_unreachable(self):
        d=deepcopy(D);d["recipes"][0]["inputs"][0]["item_id"]="bottle"
        with self.assertRaises(ValueError):validate(d)
    def test_milk_golden(self):
        r=run("milk_glass",{"milk_raw":25,"bottle":18},"dairy")
        self.assertEqual((r["runs"],r["stock"]["milk_raw"],r["stock"]["bottle"],r["stock"]["milk_pack"]),(1,15,8,10))
    def test_idempotence(self):
        ledger={};a=run("milk_glass",{"milk_raw":25,"bottle":18},"dairy",ledger=ledger)
        b=run("milk_glass",a["stock"],"dairy",ledger=ledger)
        self.assertEqual(a,b);self.assertEqual(len(ledger),1)
    def test_alternative(self):
        r=run("milk_plastic",{"milk_raw":10,"plastic_bottle":10},"dairy")
        self.assertEqual(r["stock"]["milk_pack"],10)
    def test_packaging(self):
        self.assertEqual(run("bread_wrap",{"bread":10,"bag":0},"bakery")["runs"],0)
    def test_bread(self):
        a=run("flour_mill",{"wheat":10},"mill")
        b=run("bread_bake",a["stock"],"bakery")
        self.assertEqual(b["stock"]["bread"],10)
    def test_glass(self):
        a=run("glass_melt",{"glass_sand":10},"glassworks")
        b=run("bottle_form",a["stock"],"bottleworks")
        self.assertEqual(b["stock"]["bottle"],10)
    def test_flag_off(self):
        with self.assertRaises(RuntimeError):simulate(D,"milk_glass",{},capacity_runs=1,energy=1,workers=1,tick_id="1",enterprise_id="dairy",company_id="c")
    def test_round(self):self.assertEqual([round_half_up(x,100) for x in (7449,7450,7499)],[74,75,75])
    def test_quality(self):
        r=next(x for x in D["recipes"] if x["id"]=="milk_glass")
        self.assertEqual(quality(r,{"milk_raw":80,"bottle":60},80,80,80),76)
    def test_overflow(self):
        with self.assertRaises(OverflowError):run("milk_glass",{"milk_raw":10,"bottle":10,"milk_pack":2**63-1},"dairy")
    def test_zero(self):self.assertEqual(run("milk_glass",{},"dairy")["runs"],0)
if __name__=="__main__":unittest.main()
