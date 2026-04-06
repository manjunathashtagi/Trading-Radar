import xml.etree.ElementTree as ET
import json
from pathlib import Path


class WiringDataBuilder:
    def __init__(self, input_file):
        self.input_file = Path(input_file)
        self.tree = None
        self.root = None

        # Structured output
        self.data = {
            "wires": [],
            "connectors": [],
            "splices": [],
            "components": [],
            "metadata": {}
        }

    def load_file(self):
        """Load and parse XML-based wiring file (.kbl / .dsi)"""
        try:
            self.tree = ET.parse(self.input_file)
            self.root = self.tree.getroot()
            print(f"[INFO] File loaded: {self.input_file}")
        except Exception as e:
            print(f"[ERROR] Failed to load file: {e}")

    def parse_metadata(self):
        """Extract basic metadata"""
        if self.root is None:
            return

        self.data["metadata"] = {
            "source_file": str(self.input_file),
            "root_tag": self.root.tag
        }

    def parse_wires(self):
        """Extract wire data"""
        for wire in self.root.findall(".//wire"):
            wire_data = {
                "id": wire.get("id"),
                "color": wire.get("color"),
                "length": wire.get("length"),
                "from": wire.get("from"),
                "to": wire.get("to")
            }
            self.data["wires"].append(wire_data)

    def parse_connectors(self):
        """Extract connector data"""
        for conn in self.root.findall(".//connector"):
            conn_data = {
                "id": conn.get("id"),
                "type": conn.get("type"),
                "pins": []
            }

            for pin in conn.findall(".//pin"):
                conn_data["pins"].append({
                    "pin_id": pin.get("id"),
                    "wire": pin.get("wire")
                })

            self.data["connectors"].append(conn_data)

    def parse_splices(self):
        """Extract splice data"""
        for splice in self.root.findall(".//splice"):
            splice_data = {
                "id": splice.get("id"),
                "wires": [w.get("id") for w in splice.findall(".//wire")]
            }
            self.data["splices"].append(splice_data)

    def parse_components(self):
        """Extract components like sensors, ECUs, etc."""
        for comp in self.root.findall(".//component"):
            comp_data = {
                "id": comp.get("id"),
                "name": comp.get("name"),
                "type": comp.get("type")
            }
            self.data["components"].append(comp_data)

    def build(self):
        """Run full parsing pipeline"""
        self.load_file()
        self.parse_metadata()
        self.parse_wires()
        self.parse_connectors()
        self.parse_splices()
        self.parse_components()

        return self.data

    def save_json(self, output_path="stage1_output.json"):
        """Save structured data"""
        with open(output_path, "w") as f:
            json.dump(self.data, f, indent=4)
        print(f"[INFO] Output saved to {output_path}")


# -------------------------
# Run standalone
# -------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stage 1 Wiring Data Builder")
    parser.add_argument("input_file", nargs="?", default="sample.kbl",
                    help="Path to .kbl / .dsi file")
    parser.add_argument("--output", default="stage1_output.json", help="Output JSON file")

    args = parser.parse_args()

    builder = WiringDataBuilder(args.input_file)
    data = builder.build()
    builder.save_json(args.output)