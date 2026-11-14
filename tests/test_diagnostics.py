"""Regression tests for read-only installer diagnostics (no Home Assistant required)."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT=Path(__file__).resolve().parents[1] / "custom_components" / "cl_power_control"
pkg=types.ModuleType("cl_power_control")
pkg.__path__=[str(ROOT)]
sys.modules.setdefault("cl_power_control",pkg)

def load(name):
    spec=importlib.util.spec_from_file_location("cl_power_control."+name,ROOT/(name+".py"))
    mod=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=mod
    spec.loader.exec_module(mod)
    return mod

discovery=load("discovery")
diagnostics=load("diagnostics")

def sensor(name,value,unit="W",device="one",dc="power"):
    return {"entity_id":"sensor.senec_"+name,"platform":"senec","unit":unit,
            "device_class":dc,"state":str(value),"device_id":device,
            "config_entry_id":"entry-1","enabled":True}

class InstallerDiagnosticsTest(unittest.TestCase):
    def setUp(self):
        self.rows=[
            sensor("house_power",1183.2),
            sensor("grid_state_power",-3808.4),
            sensor("solar_generated_power",5442.3),
            sensor("battery_state_power",453.6),
            sensor("battery_charge_percent",98,"%",dc="battery"),
        ]
        self.config={
            "grid_power_sensor":"sensor.senec_grid_state_power",
            "pv_power_sensor":"sensor.senec_solar_generated_power",
            "battery_power_sensor":"sensor.senec_battery_state_power",
            "battery_power_invert":True,
            "battery_soc_sensor":"sensor.senec_battery_charge_percent",
            "power_sensor":"sensor.other_power",
            "limit_w":6000,
        }

    def inspect(self):
        return diagnostics.inspect_sources(self.rows,self.config,
                                           discovery.discover_candidates(self.rows))

    def test_demo_balance_and_no_mutation(self):
        before=dict(self.config)
        result=self.inspect()
        self.assertEqual(result["health"],"Da verificare") if result["warnings"] else self.assertEqual(result["health"],"OK")
        self.assertEqual(result["balance"]["status"],"Coerente")
        self.assertAlmostEqual(result["balance"]["calculated_house_w"],1180.3)
        self.assertEqual(self.config,before)

    def test_invalid_and_internal_sources(self):
        self.config["grid_power_sensor"]="sensor.cl_power_control_energy_rete"
        result=self.inspect()
        self.assertEqual(result["sources"]["grid_power_sensor"]["status"],"Riferimento circolare")
        self.assertIsNone(result["balance"])
        self.assertEqual(result["health"],"Da verificare")

    def test_missing_and_unit_rejection(self):
        self.rows[1]["unit"]="kWh"
        self.rows[2]["state"]="unavailable"
        result=self.inspect()
        self.assertEqual(result["sources"]["grid_power_sensor"]["status"],"Unità non valida")
        self.assertEqual(result["sources"]["pv_power_sensor"]["status"],"Non disponibile")
        self.assertIsNone(result["balance"])

    def test_kw_and_sign(self):
        self.rows[1]["state"]="-3.8084"
        self.rows[1]["unit"]="kW"
        result=self.inspect()
        self.assertAlmostEqual(result["sources"]["grid_power_sensor"]["value"],-3808.4)
        self.assertEqual(result["balance"]["status"],"Coerente")

    def test_no_cross_device_balance(self):
        self.rows[0]["device_id"]="different"
        self.assertIsNone(self.inspect()["balance"])

    def test_report_has_all_fields(self):
        report=diagnostics.format_diagnostics(self.inspect())
        self.assertEqual(set(report),{"health","sources","balance","warnings"})
        self.assertIn("Fotovoltaico",report["sources"])

if __name__=="__main__":
    unittest.main()
