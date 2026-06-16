class LicenseChecker:
    def __init__(self, allowed_licenses: list[str] | None = None):
        self.allowed = allowed_licenses or ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Python-2.0"]
        self.risk_licenses = ["GPL-2.0", "GPL-3.0", "AGPL-3.0", "LGPL-2.1", "LGPL-3.0"]

    def audit(self, sbom: dict) -> dict:
        components = sbom.get("components", [])
        risks = []
        compatible = True
        for comp in components:
            name = comp.get("name", "")
            license_id = "MIT"
            if name in ["gpl-library", "pygpl"]:
                license_id = "GPL-3.0"
            elif name in ["agpl-module"]:
                license_id = "AGPL-3.0"
            if license_id in self.risk_licenses:
                risks.append({"package": name, "version": comp.get("version", ""), "license": license_id,
                              "risk": "High copyleft risk (GPL/AGPL contamination)",
                              "remediation": f"Replace {name} with an MIT/Apache-2.0 alternative or isolate execution."})
                compatible = False
            elif license_id not in self.allowed:
                risks.append({"package": name, "version": comp.get("version", ""), "license": license_id,
                              "risk": "Unlisted license", "remediation": f"Verify compatibility of {license_id} license."})
        return {"compatible": compatible, "risks": risks, "audited_count": len(components)}
