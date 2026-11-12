"""Pure Python SENEC / Solarman source discovery regression tests."""
import importlib.util
from pathlib import Path
import unittest

PATH=Path(__file__).resolve().parents[1] / "custom_components" / "cl_power_control" / "discovery.py"
spec=importlib.util.spec_from_file_location("cl_power_control_discovery_standalone",PATH)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def entity(name, platform="senec", unit="W", state="0", device="device-1", dc="power"):
    return {
        "entity_id":"sensor."+name, "platform":platform, "unit":unit,
        "device_class":dc, "state":state, "device_id":device,
        "config_entry_id":"integration-1", "enabled":True,
    }

class DiscoveryTest(unittest.TestCase):
    def senec(self):
        rows=[
            entity("senec_house_power",state="1319.16"),
            entity("senec_grid_state_power",state="1315.31"),
            entity("senec_solar_generated_power",state="0"),
            entity("senec_battery_state_power",state="-1.9"),
            entity("senec_battery_charge_percent",unit="%",dc="battery",state="0"),
            entity("senec_grid_imported_power",state="1315.31"),
            entity("senec_grid_exported_power",state="0"),
            entity("senec_solar_mpp1_power",state="0"),
            entity("senec_enfluri_net_power_p1",state="1315.31"),
            entity("cl_power_control_energy_rete",platform="cl_power_control",state="unknown"),
        ]
        return rows

    def test_senec_real_demo(self):
        found=mod.discover_candidates(self.senec())
        self.assertEqual(len(found),1)
        src=found[0]["sources"]
        self.assertEqual(src, {
            "power_sensor":"sensor.senec_house_power",
            "grid_power_sensor":"sensor.senec_grid_state_power",
            "pv_power_sensor":"sensor.senec_solar_generated_power",
            "battery_power_sensor":"sensor.senec_battery_state_power",
            "battery_soc_sensor":"sensor.senec_battery_charge_percent",
        })
        self.assertEqual(found[0]["provider"],"senec")

    def test_circular_config_suggested_replacement(self):
        found=mod.discover_candidates(self.senec())[0]
        current={
            "power_sensor":"sensor.my_existing_meter",
            "grid_power_sensor":"sensor.cl_power_control_energy_rete",
            "grid_power_invert":True,
            "pv_power_sensor":"sensor.senec_solar_generated_power",
            "enabled":True,"energy_enabled":True,
            "limit_w":6000,
        }
        patch=mod.proposal_for(current,found)
        self.assertEqual(patch,{
            "grid_power_sensor":"sensor.senec_grid_state_power",
            "grid_power_invert":False,
            "battery_power_sensor":"sensor.senec_battery_state_power",
            "battery_soc_sensor":"sensor.senec_battery_charge_percent",
        })
        self.assertNotIn("power_sensor",patch)
        self.assertNotIn("energy_enabled",patch)
        self.assertNotIn("limit_w",patch)
        self.assertNotIn("enabled",patch)

    def test_no_cross_inverter_merge(self):
        sample=self.senec()+[
            entity("solarman_pv_power",platform="solarman",device="device-2",state="600"),
            entity("solarman_grid_power",platform="solarman",device="device-3",state="220"),
        ]
        results=mod.discover_candidates(sample)
        self.assertEqual(len(results),3)
        self.assertEqual(max(g["matched"] for g in results),5)
        self.assertTrue(all(not (
            "pv_power_sensor" in g["sources"] and "grid_power_sensor" in g["sources"]
            ) for g in results if g["provider"]=="solarman"))

    def test_solarman_partial_and_units(self):
        rows=[
            entity("solarman_pv1_power",platform="solarman",device="a"),
            entity("solarman_pv_total_power",platform="solarman",device="a",unit="kW",state="2.4"),
            entity("solarman_grid_import_power",platform="solarman",device="a"),
            entity("solarman_grid_power",platform="solarman",device="a",unit="kWh"),
            entity("solarman_battery_soc",platform="solarman",device="a",unit="%",dc="battery",state="45"),
        ]
        result=mod.discover_candidates(rows)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["sources"],{
            "battery_soc_sensor":"sensor.solarman_battery_soc",
            "pv_power_sensor":"sensor.solarman_pv_total_power",
        })
        self.assertIn("Nessun sensore rete bidirezionale",result[0]["warnings"][0])

    def test_disabled_unknown_and_zero(self):
        rows=self.senec()
        rows[0]["state"]="unavailable"
        rows[1]["enabled"]=False
        rows[8]["enabled"]=False
        result=mod.discover_candidates(rows)[0]["sources"]
        self.assertNotIn("power_sensor",result)
        self.assertNotIn("grid_power_sensor",result)
        self.assertIn("pv_power_sensor",result) # zero at night remains valid

    def test_unknown_platform_not_guessed_from_entity_name(self):
        self.assertFalse(mod.discover_candidates([
            entity("senec_house_power",platform="template"),
            entity("solarman_grid_power",platform="mqtt"),
        ]))
if __name__=="__main__":
    unittest.main()
