from __future__ import annotations

import json
from pathlib import Path
import struct
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]


class DeploymentTests(unittest.TestCase):
    def test_compose_contains_api_and_https_proxy(self) -> None:
        compose = yaml.safe_load((ROOT / "deploy" / "docker-compose.yml").read_text(encoding="utf-8"))
        self.assertEqual(set(compose["services"]), {"api", "caddy"})
        self.assertEqual(compose["services"]["api"]["restart"], "unless-stopped")
        self.assertIn("no-new-privileges:true", compose["services"]["api"]["security_opt"])
        environment = compose["services"]["api"]["environment"]
        self.assertIn("PACHEVIDEO_DOWNLOAD_ATTEMPTS", environment)
        self.assertIn("PACHEVIDEO_RETRY_MAX_SECONDS", environment)
        self.assertIn("PACHEVIDEO_MAX_ACTIVE_JOBS", environment)
        self.assertIn("PACHEVIDEO_MP_ACCESS_TOKEN", environment)
        self.assertIn("PACHEVIDEO_MP_BACK_URL", environment)
        self.assertIn("PACHEVIDEO_SUPABASE_URL", environment)
        self.assertIn("PACHEVIDEO_SUPABASE_ANON_KEY", environment)
        self.assertEqual(
            environment["PACHEVIDEO_MP_SUBSCRIPTION_AMOUNT"],
            "${PACHEVIDEO_MP_SUBSCRIPTION_AMOUNT:-9999.99}",
        )

    def test_subscription_price_examples_match_product_price(self) -> None:
        server_env = (ROOT / "server" / ".env.example").read_text(encoding="utf-8")
        deploy_env = (ROOT / "deploy" / ".env.example").read_text(encoding="utf-8")
        self.assertIn("PACHEVIDEO_MP_SUBSCRIPTION_AMOUNT=9999.99", server_env)
        self.assertIn("PACHEVIDEO_MP_SUBSCRIPTION_AMOUNT=9999.99", deploy_env)

    def test_manifest_matches_logo_dimensions(self) -> None:
        manifest = json.loads((ROOT / "web" / "public" / "manifest.webmanifest").read_text(encoding="utf-8"))
        with (ROOT / "web" / "public" / "logo.png").open("rb") as image:
            header = image.read(24)
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", header[16:24])
        self.assertEqual(manifest["icons"][0]["sizes"], f"{width}x{height}")

    def test_local_launcher_loads_private_server_environment(self) -> None:
        launcher = (ROOT / "scripts" / "run-api-local.bat").read_text(encoding="utf-8")
        self.assertIn(r"server\.env", launcher)
        self.assertIn("tokens=1,* delims==", launcher)


if __name__ == "__main__":
    unittest.main()
